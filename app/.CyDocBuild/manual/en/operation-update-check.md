---
id: operation-update-check
title: update_check
description: Ask the configured GitHub sources what the application and the engine could move to.
section: Reference
order: 200
parent: operations
revision: f0457d93a4695a01
---

Ask the configured GitHub sources what the application and the engine could move to.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | No | See the operation parameters. `default="all"`, `enum=["application", "engine", "all"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `streams` | `array` | Yes | One entry per update stream.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_check
```
