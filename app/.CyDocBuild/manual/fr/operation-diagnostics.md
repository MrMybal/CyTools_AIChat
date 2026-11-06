---
id: operation-diagnostics
title: diagnostics
description: Un rapport couvrant les fournisseurs, les moteurs, les poids, l'archivage et le modèle résident.
section: Référence
order: 200
parent: operations
sourceRevision: e0d652a37e1c2a00
---

Un rapport couvrant les fournisseurs, les moteurs, les poids, l'archivage et le modèle résident.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `report` | `object` | Oui | Le rapport diagnostique.  |
| `file` | `string` | Oui | Fichier de rapport dans l'espace de travail du travail.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`, `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation diagnostics
```
