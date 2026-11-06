---
id: operation-resident-status
title: resident_status
description: Quel modèle local est chargé, sur quel device, avec quelles adapters.
section: Référence
order: 200
parent: operations
sourceRevision: 7994c3e43e42a1fd
---

Quel modèle local est chargé, sur quel device, avec quelles adapters.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `resident` | `object` | Oui | État du serveur résident.  |
| `adapters` | `array` | Oui | Adapters signalés par le serveur en cours d'exécution.  |
| `properties` | `object` | Oui | Propriétés du serveur, lors du chargement.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation resident_status
```
