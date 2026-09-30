"""CyTools_AIChat runtime: one chat engine behind the CLI, MCP, HTTP and the desktop window.

Every transport submits to this same Runtime, so a conversation continued from the window,
from an AI client over MCP, or from the command line is the same conversation, and the local
model loaded for one of them is the one the others use. There is no second scheduler and no
second resident model in the interface process.
"""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from installation_ui import configure as configure_storage  # noqa: E402

configure_storage()

import model_options  # noqa: E402
from cytools_core import CyToolError, load_manifest  # noqa: E402
from cytools_core.shared_installation import register_operations  # noqa: E402
from cytools_core.transports.cli import run_cli  # noqa: E402

from aichat import (catalog, chat, conversations, credentials, engine, library,  # noqa: E402
                    maintenance, paths, presets)
from aichat.providers import Registry  # noqa: E402

# Streaming publishes a batched event roughly every 80 ms. The default buffer of 2000 events
# would be consumed by a few long replies, and the window would miss the start of its own
# stream, so this Tool asks for a larger one.
EVENT_LIMIT = 20000


# Operations here declare the effects they really have: reaching the network, spawning an
# agent CLI, writing an export outside data/. The Core treats a declared permission as a gate
# on the calling identity, so the implicit "standalone" client the CLI, MCP and desktop
# transports create would be refused by its own Tool.
#
# When no identity is configured, this Tool therefore mints its own local client holding
# exactly the permissions its manifest declares, and hands its token to the transport through
# the environment variable the Core already reads. This grants nothing beyond what the
# manifest states and it is not a bypass: set CYTOOLS_TOKEN yourself, or connect a client
# created with `create-client --permission ...`, and that restricted identity is used instead.
PERMISSIONS = ('network', 'processSpawn', 'filesystemExternal', 'manageResources')


def ensure_standalone_identity(runtime):
    import os
    if os.environ.get('CYTOOLS_TOKEN'):
        return ''
    declared = set(PERMISSIONS)
    for operation in runtime.descriptor['operations']:
        declared.update(operation.get('permissions', []))
    token = runtime.create_client('standalone', sorted(declared))['token']
    os.environ['CYTOOLS_TOKEN'] = token
    return token


