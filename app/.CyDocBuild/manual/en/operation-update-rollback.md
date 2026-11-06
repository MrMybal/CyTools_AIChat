---
id: operation-update-rollback
title: update_rollback
description: Restore the version kept before the last update.
section: Reference
order: 200
parent: operations
revision: f312a6eef12a2d8c
---

Restore the version kept before the last update.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | No | See the operation parameters. `default="application"`, `enum=["application", "engine"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `restored` | `boolean` | Yes | See the operation parameters.  |
| `stream` | `string` | Yes | Stream restored.  |
| `version` | `string` | Yes | Version restored.  |
| `restartRequired` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_rollback
```
