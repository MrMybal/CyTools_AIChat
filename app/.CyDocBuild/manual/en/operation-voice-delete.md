---
id: operation-voice-delete
title: voice_delete
description: Move a recorded or imported voice to data/voices/deleted.
section: Reference
order: 200
parent: operations
revision: 2aec03dd0b71f880
---

Move a recorded or imported voice to data/voices/deleted.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `voice` | `string` | Yes | Voice id.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `voice` | `string` | Yes | Voice id.  |
| `deleted` | `boolean` | Yes | See the operation parameters.  |
| `keptIn` | `string` | Yes | Where the voice was moved.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation voice_delete
```
