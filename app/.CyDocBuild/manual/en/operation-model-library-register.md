---
id: operation-model-library-register
title: model_library_register
description: Register an existing compatible local model or LoRA by reference; does not download or copy weights. Registration is shared by clients of this local Tool.
section: Reference
order: 200
parent: operations
revision: f4fd31f843abc81d
---

Register an existing compatible local model or LoRA by reference; does not download or copy weights. Registration is shared by clients of this local Tool.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes | Display name  |
| `path` | `string` | Yes | Absolute local path visible on the Tool host  |
| `format` | `string` | Yes | Format ID from model_library_list  |
| `base` | `string` | No | Compatible base variant ID  |
| `license` | `string` | No | License identifier or terms  |
| `source` | `string` | No | Original source URL or repository  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `object` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_library_register
```
