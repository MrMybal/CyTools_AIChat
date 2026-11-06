---
id: operation-speech-engine-remove
title: speech_engine_remove
description: Delete runtime/engines/stt or runtime/engines/tts. Models and voices stay.
section: Reference
order: 200
parent: operations
revision: 45b20c6d9c9768dd
---

Delete runtime/engines/stt or runtime/engines/tts. Models and voices stay.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | Yes | See the operation parameters. `enum=["stt", "tts"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | Yes | Environment.  |
| `removed` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_engine_remove
```
