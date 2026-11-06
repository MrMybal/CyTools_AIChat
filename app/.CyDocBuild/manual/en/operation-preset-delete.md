---
id: operation-preset-delete
title: preset_delete
description: Remove a preset you saved.
section: Reference
order: 200
parent: operations
revision: 8f8832a76eb6a472
---

Remove a preset you saved.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Preset id.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Preset id.  |
| `deleted` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preset_delete
```
