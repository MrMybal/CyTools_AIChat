---
id: operation-credential-status
title: credential_status
description: Whether a key is configured for a provider and how it is protected. Never returns the key.
section: Reference
order: 200
parent: operations
revision: 285d06aa18c34157
---

Whether a key is configured for a provider and how it is protected. Never returns the key.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `provider` | `string` | No | Provider id. Empty reports every provider that can take a key. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `credentials` | `array` | Yes | One status per provider.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation credential_status
```
