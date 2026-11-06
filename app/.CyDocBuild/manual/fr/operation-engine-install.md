---
id: operation-engine-install
title: engine_install
description: Télécharger, vérifier et décompresser un build de llama.cpp enregistré dans runtime/engines.
section: Référence
order: 200
parent: operations
sourceRevision: 35c62d6e4740c5e8
---

Télécharger, vérifier et décompresser un build de llama.cpp enregistré dans runtime/engines.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `build` | `string` | Non | Voir les paramètres de l’opération. `default="cpu"`, `enum=["cpu", "cuda"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Oui | Identifiant de build.  |
| `name` | `string` | Oui | Nom de la build.  |
| `installed` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `path` | `string` | Oui | Exécutable du serveur.  |
| `version` | `string` | Oui | Balise de release.  |
| `release` | `string` | Oui | Release pinnée.  |
| `device` | `string` | Oui | cpu ou cuda.  |
| `platform` | `string` | Oui | Plateforme cible.  |
| `sizeBytes` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `license` | `string` | Oui | Licence.  |
| `source` | `string` | Oui | Page de release.  |
| `devices` | `string` | Oui | Sortie de la recherche de périphérique, pour CUDA.  |
| `requires` | `string` | Oui | Ce dont a besoin cette construction.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`, `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation engine_install
```
