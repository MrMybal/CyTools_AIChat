---
id: operation-model-uninstall
title: model_uninstall
description: Supprimer les fichiers d'une entrée du catalogue.
section: Référence
order: 200
parent: operations
sourceRevision: 091bef0c40381f1b
---

Supprimer les fichiers d'une entrée du catalogue.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Identifiant d'entrée du catalogue.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant d'entrée.  |
| `removedFiles` | `array` | Oui | Voir les paramètres de l’opération.  |
| `installed` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `libraryReferencesRemoved` | `integer` | Oui | Les références de la bibliothèque de modèles ont été supprimées avec les fichiers.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_uninstall
```
