---
id: operation-engine-list
title: engine_list
description: The pinned llama.cpp builds and which one is installed.
section: Reference
order: 200
parent: operations
revision: 6c38461e1d523e34
---

The pinned llama.cpp builds and which one is installed.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `release` | `string` | Yes | Pinned release tag.  |
| `repository` | `string` | Yes | Source repository.  |
| `builds` | `array` | Yes | See the operation parameters.  |
| `notes` | `string` | Yes | Notes.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation engine_list
```
