---
id: operation-model-install
title: model_install
description: Télécharger et vérifier une entrée du catalogue. Reprend une télécharge interrompu.
section: Référence
order: 200
parent: operations
sourceRevision: 690ea08e3a086285
---

Télécharger et vérifier une entrée du catalogue. Reprend une télécharge interrompu.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Identifiant d'entrée du catalogue.  |
| `accept_license` | `boolean` | Non | Confirme que vous avez accepté la licence sur la page du fournisseur vous-même. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant d'entrée.  |
| `installed` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `sizeBytes` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `presentBytes` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `kind` | `string` | Oui | modèle ou lora  |
| `name` | `string` | Oui | Nom d'affichage.  |
| `license` | `string` | Oui | Licence déclarée.  |
| `source` | `string` | Oui | Page du modèle.  |
| `repository` | `string` | Oui | Dépôt.  |
| `revision` | `string` | Oui | Révision pinnée.  |
| `gated` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `licenseAccepted` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `baseModel` | `string` | Oui | Identifiant du modèle de base, pour un adaptateur.  |
| `architecture` | `string` | Oui | Architecture déclarée.  |
| `contextTokens` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `ramGiB` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `vramGiB` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `notes` | `string` | Oui | Notes.  |
| `path` | `string` | Oui | Chemin du fichier installé; le dossier, pour un modèle de parole.  |
| `languages` | `array` | Non | Langues d'un modèle de parole.  |
| `family` | `string` | Non | Famille d'engine d'un modèle de parole.  |
| `component` | `boolean` | Non | Installé pour un autre modèle, pas choisi directement.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation model_install
```
