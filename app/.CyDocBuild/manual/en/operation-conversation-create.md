---
id: operation-conversation-create
title: conversation_create
description: Start an empty conversation and return its id.
section: Reference
order: 200
parent: operations
revision: 5e9fb46fd68eddfe
---

Start an empty conversation and return its id.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `title` | `string` | No | Title. Empty derives one from the first message. `default=""` |
| `provider` | `string` | No | See the operation parameters. `default=""`, `enum=["", "codex", "claude-code", "antigravity", "opencode", "codebuddy", "command-code", "devin", "openai", "openrouter", "openai-compatible", "anthropic", "ollama", "llamacpp"]` |
| `transport` | `string` | No | See the operation parameters. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
| `model` | `string` | No | Model identifier. `default=""` |
| `system_prompt` | `string` | No | System prompt. `default=""` |
| `preset` | `string` | No | Preset id to start from. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversation` | `object` | Yes | The created document.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_create
```
