---
id: operation-model-repair
title: model_repair
description: Re-verify an entry and delete only the files whose digest does not match.
section: Reference
order: 200
parent: operations
revision: b41505ece1ee6c09
---

Re-verify an entry and delete only the files whose digest does not match.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Catalogue entry id.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Entry id.  |
| `removedFiles` | `array` | Yes | See the operation parameters.  |
| `installed` | `boolean` | Yes | See the operation parameters.  |
| `repaired` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_repair
```
