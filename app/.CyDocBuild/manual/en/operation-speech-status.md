---
id: operation-speech-status
title: speech_status
description: The two speech environments, the speech models with their installation state, the running speech workers and the speech settings.
section: Reference
order: 200
parent: operations
revision: 9018a9f150fcc0c4
---

The two speech environments, the speech models with their installation state, the running speech workers and the speech settings.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `engines` | `object` | Yes | stt and tts environments.  |
| `models` | `array` | Yes | Speech catalogue rows (kinds stt and tts).  |
| `workers` | `object` | Yes | Running speech workers.  |
| `settings` | `object` | Yes | Speech settings.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_status
```
