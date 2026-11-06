---
id: operation-engine-install
title: engine_install
description: Download, verify and unpack a pinned llama.cpp build into runtime/engines.
section: Reference
order: 200
parent: operations
revision: 35c62d6e4740c5e8
---

Download, verify and unpack a pinned llama.cpp build into runtime/engines.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `build` | `string` | No | See the operation parameters. `default="cpu"`, `enum=["cpu", "cuda"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Build id.  |
| `name` | `string` | Yes | Build name.  |
| `installed` | `boolean` | Yes | See the operation parameters.  |
| `path` | `string` | Yes | Server executable.  |
| `version` | `string` | Yes | Release tag.  |
| `release` | `string` | Yes | Pinned release.  |
| `device` | `string` | Yes | cpu or cuda.  |
| `platform` | `string` | Yes | Target platform.  |
| `sizeBytes` | `integer` | Yes | See the operation parameters.  |
| `license` | `string` | Yes | Licence.  |
| `source` | `string` | Yes | Release page.  |
| `devices` | `string` | Yes | Device probe output, for CUDA.  |
| `requires` | `string` | Yes | What this build needs.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`, `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation engine_install
```
