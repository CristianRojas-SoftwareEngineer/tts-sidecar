"""
Motor TTS de Chatterbox.
Wrapper de Chatterbox Multilingual TTS desde HuggingFace.
Soporta el language pack es-mx-latam vía un loader propio.

Arquitectura: T3 (autoregresivo, ~0.4B params) + S3Gen (vocoder de flow matching).
Parámetros de síntesis optimizados, propios del engine (aplican en modo directo
y en el daemon por igual):
  - max_new_tokens=500  (tope de output del T3; el default es 1000)
  - n_cfm_timesteps=4  (pasos de flow matching; el default es 10)
  - exaggeration=0.75   (expresividad emocional; el default es 0.5)
  - bypass del watermark PerthNet: el audio generado NO lleva marca de agua.
    Esto implica que no es distinguible técnicamente de una grabación real y
    traslada al usuario la responsabilidad del uso legítimo (ver «Uso ético y
    responsable» en README.md/USAGE.md).

Optimizaciones multiplataforma para Windows, Linux y Mac.
"""

import os
import platform
import threading
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from . import voices
from .model_cache import (
    MODELS as _MODEL_ALIASES,
    _resolve_cached_snapshot,
    cache_folder_for,
    hub_cache_path,
    is_model_cached,  # re-export para compatibilidad interna
)
from .timing import StageTimer, log

# =============================================================================
# Configuración de PyTorch según la plataforma para inferencia en CPU
# =============================================================================

def _configure_torch_for_platform():
    """Configura los ajustes de PyTorch según la plataforma actual."""
    system = platform.system()

    # Determina el número óptimo de hilos según los núcleos de CPU
    cpu_count = os.cpu_count() or 4
    # Usa hasta 8 hilos: más allá, el ancho de banda de memoria se vuelve el cuello
    # de botella para modelos transformer en CPU (más hilos = peor por contención).
    optimal_threads = min(8, cpu_count)

    torch.set_num_threads(optimal_threads)

    if system == "Windows":
        # Windows: Intel MKL suele estar disponible vía PyTorch
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        os.environ["MKL_NUM_THREADS"] = str(optimal_threads)
        # Habilita el fallback de MPS (inofensivo en Windows)
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    elif system == "Linux":
        # Linux: OpenMP vía libgomp, potencialmente MKL
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        os.environ["MKL_NUM_THREADS"] = str(optimal_threads)
        # Intenta habilitar oneDNN para mejor rendimiento en CPU
        try:
            torch.backends.mkldnn.enabled = True
        except Exception:
            pass

    elif system == "Darwin":
        # Mac: framework Accelerate (nativo)
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        # Fallback de MPS para Macs con Apple Silicon
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    # Habilita MKLDNN si está disponible (las CPU Intel/AMD se benefician)
    try:
        torch.backends.mkldnn.enabled = True
        torch.backends.mkldnn.verbose(0)
    except Exception:
        pass  # MKL-DNN no disponible

    # Desactiva el flushing de denormales para cómputo más rápido en CPU modernas
    try:
        torch.set_flush_denormal(True)
    except Exception:
        pass

    return optimal_threads


# Aplica la configuración de plataforma al importar el módulo
_THREAD_COUNT = _configure_torch_for_platform()
del _configure_torch_for_platform  # Mantiene limpio el namespace


from safetensors.torch import load_file

# Imports de Chatterbox
try:
    from chatterbox.tts import (
        ChatterboxTTS, T3, S3Gen, VoiceEncoder,
        Conditionals, EnTokenizer,
    )
    from chatterbox.mtl_tts import (
        ChatterboxMultilingualTTS, MTLTokenizer, T3Config, T3Cond,
    )
    from chatterbox.models.s3tokenizer import S3_SR
except ImportError:
    raise ImportError(
        "Chatterbox not installed. Run: pip install chatterbox-tts"
    )


