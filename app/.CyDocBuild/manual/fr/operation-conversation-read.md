---
id: operation-conversation-read
title: conversation_read
description: La transcription complète d'une conversation enregistrée.
section: Référence
order: 200
parent: operations
sourceRevision: 4d99b9767aeef3ca
---

La transcription complète d'une conversation enregistrée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `string` | Oui | Identifiant de la conversation.  |
| `limit` | `integer` | Non | Renvoyez uniquement les dernières N messages. 0 renvoie tous les messages. `default=0`, `minimum=0`, `maximum=10000` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `object` | Oui | Le document stocké.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_read
```
