---
id: operation-update-settings
title: update_settings
description: Read or change the GitHub sources and the automatic check preference.
section: Reference
order: 200
parent: operations
revision: 4278824b3735ee19
---

Read or change the GitHub sources and the automatic check preference.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `application_repository` | `string` | No | owner/name of the application repository. Empty leaves it unchanged. `default=""` |
| `engine_repository` | `string` | No | owner/name of the engine repository. `default=""` |
| `automatic_check` | `string` | No | Turn the startup check on or off. `default=""`, `enum=["", "on", "off"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `settings` | `object` | Yes | The stored update settings.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_settings
```
