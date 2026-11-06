---
id: operations
title: Automatisation et API
description: Connectez un client et consultez les opérations disponibles.
section: Référence
order: 80
parent: overview
sourceRevision: 59ec8539b4962d95
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
