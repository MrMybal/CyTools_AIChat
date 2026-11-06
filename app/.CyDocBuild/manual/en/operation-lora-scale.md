---
id: operation-lora-scale
title: lora_scale
description: Set LoRA strengths on the running local server without reloading the model.
section: Reference
order: 200
parent: operations
revision: 00ddb1afbc00fa58
---

Set LoRA strengths on the running local server without reloading the model.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `loras` | `array` | No | Strengths in the order the adapters were loaded. `default=[]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `adapters` | `array` | Yes | Adapters as the server reports them afterwards.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation lora_scale
```
