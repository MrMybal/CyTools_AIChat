---
id: operation-transcribe
title: transcribe
description: Speech to text with Phonon-2 (English) or Parakeet TDT 0.6B v3 (25 languages, French included), on the CPU. The model stays loaded for the next request.
section: Reference
order: 200
parent: operations
revision: f048e11415d9a6c7
---

Speech to text with Phonon-2 (English) or Parakeet TDT 0.6B v3 (25 languages, French included), on the CPU. The model stays loaded for the next request.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `audio` | `string` | Yes | Audio file: an absolute path anywhere on this machine, or a name inside data/inputs. WAV, FLAC, OGG or MP3. It is copied for the job and the original is left untouched.  |
| `model` | `string` | No | Speech-to-text model id. Empty uses the settings, then the best installed model for the language. `default=""` |
| `language` | `string` | No | Expected language, used only to choose the model: en prefers Phonon-2. The models detect the language themselves. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | Yes | What was said.  |
| `model` | `string` | Yes | Model used.  |
| `audioSeconds` | `number` | Yes | See the operation parameters.  |
| `seconds` | `number` | Yes | See the operation parameters.  |
| `loadSeconds` | `number` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation transcribe
```
