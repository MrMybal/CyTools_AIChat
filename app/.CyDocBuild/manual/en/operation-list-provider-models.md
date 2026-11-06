---
id: operation-list-provider-models
title: list_provider_models
description: Ask a provider for the models it offers. Not every provider publishes a catalogue.
section: Reference
order: 200
parent: operations
revision: d13f9970640228bf
---

Ask a provider for the models it offers. Not every provider publishes a catalogue.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `provider` | `string` | Yes | Provider id.  |
| `transport` | `string` | No | See the operation parameters. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `models` | `array` | Yes | Model rows.  |
| `providerId` | `string` | Yes | Provider queried.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`, `processSpawn`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_provider_models
```
