"""Generate app/CyTool.json.

The manifest is built from this script rather than edited by hand so the provider list, the
sampling bounds and the operation contracts stay consistent between the CLI, MCP and the
desktop window. Run it after changing a provider or a parameter:

    runtime/python/Scripts/python.exe app/build_manifest.py

Platform entries follow the project rule that a declared platform and a tested platform are
two different statements: `platforms[].tested` is filled from app/platform-tested.json,
which is only written after a real run on that platform.
"""
import json
from pathlib import Path

APP = Path(__file__).resolve().parent
VERSION = '0.1.0'

PROVIDERS = [
    ('codex', 'Codex (agent CLI, your ChatGPT sign-in)'),
    ('claude-code', 'Claude Code (agent CLI, your Claude sign-in)'),
    ('antigravity', 'Antigravity (agent CLI)'),
    ('opencode', 'OpenCode (agent CLI)'),
    ('codebuddy', 'CodeBuddy (declared, no adapter)'),
    ('command-code', 'Command Code (declared, no adapter)'),
    ('devin', 'Devin (declared, no adapter)'),
    ('openai', 'OpenAI API (your API key)'),
    ('openrouter', 'OpenRouter (your API key)'),
    ('openai-compatible', 'Any OpenAI-compatible endpoint (LM Studio, vLLM, gateway)'),
    ('anthropic', 'Claude API (your API key)'),
    ('ollama', 'Ollama (local server)'),
    ('llamacpp', 'Local GGUF model with LoRA (llama.cpp, runs on this machine)'),
]

TRANSPORTS = ['', 'app-server', 'cli-jsonl', 'chat-completions', 'messages', 'native',
              'local-server']

SAMPLING = {
    'temperature': {'type': 'number', 'minimum': 0, 'maximum': 2,
                    'description': 'Sampling temperature. Higher is more varied. Left unset, the provider default applies.'},
    'top_p': {'type': 'number', 'minimum': 0, 'maximum': 1,
              'description': 'Nucleus sampling threshold.'},
    'top_k': {'type': 'integer', 'minimum': 0, 'maximum': 1000,
              'description': 'Keep only the K most likely tokens. Ignored by providers that do not expose it.'},
    'max_tokens': {'type': 'integer', 'minimum': 1, 'maximum': 131072,
                   'description': 'Maximum tokens in the reply.'},
    'repeat_penalty': {'type': 'number', 'minimum': 0, 'maximum': 4,
                       'description': 'Penalty applied to repeated tokens. Local and Ollama providers only.'},
    'seed': {'type': 'integer', 'minimum': -1, 'maximum': 2147483647,
             'description': 'Sampling seed. -1 leaves it to the provider. The same seed only reproduces a reply with the same weights and runtime.'},
    'context_tokens': {'type': 'integer', 'minimum': 512, 'maximum': 1048576,
                       'description': 'Context window requested when loading a local model. Changing it restarts the local server.'},
    'history_limit': {'type': 'integer', 'minimum': 0, 'maximum': 1000,
                      'description': 'Send only the last N stored messages to a stateless provider. 0 sends the whole conversation. A session provider keeps its own history and ignores this.'},
}


def operation(identifier, name, description, properties, required, outputs,
              *, resources=None, cancel=True, progress=False, permissions=(), async_run=True,
              additional=False):
    return {
        'id': identifier, 'name': name, 'description': description,
        'inputSchema': {'type': 'object', 'properties': properties, 'required': list(required),
                        'additionalProperties': additional},
        'outputSchema': {'type': 'object',
                         'properties': {key: value for key, value in outputs.items()},
                         'required': [key for key, value in outputs.items()
                                      if not value.pop('_optional', False)],
                         'additionalProperties': False},
        'outputs': [{'id': key, 'type': 'Object' if value.get('type') == 'object' else
                     'File' if value.get('x-cy-kind') == 'File' else 'Value',
                     'description': value.get('description', key)}
                    for key, value in outputs.items()],
        'resourceRequirements': resources or {'ramBytes': 64 * 1024 ** 2, 'cpuThreads': 1},
        'supportedBackends': [], 'permissions': list(permissions),
        'canRunAsync': async_run, 'canCancel': cancel, 'supportsProgress': progress,
    }


