---
id: operation-model-list
title: model_list
description: Catalogue des modèles GGUF téléchargeables, adaptateurs LoRA et modèles de parole avec leur état d'installation.
section: Référence
order: 200
parent: operations
sourceRevision: 5189171a2245a610
---

Catalogue des modèles GGUF téléchargeables, adaptateurs LoRA et modèles de parole avec leur état d'installation.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `kind` | `string` | Non | model et lora sont des poids de conversation ; stt et tts sont des modèles de parole. `default=""`, `enum=["", "model", "lora", "stt", "tts"]` |
| `verify` | `boolean` | Non | Re-hacher les fichiers installés. Lent sur de gros poids. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `models` | `array` | Oui | Lignes du catalogue.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_list
```
