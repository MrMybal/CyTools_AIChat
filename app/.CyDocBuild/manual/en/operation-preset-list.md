---
id: operation-preset-list
title: preset_list
description: Presets shipped with the application and those you saved.
section: Reference
order: 200
parent: operations
revision: 0b8959bd2762347c
---

Presets shipped with the application and those you saved.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `presets` | `array` | Yes | Preset documents.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preset_list
```
