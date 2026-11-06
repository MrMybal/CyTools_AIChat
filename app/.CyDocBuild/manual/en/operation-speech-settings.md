---
id: operation-speech-settings
title: speech_settings
description: Read or change the speech preferences. A field left out keeps its value.
section: Reference
order: 200
parent: operations
revision: afcc70a46cdecee1
---

Read or change the speech preferences. A field left out keeps its value.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stt_model` | `string` | No | Speech-to-text model id. Empty picks the best installed one.  |
| `tts_model` | `string` | No | Voice model id. Empty picks an installed one that speaks the language.  |
| `voice` | `string` | No | Voice id (voice_list). Empty picks a default for the model.  |
| `language` | `string` | No | auto, or a code such as fr or en.  |
| `speed` | `number` | No | See the operation parameters. `minimum=0.5`, `maximum=2.0` |
| `tts_device` | `string` | No | See the operation parameters. `enum=["auto", "cuda", "cpu"]` |
| `auto_read` | `boolean` | No | Read new replies aloud in the window.  |
| `live_dictation` | `boolean` | No | Show the words in the window while you speak.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `settings` | `object` | Yes | The stored settings.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_settings
```
