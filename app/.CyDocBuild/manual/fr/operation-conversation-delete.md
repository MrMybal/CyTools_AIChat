---
id: operation-conversation-delete
title: conversation_delete
description: Déplacez une conversation hors de la liste active. Le document est conservé en tant que sauvegarde temporelle.
section: Référence
order: 200
parent: operations
sourceRevision: d86bd9b9ee704bcb
---

Déplacez une conversation hors de la liste active. Le document est conservé en tant que sauvegarde temporelle.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `string` | Oui | Identifiant de la conversation.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant de la conversation.  |
| `deleted` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `backup` | `string` | Oui | Où le document a été déplacé.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_delete
```
