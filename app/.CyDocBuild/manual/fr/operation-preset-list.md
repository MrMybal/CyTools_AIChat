---
id: operation-preset-list
title: preset_list
description: Préférences fournis avec l'application et ceux que vous avez enregistrés.
section: Référence
order: 200
parent: operations
sourceRevision: 0b8959bd2762347c
---

Préférences fournis avec l'application et ceux que vous avez enregistrés.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `presets` | `array` | Oui | Documents de préférences.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preset_list
```
