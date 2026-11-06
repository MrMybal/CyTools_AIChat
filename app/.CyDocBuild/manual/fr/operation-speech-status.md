---
id: operation-speech-status
title: speech_status
description: Les deux environnements de parole, les modèles de parole avec leur état d'installation, les travailleurs de parole en cours d'exécution et les paramètres de parole.
section: Référence
order: 200
parent: operations
sourceRevision: 9018a9f150fcc0c4
---

Les deux environnements de parole, les modèles de parole avec leur état d'installation, les travailleurs de parole en cours d'exécution et les paramètres de parole.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engines` | `object` | Oui | Les environnements stt et tts.  |
| `models` | `array` | Oui | Lignes du catalogue de parole (types stt et tts).  |
| `workers` | `object` | Oui | Travailleurs de parole en cours d'exécution.  |
| `settings` | `object` | Oui | Paramètres de parole.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_status
```
