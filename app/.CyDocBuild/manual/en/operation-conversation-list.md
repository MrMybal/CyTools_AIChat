---
id: operation-conversation-list
title: conversation_list
description: Every stored conversation, most recent first.
section: Reference
order: 200
parent: operations
revision: 999e530b85935e6c
---

Every stored conversation, most recent first.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversations` | `array` | Yes | Conversation summaries.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_list
```