def create_runtime(data_dir, **options):
    paths.ensure_tree()
    options.setdefault('event_limit', EVENT_LIMIT)
    runtime = model_options.Runtime(load_manifest(APP / 'CyTool.json'), data_dir, **options)
    runtime.configure_inputs(paths.DATA / 'inputs', fields={})
    registry = Registry(runtime)
    # The desktop frontend reads these back instead of building a second registry.
    runtime.aichat = registry

    # ------------------------------------------------------------------ chat

    def handle_chat(context, parameters):
        return chat.run_turn(registry, context, parameters, resolved=model_options.current())

    def estimate_chat(parameters, backend, model):
        """What one turn costs *on top of* whatever is already loaded.

        The weights are not reserved here. A local model is held by the resident worker,
        which reserves the device for as long as its process runs and releases it only once
        it has stopped. Counting the same gigabytes again for the job would double the
        requirement: a 16 GiB model would need 32 GiB and be refused on a 24 GB card that
        holds it.

        What is left for the job itself is the process overhead: the request, the streamed
        reply, and the transcript being assembled.
        """
        provider = str(parameters.get('provider') or '')
        conversation = str(parameters.get('conversation') or '')
        if conversation and not provider:
            try:
                provider = conversations.load(conversation).get('providerId', '')
            except CyToolError:
                pass
        if provider == 'llamacpp':
            # Prompt processing and the streamed reply are held in this process.
            return {'ramBytes': 768 * 1024 ** 2, 'cpuThreads': 1}
        return {'ramBytes': 512 * 1024 ** 2, 'cpuThreads': 1}

    runtime.register('chat', handle_chat, estimate=estimate_chat)

    # ------------------------------------------------------------------ providers

    def list_providers(context, parameters):
        return {'providers': registry.detect(parameters.get('provider', ''))}

    def list_provider_models(context, parameters):
        provider = registry.get(parameters['provider'])
        return {'providerId': provider.id,
                'models': provider.list_models(parameters.get('transport', ''))}

    runtime.register('list_providers', list_providers)
    runtime.register('list_provider_models', list_provider_models)

    # ------------------------------------------------------------------ conversations

    def conversation_list(context, parameters):
        return {'conversations': conversations.listing()}

    def conversation_read(context, parameters):
        document = conversations.load(parameters['conversation'])
        limit = int(parameters.get('limit') or 0)
        if limit:
            document = {**document, 'messages': document['messages'][-limit:]}
        return {'conversation': document}

    def conversation_create(context, parameters):
        return {'conversation': conversations.create(
            title=parameters.get('title', ''), provider_id=parameters.get('provider', ''),
            transport=parameters.get('transport', ''), model=parameters.get('model', ''),
            system_prompt=parameters.get('system_prompt', ''),
            preset_id=parameters.get('preset', ''))}

    def conversation_delete(context, parameters):
        return conversations.delete(parameters['conversation'])

    def conversation_export(context, parameters):
        fmt = parameters.get('format', 'markdown')
        destination = str(parameters.get('destination') or '').strip()
        if destination:
            target = Path(destination)
            if not target.is_absolute():
                raise CyToolError('InvalidParameters',
                                  'An export destination must be an absolute path.')
        else:
            document = conversations.load(parameters['conversation'])
            suffix = '.md' if fmt == 'markdown' else '.json'
            target = paths.EXPORTS / (document['id'] + suffix)
        return conversations.export(parameters['conversation'], target, fmt)

    def conversation_reset_session(context, parameters):
        return {'conversation': conversations.forget_native(
            parameters['conversation'], parameters.get('provider', ''),
            parameters.get('transport', ''))}

    runtime.register('conversation_list', conversation_list)
    runtime.register('conversation_read', conversation_read)
    runtime.register('conversation_create', conversation_create)
    runtime.register('conversation_delete', conversation_delete)
    runtime.register('conversation_export', conversation_export)
    runtime.register('conversation_reset_session', conversation_reset_session)

    # ------------------------------------------------------------------ presets

    runtime.register('preset_list', lambda context, parameters: {'presets': presets.listing()})
    runtime.register('preset_save', lambda context, parameters: {'preset': presets.save(
        parameters.get('id', ''), parameters['name'], parameters.get('system_prompt', ''),
        parameters.get('settings', {}), parameters.get('description', ''))})
    runtime.register('preset_delete',
                     lambda context, parameters: presets.delete(parameters['id']))

    # ------------------------------------------------------------------ weights

    def model_list(context, parameters):
        return {'models': catalog.listing(parameters.get('kind', ''),
                                          bool(parameters.get('verify')))}

    def model_install(context, parameters):
        result = catalog.install(context, parameters['model'],
                                 bool(parameters.get('accept_license')))
        # Registering it in the model library right away gives the new weights the same kind
        # of identifier as a file the user picked themselves, so a turn never has to say
        # which of the two catalogues a model or an adapter came from.
        try:
            reference = library.register_catalogue_entry(parameters['model'])
            context.log('Registered in the model library as %s' % reference['id'])
        except CyToolError as exc:
            context.log('Installed, but not registered in the model library: %s' % exc,
                        level='Warning')
        return result

    def estimate_install(parameters, backend, model):
        try:
            return catalog.installation_resources(parameters['model'])
        except (CyToolError, KeyError):
            return {'ramBytes': 256 * 1024 ** 2, 'cpuThreads': 1}

    runtime.register('model_list', model_list)
    runtime.register('model_install', model_install, estimate=estimate_install)
    runtime.register('model_repair', lambda context, parameters: catalog.repair(
        context, parameters['model']))
    def model_uninstall(context, parameters):
        path = catalog.file_path(parameters['model'])
        result = catalog.uninstall(parameters['model'])
        # A library reference to a file that no longer exists would fail validation later
        # with a confusing message, so it goes away with the file.
        result['libraryReferencesRemoved'] = library.unregister_path(path)
        return result

    runtime.register('model_uninstall', model_uninstall)

    # ------------------------------------------------------------------ engine

    runtime.register('engine_list', lambda context, parameters: engine.describe())
    runtime.register('engine_install', lambda context, parameters: engine.install(
        context, parameters.get('build', 'cpu')))
    runtime.register('engine_remove', lambda context, parameters: engine.remove(
        parameters['build']))

    # ------------------------------------------------------------------ resident model

    def resident_status(context, parameters):
        return {'resident': registry.resident.health(),
                'adapters': registry.resident.loaded_adapters(),
                'properties': registry.resident.properties()}

    def resident_unload(context, parameters):
        loaded = registry.resident.health()['loaded']
        registry.resident.stop()
        return {'stopped': loaded, 'resident': registry.resident.health()}

    def lora_scale(context, parameters):
        return {'adapters': registry.resident.set_scales(parameters.get('loras') or [])}

    runtime.register('resident_status', resident_status)
    runtime.register('resident_unload', resident_unload)
    runtime.register('lora_scale', lora_scale)

    # ------------------------------------------------------------------ credentials

    def credential_status(context, parameters):
        provider = parameters.get('provider', '')
        wanted = [provider] if provider else [key for key in registry.ids()
                                              if registry.get(key).requires_api_key
                                              or key in credentials.ENVIRONMENT]
        return {'credentials': credentials.statuses(wanted)}

    runtime.register('credential_status', credential_status)
    runtime.register('credential_clear',
                     lambda context, parameters: credentials.clear(parameters['provider']))

    # ------------------------------------------------------------------ diagnostics

    def diagnostics(context, parameters):
        report = {
            'tool': {'id': runtime.descriptor['id'], 'version': runtime.descriptor['version'],
                     'root': str(ROOT), 'python': sys.version.split()[0]},
            'providers': registry.detect(),
            'engines': engine.describe(),
            'weights': catalog.listing(),
            'resident': registry.resident.health(),
            'conversations': {'count': len(conversations.listing()),
                              'tabs': conversations.tabs(),
                              'directory': str(paths.CONVERSATIONS)},
            'presets': {'count': len(presets.listing())},
            'credentials': credentials.statuses(sorted(credentials.ENVIRONMENT)),
            'updates': maintenance.state(),
            'system': runtime.status(),
        }
        path = context.path('outputs/diagnostics.json')
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        return {'report': report, 'file': str(path)}

    runtime.register('diagnostics', diagnostics)

    # ------------------------------------------------------------------ updates

    runtime.register('update_check', lambda context, parameters: {
        'streams': maintenance.check(parameters.get('stream', 'all'))})

    def update_download(context, parameters):
        stream = parameters.get('stream', 'application')
        if stream == 'engine':
            return maintenance.download_engine(context, parameters.get('version', ''))
        return maintenance.download_application(context, parameters.get('version', ''))

    runtime.register('update_download', update_download)
    runtime.register('update_apply', lambda context, parameters: maintenance.apply(
        context, runtime, parameters.get('stream', 'application')))
    runtime.register('update_rollback', lambda context, parameters: maintenance.rollback(
        context, runtime, parameters.get('stream', 'application')))
    runtime.register('update_settings', lambda context, parameters: {
        'settings': maintenance.configure(parameters.get('application_repository'),
                                          parameters.get('engine_repository'),
                                          parameters.get('automatic_check'))})

    register_operations(runtime, ROOT)
    ensure_standalone_identity(runtime)
    original_close = runtime.close

    def close(timeout=10):
        try:
            registry.close()
        finally:
            return original_close(timeout)

    runtime.close = close
    return runtime


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--data-dir' not in argv:
        argv = ['--data-dir', str(ROOT / 'data/jobs'), *argv]
    raise SystemExit(run_cli(create_runtime, argv))