class ChatterboxEngine:
    """
    Motor TTS que usa los modelos de Chatterbox.

    Modelo por defecto: language pack es-mx-latam.
    Usa la arquitectura ChatterboxMultilingualTTS con vocabulario de 2454 tokens
    para coincidir con el checkpoint es-mx-latam (text_emb: 2454×1024).

    Soporta caché de modelos para evitar recargarlos en cada instanciación.
    """

    # Configuraciones de modelo (mapa único en model_cache)
    MODELS = _MODEL_ALIASES

    # Parámetros de síntesis optimizados (compartidos por modo directo y daemon)
    MAX_NEW_TOKENS = 500     # tope de output del T3 (default del modelo: 1000)
    N_CFM_TIMESTEPS = 4      # pasos de flow matching (default: 10; 4 es ~2.5x más rápido)
    EXAGGERATION = 0.75      # expresividad emocional (default: 0.5)
    # Adv. emocional del T3Cond: parámetro propio de la arquitectura T3, sin
    # relación con EXAGGERATION (que ajusta tts.generate()). Se deja fijo en
    # el valor neutro del modelo base; no es un default de Chatterbox a heredar.
    EMOTION_ADV = 0.5

    # Caché a nivel de clase para los modelos cargados (evita recargar en cada speak)
    _cache: dict[str, "ChatterboxEngine"] = {}
    _cache_lock = threading.Lock()

    @staticmethod
    def _auto_detect_compute_backend() -> str:
        """Resuelve el mejor compute backend disponible en el host.

        Orden de preferencia: cuda (NVIDIA) → mps (Apple Silicon) → cpu.
        Los probes de torch se envuelven en try/except: un torch sin CUDA
        o sin MPS, o un fallo de import del backend, degradan a "cpu" sin
        crashear.
        """
        try:
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        try:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    @classmethod
    def _resolve_compute_backend(cls, compute_backend: Optional[str]) -> str:
        """Acepta None/"auto" y lo mapea a uno de los backends concretos."""
        if compute_backend is None or compute_backend == "auto":
            return cls._auto_detect_compute_backend()
        return compute_backend

    @staticmethod
    def cache_key(model: str = "es-mx-latam", compute_backend: str = "cpu", models_dir: Optional[str] = None) -> str:
        """Construye la clave de caché de instancias, compartida con el daemon (run.py)."""
        return f"{model}:{compute_backend}:{models_dir}"

    @classmethod
    def get_instance(cls, model: str = "es-mx-latam", compute_backend: str = "auto", models_dir: Optional[str] = None) -> "ChatterboxEngine":
        """
        Obtiene una instancia cacheada del motor o crea una nueva.

        El modelo queda cargado en memoria para las llamadas siguientes.

        Args:
            model: Modelo a usar. El CLI solo invoca con "es-mx-latam".
            compute_backend: Backend de cómputo para la inferencia
                ("auto", "cpu", "cuda", "mps"). Con "auto" (default), se
                detecta el mejor disponible.
            models_dir: Directorio donde cachear los modelos
        """
        resolved = cls._resolve_compute_backend(compute_backend)
        key = cls.cache_key(model, resolved, models_dir)
        with cls._cache_lock:
            if key not in cls._cache:
                cls._cache[key] = cls(model=model, compute_backend=resolved, models_dir=models_dir)
            return cls._cache[key]

    def __init__(
        self,
        model: str = "es-mx-latam",
        compute_backend: str = "auto",
        models_dir: Optional[str] = None,
    ):
        """
        Inicializa el motor TTS de Chatterbox.

        Args:
            model: Modelo a usar. El CLI solo invoca con "es-mx-latam";
                   "multilingual" (modelo base) se conserva solo como path interno.
            compute_backend: Backend de cómputo ("auto", "cpu", "cuda", "mps").
                Con "auto" (default) se detecta el mejor disponible.
            models_dir: Directorio donde cachear los modelos. Default: ~/.cache/huggingface/hub
        """
        self.compute_backend = self._resolve_compute_backend(compute_backend)
        self.model_name = self.MODELS.get(model, model)

        # Descarga el modelo a la caché local
        self._cache_dir = self._download_model(self.model_name, models_dir)

        # Carga el modelo desde los archivos locales usando el loader correcto
        self._tts = self._load_model(self._cache_dir, self.model_name, self.compute_backend)

        # Memoización en memoria de los conditionals precomputados: clave
        # (voice_dir, mtime de conditionals.pt) de la última carga exitosa.
        self._conds_cache_key = None

        # Aplica los parámetros de síntesis optimizados y el timing por sub-etapa
        self._apply_synthesis_optimizations()

    def _apply_synthesis_optimizations(self):
        """
        Instrumenta el modelo con los parámetros de síntesis optimizados y el
        timing por sub-etapa (antes monkey-patches del daemon en daemon/run.py):

        - t3.inference con max_new_tokens=MAX_NEW_TOKENS y medición de tiempo
        - s3gen.inference con n_cfm_timesteps=N_CFM_TIMESTEPS y medición de tiempo
        - bypass del watermarker PerthNet (segunda red neuronal de post-procesado)

        El timing queda en self._synthesis_timing ({'t3': s, 's3gen': s}), que el
        daemon expone en los headers HTTP X-T3-Time / X-S3Gen-Time.
        """
        import functools
        import time as time_mod

        self._synthesis_timing = {'t3': 0.0, 's3gen': 0.0}
        tts = self._tts

        _orig_t3 = tts.t3.inference

        @functools.wraps(_orig_t3)
        def timed_t3(*args, **kwargs):
            kwargs['max_new_tokens'] = self.MAX_NEW_TOKENS
            t0 = time_mod.time()
            result = _orig_t3(*args, **kwargs)
            self._synthesis_timing['t3'] = time_mod.time() - t0
            log(f"   [Stage 2a] T3 autoregresivo: {self._synthesis_timing['t3']:.1f}s")
            return result

        tts.t3.inference = timed_t3

        _orig_s3gen = tts.s3gen.inference

        @functools.wraps(_orig_s3gen)
        def timed_s3gen(*args, **kwargs):
            kwargs['n_cfm_timesteps'] = self.N_CFM_TIMESTEPS
            t0 = time_mod.time()
            result = _orig_s3gen(*args, **kwargs)
            self._synthesis_timing['s3gen'] = time_mod.time() - t0
            log(f"   [Stage 2b] S3Gen vocoder:   {self._synthesis_timing['s3gen']:.1f}s")
            return result

        tts.s3gen.inference = timed_s3gen

        # El audio generado NO lleva la marca de agua de PerthNet: este reemplazo
        # neutraliza `apply_watermark`. En consecuencia, el audio producido no es
        # distinguible por medios técnicos de una grabación real, lo que traslada
        # al usuario la responsabilidad del uso legítimo (consentimiento para
        # clonar voces, no suplantación). Ver la sección «Uso ético y responsable»
        # en README.md/USAGE.md. No es una mera optimización de velocidad.
        def noop_watermark(wav, sample_rate=None, **kwargs):
            return wav

        tts.watermarker.apply_watermark = noop_watermark

    def _download_model(self, model_name: str, models_dir: Optional[str] = None) -> Path:
        """Descarga el modelo desde HuggingFace o lo obtiene de la caché local."""
        from huggingface_hub import snapshot_download
        import os

        # Intenta encontrar un modelo ya cacheado
        cached = _resolve_cached_snapshot(hub_cache_path() / cache_folder_for(model_name))

        if cached is not None:
            # Verifica que existan los archivos de es-mx-latam
            if model_name == "es-mx-latam" or "es-mx-latam" in model_name:
                if (cached / "t3_es_mx_latam.safetensors").exists():
                    log(f"Using cached model: {model_name} ({cached})")
                    return cached
            else:
                log(f"Using cached model: {model_name} ({cached})")
                return cached

        # Descarga desde HuggingFace
        log(f"Downloading {model_name} from HuggingFace")

        cached_path = Path(
            snapshot_download(
                repo_id=model_name,
                repo_type="model",
                token=os.getenv("HF_TOKEN"),
            )
        )
        log(f"Model downloaded to: {cached_path}")
        return cached_path

    def _load_model(self, cache_dir: Path, model_name: str, compute_backend: str):
        """Carga el modelo según la ruta de caché: es-mx-latam o el multilingüe base."""
        cache_dir = Path(cache_dir)

        # Selecciona el loader según el modelo en la ruta de caché.
        # El alias vivo es "es-mx-latam"; cualquier otra ruta usa el loader multilingüe.
        if "es-mx-latam" in str(cache_dir):
            return self._load_es_latam(cache_dir, compute_backend)
        else:
            return self._load_multilingual(cache_dir, compute_backend)

    def _load_es_latam(self, cache_dir: Path, compute_backend: str):
        """
        Carga el language pack es-mx-latam.

        Arquitectura: ChatterboxMultilingualTTS (vocab de 2454 tokens)
        - T3: t3_es_mx_latam.safetensors (entrenado con vocab expandido)
        - S3Gen: s3gen_v3.safetensors
        - Tokenizer: grapheme_mtl_merged_expanded_v1.json (2454 tokens)
        """
        device = compute_backend
        if device in ["cpu", "mps"]:
            map_location = torch.device("cpu")
        else:
            map_location = None

        # Carga el Voice Encoder
        # es-mx-latam no incluye ve.safetensors; se comparte con el modelo base
        ve_path = cache_dir / "ve.safetensors"
        if not ve_path.exists():
            # Intenta la caché del modelo base, con el mismo criterio de
            # resolución determinista (refs/main, luego mtime) que el resto
            # del motor, en vez de un os.listdir()[0] de orden no garantizado.
            base_snapshot = _resolve_cached_snapshot(
                hub_cache_path() / cache_folder_for("ResembleAI/chatterbox")
            )
            if base_snapshot is not None:
                ve_path = base_snapshot / "ve.safetensors"
        if not ve_path.exists():
            # Red de seguridad: 'setup' provisiona ve.safetensors explícitamente,
            # así que llegar aquí indica una caché podada tras la provisión.
            log(
                "[VE] ve.safetensors no está en la caché local; descargándolo ahora. "
                "Ejecuta 'tts-sidecar setup' para reprovisionar la caché completa"
            )
            from huggingface_hub import hf_hub_download
            ve_path = Path(hf_hub_download(
                repo_id="ResembleAI/chatterbox",
                filename="ve.safetensors",
                token=os.getenv("HF_TOKEN"),
            ))

        ve = VoiceEncoder()
        ve.load_state_dict(load_file(ve_path))
        ve.to(device).eval()

        # Carga el T3 con la config multilingüe (vocab de 2454 tokens)
        t3 = T3(T3Config.multilingual())
        t3_path = cache_dir / "t3_es_mx_latam.safetensors"
        t3_state = load_file(t3_path)
        if "model" in t3_state.keys():
            t3_state = t3_state["model"][0]
        t3.load_state_dict(t3_state)
        t3.to(device).eval()

        # Carga S3Gen v3
        s3gen = S3Gen()
        # Intenta safetensors primero, luego pt
        s3gen_path = cache_dir / "s3gen_v3.safetensors"
        if not s3gen_path.exists():
            s3gen_path = cache_dir / "s3gen_v3.pt"
        s3gen_state = load_file(s3gen_path) if s3gen_path.suffix == ".safetensors" else torch.load(s3gen_path, map_location=map_location, weights_only=True)
        s3gen.load_state_dict(s3gen_state, strict=False)
        s3gen.to(device).eval()

        # Carga el tokenizer multilingüe (2454 tokens)
        tokenizer = MTLTokenizer(str(cache_dir / "grapheme_mtl_merged_expanded_v1.json"))

        # Carga los conditionals (voz incorporada del modelo)
        # Esto permite generar sin audio_prompt_path
        conds = None
        conds_path = cache_dir / "conds.pt"
        if conds_path.exists():
            from chatterbox.mtl_tts import Conditionals
            conds = Conditionals.load(conds_path, map_location=map_location).to(device)

        tts = ChatterboxMultilingualTTS(t3, s3gen, ve, tokenizer, device, conds=conds)

        # Si no hay conds incorporados, exige audio_prompt_path en generate()
        tts._require_voice_prompt = conds is None

        log(f"Model loaded: es-MX-Latam (vocab=2454, compute_backend={compute_backend}, builtin_voice={'yes' if conds else 'no'})")
        return tts

    def _load_multilingual(self, cache_dir: Path, compute_backend: str):
        """Carga el modelo multilingüe base (path de producción del modelo 'multilingual')."""
        return ChatterboxTTS.from_local(cache_dir, compute_backend)

    def speak(
        self,
        text: str,
        voice_audio: Optional[str] = None,
        speech_audio: Optional[str] = None,
        output_path: Optional[str] = None,
        verbose: bool = True,
    ) -> bytes:
        """
        Genera y opcionalmente guarda audio a partir de texto.

        Args:
            text: Texto a sintetizar (español)
            voice_audio: Archivo de audio para el Voice Encoder (audio completo para el embedding de timbre)
            speech_audio: Archivo de audio para el conditioning del T3 (6s) + decoder S3Gen (10s).
                         Si es None pero se da voice_audio, se usa voice_audio para ambos.
            output_path: Ruta opcional para guardar el archivo WAV
            verbose: Si es True, imprime info de timing por etapa (default True)

        Returns:
            Datos de audio como bytes WAV
        """
        if not voice_audio and not speech_audio:
            raise ValueError(
                "Se requiere al menos un archivo de audio. "
                "Usa --voice para una voz registrada, --voice-audio para el timbre "
                "o --speech-audio para el conditioning. Sin ninguno de estos, la CLI "
                "recurre a la voz de fábrica 'default'. "
                "Si solo se da --voice-audio, se usa para ambos."
            )

        # Si solo hay voice_audio, úsalo para ambos
        if voice_audio and not speech_audio:
            speech_audio = voice_audio

        # Stage 1: Carga de conditionals
        with StageTimer("1-Speak", "Stage 1/4: Loading conditionals"):
            voice_dir = None
            if speech_audio:
                voice_dir = os.path.dirname(speech_audio)
                conditionals_path = os.path.join(voice_dir, "conditionals.pt")
                if os.path.exists(conditionals_path):
                    conds_key = (voice_dir, os.path.getmtime(conditionals_path))
                    if (
                        getattr(self, "_conds_cache_key", None) == conds_key
                        and getattr(self._tts, "conds", None) is not None
                    ):
                        # Misma voz consecutiva: los conds ya están en memoria
                        log("   -> Precomputed conditionals (memoized, no disk read)")
                    elif self.load_precomputed_conditionals(voice_dir):
                        self._conds_cache_key = conds_key
                        log("   -> Precomputed conditionals loaded")
                    else:
                        # conditionals.pt ilegible: degradar al cómputo on-the-fly
                        # en vez de sintetizar en silencio con los conds previos.
                        log("   -> conditionals.pt inválido, recomputando on-the-fly...")
                        self._conds_cache_key = None
                        self._prepare_conditionals_multi(
                            voice_audio_path=voice_audio,
                            speech_audio_path=speech_audio,
                        )
                else:
                    log("   -> Computing conditionals on-the-fly...")
                    self._conds_cache_key = None
                    self._prepare_conditionals_multi(
                        voice_audio_path=voice_audio,
                        speech_audio_path=speech_audio,
                    )
            else:
                self._conds_cache_key = None
                self._prepare_conditionals_multi(
                    voice_audio_path=voice_audio,
                    speech_audio_path=speech_audio,
                )

        # Stage 2: Generación TTS con los parámetros optimizados del engine.
        # max_new_tokens y n_cfm_timesteps se inyectan en t3/s3gen.inference
        # vía _apply_synthesis_optimizations; exaggeration se pasa aquí.
        with StageTimer("2-Speak", "Stage 2/4: Generating audio (TTS)"):
            wav = self._tts.generate(text, language_id="es", exaggeration=self.EXAGGERATION)

        # Stage 3: Conversión a WAV
        with StageTimer("3-Speak", "Stage 3/4: Converting to WAV"):
            wav_bytes = self._audio_to_wav(wav)

        # Stage 4: Guardado a archivo (opcional)
        if output_path:
            with StageTimer("4-Speak", "Stage 4/4: Saving to file"):
                self._save_wav(wav_bytes, output_path)
                log("   -> File saved")

        return wav_bytes

    def _prepare_conditionals_multi(
        self,
        voice_audio_path: Optional[str],
        speech_audio_path: str,
    ):
        """
        Prepara los conditionals del modelo con fuentes de audio separadas.

        Si voice_audio_path es None, usa speech_audio_path para todo.
        """
        self._tts.conds = self._compute_conditionals(voice_audio_path, speech_audio_path)

    def _compute_conditionals(
        self,
        voice_audio_path: Optional[str],
        speech_audio_path: str,
    ):
        """
        Computa los conditionals con fuentes de audio separadas (implementación
        única, compartida con la precomputación a disco de add_voice).

        - voice_audio_path: audio para el Voice Encoder (usa el audio COMPLETO para el embedding de timbre)
        - speech_audio_path: audio para el conditioning del T3 (6s) + decoder S3Gen (10s)

        Si voice_audio_path es None, usa speech_audio_path para todo.
        """
        import librosa
        from chatterbox.mtl_tts import Conditionals

        tts = self._tts

        # --- Carga el audio UNA vez a 24kHz ---
        ref_24k_speech, _ = librosa.load(speech_audio_path, sr=24000)

        # --- Voice Encoder: usa el audio completo para el timbre ---
        if voice_audio_path:
            ref_24k_voice, _ = librosa.load(voice_audio_path, sr=24000)
            ref_16k_voice = librosa.resample(ref_24k_voice, orig_sr=24000, target_sr=16000)
            # El conditioning del T3 solo consume ENC_COND_LEN muestras a 16k:
            # se recorta a 24k antes de resamplear en vez de bajar el audio completo.
            head_24k = ref_24k_speech[: tts.ENC_COND_LEN * 24000 // 16000]
            ref_16k_speech = librosa.resample(head_24k, orig_sr=24000, target_sr=16000)
        else:
            # Sin voice_audio, el timbre exige el audio completo a 16k; el
            # conditioning del T3 reutiliza ese mismo buffer.
            ref_16k_speech = librosa.resample(ref_24k_speech, orig_sr=24000, target_sr=16000)
            ref_16k_voice = ref_16k_speech

        ve_embed = torch.from_numpy(
            tts.ve.embeds_from_wavs([ref_16k_voice], sample_rate=16000)
        )
        ve_embed = ve_embed.mean(axis=0, keepdim=True).to(self.compute_backend)

        # --- Audio de habla: conditioning del T3 (6s) + decoder S3Gen (10s) ---
        # Referencia del decoder S3Gen (primeros 10s)
        ref_24k_speech = ref_24k_speech[:tts.DEC_COND_LEN]
        s3gen_ref_dict = tts.s3gen.embed_ref(ref_24k_speech, 24000, device=self.compute_backend)

        # Tokens de conditioning de habla del T3 (primeros 6s)
        t3_cond_prompt_tokens = None
        if plen := tts.t3.hp.speech_cond_prompt_len:
            s3_tokzr = tts.s3gen.tokenizer
            t3_cond_prompt_tokens, _ = s3_tokzr.forward(
                [ref_16k_speech[:tts.ENC_COND_LEN]], max_len=plen
            )
            t3_cond_prompt_tokens = torch.atleast_2d(t3_cond_prompt_tokens).to(self.compute_backend)

        t3_cond = T3Cond(
            speaker_emb=ve_embed,
            cond_prompt_speech_tokens=t3_cond_prompt_tokens,
            emotion_adv=self.EMOTION_ADV * torch.ones(1, 1, 1),
        ).to(device=self.compute_backend)

        return Conditionals(t3_cond, s3gen_ref_dict)

    def _audio_to_wav(self, audio_data) -> bytes:
        """Convierte un array numpy o tensor de audio a bytes WAV."""
        if hasattr(audio_data, 'numpy'):
            audio_np = audio_data.numpy()
        elif hasattr(audio_data, 'cpu'):
            audio_np = audio_data.cpu().numpy()
        else:
            audio_np = np.array(audio_data)

        # Asegura que sea float32 en [-1, 1]
        if audio_np.dtype != np.float32:
            audio_np = audio_np.astype(np.float32)

        # Maneja la dimensión de batch
        if audio_np.ndim > 1:
            audio_np = audio_np.flatten()

        # Normaliza si hace falta
        max_val = np.abs(audio_np).max()
        if max_val > 1.0:
            audio_np = audio_np / max_val

        # Crea el WAV
        import io
        buffer = io.BytesIO()
        sample_rate = getattr(self._tts, 'sr', 24000)

        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16 bits
            wf.setframerate(sample_rate)
            audio_int16 = (audio_np * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())

        return buffer.getvalue()

    def _save_wav(self, wav_bytes: bytes, path: str) -> None:
        """Guarda los bytes WAV a un archivo."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(wav_bytes)

    def add_voice(
        self,
        name: str,
        reference_audio: str,
        speech_audio: str,
        precompute: bool = True,
        force: bool = False,
    ) -> tuple[str, str]:
        """
        Registra una voz clonada a partir de dos archivos de audio.

        Args:
            name: Nombre para la voz
            reference_audio: Ruta al archivo de audio de referencia (cualquier largo, audio completo para el timbre)
            speech_audio: Ruta al archivo de audio de habla (10+ segundos, habla limpia para el conditioning)
            precompute: Si es True, precomputa y cachea los conditionals (default True)
            force: Si es True, sobrescribe una voz existente con el mismo nombre

        Returns:
            Tupla de (reference_path, speech_path)

        Raises:
            ValueError: si algún audio no es cargable, o si la voz ya existe
                        (usuario o fábrica) y no se pasó force.
        """
        # Validación y copia sin modelo: núcleo compartido con `voice add`,
        # que registra voces sin instanciar el motor (voices.register_voice_files).
        ref_path, speech_path = voices.register_voice_files(
            name=name,
            reference_audio=reference_audio,
            speech_audio=speech_audio,
            force=force,
        )

        # Precomputa los conditionals y los guarda a disco para una carga más rápida
        if precompute:
            try:
                voices_dir = os.path.dirname(ref_path)
                self._precompute_and_save_conditionals(voices_dir, ref_path, speech_path)
                log(f"Conditionals precomputados para la voz '{name}'")
            except Exception as e:
                log(f"Advertencia: no se pudieron precomputar los conditionals: {e}")

        return (ref_path, speech_path)

    def _precompute_and_save_conditionals(self, voice_dir: str, reference_audio: str, speech_audio: str):
        """
        Precomputa los conditionals desde los archivos de audio y los guarda a disco.

        Reutiliza el cómputo único de _compute_conditionals y crea un archivo
        conditionals.pt en el directorio de la voz.
        """
        conds = self._compute_conditionals(reference_audio, speech_audio)
        conds.save(os.path.join(voice_dir, "conditionals.pt"))

    def load_precomputed_conditionals(self, voice_dir: str) -> bool:
        """
        Carga los conditionals precomputados del directorio de la voz si existen.

        Devuelve True si los cargó, False en caso contrario.
        """
        import os
        from chatterbox.mtl_tts import Conditionals

        conds_path = os.path.join(voice_dir, "conditionals.pt")
        if not os.path.exists(conds_path):
            return False

        try:
            conds = Conditionals.load(conds_path, map_location=torch.device(self.compute_backend))
            self._tts.conds = conds.to(self.compute_backend)
            return True
        except Exception as e:
            log(f"   -> No se pudieron cargar los conditionals precomputados ({conds_path}): {e}")
            return False

    def list_voices(self) -> list[str]:
        """Lista todas las voces registradas."""
        return voices.list_voices()

    def remove_voice(self, name: str) -> bool:
        """Elimina una voz registrada."""
        return voices.remove_voice(name)

    def resolve_voice(self, name: str) -> tuple[str, str]:
        """
        Resuelve el nombre de la voz a sus rutas de audio de referencia y habla.

        Args:
            name: Nombre de la voz

        Returns:
            Tupla de (reference_path, speech_path)
        """
        return voices.voice_paths(name)
