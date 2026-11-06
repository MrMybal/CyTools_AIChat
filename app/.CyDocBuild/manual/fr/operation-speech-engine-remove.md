---
id: operation-speech-engine-remove
title: speech_engine_remove
description: Supprimez runtime/engines/stt ou runtime/engines/tts. Les modèles et voix restent.
section: Référence
order: 200
parent: operations
sourceRevision: 45b20c6d9c9768dd
---

Supprimez runtime/engines/stt ou runtime/engines/tts. Les modèles et voix restent.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Oui | Voir les paramètres de l’opération. `enum=["stt", "tts"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Oui | Environnement.  |
| `removed` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_engine_remove
```
