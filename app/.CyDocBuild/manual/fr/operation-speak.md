---
id: operation-speak
title: speak
description: Texte à lire avec XTTS-v2 ou F5-TTS. Donnez un texte, ou une conversation et l'un de ses messages pour lire une réponse enregistrée. L'audio d'une réponse enregistrée est conservé dans data/speech et réutilisé lorsque la même…
section: Référence
order: 200
parent: operations
sourceRevision: 696a63a62c4f59f9
---

Texte à lire avec XTTS-v2 ou F5-TTS. Donnez un texte, ou une conversation et l'un de ses messages pour lire une réponse enregistrée. L'audio d'une réponse enregistrée est conservé dans data/speech et réutilisé lorsque la même réponse est lue à nouveau avec la même voix.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `text` | `string` | Non | Texte à lire. Ignoré lorsque conversation et message sont donnés. `default=""` |
| `conversation` | `string` | Non | Identifiant de la conversation, pour lire l'un de ses messages. `default=""` |
| `message` | `string` | Non | Identifiant du message dans cette conversation. `default=""` |
| `model` | `string` | Non | Identifiant du modèle de voix. Vider utilise les paramètres. `default=""` |
| `voice` | `string` | Non | Identifiant du personnage depuis voice_list. Vider utilise les paramètres, puis un par défaut. `default=""` |
| `language` | `string` | Non | auto, ou un code tel que fr ou en. Vider utilise les paramètres. `default=""` |
| `speed` | `number` | Non | Vitesse de parole. Vider utilise les paramètres. `minimum=0.5`, `maximum=2.0` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "auto", "cuda", "cpu"]` |
| `progressive` | `boolean` | Non | Publier un événement SpeechPiece avec un fichier WAV pour chaque phrase dès qu'elle est créée, afin que le lecture puisse commencer avant que tout le texte ne soit prêt. Les morceaux sont écrits dans data/speech/pieces ; qui les joue les supprime. Annuler s'arrête après la phrase actuelle. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `audio` | `string` | Oui | Fichier WAV (16-bit PCM).  |
| `durationSeconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `model` | `string` | Oui | Modèle utilisé.  |
| `voice` | `string` | Oui | Identifiant du personnage utilisé.  |
| `voiceName` | `string` | Oui | Nom de la voix.  |
| `language` | `string` | Oui | Langue parlée.  |
| `cached` | `boolean` | Oui | Réutilisé depuis une lecture précédente.  |
| `seconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `device` | `string` | Oui | cuda ou cpu.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak
```
