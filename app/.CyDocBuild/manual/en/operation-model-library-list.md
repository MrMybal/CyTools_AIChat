---
id: operation-model-library-list
title: model_library_list
description: List compatible model formats, device capabilities and registered local model/LoRA references.
section: Reference
order: 200
parent: operations
revision: 1212a32cee646962
---

List compatible model formats, device capabilities and registered local model/LoRA references.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `capabilities` | `object` | Yes | See the operation parameters.  |
| `library` | `object` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_library_list
```
