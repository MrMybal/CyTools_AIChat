---
id: operation-conversation-reset-session
title: conversation_reset_session
description: Supprimez la session côté fournisseur afin que le prochain tour commence par un nouveau. Le transcript enregistré est conservé.
section: Référence
order: 200
parent: operations
sourceRevision: 1d13473cca89a2d0
---

Supprimez la session côté fournisseur afin que le prochain tour commence par un nouveau. Le transcript enregistré est conservé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `string` | Oui | Identifiant de la conversation.  |
| `provider` | `string` | Non | Limit to one fournisseur. Vider oublie toutes les sessions de la conversation. `default=""` |
| `transport` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `object` | Oui | Le document mis à jour.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_reset_session
```
