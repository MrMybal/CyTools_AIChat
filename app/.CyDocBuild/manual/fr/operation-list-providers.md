---
id: operation-list-providers
title: list_providers
description: Inventaire chaque fournisseur avec ses transports et ce qui a été détecté sur cette machine.
section: Référence
order: 200
parent: operations
sourceRevision: da208cfc263f368b
---

Inventaire chaque fournisseur avec ses transports et ce qui a été détecté sur cette machine.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `provider` | `string` | Non | Limiter le rapport à un fournisseur. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `providers` | `array` | Oui | Un rapport par fournisseur.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`, `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_providers
```
