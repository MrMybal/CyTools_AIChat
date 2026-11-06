---
id: operation-update-apply
title: update_apply
description: Activer une mise à jour validée en état, en conservant la version précédente pour un rollback. data/ ne est jamais remplacé.
section: Référence
order: 200
parent: operations
sourceRevision: ba3656a35c821753
---

Activer une mise à jour validée en état, en conservant la version précédente pour un rollback. data/ ne est jamais remplacé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Non | Voir les paramètres de l’opération. `default="application"`, `enum=["application", "engine"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `applied` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `stream` | `string` | Oui | Flux appliqué.  |
| `version` | `string` | Oui | Version maintenant active.  |
| `backup` | `string` | Oui | Version précédente conservée.  |
| `restartRequired` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_apply
```
