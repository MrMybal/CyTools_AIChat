---
id: operation-conversation-reset-session
title: conversation_reset_session
description: Drop the provider-side session so the next turn starts a fresh one. The stored transcript is kept.
section: Reference
order: 200
parent: operations
revision: 1d13473cca89a2d0
---

Drop the provider-side session so the next turn starts a fresh one. The stored transcript is kept.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `string` | Yes | Conversation id.  |
| `provider` | `string` | No | Limit to one provider. Empty forgets every session of the conversation. `default=""` |
| `transport` | `string` | No | See the operation parameters. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `object` | Yes | The updated document.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_reset_session
```
