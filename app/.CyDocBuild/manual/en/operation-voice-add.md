---
id: operation-voice-add
title: voice_add
description: Keep a clip as a voice to imitate. Its words are found by speech to text unless you give them: F5-TTS needs them, XTTS-v2 does not.
section: Reference
order: 200
parent: operations
revision: c3d9ab013883ca24
---

Keep a clip as a voice to imitate. Its words are found by speech to text unless you give them: F5-TTS needs them, XTTS-v2 does not.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `audio` | `string` | Yes | Audio file: an absolute path anywhere on this machine, or a name inside data/inputs. WAV, FLAC, OGG or MP3. It is copied for the job and the original is left untouched.  |
| `name` | `string` | No | Name shown in the voice list. `default=""` |
| `language` | `string` | No | Language spoken in the clip, such as fr or en. `default=""` |
| `transcript` | `string` | No | The exact words spoken in the clip. `default=""` |
| `transcribe` | `boolean` | No | Find the words by speech to text when none are given. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `voice` | `object` | Yes | id, name, kind (recorded, sample, studio), language, transcript, clip, families.  |

## Behaviour and access {#behaviour}

- Required permissions: `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation voice_add
```
