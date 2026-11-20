---
id: operations
title: Automatisation et API
description: Connectez un client et consultez les opérations disponibles.
section: Référence
order: 80
parent: overview
sourceRevision: 7dce99fc1ac236dc
---

## Ligne de commande {#cli}

Depuis la racine de l’application, utilisez son interpréteur Python privé. `describe` et `list-operations` examinent le contrat public.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py list-operations
runtime\python\Scripts\python.exe app\tool.py invoke list_providers --params "{}"
```

## MCP {#mcp}

Configurez votre client MCP pour lancer l’interpréteur privé avec `app/tool.py mcp`, en utilisant le dossier de l’application comme dossier de travail. Reconnectez-le lorsque le catalogue d’opérations exposées change.

## Fichiers des tâches {#task-files}

Les entrées locales acceptent des chemins absolus lisibles et sont importées automatiquement dans l’espace de la tâche. Exportez les résultats utiles avant de terminer la tâche. Ne réutilisez pas les chemins temporaires après nettoyage.

## Opérations {#operations}

- [`chat`](doc:operation-chat)
- [`list_providers`](doc:operation-list-providers)
- [`list_provider_models`](doc:operation-list-provider-models)
- [`conversation_list`](doc:operation-conversation-list)
- [`conversation_read`](doc:operation-conversation-read)
- [`conversation_create`](doc:operation-conversation-create)
- [`conversation_delete`](doc:operation-conversation-delete)
- [`conversation_export`](doc:operation-conversation-export)
- [`conversation_reset_session`](doc:operation-conversation-reset-session)
- [`preset_list`](doc:operation-preset-list)
- [`preset_save`](doc:operation-preset-save)
- [`preset_delete`](doc:operation-preset-delete)
- [`model_list`](doc:operation-model-list)
- [`model_install`](doc:operation-model-install)
- [`model_repair`](doc:operation-model-repair)
- [`model_uninstall`](doc:operation-model-uninstall)
- [`engine_list`](doc:operation-engine-list)
- [`engine_install`](doc:operation-engine-install)
- [`engine_remove`](doc:operation-engine-remove)
- [`speech_status`](doc:operation-speech-status)
- [`speech_engine_install`](doc:operation-speech-engine-install)
- [`speech_engine_remove`](doc:operation-speech-engine-remove)
- [`speech_settings`](doc:operation-speech-settings)
- [`transcribe`](doc:operation-transcribe)
- [`transcribe_live`](doc:operation-transcribe-live)
- [`speak`](doc:operation-speak)
- [`voice_list`](doc:operation-voice-list)
- [`voice_add`](doc:operation-voice-add)
- [`voice_delete`](doc:operation-voice-delete)
- [`speech_unload`](doc:operation-speech-unload)
- [`resident_status`](doc:operation-resident-status)
- [`resident_unload`](doc:operation-resident-unload)
- [`lora_scale`](doc:operation-lora-scale)
- [`credential_status`](doc:operation-credential-status)
- [`credential_clear`](doc:operation-credential-clear)
- [`diagnostics`](doc:operation-diagnostics)
- [`update_check`](doc:operation-update-check)
- [`update_download`](doc:operation-update-download)
- [`update_apply`](doc:operation-update-apply)
- [`update_rollback`](doc:operation-update-rollback)
- [`update_settings`](doc:operation-update-settings)
- [`model_library_list`](doc:operation-model-library-list)
- [`model_library_register`](doc:operation-model-library-register)


## Communication native {#native-communication}

Le paquet Windows contient CyToolsCore 0.12.0 et la bibliothèque de communication
native CyMCPSDK 0.7.1. Les mêmes paramètres complets des opérations sont disponibles
pour les clients IA et l’application autonome. Lancez `ai_communication_status` avec
`includeOperations: true` pour consulter le catalogue effectif. Cette opération ne
contacte aucun fournisseur IA et ne génère pas de contenu.

Les fichiers générés par la CLI sont temporaires par défaut. Ajoutez `--export-dir`
suivi d’un dossier absolu hors du stockage des jobs pour les conserver. Par MCP,
exportez avec `cy_export_job` avant `cy_finish_task`. Le nettoyage des tâches ne
supprime pas les entrées originales, modèles installés, conversations et documents
de projet persistants.

Pour la première migration depuis Core 0.10.x, installez le paquet Windows complet.
Une mise à jour de l’application seule ne peut pas ajouter la bibliothèque native
au précédent runtime. Les intégrations de modèles et de fournisseurs conservent
leurs compatibilités et permissions : cette mise à jour ne rend pas compatible un
modèle ou une plateforme non pris en charge.


## Accès MCP local {#local-mcp-access}

Core **0.12.0** embarque CyMCPSDK natif au commit **`34d4bca`**. Depuis la racine du
Tool, démarrez explicitement le service local :

```powershell
runtime/python/Scripts/python.exe app/tool.py --data-dir data/jobs serve --port 8766
```

Free est le profil initial : connectez-vous avec seulement `http://127.0.0.1:8766/mcp`.
Toutes les opérations exposées sont accessibles sans jeton ni confirmation de transport.
La validation des arguments, l’acceptation des licences et les confirmations explicites
des actions destructives restent des règles métier. L’API portable reste sur `/v1` ;
le serveur écoute uniquement sur 127.0.0.1.

Un choix absent devient Free ; les profils explicites sont conservés. L’option du serveur
accepte `--access-profile free`, `--access-profile local_controlled`,
`--access-profile token_only` ou `--access-profile protected_access`. Local contrôlé
applique les permissions choisies par l’hôte. Jeton seul et Protégé exigent un jeton
valide ; Protégé conserve les permissions de l’identité. Avec la commande ci-dessus,
le choix persiste dans `data/jobs/communication.json`. Redémarrez le service pour changer
le profil actif. Les droits CLI/embarqués et du fournisseur de chat sont inchangés.
Utilisez `ai_communication_status` avec `includeOperations: true` pour la découverte.

Installez le paquet Windows complet pour remplacer le runtime natif ; les mises à jour
de l’application seule refusent l’ancien ABI. Pour une mise à niveau locale des sources :

```powershell
runtime/python/Scripts/python.exe -m pip install --no-deps app/packages/cytools_core-0.12.0-py3-none-win_amd64.whl
```

Exportez les résultats voulus avant `cy_finish_task`. Le nettoyage préserve les entrées
originales, modèles installés, conversations et documents de projet persistants.
Cette mise à jour est validée sur Windows x64 ; les builds natifs Linux/macOS restent
à vérifier sur leur plateforme.
