---
id: operation-voice-add
title: voice_add
description: Conserver un extrait sonore comme une voix à imiter. Ses mots sont trouvés par la reconnaissance vocale à moins que vous ne les fournissiez : F5-TTS en a besoin, XTTS-v2 non.
section: Référence
order: 200
parent: operations
sourceRevision: c3d9ab013883ca24
---

Conserver un extrait sonore comme une voix à imiter. Ses mots sont trouvés par la reconnaissance vocale à moins que vous ne les fournissiez : F5-TTS en a besoin, XTTS-v2 non.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `audio` | `string` | Oui | Fichier audio : un chemin absolu n'importe où sur cette machine, ou un nom dans data/inputs. WAV, FLAC, OGG ou MP3. Il est copié pour la tâche et l'original est laissé tel quel.  |
| `name` | `string` | Non | Nom affiché dans la liste des voix. `default=""` |
| `language` | `string` | Non | Langue parlée dans l'extrait sonore, comme fr ou en. `default=""` |
| `transcript` | `string` | Non | Les paroles exactes prononcées dans la bande-son. `default=""` |
| `transcribe` | `boolean` | Non | Trouvez les mots par reconnaissance vocale lorsque aucun ne sont fournis. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voice` | `object` | Oui | id, nom, type (enregistré, échantillon, studio), langue, transcription, bande-son, familles.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation voice_add
```
