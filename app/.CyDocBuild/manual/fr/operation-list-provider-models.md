---
id: operation-list-provider-models
title: list_provider_models
description: Demandez à un fournisseur les modèles qu'il propose. Pas tous les fournisseurs publient un catalogue.
section: Référence
order: 200
parent: operations
sourceRevision: d13f9970640228bf
---

Demandez à un fournisseur les modèles qu'il propose. Pas tous les fournisseurs publient un catalogue.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `provider` | `string` | Oui | Identifiant du fournisseur.  |
| `transport` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `models` | `array` | Oui | Lignes de modèles.  |
| `providerId` | `string` | Oui | Fournisseur interrogé.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`, `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_provider_models
```