def string(description, **extra):
    return {'type': 'string', 'description': description, **extra}


def chat_operation():
    properties = {
        'message': string('The message to send.', **{'x-cy-kind': 'MultilineString'}),
        'conversation': string('Conversation id to continue. Empty starts a new conversation and returns its id.',
                               default=''),
        'provider': {'type': 'string', 'enum': [''] + [p for p, _ in PROVIDERS], 'default': '',
                     'description': 'Provider to talk to. Empty reuses the one stored in the conversation.'},
        'transport': {'type': 'string', 'enum': TRANSPORTS, 'default': '',
                      'description': 'Transport within the provider. Empty uses its default.'},
        'model': string('Model identifier for the provider. Empty reuses the conversation model.',
                        default=''),
        'system_prompt': string('System prompt for this conversation. A session provider that has no system field receives it folded into the first message, and the reply reports that.',
                                default='', **{'x-cy-kind': 'MultilineString'}),
        'preset': string('Preset id whose system prompt and sampling values fill anything not set explicitly.',
                         default=''),
        'engine': {'type': 'string', 'enum': ['auto', 'cpu', 'cuda'], 'default': 'auto',
                   'description': 'llama.cpp build for the local provider. auto prefers an installed CUDA build.'},
        'threads': {'type': 'integer', 'minimum': 0, 'maximum': 256, 'default': 0,
                    'description': 'CPU threads for the local provider. 0 lets llama.cpp decide.'},
        'keep_loaded': {'type': 'boolean', 'default': True,
                        'description': 'Keep the local model resident after the reply so the next turn starts immediately.'},
        'reasoning_effort': {'type': 'string',
                             'enum': ['', 'default', 'none', 'minimal', 'low', 'medium', 'high',
                                      'xhigh', 'max'],
                             'default': '',
                             'description': 'How much a reasoning model should think before answering. Empty uses the value the catalogue records for that model. "none" turns thinking off through the chat template; the other levels are passed to llama.cpp. Local provider only.'},
        'settings': {'type': 'object', 'default': {},
                     'description': 'Extra provider fields merged into the request, for options this schema does not name.'},
    }
    properties.update({key: dict(value) for key, value in SAMPLING.items()})
    outputs = {
        'conversationId': string('Conversation the reply was stored in.'),
        'messageId': string('Identifier of the stored assistant message.'),
        'text': string('The reply text.'),
        'providerId': string('Provider that produced the reply.'),
        'transport': string('Transport used.'),
        'model': string('Model reported by the provider.'),
        'kind': string('stateless when the transcript is the context, session when the provider keeps the history.'),
        'usage': {'type': 'object', 'description': 'Token accounting as reported by the provider, when it reports any.'},
        'seconds': {'type': 'number', 'description': 'Wall-clock duration of the turn.'},
        'nativeSessionId': string('Provider-side session identifier, when the provider has one.'),
        'thinkingCharacters': {'type': 'integer', 'description': 'Characters of reasoning text streamed but not stored in the reply.'},
        'file': string('Markdown file holding the reply inside the job workspace.', **{'x-cy-kind': 'File'}),
        'mimeType': string('MIME type of the reply file.'),
    }
    return operation('chat', 'Chat', 'Send one message and store the reply in a conversation.',
                     properties, ['message'], outputs,
                     resources={'ramBytes': 512 * 1024 ** 2, 'cpuThreads': 1},
                     progress=True, permissions=['network', 'processSpawn'])


