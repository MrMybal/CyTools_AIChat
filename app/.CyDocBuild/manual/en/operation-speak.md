---
id: operation-speak
title: speak
description: Text to speech with XTTS-v2 or F5-TTS. Give a text, or a conversation and one of its messages to read a stored reply. The audio of a stored reply is kept in data/speech and reused when the same reply is read again with the…
section: Reference
order: 200
parent: operations
revision: 696a63a62c4f59f9
---

Text to speech with XTTS-v2 or F5-TTS. Give a text, or a conversation and one of its messages to read a stored reply. The audio of a stored reply is kept in data/speech and reused when the same reply is read again with the same voice.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | No | Text to read. Ignored when conversation and message are given. `default=""` |
| `conversation` | `string` | No | Conversation id, to read one of its messages. `default=""` |
| `message` | `string` | No | Message id within that conversation. `default=""` |
| `model` | `string` | No | Voice model id. Empty uses the settings. `default=""` |
| `voice` | `string` | No | Voice id from voice_list. Empty uses the settings, then a default. `default=""` |
| `language` | `string` | No | auto, or a code such as fr or en. Empty uses the settings. `default=""` |
| `speed` | `number` | No | Speaking rate. Empty uses the settings. `minimum=0.5`, `maximum=2.0` |
| `device` | `string` | No | See the operation parameters. `default=""`, `enum=["", "auto", "cuda", "cpu"]` |
| `progressive` | `boolean` | No | Publish a SpeechPiece event with a WAV file for each sentence as soon as it is made, so playback can start before the whole text is ready. The pieces are written to data/speech/pieces; whoever plays them deletes them. Cancelling stops after the current sentence. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `audio` | `string` | Yes | WAV file (16-bit PCM).  |
| `durationSeconds` | `number` | Yes | See the operation parameters.  |
| `model` | `string` | Yes | Model used.  |
| `voice` | `string` | Yes | Voice id used.  |
| `voiceName` | `string` | Yes | Voice name.  |
| `language` | `string` | Yes | Language spoken.  |
| `cached` | `boolean` | Yes | Reused from an earlier reading.  |
| `seconds` | `number` | Yes | See the operation parameters.  |
| `device` | `string` | Yes | cuda or cpu.  |

## Behaviour and access {#behaviour}

- Required permissions: `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak
```
