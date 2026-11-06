---
id: operation-conversation-create
title: conversation_create
description: Démarrez une conversation vide et renvoyez son id.
section: Référence
order: 200
parent: operations
sourceRevision: 5e9fb46fd68eddfe
---

Démarrez une conversation vide et renvoyez son id.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `title` | `string` | Non | Titre. Vide dérive un de la première message. `default=""` |
| `provider` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "codex", "claude-code", "antigravity", "opencode", "codebuddy", "command-code", "devin", "openai", "openrouter", "openai-compatible", "anthropic", "ollama", "llamacpp"]` |
| `transport` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
| `model` | `string` | Non | Identifiant du modèle. `default=""` |
| `system_prompt` | `string` | Non | Prompt système. `default=""` |
| `preset` | `string` | Non | Id de la préconfiguration à partir de laquelle commencer. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `object` | Oui | Le document créé.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_create
```
