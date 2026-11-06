---
id: operation-speech-unload
title: speech_unload
description: Stop both speech workers and free the memory they hold.
section: Reference
order: 200
parent: operations
revision: 2dcedcb9a52a32e2
---

Stop both speech workers and free the memory they hold.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `stopped` | `object` | Yes | Which workers were running.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_unload
```
