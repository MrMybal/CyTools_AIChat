---
id: operation-voice-delete
title: voice_delete
description: Déplacez un enregistrement ou une voix importée vers data/voices/deleted.
section: Référence
order: 200
parent: operations
sourceRevision: 2aec03dd0b71f880
---

Déplacez un enregistrement ou une voix importée vers data/voices/deleted.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voice` | `string` | Oui | Identifiant de la voix.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voice` | `string` | Oui | Identifiant de la voix.  |
| `deleted` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `keptIn` | `string` | Oui | Où la voix a été déplacée.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation voice_delete
```
