---
id: operation-model-list
title: model_list
description: Catalogue of downloadable GGUF models, LoRA adapters and speech models with their installation state.
section: Reference
order: 200
parent: operations
revision: 5189171a2245a610
---

Catalogue of downloadable GGUF models, LoRA adapters and speech models with their installation state.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | No | model and lora are chat weights; stt and tts are speech models. `default=""`, `enum=["", "model", "lora", "stt", "tts"]` |
| `verify` | `boolean` | No | Re-hash installed files. Slow on large weights. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `models` | `array` | Yes | Catalogue rows.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_list
```
