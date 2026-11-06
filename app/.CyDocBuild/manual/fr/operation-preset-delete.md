---
id: operation-preset-delete
title: preset_delete
description: Supprimer une prédéfinie que vous avez enregistrée.
section: Référence
order: 200
parent: operations
sourceRevision: 8f8832a76eb6a472
---

Supprimer une prédéfinie que vous avez enregistrée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant de la prédéfinie.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant de la prédéfinie.  |
| `deleted` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preset_delete
```
