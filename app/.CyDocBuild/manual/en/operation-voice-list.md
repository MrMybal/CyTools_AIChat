---
id: operation-voice-list
title: voice_list
description: Recorded and imported voices, the sample clips of installed models and the XTTS-v2 studio voices.
section: Reference
order: 200
parent: operations
revision: 09885639d92be69e
---

Recorded and imported voices, the sample clips of installed models and the XTTS-v2 studio voices.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `voices` | `array` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation voice_list
```
