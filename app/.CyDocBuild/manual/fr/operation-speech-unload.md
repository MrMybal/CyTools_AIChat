---
id: operation-speech-unload
title: speech_unload
description: Arrêtez les deux travailleurs de reconnaissance vocale et libérez la mémoire qu'ils utilisent.
section: Référence
order: 200
parent: operations
sourceRevision: 2dcedcb9a52a32e2
---

Arrêtez les deux travailleurs de reconnaissance vocale et libérez la mémoire qu'ils utilisent.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stopped` | `object` | Oui | Quels travailleurs étaient en cours d'exécution.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_unload
```
