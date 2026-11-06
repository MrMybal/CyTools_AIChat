---
id: operation-engine-remove
title: engine_remove
description: Supprimer une construction installée par ce Outil.
section: Référence
order: 200
parent: operations
sourceRevision: ff012099a75dbe8d
---

Supprimer une construction installée par ce Outil.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `build` | `string` | Oui | Voir les paramètres de l’opération. `enum=["cpu", "cuda"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant de build.  |
| `removed` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation engine_remove
```
