---
id: operation-credential-status
title: credential_status
description: Quel est la configuration d'une clé pour un fournisseur et comment elle est protégée. Elle ne retourne jamais la clé.
section: Référence
order: 200
parent: operations
sourceRevision: 285d06aa18c34157
---

Quel est la configuration d'une clé pour un fournisseur et comment elle est protégée. Elle ne retourne jamais la clé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `provider` | `string` | Non | Identifiant du fournisseur. Rapporter vide indique tous les fournisseurs capables de prendre une clé. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `credentials` | `array` | Oui | Un statut par fournisseur.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation credential_status
```
