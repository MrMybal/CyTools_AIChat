"""CyTools_AIChat runtime: one chat engine behind the CLI, MCP, HTTP and the desktop window.

Every transport submits to this same Runtime, so a conversation continued from the window,
from an AI client over MCP, or from the command line is the same conversation, and the local
model loaded for one of them is the one the others use. There is no second scheduler and no
second resident model in the interface process.
"""
import json
import re
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
                    maintenance, paths, presets, speech, speech_env, voices)
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
    runtime.configure_inputs(paths.INPUTS, fields={'transcribe': ['audio'],
                                                   'voice_add': ['audio']})
    registry = Registry(runtime)
    speech_engines = speech.Speech(runtime)
    # The desktop frontend reads these back instead of building a second registry.
    runtime.aichat = registry
    runtime.aichat_speech = speech_engines

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
        if result['kind'] in catalog.SPEECH_KINDS:
            # Speech models are folders read by the speech engine, not GGUF files a chat
            # turn picks from the model library.
            return result
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
        if catalog.entry(parameters['model'])['kind'] in catalog.SPEECH_KINDS:
            # The speech engine may hold these weights open: unload them first.
            speech_engines.unload_all()
            result = catalog.uninstall(parameters['model'])
            result['libraryReferencesRemoved'] = 0
            return result
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

    # ------------------------------------------------------------------ speech

    def audio_input(context, value):
        """An absolute path anywhere, or a name inside data/inputs, imported for this job."""
        return context.import_input(value, base_dir=paths.INPUTS,
                                    suffixes=list(voices.AUDIO_SUFFIXES),
                                    max_bytes=512 * 1024 ** 2)

    def speech_status(context, parameters):
        return speech_engines.status()

    def speech_engine_install(context, parameters):
        name = parameters['engine']
        # The worker of that environment runs from the files being replaced.
        speech_engines.workers[name].stop()
        return speech_env.install(context, name, parameters.get('device', 'cuda'))

    def speech_engine_remove(context, parameters):
        speech_engines.workers[parameters['engine']].stop()
        return speech_env.remove(parameters['engine'])

    def speech_settings(context, parameters):
        names = {'stt_model': 'sttModel', 'tts_model': 'ttsModel', 'voice': 'voice',
                 'language': 'language', 'speed': 'speed', 'tts_device': 'ttsDevice',
                 'auto_read': 'autoRead', 'live_dictation': 'liveDictation'}
        return {'settings': voices.configure(**{names[key]: value
                                                for key, value in parameters.items()
                                                if key in names})}

    def transcribe(context, parameters):
        snapshot = audio_input(context, parameters['audio'])
        return speech_engines.transcribe(context, snapshot, parameters.get('model', ''),
                                         parameters.get('language', ''))

    def transcribe_live(context, parameters):
        # Only a recording the window is writing in data/inputs/dictation can be followed:
        # the name is a plain file name, never a path.
        name = str(parameters['stream'])
        if not re.fullmatch(r'live-[A-Za-z0-9_-]{1,64}\.pcm', name):
            raise CyToolError('InvalidParameters', 'A live recording is named live-<id>.pcm.')
        folder = paths.INPUTS / 'dictation'
        return speech_engines.transcribe_live(
            context, folder / name, folder / (name + '.done'), int(parameters['rate']),
            parameters.get('model', ''), parameters.get('language', ''),
            float(parameters.get('max_seconds') or 600))

    def speak(context, parameters):
        text = str(parameters.get('text') or '')
        output = None
        conversation_id = parameters.get('conversation', '')
        if conversation_id and parameters.get('message'):
            # Reading a stored reply: the text comes from the conversation, so an AI client
            # asking for "read message X" cannot have the Tool say something else in its name.
            document = conversations.load(conversation_id)
            message = next((item for item in document.get('messages', [])
                            if item.get('id') == parameters['message']), None)
            if message is None:
                raise CyToolError('NotFound', 'No message %s in this conversation.'
                                  % parameters['message'])
            text = message.get('text', '')
        if not text.strip():
            raise CyToolError('InvalidParameters', 'There is no text to read.')
        if not conversation_id:
            output = context.path('outputs/speech.wav')
        return speech_engines.speak(context, text, model=parameters.get('model', ''),
                                    voice=parameters.get('voice', ''),
                                    language=parameters.get('language', ''),
                                    speed=parameters.get('speed'), output=output,
                                    device=parameters.get('device', ''),
                                    progressive=bool(parameters.get('progressive')))

    def voice_list(context, parameters):
        return {'voices': speech_engines.voice_list(context)}

    def voice_add(context, parameters):
        snapshot = audio_input(context, parameters['audio'])
        transcript = str(parameters.get('transcript') or '').strip()
        if not transcript and parameters.get('transcribe', True):
            try:
                transcript = speech_engines.transcribe(context, snapshot,
                                                       language=parameters.get('language', ''))['text']
            except CyToolError as exc:
                # The clip is still useful to XTTS-v2; F5 will ask for the words when used.
                context.log('The voice was kept without its words: %s' % exc, level='Warning')
        identifier = voices.add(snapshot, parameters.get('name', ''),
                                parameters.get('language', ''), transcript)
        return {'voice': next(item for item in voices.recorded() if item['id'] == identifier)}

    def speech_unload(context, parameters):
        before = {name: worker.health()['running']
                  for name, worker in speech_engines.workers.items()}
        speech_engines.unload_all()
        return {'stopped': before}

    def estimate_speech_engine(parameters, backend, model):
        size = speech_env.engine_spec(parameters.get('engine', 'tts')).get('estimatedBytes', 0)
        return {'ramBytes': 1024 ** 3, 'cpuThreads': 1, 'diskBytes': int(size * 1.3)}

    runtime.register('speech_status', speech_status)
    runtime.register('speech_engine_install', speech_engine_install,
                     estimate=estimate_speech_engine)
    runtime.register('speech_engine_remove', speech_engine_remove)
    runtime.register('speech_settings', speech_settings)
    runtime.register('transcribe', transcribe)
    runtime.register('transcribe_live', transcribe_live)
    runtime.register('speak', speak)
    runtime.register('voice_list', voice_list)
    runtime.register('voice_add', voice_add)
    runtime.register('voice_delete', lambda context, parameters: voices.delete(parameters['voice']))
    runtime.register('speech_unload', speech_unload)

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
            'speech': speech_engines.status(),
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
            speech_engines.close()
        finally:
            return original_close(timeout)

    runtime.close = close
    return runtime


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--data-dir' not in argv:
        argv = ['--data-dir', str(ROOT / 'data/jobs'), *argv]
    raise SystemExit(run_cli(create_runtime, argv))
