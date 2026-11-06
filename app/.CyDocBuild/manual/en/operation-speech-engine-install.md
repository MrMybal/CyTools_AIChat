---
id: operation-speech-engine-install
title: speech_engine_install
description: Create or repair a private Python environment for speech under runtime/engines: stt (PyTorch CPU and transformers 5, for Phonon-2 and Parakeet) or tts (PyTorch CUDA 12.8 or CPU, XTTS-v2 and F5-TTS). Downloads several gigabytes…
section: Reference
order: 200
parent: operations
revision: c30b1bc6a48a0b79
---

Create or repair a private Python environment for speech under runtime/engines: stt (PyTorch CPU and transformers 5, for Phonon-2 and Parakeet) or tts (PyTorch CUDA 12.8 or CPU, XTTS-v2 and F5-TTS). Downloads several gigabytes from PyPI and the PyTorch index. Speech models and voices in data/ are not touched.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | Yes | See the operation parameters. `enum=["stt", "tts"]` |
| `device` | `string` | No | PyTorch build for the tts environment. stt always uses the CPU. `default="cuda"`, `enum=["cuda", "cpu"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | Yes | Environment.  |
| `label` | `string` | Yes | Description.  |
| `directory` | `string` | Yes | Folder.  |
| `installed` | `boolean` | Yes | See the operation parameters.  |
| `families` | `array` | Yes | See the operation parameters.  |
| `estimatedBytes` | `integer` | Yes | See the operation parameters.  |
| `cuda` | `boolean` | Yes | See the operation parameters.  |
| `cpuOnly` | `boolean` | Yes | See the operation parameters.  |
| `device` | `string` | Yes | Device found.  |
| `torch` | `string` | Yes | PyTorch version.  |
| `installedAt` | `string` | Yes | Date.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`, `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_engine_install
```
