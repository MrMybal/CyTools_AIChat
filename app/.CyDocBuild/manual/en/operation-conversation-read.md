---
id: operation-conversation-read
title: conversation_read
description: The full stored transcript of one conversation.
section: Reference
order: 200
parent: operations
revision: 4d99b9767aeef3ca
---

The full stored transcript of one conversation.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `string` | Yes | Conversation id.  |
| `limit` | `integer` | No | Return only the last N messages. 0 returns all of them. `default=0`, `minimum=0`, `maximum=10000` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `object` | Yes | The stored document.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_read
```
