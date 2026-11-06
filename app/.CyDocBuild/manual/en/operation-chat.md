---
id: operation-chat
title: chat
description: Send one message and store the reply in a conversation.
section: Reference
order: 200
parent: operations
revision: 47de2068bbb2332c
---

Send one message and store the reply in a conversation.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `message` | `string` | Yes | The message to send.  |
| `conversation` | `string` | No | Conversation id to continue. Empty starts a new conversation and returns its id. `default=""` |
| `provider` | `string` | No | Provider to talk to. Empty reuses the one stored in the conversation. `default=""`, `enum=["", "codex", "claude-code", "antigravity", "opencode", "codebuddy", "command-code", "devin", "openai", "openrouter", "openai-compatible", "anthropic", "ollama", "llamacpp"]` |
| `transport` | `string` | No | Transport within the provider. Empty uses its default. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
| `model` | `string` | No | Model identifier for the provider. Empty reuses the conversation model. `default=""` |
| `system_prompt` | `string` | No | System prompt for this conversation. A session provider that has no system field receives it folded into the first message, and the reply reports that. `default=""` |
| `preset` | `string` | No | Preset id whose system prompt and sampling values fill anything not set explicitly. `default=""` |
| `engine` | `string` | No | llama.cpp build for the local provider. auto prefers an installed CUDA build. `default="auto"`, `enum=["auto", "cpu", "cuda"]` |
| `threads` | `integer` | No | CPU threads for the local provider. 0 lets llama.cpp decide. `default=0`, `minimum=0`, `maximum=256` |
| `keep_loaded` | `boolean` | No | Keep the local model resident after the reply so the next turn starts immediately. `default=true` |
| `reasoning_effort` | `string` | No | How much a reasoning model should think before answering. Empty uses the value the catalogue records for that model. "none" turns thinking off through the chat template; the other levels are passed to llama.cpp. Local provider only. `default=""`, `enum=["", "default", "none", "minimal", "low", "medium", "high", "xhigh", "max"]` |
| `settings` | `object` | No | Extra provider fields merged into the request, for options this schema does not name. `default={}` |
| `temperature` | `number` | No | Sampling temperature. Higher is more varied. Left unset, the provider default applies. `minimum=0`, `maximum=2` |
| `top_p` | `number` | No | Nucleus sampling threshold. `minimum=0`, `maximum=1` |
| `top_k` | `integer` | No | Keep only the K most likely tokens. Ignored by providers that do not expose it. `minimum=0`, `maximum=1000` |
| `max_tokens` | `integer` | No | Maximum tokens in the reply. `minimum=1`, `maximum=131072` |
| `repeat_penalty` | `number` | No | Penalty applied to repeated tokens. Local and Ollama providers only. `minimum=0`, `maximum=4` |
| `seed` | `integer` | No | Sampling seed. -1 leaves it to the provider. The same seed only reproduces a reply with the same weights and runtime. `minimum=-1`, `maximum=2147483647` |
| `context_tokens` | `integer` | No | Context window requested when loading a local model. Changing it restarts the local server. `minimum=512`, `maximum=1048576` |
| `history_limit` | `integer` | No | Send only the last N stored messages to a stateless provider. 0 sends the whole conversation. A session provider keeps its own history and ignores this. `minimum=0`, `maximum=1000` |
| `model_profile` | `string` | No | ID from the local model library; empty uses the selected built-in model. `default=""` |
| `loras` | `array` | No | See the operation parameters. `default=[]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `conversationId` | `string` | Yes | Conversation the reply was stored in.  |
| `messageId` | `string` | Yes | Identifier of the stored assistant message.  |
| `text` | `string` | Yes | The reply text.  |
| `providerId` | `string` | Yes | Provider that produced the reply.  |
| `transport` | `string` | Yes | Transport used.  |
| `model` | `string` | Yes | Model reported by the provider.  |
| `kind` | `string` | Yes | stateless when the transcript is the context, session when the provider keeps the history.  |
| `usage` | `object` | Yes | Token accounting as reported by the provider, when it reports any.  |
| `seconds` | `number` | Yes | Wall-clock duration of the turn.  |
| `nativeSessionId` | `string` | Yes | Provider-side session identifier, when the provider has one.  |
| `thinkingCharacters` | `integer` | Yes | Characters of reasoning text streamed but not stored in the reply.  |
| `file` | `string` | Yes | Markdown file holding the reply inside the job workspace.  |
| `mimeType` | `string` | Yes | MIME type of the reply file.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`, `processSpawn`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation chat
```
