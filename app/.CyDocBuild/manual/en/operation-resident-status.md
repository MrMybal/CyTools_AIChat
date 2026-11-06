---
id: operation-resident-status
title: resident_status
description: Whether a local model is loaded, on which device, with which adapters.
section: Reference
order: 200
parent: operations
revision: 7994c3e43e42a1fd
---

Whether a local model is loaded, on which device, with which adapters.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `resident` | `object` | Yes | Resident server state.  |
| `adapters` | `array` | Yes | Adapters reported by the running server.  |
| `properties` | `object` | Yes | Server properties, when loaded.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation resident_status
```
