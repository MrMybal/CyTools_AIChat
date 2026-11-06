---
id: operation-update-rollback
title: update_rollback
description: Restaurer la version conservée avant la dernière mise à jour.
section: Référence
order: 200
parent: operations
sourceRevision: f312a6eef12a2d8c
---

Restaurer la version conservée avant la dernière mise à jour.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Non | Voir les paramètres de l’opération. `default="application"`, `enum=["application", "engine"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `restored` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `stream` | `string` | Oui | Flux restauré.  |
| `version` | `string` | Oui | Version restaurée.  |
| `restartRequired` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_rollback
```
