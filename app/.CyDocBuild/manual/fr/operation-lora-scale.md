---
id: operation-lora-scale
title: lora_scale
description: Définissez les forces LoRA sur le serveur local en cours d'exécution sans recharger le modèle.
section: Référence
order: 200
parent: operations
sourceRevision: 00ddb1afbc00fa58
---

Définissez les forces LoRA sur le serveur local en cours d'exécution sans recharger le modèle.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `loras` | `array` | Non | Forces dans l'ordre dans lequel les adapters ont été chargés. `default=[]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `adapters` | `array` | Oui | Adapters tels que le serveur les rapporte ultérieurement.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation lora_scale
```
