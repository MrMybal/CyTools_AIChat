---
id: operation-update-check
title: update_check
description: Demandez aux sources GitHub configurées ce que l'application et l'engine pourraient déplacer.
section: Référence
order: 200
parent: operations
sourceRevision: f0457d93a4695a01
---

Demandez aux sources GitHub configurées ce que l'application et l'engine pourraient déplacer.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Non | Voir les paramètres de l’opération. `default="all"`, `enum=["application", "engine", "all"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `streams` | `array` | Oui | Une entrée par flux de mises à jour.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_check
```
