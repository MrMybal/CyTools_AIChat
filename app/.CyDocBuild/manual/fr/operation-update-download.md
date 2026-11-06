---
id: operation-update-download
title: update_download
description: Soyez en attente d'une mise à jour sous runtime/updates et vérifiez-la là-bas. Rien n'est activé.
section: Référence
order: 200
parent: operations
sourceRevision: 110d0fc653047a3d
---

Soyez en attente d'une mise à jour sous runtime/updates et vérifiez-la là-bas. Rien n'est activé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Non | Voir les paramètres de l’opération. `default="application"`, `enum=["application", "engine"]` |
| `version` | `string` | Non | Étiquette de version exacte à mettre en place. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `staged` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `stream` | `string` | Oui | Flux mis en place.  |
| `version` | `string` | Oui | Version mise en place.  |
| `path` | `string` | Oui | Répertoire de mise en place.  |
| `report` | `object` | Oui | Détails de vérification.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_download
```
