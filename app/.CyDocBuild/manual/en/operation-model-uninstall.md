---
id: operation-model-uninstall
title: model_uninstall
description: Delete the files of a catalogue entry.
section: Reference
order: 200
parent: operations
revision: 091bef0c40381f1b
---

Delete the files of a catalogue entry.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Catalogue entry id.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Entry id.  |
| `removedFiles` | `array` | Yes | See the operation parameters.  |
| `installed` | `boolean` | Yes | See the operation parameters.  |
| `libraryReferencesRemoved` | `integer` | Yes | Model library references dropped with the files.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_uninstall
```
