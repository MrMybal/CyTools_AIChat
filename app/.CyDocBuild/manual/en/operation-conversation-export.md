---
id: operation-conversation-export
title: conversation_export
description: Write a conversation to a file.
section: Reference
order: 200
parent: operations
revision: bd9f4a7649ace939
---

Write a conversation to a file.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `string` | Yes | Conversation id.  |
| `format` | `string` | No | See the operation parameters. `default="markdown"`, `enum=["markdown", "json"]` |
| `destination` | `string` | No | Absolute path to write to. Empty writes into data/exports. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | The written file.  |
| `format` | `string` | Yes | Format written.  |
| `mimeType` | `string` | Yes | MIME type.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_export
```
