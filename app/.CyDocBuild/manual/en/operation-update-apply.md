---
id: operation-update-apply
title: update_apply
description: Activate a verified staged update, keeping the previous version for a rollback. data/ is never replaced.
section: Reference
order: 200
parent: operations
revision: ba3656a35c821753
---

Activate a verified staged update, keeping the previous version for a rollback. data/ is never replaced.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | No | See the operation parameters. `default="application"`, `enum=["application", "engine"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `applied` | `boolean` | Yes | See the operation parameters.  |
| `stream` | `string` | Yes | Stream applied.  |
| `version` | `string` | Yes | Version now active.  |
| `backup` | `string` | Yes | Kept previous version.  |
| `restartRequired` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_apply
```
