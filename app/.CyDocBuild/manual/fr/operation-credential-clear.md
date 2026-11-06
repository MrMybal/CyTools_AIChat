---
id: operation-credential-clear
title: credential_clear
description: Supprimer une clé stockée.
section: Référence
order: 200
parent: operations
sourceRevision: 6e4b7ab3b6d9e9f9
---

Supprimer une clé stockée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `provider` | `string` | Oui | Identifiant du fournisseur.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `providerId` | `string` | Oui | Identifiant du fournisseur.  |
| `removed` | `boolean` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation credential_clear
```
