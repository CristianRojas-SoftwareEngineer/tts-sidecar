# Licencias de terceros (Third-Party Licenses)

`tts-sidecar` se distribuye bajo **GPL-3.0-or-later** (ver `LICENSE`). El binario
autocontenido generado con PyInstaller empaqueta software de terceros bajo sus propias
licencias, todas permisivas y compatibles con GPLv3. Este documento reúne los avisos de
copyright y las licencias correspondientes, cuya preservación exigen dichas licencias al
redistribuir el software.

El **modelo de voz** (`ResembleAI/Chatterbox-Multilingual-es-mx-latam`) **no** se empaqueta
en el binario: se descarga a la caché de HuggingFace del usuario mediante `tts-sidecar
setup`. Se lista aquí por completitud, pero sus pesos no forman parte de la distribución.

> Nota sobre PyInstaller: el proceso de empaquetado elimina los archivos de licencia
> originales de cada dependencia. Este documento los restituye. Los textos íntegros de cada
> licencia están disponibles en los enlaces canónicos indicados.

---

## Componentes con licencia MIT

Licencia MIT — permiso de uso, copia, modificación y distribución conservando el aviso de
copyright y la nota de permiso. Texto: <https://opensource.org/license/mit>.

| Componente | Titular del copyright |
|-----------|-----------------------|
| Chatterbox TTS (`chatterbox-tts`) | Copyright (c) Resemble AI |
| Perth watermarker (`resemble-perth`) | Copyright (c) Resemble AI |
| Modelo `Chatterbox-Multilingual-es-mx-latam` (no empaquetado) | Copyright (c) Resemble AI |
| `s3tokenizer` | Copyright (c) sus autores |
| ONNX Runtime (`onnxruntime`) | Copyright (c) Microsoft Corporation |
| `sounddevice` | Copyright (c) Matthias Geier |
| `simpleaudio` | Copyright (c) Simpleaudio Authors |
| `pycaw` | Copyright (c) Andre Miras |

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Componentes con licencia BSD

Licencia BSD (2-Clause / 3-Clause) — permiten redistribución conservando el aviso de
copyright, la lista de condiciones y el descargo de garantía. Texto 3-Clause:
<https://opensource.org/license/bsd-3-clause>.

| Componente | Licencia | Titular del copyright |
|-----------|----------|-----------------------|
| PyTorch (`torch`) | BSD-3-Clause | Copyright (c) The PyTorch Contributors |
| NumPy (`numpy`) | BSD-3-Clause | Copyright (c) NumPy Developers |
| SciPy (`scipy`) | BSD-3-Clause | Copyright (c) SciPy Developers |
| scikit-learn (`sklearn`) | BSD-3-Clause | Copyright (c) The scikit-learn developers |
| pandas | BSD-3-Clause | Copyright (c) The pandas Development Team, AQR Capital Management |
| Starlette (base de FastAPI) | BSD-3-Clause | Copyright (c) Encode OSS Ltd |
| Uvicorn | BSD-3-Clause | Copyright (c) Encode OSS Ltd |

```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED. IN NO EVENT SHALL THE
COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## Componentes con licencia Apache 2.0

Licencia Apache License 2.0 — compatible con GPLv3. Requiere conservar los avisos de
copyright, el texto de la licencia y el archivo `NOTICE` cuando el trabajo lo incluya.
Texto íntegro: <https://www.apache.org/licenses/LICENSE-2.0>.

| Componente | Titular del copyright |
|-----------|-----------------------|
| `transformers` (Hugging Face) | Copyright (c) The HuggingFace Inc. team |
| `diffusers` (Hugging Face) | Copyright (c) The HuggingFace Inc. team |
| `safetensors` (Hugging Face) | Copyright (c) The HuggingFace Inc. team |
| `tokenizers` (Hugging Face) | Copyright (c) The HuggingFace Inc. team |

**NOTICE (Hugging Face):** los proyectos `transformers`, `diffusers`, `safetensors` y
`tokenizers` se distribuyen bajo Apache 2.0. Sus archivos `NOTICE` atribuyen el trabajo a
"The HuggingFace Inc. team" y a la comunidad de contribuidores. Consulte el `NOTICE` de cada
paquete en su repositorio oficial (<https://github.com/huggingface>) para el detalle
completo de atribuciones.

---

## Componentes con licencia ISC

| Componente | Titular del copyright |
|-----------|-----------------------|
| `librosa` | Copyright (c) The librosa development team |

Licencia ISC — funcionalmente equivalente a MIT/BSD-2. Texto:
<https://opensource.org/license/isc-license-txt>.

---

## Componentes con licencia PSF

| Componente | Licencia | Titular del copyright |
|-----------|----------|-----------------------|
| `pyalsaaudio` (solo Linux) | PSF-2.0 | Copyright (c) Casper Wilstrup, Lars Immisch |

Python Software Foundation License 2.0 — permisiva y compatible con GPLv3. Texto:
<https://docs.python.org/3/license.html>.

---

## Herramienta de empaquetado: PyInstaller

`tts-sidecar` se compila con **PyInstaller**, distribuido bajo **GPL 2.0 con una excepción**
que permite redistribuir los ejecutables generados bajo cualquier licencia, siempre que no
se modifique el *bootloader*. `tts-sidecar` usa el bootloader estándar sin modificar.
Texto y excepción: <https://pyinstaller.org/en/stable/license.html>.

---

## Verificación

El listado anterior cubre las dependencias empaquetadas conocidas. Para regenerar un
inventario exhaustivo del entorno concreto de build puede usarse `pip-licenses`:

```bash
pip install pip-licenses
pip-licenses --with-authors --with-urls --format=markdown
```
