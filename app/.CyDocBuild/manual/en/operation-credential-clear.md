---
id: operation-credential-clear
title: credential_clear
description: Delete a stored key.
section: Reference
order: 200
parent: operations
revision: 6e4b7ab3b6d9e9f9
---

Delete a stored key.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `provider` | `string` | Yes | Provider id.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `providerId` | `string` | Yes | Provider id.  |
| `removed` | `boolean` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation credential_clear
```
