---
id: operation-model-library-list
title: model_library_list
description: Liste les formats de modèles compatibles, les capacités des périphériques et les références locales de modèles et de LoRA enregistrées.
section: Référence
order: 200
parent: operations
sourceRevision: 1212a32cee646962
---

Liste les formats de modèles compatibles, les capacités des périphériques et les références locales de modèles et de LoRA enregistrées.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `capabilities` | `object` | Oui | Voir les paramètres de l’opération.  |
| `library` | `object` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_library_list
```
