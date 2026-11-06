---
id: operation-resident-unload
title: resident_unload
description: Arrêtez le serveur local llama.cpp et libérez sa réservation.
section: Référence
order: 200
parent: operations
sourceRevision: 357f026d4cc28315
---

Arrêtez le serveur local llama.cpp et libérez sa réservation.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stopped` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `resident` | `object` | Oui | État après l'arrêt.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation resident_unload
```
