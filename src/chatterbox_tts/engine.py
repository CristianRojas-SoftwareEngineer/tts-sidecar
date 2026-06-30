"""
Chatterbox TTS Engine
Wrapper for Chatterbox Multilingual TTS from HuggingFace.
Supports es-MX-Latam single language pack via custom loader.

Architecture: T3 (autoregressive, ~0.4B params) + S3Gen (flow matching vocoder).
Default synthesis parameters (override in daemon):
  - max_new_tokens=500  (T3 output cap; default is 1000)
  - n_cfm_timesteps=4  (flow matching steps; default is 10)
  - exaggeration=0.75   (emotional expressiveness; default is 0.5)

Multi-platform optimizations for Windows, Linux, and Mac.
"""

import os
import platform
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from . import voices
from .timing import StageTimer, log

# =============================================================================
# Platform-aware PyTorch configuration for CPU inference
# =============================================================================

def _configure_torch_for_platform():
    """Configure PyTorch settings based on the current platform."""
    system = platform.system()

    # Determine optimal thread count based on CPU cores
    cpu_count = os.cpu_count() or 4
    # Use up to 8 threads - beyond this, memory bandwidth becomes the bottleneck
    # for transformer models on CPU (more threads = worse due to thread contention)
    optimal_threads = min(8, cpu_count)

    torch.set_num_threads(optimal_threads)

    if system == "Windows":
        # Windows: Intel MKL is typically available via PyTorch
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        os.environ["MKL_NUM_THREADS"] = str(optimal_threads)
        # Disable oneDNN custom kernels if they cause issues
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    elif system == "Linux":
        # Linux: OpenMP via libgomp, potentially MKL
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        os.environ["MKL_NUM_THREADS"] = str(optimal_threads)
        # Try to enable oneDNN for better CPU performance
        try:
            torch.backends.mkldnn.enabled = True
        except Exception:
            pass

    elif system == "Darwin":
        # Mac: Accelerate framework (built-in)
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        # MPS fallback for Macs with Apple Silicon
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    # Enable MKLDNN if available (Intel/AMD CPUs benefit from it)
    try:
        torch.backends.mkldnn.enabled = True
        torch.backends.mkldnn.verbose(0)
    except Exception:
        pass  # MKL-DNN not available

    # Disable denormal flushing for faster computation on modern CPUs
    try:
        torch.set_flush_denormal(True)
    except Exception:
        pass

    return optimal_threads


# Apply platform configuration at module import
_THREAD_COUNT = _configure_torch_for_platform()
del _configure_torch_for_platform  # Keep namespace clean


from safetensors.torch import load_file

