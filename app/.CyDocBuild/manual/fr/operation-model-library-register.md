---
id: operation-model-library-register
title: model_library_register
description: Enregistre par référence un modèle local compatible ou un LoRA existant, sans télécharger ni copier les poids. Cet enregistrement est partagé par les clients de ce Tool local.
section: Référence
order: 200
parent: operations
sourceRevision: f4fd31f843abc81d
---

Enregistre par référence un modèle local compatible ou un LoRA existant, sans télécharger ni copier les poids. Cet enregistrement est partagé par les clients de ce Tool local.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `name` | `string` | Oui | Nom affiché  |
| `path` | `string` | Oui | Chemin local absolu accessible sur l’hôte du Tool  |
| `format` | `string` | Oui | Format ID from model_library_list  |
| `base` | `string` | Non | Compatible variante base ID  |
| `license` | `string` | Non | Identifiant de licence ou conditions  |
| `source` | `string` | Non | Source originale URL ou dépôt  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `object` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_library_register
```