def operations():
    items = [chat_operation()]

    items.append(operation(
        'list_providers', 'List providers',
        'Inventory every provider with its transports and what was actually detected on this machine.',
        {'provider': string('Limit the report to one provider.', default='')},
        [], {'providers': {'type': 'array', 'items': {'type': 'object'},
                           'description': 'One report per provider.'}},
        cancel=False, permissions=['network', 'processSpawn']))

    items.append(operation(
        'list_provider_models', 'List provider models',
        'Ask a provider for the models it offers. Not every provider publishes a catalogue.',
        {'provider': string('Provider id.'),
         'transport': {'type': 'string', 'enum': TRANSPORTS, 'default': ''}},
        ['provider'],
        {'models': {'type': 'array', 'items': {'type': 'object'}, 'description': 'Model rows.'},
         'providerId': string('Provider queried.')},
        cancel=False, permissions=['network', 'processSpawn']))

    items.append(operation(
        'conversation_list', 'List conversations', 'Every stored conversation, most recent first.',
        {}, [], {'conversations': {'type': 'array', 'items': {'type': 'object'},
                                   'description': 'Conversation summaries.'}},
        cancel=False))

    items.append(operation(
        'conversation_read', 'Read a conversation', 'The full stored transcript of one conversation.',
        {'conversation': string('Conversation id.'),
         'limit': {'type': 'integer', 'minimum': 0, 'maximum': 10000, 'default': 0,
                   'description': 'Return only the last N messages. 0 returns all of them.'}},
        ['conversation'],
        {'conversation': {'type': 'object', 'description': 'The stored document.'}},
        cancel=False))

    items.append(operation(
        'conversation_create', 'Create a conversation', 'Start an empty conversation and return its id.',
        {'title': string('Title. Empty derives one from the first message.', default=''),
         'provider': {'type': 'string', 'enum': [''] + [p for p, _ in PROVIDERS], 'default': ''},
         'transport': {'type': 'string', 'enum': TRANSPORTS, 'default': ''},
         'model': string('Model identifier.', default=''),
         'system_prompt': string('System prompt.', default='', **{'x-cy-kind': 'MultilineString'}),
         'preset': string('Preset id to start from.', default='')},
        [], {'conversation': {'type': 'object', 'description': 'The created document.'}},
        cancel=False))

    items.append(operation(
        'conversation_delete', 'Delete a conversation',
        'Move a conversation out of the active list. The document is kept as a timestamped backup.',
        {'conversation': string('Conversation id.')}, ['conversation'],
        {'id': string('Conversation id.'), 'deleted': {'type': 'boolean'},
         'backup': string('Where the document was moved.')},
        cancel=False))

    items.append(operation(
        'conversation_export', 'Export a conversation', 'Write a conversation to a file.',
        {'conversation': string('Conversation id.'),
         'format': {'type': 'string', 'enum': ['markdown', 'json'], 'default': 'markdown'},
         'destination': string('Absolute path to write to. Empty writes into data/exports.', default='')},
        ['conversation'],
        {'file': string('The written file.', **{'x-cy-kind': 'File'}),
         'format': string('Format written.'), 'mimeType': string('MIME type.')},
        cancel=False, permissions=['filesystemExternal']))

    items.append(operation(
        'conversation_reset_session', 'Forget the provider session',
        'Drop the provider-side session so the next turn starts a fresh one. The stored transcript is kept.',
        {'conversation': string('Conversation id.'),
         'provider': string('Limit to one provider. Empty forgets every session of the conversation.', default=''),
         'transport': {'type': 'string', 'enum': TRANSPORTS, 'default': ''}},
        ['conversation'],
        {'conversation': {'type': 'object', 'description': 'The updated document.'}},
        cancel=False))

    items.append(operation(
        'preset_list', 'List presets', 'Presets shipped with the application and those you saved.',
        {}, [], {'presets': {'type': 'array', 'items': {'type': 'object'},
                             'description': 'Preset documents.'}},
        cancel=False))

    items.append(operation(
        'preset_save', 'Save a preset', 'Create or replace a preset. Secrets are never part of a preset.',
        {'id': string('Preset id. Empty mints one.', default=''),
         'name': string('Display name.'),
         'description': string('What this preset is for.', default=''),
         'system_prompt': string('System prompt.', default='', **{'x-cy-kind': 'MultilineString'}),
         'settings': {'type': 'object', 'default': {},
                      'description': 'Sampling values: ' + ', '.join(sorted(SAMPLING))}},
        ['name'], {'preset': {'type': 'object', 'description': 'The stored preset.'}},
        cancel=False))

    items.append(operation(
        'preset_delete', 'Delete a preset', 'Remove a preset you saved.',
        {'id': string('Preset id.')}, ['id'],
        {'id': string('Preset id.'), 'deleted': {'type': 'boolean'}}, cancel=False))

    items.append(operation(
        'model_list', 'List local weights',
        'Catalogue of downloadable GGUF models and LoRA adapters with their installation state.',
        {'kind': {'type': 'string', 'enum': ['', 'model', 'lora'], 'default': ''},
         'verify': {'type': 'boolean', 'default': False,
                    'description': 'Re-hash installed files. Slow on large weights.'}},
        [], {'models': {'type': 'array', 'items': {'type': 'object'},
                        'description': 'Catalogue rows.'}},
        cancel=True))

    items.append(operation(
        'model_install', 'Install local weights',
        'Download and verify a catalogue entry. Resumes an interrupted download.',
        {'model': string('Catalogue entry id.'),
         'accept_license': {'type': 'boolean', 'default': False,
                            'description': 'Confirms you accepted the licence on the provider page yourself.'}},
        ['model'],
        {'id': string('Entry id.'), 'installed': {'type': 'boolean'},
         'sizeBytes': {'type': 'integer'}, 'presentBytes': {'type': 'integer'},
         'kind': string('model or lora'), 'name': string('Display name.'),
         'license': string('Declared licence.'), 'source': string('Model page.'),
         'repository': string('Repository.'), 'revision': string('Pinned revision.'),
         'gated': {'type': 'boolean'}, 'licenseAccepted': {'type': 'boolean'},
         'baseModel': string('Base model id, for an adapter.'),
         'architecture': string('Declared architecture.'),
         'contextTokens': {'type': 'integer'}, 'ramGiB': {'type': 'integer'},
         'vramGiB': {'type': 'integer'}, 'notes': string('Notes.'),
         'path': string('Installed file path.')},
        progress=True, permissions=['network']))

    items.append(operation(
        'model_repair', 'Repair local weights',
        'Re-verify an entry and delete only the files whose digest does not match.',
        {'model': string('Catalogue entry id.')}, ['model'],
        {'id': string('Entry id.'), 'removedFiles': {'type': 'array', 'items': {'type': 'string'}},
         'installed': {'type': 'boolean'}, 'repaired': {'type': 'boolean'}},
        progress=False))

    items.append(operation(
        'model_uninstall', 'Remove local weights', 'Delete the files of a catalogue entry.',
        {'model': string('Catalogue entry id.')}, ['model'],
        {'id': string('Entry id.'), 'removedFiles': {'type': 'array', 'items': {'type': 'string'}},
         'installed': {'type': 'boolean'},
         'libraryReferencesRemoved': {'type': 'integer',
                                      'description': 'Model library references dropped with the files.'}},
        cancel=False))

    items.append(operation(
        'engine_list', 'List llama.cpp engines',
        'The pinned llama.cpp builds and which one is installed.',
        {}, [], {'release': string('Pinned release tag.'),
                 'repository': string('Source repository.'),
                 'builds': {'type': 'array', 'items': {'type': 'object'}},
                 'notes': string('Notes.')}, cancel=False))

    items.append(operation(
        'engine_install', 'Install a llama.cpp engine',
        'Download, verify and unpack a pinned llama.cpp build into runtime/engines.',
        {'build': {'type': 'string', 'enum': ['cpu', 'cuda'], 'default': 'cpu'}}, [],
        {'id': string('Build id.'), 'name': string('Build name.'),
         'installed': {'type': 'boolean'}, 'path': string('Server executable.'),
         'version': string('Release tag.'), 'release': string('Pinned release.'),
         'device': string('cpu or cuda.'), 'platform': string('Target platform.'),
         'sizeBytes': {'type': 'integer'}, 'license': string('Licence.'),
         'source': string('Release page.'), 'devices': string('Device probe output, for CUDA.'),
         'requires': string('What this build needs.')},
        progress=True, permissions=['network', 'processSpawn']))

    items.append(operation(
        'engine_remove', 'Remove a llama.cpp engine', 'Delete a build this Tool installed.',
        {'build': {'type': 'string', 'enum': ['cpu', 'cuda']}}, ['build'],
        {'id': string('Build id.'), 'removed': {'type': 'boolean'}}, cancel=False))

    items.append(operation(
        'resident_status', 'Local model status',
        'Whether a local model is loaded, on which device, with which adapters.',
        {}, [], {'resident': {'type': 'object', 'description': 'Resident server state.'},
                 'adapters': {'type': 'array', 'items': {'type': 'object'},
                              'description': 'Adapters reported by the running server.'},
                 'properties': {'type': 'object', 'description': 'Server properties, when loaded.'}},
        cancel=False))

    items.append(operation(
        'resident_unload', 'Unload the local model',
        'Stop the local llama.cpp server and release its reservation.',
        {}, [], {'stopped': {'type': 'boolean'},
                 'resident': {'type': 'object', 'description': 'State after stopping.'}},
        cancel=False))

    items.append(operation(
        'lora_scale', 'Change adapter strength',
        'Set LoRA strengths on the running local server without reloading the model.',
        {'loras': {'type': 'array', 'default': [], 'maxItems': 8,
                   'items': {'type': 'object', 'additionalProperties': False,
                             'required': ['id', 'strength'],
                             'properties': {'id': {'type': 'string'},
                                            'strength': {'type': 'number', 'minimum': -4, 'maximum': 4}}},
                   'description': 'Strengths in the order the adapters were loaded.'}},
        [], {'adapters': {'type': 'array', 'items': {'type': 'object'},
                          'description': 'Adapters as the server reports them afterwards.'}},
        cancel=False))

    items.append(operation(
        'credential_status', 'API key status',
        'Whether a key is configured for a provider and how it is protected. Never returns the key.',
        {'provider': string('Provider id. Empty reports every provider that can take a key.', default='')},
        [], {'credentials': {'type': 'array', 'items': {'type': 'object'},
                             'description': 'One status per provider.'}},
        cancel=False))

    items.append(operation(
        'credential_clear', 'Remove an API key', 'Delete a stored key.',
        {'provider': string('Provider id.')}, ['provider'],
        {'providerId': string('Provider id.'), 'removed': {'type': 'boolean'}}, cancel=False))

    items.append(operation(
        'diagnostics', 'Diagnostics',
        'One report covering providers, engines, weights, storage and the resident model.',
        {}, [], {'report': {'type': 'object', 'description': 'The diagnostic report.'},
                 'file': string('Report file in the job workspace.', **{'x-cy-kind': 'File'})},
        cancel=False, permissions=['network', 'processSpawn']))

    items.append(operation(
        'update_check', 'Check for updates',
        'Ask the configured GitHub sources what the application and the engine could move to.',
        {'stream': {'type': 'string', 'enum': ['application', 'engine', 'all'], 'default': 'all'}},
        [], {'streams': {'type': 'array', 'items': {'type': 'object'},
                         'description': 'One entry per update stream.'}},
        permissions=['network']))

    items.append(operation(
        'update_download', 'Download an update',
        'Stage an update under runtime/updates and verify it there. Nothing is activated.',
        {'stream': {'type': 'string', 'enum': ['application', 'engine'], 'default': 'application'},
         'version': string('Exact release tag to stage.', default='')},
        [], {'staged': {'type': 'boolean'}, 'stream': string('Stream staged.'),
             'version': string('Version staged.'), 'path': string('Staging directory.'),
             'report': {'type': 'object', 'description': 'Verification details.'}},
        progress=True, permissions=['network']))

    items.append(operation(
        'update_apply', 'Apply a staged update',
        'Activate a verified staged update, keeping the previous version for a rollback. data/ is never replaced.',
        {'stream': {'type': 'string', 'enum': ['application', 'engine'], 'default': 'application'}},
        [], {'applied': {'type': 'boolean'}, 'stream': string('Stream applied.'),
             'version': string('Version now active.'), 'backup': string('Kept previous version.'),
             'restartRequired': {'type': 'boolean'}},
        progress=True))

    items.append(operation(
        'update_rollback', 'Roll back an update', 'Restore the version kept before the last update.',
        {'stream': {'type': 'string', 'enum': ['application', 'engine'], 'default': 'application'}},
        [], {'restored': {'type': 'boolean'}, 'stream': string('Stream restored.'),
             'version': string('Version restored.'), 'restartRequired': {'type': 'boolean'}},
        progress=True))

    items.append(operation(
        'update_settings', 'Update sources',
        'Read or change the GitHub sources and the automatic check preference.',
        {'application_repository': string('owner/name of the application repository. Empty leaves it unchanged.', default=''),
         'engine_repository': string('owner/name of the engine repository.', default=''),
         'automatic_check': {'type': 'string', 'enum': ['', 'on', 'off'], 'default': '',
                             'description': 'Turn the startup check on or off.'}},
        [], {'settings': {'type': 'object', 'description': 'The stored update settings.'}},
        cancel=False))

    return items


