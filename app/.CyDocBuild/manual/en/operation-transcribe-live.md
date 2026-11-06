---
id: operation-transcribe-live
title: transcribe_live
description: Follow a recording the desktop window is writing (data/inputs/dictation/live-<id>.pcm, 16-bit mono PCM) and publish DictationPartial events with the text so far, about every half second of new speech. Sentences are closed at…
section: Reference
order: 200
parent: operations
revision: 7f06a1d100eed3be
---

Follow a recording the desktop window is writing (data/inputs/dictation/live-<id>.pcm, 16-bit mono PCM) and publish DictationPartial events with the text so far, about every half second of new speech. Sentences are closed at pauses and their words become final; the sentence being spoken may still change. The job ends when the window creates <name>.done and returns the whole text. Meant for the window; give a file to transcribe instead.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | Yes | Name of the live recording in data/inputs/dictation.  |
| `rate` | `integer` | Yes | Sample rate of the recording. `minimum=8000`, `maximum=192000` |
| `model` | `string` | No | Speech-to-text model id. Empty uses the settings. `default=""` |
| `language` | `string` | No | Expected language, used only to choose the model. `default=""` |
| `max_seconds` | `number` | No | See the operation parameters. `default=600`, `minimum=5`, `maximum=3600` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | Yes | Everything that was said.  |
| `model` | `string` | Yes | Model used.  |
| `audioSeconds` | `number` | Yes | See the operation parameters.  |
| `passes` | `integer` | Yes | See the operation parameters.  |
| `seconds` | `number` | Yes | See the operation parameters.  |
| `loadSeconds` | `number` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation transcribe_live
```
