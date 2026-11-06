---
id: operation-conversation-list
title: conversation_list
description: Toutes les conversations enregistrées, la plus récente en premier.
section: Référence
order: 200
parent: operations
sourceRevision: 999e530b85935e6c
---

Toutes les conversations enregistrées, la plus récente en premier.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversations` | `array` | Oui | Résumés de conversations.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_list
```
