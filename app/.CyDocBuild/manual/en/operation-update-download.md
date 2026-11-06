---
id: operation-update-download
title: update_download
description: Stage an update under runtime/updates and verify it there. Nothing is activated.
section: Reference
order: 200
parent: operations
revision: 110d0fc653047a3d
---

Stage an update under runtime/updates and verify it there. Nothing is activated.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | No | See the operation parameters. `default="application"`, `enum=["application", "engine"]` |
| `version` | `string` | No | Exact release tag to stage. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `staged` | `boolean` | Yes | See the operation parameters.  |
| `stream` | `string` | Yes | Stream staged.  |
| `version` | `string` | Yes | Version staged.  |
| `path` | `string` | Yes | Staging directory.  |
| `report` | `object` | Yes | Verification details.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_download
```
