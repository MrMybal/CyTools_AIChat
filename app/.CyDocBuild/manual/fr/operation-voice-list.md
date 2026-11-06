---
id: operation-voice-list
title: voice_list
description: Voix enregistrées et importées, les extraits sonores des modèles installés et les voix du studio XTTS-v2.
section: Référence
order: 200
parent: operations
sourceRevision: 09885639d92be69e
---

Voix enregistrées et importées, les extraits sonores des modèles installés et les voix du studio XTTS-v2.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voices` | `array` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation voice_list
```
