---
id: operation-transcribe-live
title: transcribe_live
description: Suivez une enregistrement, la fenêtre du bureau écrit (data/inputs/dictation/live-<id>.pcm, 16-bit mono PCM) et publie des événements DictationPartial avec le texte jusqu'ici, environ tous les demi-secondes de nouveau…
section: Référence
order: 200
parent: operations
sourceRevision: 7f06a1d100eed3be
---

Suivez une enregistrement, la fenêtre du bureau écrit (data/inputs/dictation/live-<id>.pcm, 16-bit mono PCM) et publie des événements DictationPartial avec le texte jusqu'ici, environ tous les demi-secondes de nouveau discours. Les phrases sont fermées aux pauses et leurs mots deviennent définitifs ; la phrase qui est dite peut encore changer. La tâche se termine lorsque la fenêtre crée <name>.done et retourne le texte complet. Destiné à la fenêtre ; donnez un fichier à transcrire au lieu de cela.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Oui | Nom de l'enregistrement en direct dans data/inputs/dictation.  |
| `rate` | `integer` | Oui | Taux d'échantillonnage de l'enregistrement. `minimum=8000`, `maximum=192000` |
| `model` | `string` | Non | Identifiant du modèle de reconnaissance vocale. Vide utilise les paramètres par défaut. `default=""` |
| `language` | `string` | Non | Langue attendue, utilisée uniquement pour choisir le modèle. `default=""` |
| `max_seconds` | `number` | Non | Voir les paramètres de l’opération. `default=600`, `minimum=5`, `maximum=3600` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `text` | `string` | Oui | Tout ce qui a été dit.  |
| `model` | `string` | Oui | Modèle utilisé.  |
| `audioSeconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `passes` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `loadSeconds` | `number` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation transcribe_live
```
