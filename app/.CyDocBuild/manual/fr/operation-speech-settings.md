---
id: operation-speech-settings
title: speech_settings
description: Lisez ou modifiez les préférences de la parole. Un champ laissé vide conserve sa valeur.
section: Référence
order: 200
parent: operations
sourceRevision: afcc70a46cdecee1
---

Lisez ou modifiez les préférences de la parole. Un champ laissé vide conserve sa valeur.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stt_model` | `string` | Non | Identifiant du modèle de transcription vocale. Vide sélectionne le meilleur installé.  |
| `tts_model` | `string` | Non | Identifiant du modèle de voix. Vide sélectionne un installé qui parle la langue.  |
| `voice` | `string` | Non | Identifiant du personnage (voice_list). Vide sélectionne un par défaut pour le modèle.  |
| `language` | `string` | Non | auto, ou un code tel que fr ou en.  |
| `speed` | `number` | Non | Voir les paramètres de l’opération. `minimum=0.5`, `maximum=2.0` |
| `tts_device` | `string` | Non | Voir les paramètres de l’opération. `enum=["auto", "cuda", "cpu"]` |
| `auto_read` | `boolean` | Non | Lisez les nouvelles réponses vocales à haute voix dans la fenêtre.  |
| `live_dictation` | `boolean` | Non | Affichez les mots dans la fenêtre pendant que vous parlez.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `settings` | `object` | Oui | Les paramètres stockés.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_settings
```
