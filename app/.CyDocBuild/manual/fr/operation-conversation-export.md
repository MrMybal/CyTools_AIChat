---
id: operation-conversation-export
title: conversation_export
description: Écrivez une conversation dans un fichier.
section: Référence
order: 200
parent: operations
sourceRevision: bd9f4a7649ace939
---

Écrivez une conversation dans un fichier.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversation` | `string` | Oui | Identifiant de la conversation.  |
| `format` | `string` | Non | Voir les paramètres de l’opération. `default="markdown"`, `enum=["markdown", "json"]` |
| `destination` | `string` | Non | Chemin absolu pour écrire. Un enregistrement vide s'écrit dans data/exports. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | Le fichier écrit.  |
| `format` | `string` | Oui | Format écrit.  |
| `mimeType` | `string` | Oui | MIME type.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation conversation_export
```
