---
id: operation-preset-save
title: preset_save
description: Créez ou remplacez une préférence. Les secrets ne font jamais partie d'une préférence.
section: Référence
order: 200
parent: operations
sourceRevision: f5e047dc871735ba
---

Créez ou remplacez une préférence. Les secrets ne font jamais partie d'une préférence.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Non | Identifiant de la préférence. Vider crée un nouveau. `default=""` |
| `name` | `string` | Oui | Nom d'affichage.  |
| `description` | `string` | Non | Ce que cette préférence est utilisée pour. `default=""` |
| `system_prompt` | `string` | Non | Prompt système. `default=""` |
| `settings` | `object` | Non | Valeurs de prélèvement : context_tokens, history_limit, max_tokens, repeat_penalty, seed, temperature, top_k, top_p `default={}` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `preset` | `object` | Oui | La prédéfinie enregistrée.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preset_save
```
