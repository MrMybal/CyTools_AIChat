---
id: operation-diagnostics
title: diagnostics
description: One report covering providers, engines, weights, storage and the resident model.
section: Reference
order: 200
parent: operations
revision: e0d652a37e1c2a00
---

One report covering providers, engines, weights, storage and the resident model.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `report` | `object` | Yes | The diagnostic report.  |
| `file` | `string` | Yes | Report file in the job workspace.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`, `processSpawn`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation diagnostics
```
