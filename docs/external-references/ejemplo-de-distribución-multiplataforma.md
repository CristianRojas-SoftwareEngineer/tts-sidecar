# Desafíos de distribución multiplataforma para software open source

## Tabla de contenidos

- [¿Cuál es el problema?](#cual-es-el-problema)
  - [1. Firma digital (Code Signing)](#1-firma-digital-code-signing)
  - [2. Reputación](#2-reputacion)
  - [3. Heurísticas](#3-heuristicas)
- [¿Por qué afecta tanto a proyectos pequeños?](#por-que-afecta-tanto-a-proyectos-pequenos)
- [¿Cómo lo resuelve Engram?](#como-lo-resuelve-engram)
- [¿Significa que un binario compilado localmente es "más seguro"?](#significa-que-un-binario-compilado-localmente-es-mas-seguro)
- [¿Es Engram multiplataforma?](#es-engram-multiplataforma)
- [Plataformas soportadas](#plataformas-soportadas)
- [¿Necesita runtime?](#necesita-runtime)
- [¿Cómo distribuyen el mismo programa para todas las plataformas?](#como-distribuyen-el-mismo-programa-para-todas-las-plataformas)
- [¿Y cómo instala cada plataforma?](#y-como-instala-cada-plataforma)
- [Lo que más me gustó de la arquitectura](#lo-que-mas-me-gusto-de-la-arquitectura)

Sí, investigué específicamente ese punto y es interesante porque **no es un problema propio de Engram**, sino un problema general de la distribución de software open source para Windows.

## ¿Cuál es el problema?

Cuando descargas un ejecutable (`.exe`) de Internet, Windows y muchos antivirus intentan responder una pregunta:

> **"¿Puedo confiar en este programa?"**

Hay tres mecanismos principales.

### 1. Firma digital (Code Signing)

Los grandes fabricantes como:

* Microsoft
* Google
* JetBrains

firman sus ejecutables con un certificado criptográfico.

Cuando ejecutas un programa firmado, Windows puede comprobar:

* quién lo creó;
* que no fue modificado;
* que el certificado sigue siendo válido.

Eso genera mucha confianza.

---

### 2. Reputación

Windows Defender y SmartScreen también mantienen una reputación.

Por ejemplo:

* Visual Studio Code ha sido descargado millones de veces.
* Git tiene millones de instalaciones.

Aunque no conocieras al desarrollador, Windows sabe que ese binario lleva años siendo usado sin problemas.

---

### 3. Heurísticas

Si ninguna de las dos anteriores existe, entra en juego la heurística.

El antivirus analiza:

* estructura del PE
* imports
* compresores
* comportamiento esperado
* entropía
* patrones típicos de malware

No intenta demostrar que sea malware.

Intenta estimar una probabilidad.

Por eso aparecen mensajes como:

```
Trojan:Script/Wacatac.H!ml
```

Ese nombre es una **clasificación heurística**, no una identificación de un malware concreto. ([arXiv][1])

---

## ¿Por qué afecta tanto a proyectos pequeños?

Porque un certificado de firma cuesta normalmente **cientos de dólares al año** y además requiere un proceso de validación de identidad.

Para un proyecto open source mantenido por una persona, el coste suele ser difícil de justificar.

El propio autor de Engram explica que **no piensa pagar un certificado de firma por ahora**, y considera que el problema es de confianza en la distribución, no de seguridad del código. ([GitHub][2])

---

## ¿Cómo lo resuelve Engram?

En lugar de intentar convencer al antivirus de que el binario descargado es seguro, propone algo diferente:

**Que tú mismo lo compiles.**

Con:

```bash
go install github.com/Gentleman-Programming/engram/cmd/engram@latest
```

ocurre este flujo:

```
Código fuente

↓

Go descarga dependencias

↓

Compila localmente

↓

engram.exe
```

Ahora el ejecutable:

* fue generado por tu compilador;
* fue creado en tu máquina;
* no proviene de Internet como un `.zip`.

Por eso normalmente Windows Defender ya no lo clasifica como sospechoso. ([GitHub][2])

---

## ¿Significa que un binario compilado localmente es "más seguro"?

No necesariamente.

Significa que:

* puedes inspeccionar el código;
* sabes exactamente qué versión compilaste;
* reduces el riesgo de una cadena de distribución comprometida;
* evitas muchas detecciones heurísticas asociadas a binarios descargados.

Es una cuestión de **cadena de confianza**, no de que el código cambie.

---

## ¿Es Engram multiplataforma?

Sí.

Y aquí hay otra decisión de diseño muy buena.

Engram está escrito completamente en **Go**.

No usa:

* Python
* Node.js
* Java
* .NET

El resultado es un único ejecutable nativo por plataforma. ([GitHub][3])

---

## Plataformas soportadas

Actualmente distribuye binarios para:

| Sistema | Arquitecturas                      |
| ------- | ---------------------------------- |
| Windows | x64, ARM64                         |
| Linux   | x64, ARM64                         |
| macOS   | Intel (x64), Apple Silicon (ARM64) |

Todos son binarios nativos. ([GitHub][2])

---

## ¿Necesita runtime?

No.

Ese es otro punto interesante.

Como está escrito en Go:

```
engram.exe
```

ya contiene prácticamente todo.

No necesitas instalar:

* Go
* Python
* Node
* Java

Solamente el ejecutable. Además, el proyecto utiliza la implementación pura de Go de SQLite (`modernc.org/sqlite`), por lo que tampoco depende de bibliotecas nativas de SQLite. ([GitHub][2])

---

## ¿Cómo distribuyen el mismo programa para todas las plataformas?

Utilizan compilación cruzada (*cross-compilation*).

El proceso de publicación genera automáticamente artefactos específicos para cada combinación de sistema operativo y arquitectura, por ejemplo:

```
engram_1.15.8_windows_amd64.zip

engram_1.15.8_windows_arm64.zip

engram_1.15.8_linux_amd64.tar.gz

engram_1.15.8_linux_arm64.tar.gz

engram_1.15.8_darwin_amd64.tar.gz

engram_1.15.8_darwin_arm64.tar.gz
```

Todos esos artefactos se construyen desde el mismo código fuente durante el proceso de publicación. ([GitHub][2])

---

## ¿Y cómo instala cada plataforma?

Aquí el proyecto adapta el método a las convenciones de cada sistema operativo:

| Plataforma | Instalación recomendada                                        |
| ---------- | -------------------------------------------------------------- |
| macOS      | `brew install gentleman-programming/tap/engram`                |
| Linux      | Binario precompilado (o compilación desde código)              |
| Windows    | Binario precompilado o compilación desde código (`go install`) |

Además, el proyecto **Gentle AI** automatiza la descarga del binario correcto para Windows y Linux, verificando su integridad mediante checksums antes de instalarlo, de modo que el usuario no tenga que compilarlo manualmente si no lo desea. ([Paquetes Go][4])

## Lo que más me gustó de la arquitectura

Más allá de la memoria, creo que la mejor decisión técnica de Engram es haberlo implementado como un **binario Go autocontenido**.

Eso le permite ofrecer exactamente el mismo comportamiento en Windows, Linux y macOS con una sola base de código, sin exigir runtimes adicionales. Para una herramienta MCP que debe integrarse con múltiples agentes (Claude Code, Codex, Gemini CLI, Cursor, etc.), ese enfoque reduce enormemente la complejidad de instalación y mantenimiento, y facilita que cualquier cliente simplemente ejecute `engram mcp` como un proceso nativo en su plataforma.

[1]: https://arxiv.org/abs/1804.04637?utm_source=chatgpt.com "EMBER: An Open Dataset for Training Static PE Malware Machine Learning Models"
[2]: https://github.com/Gentleman-Programming/engram/blob/main/docs/INSTALLATION.md?utm_source=chatgpt.com "engram/docs/INSTALLATION.md at main · Gentleman-Programming/engram · GitHub"
[3]: https://github.com/Gentleman-Programming/engram?utm_source=chatgpt.com "GitHub - Gentleman-Programming/engram: Persistent memory system for AI coding agents. Agent-agnostic Go binary with SQLite + FTS5, MCP server, HTTP API, CLI, and TUI. · GitHub"
[4]: https://pkg.go.dev/github.com/gentleman-programming/gentle-ai%40v1.37.2/internal/components/engram?utm_source=chatgpt.com "engram package - github.com/gentleman-programming/gentle-ai/internal/components/engram - Go Packages"