def manifest():
    tested = json.loads((APP / 'platform-tested.json').read_text('utf-8')) \
        if (APP / 'platform-tested.json').is_file() else {}
    platforms = []
    for system, architecture, status, backends in (
            ('Windows', 'x64', 'Supported', ['CPU', 'CUDA']),
            ('Linux', 'x64', 'Experimental', ['CPU', 'CUDA']),
            ('macOS', 'ARM64', 'Unknown', ['CPU'])):
        entry = {'os': system, 'architecture': architecture, 'status': status,
                 'computeBackends': backends}
        key = '%s-%s' % (system, architecture)
        if key in tested:
            entry['tested'] = tested[key]
        platforms.append(entry)
    return {
        'schemaVersion': 1, 'protocolVersion': '1.0', 'id': 'cy.tool.aichat',
        'name': 'CyTools_AIChat', 'version': VERSION,
        'description': ('A chat engine for connected agent CLIs, HTTP model APIs and local GGUF '
                        'models with LoRA adapters. Conversations are kept on disk and opened in '
                        'tabs in the standalone window.'),
        'vendor': 'Cyberalien', 'author': 'Cyberalien',
        'license': 'GPL-3.0-only', 'homepage': 'https://github.com/MrMybal/CyTools_AIChat',
        'executable': 'runtime/python/Scripts/python.exe app/tool.py',
        'standaloneExecutable': 'CyTools_AIChat.exe',
        'categories': ['ai', 'chat', 'utility'],
        'tags': ['chat', 'llm', 'codex', 'claude', 'ollama', 'llama.cpp', 'lora', 'conversations'],
        'capabilities': ['jobs', 'cancellation', 'progress', 'events'],
        'backends': [],
        'platforms': platforms,
        'interfaces': ['Native', 'CLI', 'JSONL', 'HTTP', 'MCP', 'ImGui'],
        # `required` is left false on purpose. The Core checks a required dependency by
        # looking for an absolute path or a PATH executable before every submission, and
        # none of these three fit that test: the interpreter is the one already running
        # this code, the llama.cpp server lives at a path recorded after installation and
        # is only needed by the local provider, and the agent CLIs are each needed only by
        # their own provider. Each is checked where it is actually used, with an error that
        # says which provider needs it, instead of blocking every operation of the Tool.
        'runtimeRequirements': [
            {'id': 'python', 'name': 'Python', 'version': '>=3.11,<3.13', 'required': False,
             'description': 'The private interpreter in runtime/python runs this Tool.'},
            {'id': 'llama-server', 'name': 'llama.cpp server', 'version': 'b11114',
             'required': False,
             'description': 'Needed only by the local provider. Installed from the Tool into '
                            'runtime/engines; engine_list reports whether it is present.'},
            {'id': 'agent-cli', 'name': 'Agent command line', 'required': False,
             'description': 'codex, claude, agy or opencode, for the agent CLI providers. '
                            'Each uses its own sign-in; list_providers reports what was found.'},
        ],
        # Several tabs may be waiting on different providers at once, so turns run
        # concurrently. The local provider serialises itself: its server is started with a
        # single slot, and its reservation keeps a second local turn queued until the first
        # one releases the GPU.
        'concurrency': {'policy': 'Concurrent', 'maxWorkers': 4},
        'distributionStatus': 'Standalone Windows x64 build validated locally; see app/Docs/CapabilityCoverage.md',
        'operations': operations(),
    }


def main():
    import model_options
    document = model_options.extend_manifest(manifest())
    (APP / 'CyTool.json').write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n',
                                     encoding='utf-8')
    print('Wrote %s with %d operations.' % (APP / 'CyTool.json', len(document['operations'])))


if __name__ == '__main__':
    main()
