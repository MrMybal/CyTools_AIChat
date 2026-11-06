---
id: operation-preset-save
title: preset_save
description: Create or replace a preset. Secrets are never part of a preset.
section: Reference
order: 200
parent: operations
revision: f5e047dc871735ba
---

Create or replace a preset. Secrets are never part of a preset.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | No | Preset id. Empty mints one. `default=""` |
| `name` | `string` | Yes | Display name.  |
| `description` | `string` | No | What this preset is for. `default=""` |
| `system_prompt` | `string` | No | System prompt. `default=""` |
| `settings` | `object` | No | Sampling values: context_tokens, history_limit, max_tokens, repeat_penalty, seed, temperature, top_k, top_p `default={}` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `preset` | `object` | Yes | The stored preset.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preset_save
```
