---
id: operation-resident-unload
title: resident_unload
description: Stop the local llama.cpp server and release its reservation.
section: Reference
order: 200
parent: operations
revision: 357f026d4cc28315
---

Stop the local llama.cpp server and release its reservation.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `stopped` | `boolean` | Yes | See the operation parameters.  |
| `resident` | `object` | Yes | State after stopping.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation resident_unload
```
