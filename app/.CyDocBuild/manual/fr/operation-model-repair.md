---
id: operation-model-repair
title: model_repair
description: Re-verify une entrée et supprimer uniquement les fichiers dont le digest ne correspond pas.
section: Référence
order: 200
parent: operations
sourceRevision: b41505ece1ee6c09
---

Re-verify une entrée et supprimer uniquement les fichiers dont le digest ne correspond pas.

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
| `repaired` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_repair
```
