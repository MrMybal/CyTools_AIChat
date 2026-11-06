---
id: operation-list-providers
title: list_providers
description: Inventory every provider with its transports and what was actually detected on this machine.
section: Reference
order: 200
parent: operations
revision: da208cfc263f368b
---

Inventory every provider with its transports and what was actually detected on this machine.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `provider` | `string` | No | Limit the report to one provider. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `providers` | `array` | Yes | One report per provider.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`, `processSpawn`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_providers
```
