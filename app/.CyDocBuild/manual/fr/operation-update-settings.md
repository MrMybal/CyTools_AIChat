---
id: operation-update-settings
title: update_settings
description: Lire ou modifier les sources GitHub et la préférence de vérification automatique.
section: Référence
order: 200
parent: operations
sourceRevision: 4278824b3735ee19
---

Lire ou modifier les sources GitHub et la préférence de vérification automatique.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `application_repository` | `string` | Non | owner/name du dépôt de l’application. Une valeur vide conserve le réglage actuel. `default=""` |
| `engine_repository` | `string` | Non | owner/name du dépôt du moteur. `default=""` |
| `automatic_check` | `string` | Non | Active ou désactive la vérification au démarrage. `default=""`, `enum=["", "on", "off"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `settings` | `object` | Oui | Les réglages de mise à jour enregistrés.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_settings
```
