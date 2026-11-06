---
id: operation-speech-engine-install
title: speech_engine_install
description: Créez ou réparez un environnement privé Python pour le traitement vocal sous runtime/engines : stt (PyTorch CPU et transformers 5, pour Phonon-2 et Parakeet) ou tts (PyTorch CUDA 12.8 ou CPU, XTTS-v2 et F5-TTS). Télécharge…
section: Référence
order: 200
parent: operations
sourceRevision: c30b1bc6a48a0b79
---

Créez ou réparez un environnement privé Python pour le traitement vocal sous runtime/engines : stt (PyTorch CPU et transformers 5, pour Phonon-2 et Parakeet) ou tts (PyTorch CUDA 12.8 ou CPU, XTTS-v2 et F5-TTS). Télécharge plusieurs gigabytes depuis PyPI et l'index PyTorch. Les modèles de traitement vocal et les voix dans data/ ne sont pas modifiés.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Oui | Voir les paramètres de l’opération. `enum=["stt", "tts"]` |
| `device` | `string` | Non | Construisez le PyTorch pour l'environnement tts. stt utilise toujours le CPU. `default="cuda"`, `enum=["cuda", "cpu"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Oui | Environnement.  |
| `label` | `string` | Oui | Description.  |
| `directory` | `string` | Oui | Dossier.  |
| `installed` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `families` | `array` | Oui | Voir les paramètres de l’opération.  |
| `estimatedBytes` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `cuda` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `cpuOnly` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `device` | `string` | Oui | Dispositif trouvé.  |
| `torch` | `string` | Oui | PyTorch version.  |
| `installedAt` | `string` | Oui | Date.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`, `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speech_engine_install
```
