---
id: operation-model-install
title: model_install
description: Download and verify a catalogue entry. Resumes an interrupted download.
section: Reference
order: 200
parent: operations
revision: 690ea08e3a086285
---

Download and verify a catalogue entry. Resumes an interrupted download.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Catalogue entry id.  |
| `accept_license` | `boolean` | No | Confirms you accepted the licence on the provider page yourself. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Entry id.  |
| `installed` | `boolean` | Yes | See the operation parameters.  |
| `sizeBytes` | `integer` | Yes | See the operation parameters.  |
| `presentBytes` | `integer` | Yes | See the operation parameters.  |
| `kind` | `string` | Yes | model or lora  |
| `name` | `string` | Yes | Display name.  |
| `license` | `string` | Yes | Declared licence.  |
| `source` | `string` | Yes | Model page.  |
| `repository` | `string` | Yes | Repository.  |
| `revision` | `string` | Yes | Pinned revision.  |
| `gated` | `boolean` | Yes | See the operation parameters.  |
| `licenseAccepted` | `boolean` | Yes | See the operation parameters.  |
| `baseModel` | `string` | Yes | Base model id, for an adapter.  |
| `architecture` | `string` | Yes | Declared architecture.  |
| `contextTokens` | `integer` | Yes | See the operation parameters.  |
| `ramGiB` | `integer` | Yes | See the operation parameters.  |
| `vramGiB` | `integer` | Yes | See the operation parameters.  |
| `notes` | `string` | Yes | Notes.  |
| `path` | `string` | Yes | Installed file path; the folder, for a speech model.  |
| `languages` | `array` | No | Languages of a speech model.  |
| `family` | `string` | No | Engine family of a speech model.  |
| `component` | `boolean` | No | Installed for another model, not chosen directly.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_install
```
