---
id: operations
title: Automation and API
description: Connect a client and inspect the available operations.
section: Reference
order: 80
parent: overview
revision: a79b1e45c7b5f3ee
---

## Command line {#cli}

From the application root, use the private Python interpreter. `describe` and `list-operations` inspect the public contract.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py list-operations
runtime\python\Scripts\python.exe app\tool.py invoke list_providers --params "{}"
```

## MCP {#mcp}

Configure your MCP client to start the private interpreter with `app/tool.py mcp`, using the application folder as its working directory. Restart the connection when its exposed operation catalogue changes.

## Task files {#task-files}

Local file inputs accept absolute readable paths and are imported into the task workspace automatically. Export wanted results before finishing the task. Do not rely on temporary paths after task cleanup.

## Operations {#operations}

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


## Native communication {#native-communication}

The Windows package includes CyToolsCore 0.11.0 and the native CyMCPSDK 0.7.1
communication library. The same complete operation parameters are available to AI
clients and the standalone application. Run `ai_communication_status` with
`includeOperations: true` to inspect the effective catalogue. This does not contact
an AI provider or generate content.

CLI-generated files are temporary by default. Add `--export-dir` followed by an
absolute destination outside the job store when you want to keep them. In MCP,
export with `cy_export_job` before `cy_finish_task`. The original input file, installed
models, conversations and project documents are not removed by task cleanup.

For the first upgrade from a 0.10.x Core, install the full Windows package.
Application-only updates cannot add the required native library to an older runtime.
Model and provider integrations keep their existing compatibility and permissions;
this upgrade does not make an unsupported model or platform supported.
