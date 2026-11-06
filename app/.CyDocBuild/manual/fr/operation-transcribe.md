---
id: operation-transcribe
title: transcribe
description: Speech to text avec Phonon-2 (anglais) ou Parakeet TDT 0.6B v3 (25 langues, dont le français), sur le CPU. Le modèle reste chargé pour la prochaine requête.
section: Référence
order: 200
parent: operations
sourceRevision: f048e11415d9a6c7
---

Speech to text avec Phonon-2 (anglais) ou Parakeet TDT 0.6B v3 (25 langues, dont le français), sur le CPU. Le modèle reste chargé pour la prochaine requête.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `audio` | `string` | Oui | Fichier audio : un chemin absolu n'importe où sur cette machine, ou un nom dans data/inputs. WAV, FLAC, OGG ou MP3. Il est copié pour la tâche et l'original est laissé tel quel.  |
| `model` | `string` | Non | Identifiant du modèle de speech-to-text. Vide utilise les paramètres, puis le meilleur modèle installé pour la langue. `default=""` |
| `language` | `string` | Non | Langue attendue, utilisée uniquement pour choisir le modèle : en préfère Phonon-2. Les modèles détectent la langue eux-mêmes. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `text` | `string` | Oui | Ce qui a été dit.  |
| `model` | `string` | Oui | Modèle utilisé.  |
| `audioSeconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `loadSeconds` | `number` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation transcribe
```