# Chatterbox imports
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
    TTS Engine using Chatterbox models.

    Default model: es-MX-Latam single language pack
    Uses ChatterboxMultilingualTTS architecture with 2454-token vocabulary
    to match the es-mx-latam checkpoint (text_emb: 2454×1024).

    Supports model caching to avoid reloading on each instantiation.
    """

    # Model configurations
    MODELS = {
        "multilingual": "ResembleAI/chatterbox-multilingual",
        "es-latam": "ResembleAI/Chatterbox-Multilingual-es-mx-latam",
    }

    # Class-level cache for loaded models (avoids reloading on each speak)
    _cache: dict[str, "ChatterboxEngine"] = {}

    @classmethod
    def get_instance(cls, model: str = "es-latam", device: str = "cpu", models_dir: Optional[str] = None) -> "ChatterboxEngine":
        """
        Get a cached engine instance or create a new one.

        The model stays loaded in memory for subsequent calls.

        Args:
            model: Model to use ("es-latam" or "multilingual")
            device: Device for inference ("cpu", "cuda", "mps")
            models_dir: Directory to cache models
        """
        cache_key = f"{model}:{device}"
        if cache_key not in cls._cache:
            cls._cache[cache_key] = cls(model=model, device=device, models_dir=models_dir)
        return cls._cache[cache_key]

    def __init__(
        self,
        model: str = "es-latam",
        device: str = "cpu",
        models_dir: Optional[str] = None,
    ):
        """
        Initialize the Chatterbox TTS engine.

        Args:
            model: Model to use. Options:
                   - "es-latam": Latin American Spanish (RECOMMENDED, uses 2454-token vocab)
                   - "multilingual": Base multilingual model
            device: Device for inference ("cpu", "cuda", "mps")
            models_dir: Directory to cache models. Defaults to ~/.cache/huggingface/hub
        """
        self.device = device
        self.model_name = self.MODELS.get(model, model)

        # Download model to local cache
        self._cache_dir = self._download_model(self.model_name, models_dir)

        # Load model from local files using correct loader
        self._tts = self._load_model(self._cache_dir, self.model_name, device)

    def _download_model(self, model_name: str, models_dir: Optional[str] = None) -> Path:
        """Download model from HuggingFace or get from local cache."""
        from huggingface_hub import snapshot_download
        import os

        cache_path = Path(os.path.expanduser("~/.cache/huggingface/hub"))

        # Try to find existing cached model
        cache_names = {
            "es-latam": "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
            "multilingual": "models--ResembleAI--chatterbox-multilingual",
            "ResembleAI/Chatterbox-Multilingual-es-mx-latam": "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
            "ResembleAI/chatterbox-multilingual": "models--ResembleAI--chatterbox-multilingual",
        }
        cache_folder = cache_names.get(model_name, f"models--{model_name.replace('/', '--')}")
        snap_path = cache_path / cache_folder / "snapshots"

        if snap_path.exists():
            snapshots = [d for d in os.listdir(snap_path) if (snap_path / d).is_dir()]
            if snapshots:
                cached = snap_path / snapshots[0]
                # Verify es-mx-latam files exist
                if model_name == "es-latam" or "es-mx-latam" in model_name:
                    if (cached / "t3_es_mx_latam.safetensors").exists():
                        print(f"Using cached model: {model_name} ({cached})")
                        return cached

        # Download from HuggingFace
        print(f"Downloading {model_name} from HuggingFace...")
        if model_name == "es-latam":
            model_name = "ResembleAI/Chatterbox-Multilingual-es-mx-latam"

        cached_path = Path(
            snapshot_download(
                repo_id=model_name,
                repo_type="model",
                token=os.getenv("HF_TOKEN"),
            )
        )
        print(f"Model downloaded to: {cached_path}")
        return cached_path

    def _load_model(self, cache_dir: Path, model_name: str, device: str):
        """Load es-MX-Latam model using multilingual architecture (2454 tokens)."""
        cache_dir = Path(cache_dir)

        # Map model_name to files
        if "es-mx-latam" in str(cache_dir) or "es-latam" in str(cache_dir):
            return self._load_es_latam(cache_dir, device)
        else:
            return self._load_multilingual(cache_dir, device)

    def _load_es_latam(self, cache_dir: Path, device: str):
        """
        Load es-MX-Latam single language pack.

        Architecture: ChatterboxMultilingualTTS (2454-token vocab)
        - T3: t3_es_mx_latam.safetensors (trained with expanded vocab)
        - S3Gen: s3gen_v3.safetensors
        - Tokenizer: grapheme_mtl_merged_expanded_v1.json (2454 tokens)
        """
        if device in ["cpu", "mps"]:
            map_location = torch.device("cpu")
        else:
            map_location = None

        # Load Voice Encoder
        # es-mx-latam doesn't include ve.safetensors; it's shared with base model
        ve_path = cache_dir / "ve.safetensors"
        if not ve_path.exists():
            # Try base model cache
            import os as _os
            base_ve = Path(_os.path.expanduser("~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots"))
            if base_ve.exists():
                snaps = [d for d in _os.listdir(base_ve) if (base_ve / d).is_dir()]
                if snaps:
                    ve_path = base_ve / snaps[0] / "ve.safetensors"
        if not ve_path.exists():
            # Download just the voice encoder
            from huggingface_hub import hf_hub_download
            ve_path = Path(hf_hub_download(
                repo_id="ResembleAI/chatterbox",
                filename="ve.safetensors",
                token=os.getenv("HF_TOKEN"),
            ))

        ve = VoiceEncoder()
        ve.load_state_dict(load_file(ve_path))
        ve.to(device).eval()

        # Load T3 with multilingual config (2454-token vocab)
        t3 = T3(T3Config.multilingual())
        t3_path = cache_dir / "t3_es_mx_latam.safetensors"
        t3_state = load_file(t3_path)
        if "model" in t3_state.keys():
            t3_state = t3_state["model"][0]
        t3.load_state_dict(t3_state)
        t3.to(device).eval()

        # Load S3Gen v3
        s3gen = S3Gen()
        # Try safetensors first, then pt
        s3gen_path = cache_dir / "s3gen_v3.safetensors"
        if not s3gen_path.exists():
            s3gen_path = cache_dir / "s3gen_v3.pt"
        s3gen_state = load_file(s3gen_path) if s3gen_path.suffix == ".safetensors" else torch.load(s3gen_path, map_location=map_location, weights_only=True)
        s3gen.load_state_dict(s3gen_state, strict=False)
        s3gen.to(device).eval()

        # Load multilingual tokenizer (2454 tokens)
        tokenizer = MTLTokenizer(str(cache_dir / "grapheme_mtl_merged_expanded_v1.json"))

        # Load conditionals (builtin voice from the model)
        # This allows generation without audio_prompt_path
        conds = None
        conds_path = cache_dir / "conds.pt"
        if conds_path.exists():
            from chatterbox.mtl_tts import Conditionals
            conds = Conditionals.load(conds_path, map_location=map_location).to(device)

        tts = ChatterboxMultilingualTTS(t3, s3gen, ve, tokenizer, device, conds=conds)

        # If no builtin conds, require audio_prompt_path in generate()
        tts._require_voice_prompt = conds is None

        print(f"Model loaded: es-MX-Latam (vocab=2454, device={device}, builtin_voice={'yes' if conds else 'no'})")
        return tts

    def _load_multilingual(self, cache_dir: Path, device: str):
        """Load base multilingual model (for comparison/debugging)."""
        return ChatterboxTTS.from_local(cache_dir, device)

    def speak(
        self,
        text: str,
        voice_audio: Optional[str] = None,
        speech_audio: Optional[str] = None,
        output_path: Optional[str] = None,
        verbose: bool = True,
    ) -> bytes:
        """
        Generate and optionally save audio from text.

        Args:
            text: Text to synthesize (Spanish)
            voice_audio: Audio file for Voice Encoder (full audio for timbre embedding)
            speech_audio: Audio file for T3 conditioning (6s) + S3Gen decoder (10s).
                         If None but voice_audio provided, voice_audio is used for both.
            output_path: Optional path to save WAV file
            verbose: If True, print stage timing info (default True)

        Returns:
            Audio data as WAV bytes
        """
        if not voice_audio and not speech_audio:
            raise ValueError(
                "At least one audio file is required. "
                "Use --voice-audio for timbre, --speech-audio for conditioning. "
                "If only --voice-audio is provided, it is used for both."
            )

        # If only voice_audio, use it for both
        if voice_audio and not speech_audio:
            speech_audio = voice_audio

        # Stage 1: Load conditionals
        with StageTimer("1-Speak", "Stage 1/4: Loading conditionals"):
            voice_dir = None
            if speech_audio:
                voice_dir = os.path.dirname(speech_audio)
                conditionals_path = os.path.join(voice_dir, "conditionals.pt")
                if os.path.exists(conditionals_path):
                    self.load_precomputed_conditionals(voice_dir)
                    log("   -> Precomputed conditionals loaded")
                else:
                    log("   -> Computing conditionals on-the-fly...")
                    self._prepare_conditionals_multi(
                        voice_audio_path=voice_audio,
                        speech_audio_path=speech_audio,
                    )
            else:
                self._prepare_conditionals_multi(
                    voice_audio_path=voice_audio,
                    speech_audio_path=speech_audio,
                )

        # Stage 2: TTS Generation
        # n_cfm is applied by the daemon's s3gen.inference patch (setdefault).
        # For direct mode (no daemon), Chatterbox handles defaults internally.
        with StageTimer("2-Speak", "Stage 2/4: Generating audio (TTS)"):
            wav = self._tts.generate(text, language_id="es")

        # Stage 3: Convert to WAV
        with StageTimer("3-Speak", "Stage 3/4: Converting to WAV"):
            wav_bytes = self._audio_to_wav(wav)

        # Stage 4: Save to file (optional)
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
        Prepare conditionals with separate audio sources.

        - voice_audio_path: audio for Voice Encoder (uses FULL audio for timbre embedding)
        - speech_audio_path: audio for T3 conditioning (6s) + S3Gen decoder (10s)

        If voice_audio_path is None, uses speech_audio_path for everything.
        """
        import librosa
        from chatterbox.mtl_tts import Conditionals

        tts = self._tts

        # --- Load audio ONCE at 24kHz, then downsample to 16kHz ---
        # This avoids loading the same file twice
        ref_24k_speech, _ = librosa.load(speech_audio_path, sr=24000)
        ref_16k_speech = librosa.resample(ref_24k_speech, orig_sr=24000, target_sr=16000)

        # --- Voice Encoder: uses full audio for timbre ---
        if voice_audio_path:
            ref_24k_voice, _ = librosa.load(voice_audio_path, sr=24000)
            ref_16k_voice = librosa.resample(ref_24k_voice, orig_sr=24000, target_sr=16000)
        else:
            ref_16k_voice = ref_16k_speech

        ve_embed = torch.from_numpy(
            tts.ve.embeds_from_wavs([ref_16k_voice], sample_rate=16000)
        )
        ve_embed = ve_embed.mean(axis=0, keepdim=True).to(self.device)

        # --- Speech audio: T3 conditioning (6s) + S3Gen decoder (10s) ---
        # S3Gen decoder reference (first 10s)
        ref_24k_speech = ref_24k_speech[:tts.DEC_COND_LEN]
        s3gen_ref_dict = tts.s3gen.embed_ref(ref_24k_speech, 24000, device=self.device)

        # T3 speech conditioning tokens (first 6s)
        t3_cond_prompt_tokens = None
        if plen := tts.t3.hp.speech_cond_prompt_len:
            s3_tokzr = tts.s3gen.tokenizer
            t3_cond_prompt_tokens, _ = s3_tokzr.forward(
                [ref_16k_speech[:tts.ENC_COND_LEN]], max_len=plen
            )
            t3_cond_prompt_tokens = torch.atleast_2d(t3_cond_prompt_tokens).to(self.device)

        t3_cond = T3Cond(
            speaker_emb=ve_embed,
            cond_prompt_speech_tokens=t3_cond_prompt_tokens,
            emotion_adv=0.5 * torch.ones(1, 1, 1),
        ).to(device=self.device)

        tts.conds = Conditionals(t3_cond, s3gen_ref_dict)

    def _audio_to_wav(self, audio_data) -> bytes:
        """Convert numpy array or audio tensor to WAV bytes."""
        if hasattr(audio_data, 'numpy'):
            audio_np = audio_data.numpy()
        elif hasattr(audio_data, 'cpu'):
            audio_np = audio_data.cpu().numpy()
        else:
            audio_np = np.array(audio_data)

        # Ensure it's float32 in [-1, 1]
        if audio_np.dtype != np.float32:
            audio_np = audio_np.astype(np.float32)

        # Handle batch dimension
        if audio_np.ndim > 1:
            audio_np = audio_np.flatten()

        # Normalize if needed
        max_val = np.abs(audio_np).max()
        if max_val > 1.0:
            audio_np = audio_np / max_val

        # Create WAV
        import io
        buffer = io.BytesIO()
        sample_rate = getattr(self._tts, 'sr', 24000)

        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            audio_int16 = (audio_np * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())

        return buffer.getvalue()

    def _save_wav(self, wav_bytes: bytes, path: str) -> None:
        """Save WAV bytes to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(wav_bytes)

    def add_voice(self, name: str, reference_audio: str, speech_audio: str, precompute: bool = True) -> tuple[str, str]:
        """
        Register a voice clone from two audio files.

        Args:
            name: Name for the voice
            reference_audio: Path to reference audio file (any length, full audio for timbre)
            speech_audio: Path to speech audio file (10+ seconds, clean speech for conditioning)
            precompute: If True, precompute and cache conditionals (default True)

        Returns:
            Tuple of (reference_path, speech_path)
        """
        voices_dir = voices.voice_dir(name)
        Path(voices_dir).mkdir(parents=True, exist_ok=True)

        ref_path = os.path.join(voices_dir, "reference.wav")
        speech_path = os.path.join(voices_dir, "speech.wav")

        # Copy both audio files to voices directory
        import shutil
        shutil.copy2(reference_audio, ref_path)
        shutil.copy2(speech_audio, speech_path)

        # Precompute conditionals and save to disk for faster loading
        if precompute:
            try:
                self._precompute_and_save_conditionals(voices_dir, ref_path, speech_path)
                print(f"Conditionals precomputed for voice '{name}'")
            except Exception as e:
                print(f"Warning: Could not precompute conditionals: {e}")

        return (ref_path, speech_path)

    def _precompute_and_save_conditionals(self, voice_dir: str, reference_audio: str, speech_audio: str):
        """
        Precompute conditionals from audio files and save to disk.

        Creates a conditionals.pt file in the voice directory.
        """
        import os
        import torch
        import librosa
        from chatterbox.mtl_tts import Conditionals

        tts = self._tts

        # Load audio
        ref_24k, _ = librosa.load(reference_audio, sr=24000)
        ref_16k_voice = librosa.resample(ref_24k, orig_sr=24000, target_sr=16000)

        ref_24k_speech, _ = librosa.load(speech_audio, sr=24000)
        ref_16k_speech = librosa.resample(ref_24k_speech, orig_sr=24000, target_sr=16000)

        # Voice Encoder embedding
        ve_embed = torch.from_numpy(
            tts.ve.embeds_from_wavs([ref_16k_voice], sample_rate=16000)
        )
        ve_embed = ve_embed.mean(axis=0, keepdim=True).to(self.device)

        # S3Gen reference
        ref_24k_speech = ref_24k_speech[:tts.DEC_COND_LEN]
        s3gen_ref_dict = tts.s3gen.embed_ref(ref_24k_speech, 24000, device=self.device)

        # T3 conditioning tokens
        t3_cond_prompt_tokens = None
        if plen := tts.t3.hp.speech_cond_prompt_len:
            s3_tokzr = tts.s3gen.tokenizer
            t3_cond_prompt_tokens, _ = s3_tokzr.forward(
                [ref_16k_speech[:tts.ENC_COND_LEN]], max_len=plen
            )
            t3_cond_prompt_tokens = torch.atleast_2d(t3_cond_prompt_tokens).to(self.device)

        t3_cond = T3Cond(
            speaker_emb=ve_embed,
            cond_prompt_speech_tokens=t3_cond_prompt_tokens,
            emotion_adv=0.5 * torch.ones(1, 1, 1),
        ).to(device=self.device)

        # Save conditionals
        conds = Conditionals(t3_cond, s3gen_ref_dict)
        save_path = os.path.join(voice_dir, "conditionals.pt")
        conds.save(save_path)

    def load_precomputed_conditionals(self, voice_dir: str) -> bool:
        """
        Load precomputed conditionals from voice directory if available.

        Returns True if loaded, False otherwise.
        """
        import os
        from chatterbox.mtl_tts import Conditionals

        conds_path = os.path.join(voice_dir, "conditionals.pt")
        if not os.path.exists(conds_path):
            return False

        try:
            conds = Conditionals.load(conds_path, map_location=torch.device(self.device))
            self._tts.conds = conds.to(self.device)
            return True
        except Exception:
            return False

    def list_voices(self) -> list[str]:
        """List all registered voices."""
        return voices.list_voices()

    def remove_voice(self, name: str) -> bool:
        """Remove a registered voice."""
        return voices.remove_voice(name)

    def resolve_voice(self, name: str) -> tuple[str, str]:
        """
        Resolve voice name to reference and speech audio paths.

        Args:
            name: Voice name

        Returns:
            Tuple of (reference_path, speech_path)
        """
        return voices.voice_paths(name)
