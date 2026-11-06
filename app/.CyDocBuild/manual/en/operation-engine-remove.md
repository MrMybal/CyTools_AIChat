---
id: operation-engine-remove
title: engine_remove
description: Delete a build this Tool installed.
section: Reference
order: 200
parent: operations
revision: ff012099a75dbe8d
---

Delete a build this Tool installed.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `build` | `string` | Yes | See the operation parameters. `enum=["cpu", "cuda"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Build id.  |
| `removed` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation engine_remove
```
