---
id: operation-conversation-delete
title: conversation_delete
description: Move a conversation out of the active list. The document is kept as a timestamped backup.
section: Reference
order: 200
parent: operations
revision: d86bd9b9ee704bcb
---

Move a conversation out of the active list. The document is kept as a timestamped backup.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `string` | Yes | Conversation id.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Conversation id.  |
| `deleted` | `boolean` | Yes | See the operation parameters.  |
| `backup` | `string` | Yes | Where the document was moved.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_delete
```
