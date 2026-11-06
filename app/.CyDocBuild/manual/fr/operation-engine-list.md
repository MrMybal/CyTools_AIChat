---
id: operation-engine-list
title: engine_list
description: Les builds de llama.cpp enregistrés et quel est celui qui est installé.
section: Référence
order: 200
parent: operations
sourceRevision: 6c38461e1d523e34
---

Les builds de llama.cpp enregistrés et quel est celui qui est installé.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `release` | `string` | Oui | Étiquette de la release enregistrée.  |
| `repository` | `string` | Oui | Répertoire source.  |
| `builds` | `array` | Oui | Voir les paramètres de l’opération.  |
| `notes` | `string` | Oui | Notes.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation engine_list
```
