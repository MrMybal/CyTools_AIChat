"""The standalone Dear ImGui window.

This file is the frontend only. It owns no model, no queue and no protocol: it authenticates
against the same Runtime `tool.py` builds, submits jobs, and follows them through the event
stream. Closing the window stops the runtime, which waits for the workers to really stop.

The shared facade in `ui_common` appends the Application log, Model library, Advanced and
Options tabs to the tab bar opened here, which is also what provides the English/French
switch, the theme, the text size and the licences.
"""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from imgui_bundle import hello_imgui  # noqa: E402

from ui_common import configure_generation, imgui, label, run, tr  # noqa: E402

from gui import chat_panel, models_panel, providers_panel, updates_panel  # noqa: E402
from gui.state import Interface  # noqa: E402
from tool import create_runtime  # noqa: E402

WINDOW_TITLE = 'CyTools_AIChat'
SMOKE_FRAMES = 24
_chat_schema = None


def chat_schema():
    """The declared inputSchema of the chat operation, read once."""
    global _chat_schema
    if _chat_schema is None:
        from cytools_core import load_manifest
        document = load_manifest(APP / 'CyTool.json')
        _chat_schema = next(op for op in document['operations']
                            if op['id'] == 'chat')['inputSchema']
    return _chat_schema


def smoke_option(name, default=''):
    """Read `--name VALUE` or `--name=VALUE` from the command line."""
    flag = '--' + name
    for index, argument in enumerate(sys.argv):
        if argument == flag and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        if argument.startswith(flag + '='):
            return argument.split('=', 1)[1]
    return default


def smoke_tab():
    """`--smoke-tab NAME` renders that tab for the whole run and exits.

    hello_imgui can only hand back the screenshot of the window as it was when the loop
    ended, so proving that four panels render means four runs, each ending on its own tab,
    rather than one run flipping between them and keeping only the last image.
    """
    for index, argument in enumerate(sys.argv):
        if argument == '--smoke-tab' and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        if argument.startswith('--smoke-tab='):
            return argument.split('=', 1)[1]
    return 'Chat'


def save_smoke_screenshot(name):
    try:
        from PIL import Image
        image = hello_imgui.final_app_window_screenshot()
        if getattr(image, 'size', 0):
            reports = ROOT / 'data/reports'
            reports.mkdir(parents=True, exist_ok=True)
            destination = reports / ('window-%s.png' % name.lower())
            Image.fromarray(image).save(destination)
            return destination
    except Exception as exc:
        # A screenshot is evidence, not a feature: never fail the window over one.
        print('screenshot unavailable: %s' % exc, file=sys.stderr)
    return None


def check_configuration_round_trip(runtime, session_ui, capture, restore):
    """Save the current conversation as a generation configuration and load it back.

    The generic `--ui-test-config` check in the shared facade inspects a `form` variable this
    interface does not have, so it would pass without comparing anything. This check fills a
    tab, saves, changes every field, loads, and requires the tab to come back exactly as it
    was — and requires that loading started no job.
    """
    from generation_config import load, recipe, save, secret_key
    tab = session_ui.find(session_ui.selected) or session_ui.tabs[0]
    session_ui.update_document(tab, providerId='openai-compatible', transport='chat-completions',
                               model='round-trip-model', systemPrompt='be precise',
                               presetId='precise',
                               settings={'temperature': 0.37, 'max_tokens': 321,
                                         'history_limit': 7, 'engine': 'cpu'})
    tab.input = 'a draft that must survive'
    before = capture()
    path = ROOT / 'data/reports/configuration-round-trip.json'
    save(path, recipe(runtime.descriptor, before['operationId'], before['parameters']))
    session_ui.update_document(tab, providerId='codex', model='something-else',
                               systemPrompt='', presetId='', settings={'temperature': 1.9})
    tab.input = ''
    document = load(path, runtime.descriptor)
    restore(document)
    after = capture()
    # Both sides go through `recipe`, which materialises the schema defaults. Comparing the
    # raw forms would report a difference for a field the save legitimately filled in, such
    # as a default the user never touched; comparing the effective parameters asks the real
    # question, which is whether the turn would be submitted identically.
    saved = recipe(runtime.descriptor, before['operationId'], before['parameters'])['parameters']
    restored = recipe(runtime.descriptor, after['operationId'], after['parameters'])['parameters']
    problems = []
    if before['operationId'] != after['operationId']:
        problems.append('operation: saved %s, restored %s'
                        % (before['operationId'], after['operationId']))
    for key, value in saved.items():
        if restored.get(key) != value:
            problems.append('%s: saved %r, restored %r' % (key, value, restored.get(key)))
    if tab.busy:
        problems.append('loading a configuration started a job, which it must never do')
    report = {'operationId': before['operationId'], 'saved': saved,
              'restored': restored, 'problems': problems,
              'startedAJob': bool(tab.busy),
              'secretsInConfiguration': [key for key in saved if secret_key(key)]}
    destination = ROOT / 'data/reports/configuration-round-trip-result.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('configuration round trip:', 'identical' if not problems else problems)


def main():
    from branding import configure as configure_branding
    configure_branding('Cyberalien.CyTools_AIChat')
    runner = hello_imgui.RunnerParams()
    runner.app_window_params.window_title = WINDOW_TITLE
    runner.app_window_params.window_geometry.size = (1320, 880)
    (ROOT / 'data/settings').mkdir(parents=True, exist_ok=True)
    runner.ini_filename = str(ROOT / 'data/settings/imgui.ini')
    frames = 0

    with create_runtime(ROOT / 'data/jobs') as runtime:
        token = runtime.create_client('ImGui', ['network', 'processSpawn', 'filesystemExternal',
                                                'manageResources'])['token']
        actor = runtime.authenticate(token)
        # A standalone session is explicitly not temporary: its conversations and workspaces
        # must survive the window being closed.
        session = runtime.create_session(actor, temporary=False)['sessionId']
        # Deliberately not named `interface`: ui_common.scope() treats a closure
        # variable of that name as a legacy frontend object and reaches for
        # attributes this one does not have.
        session_ui = Interface(runtime, actor, session)

        panels = (('Chat', chat_panel), ('Providers', providers_panel),
                  ('Models', models_panel), ('Updates', updates_panel))
        smoke = '--smoke-test' in sys.argv
        wanted = smoke_tab() if smoke else ''
        # A scripted turn: it exercises exactly the path a click on Send takes, so the
        # screenshot afterwards is evidence of the real streaming path, not of a mock.
        smoke_message = smoke_option('smoke-send')
        smoke_sent = [False]
        smoke_done = [False]

        def gui():
            nonlocal frames
            frames += 1
            session_ui.poll()
            if imgui.begin_tab_bar('###aichat-navigation'):
                for name, panel in panels:
                    flags = imgui.TabItemFlags_.set_selected if smoke and name == wanted else 0
                    opened, _ = imgui.begin_tab_item(label(name), None, flags)
                    if opened:
                        panel.draw(session_ui)
                        imgui.end_tab_item()
                imgui.end_tab_bar()
            if smoke and '--smoke-config' in sys.argv and frames == SMOKE_FRAMES // 2:
                check_configuration_round_trip(runtime, session_ui, capture_config, restore_config)
            if smoke and smoke_message and not smoke_sent[0] and frames == SMOKE_FRAMES // 2:
                tab = session_ui.find(session_ui.selected) or session_ui.tabs[0]
                session_ui.update_document(
                    tab, providerId=smoke_option('smoke-provider', 'llamacpp'),
                    transport='',
                    model=smoke_option('smoke-model', 'qwen25-1_5b'),
                    settings={'max_tokens': 120, 'temperature': 0.3, 'engine': 'cuda'})
                tab.input = smoke_message
                session_ui.send(tab)
                smoke_sent[0] = True
            if smoke and smoke_message and smoke_sent[0]:
                tab = session_ui.find(session_ui.selected) or session_ui.tabs[0]
                # Leave as soon as the turn is over, or when it never started at all, but
                # give the scheduler a moment first: a job accepted on one frame is not yet
                # Running on the next, and exiting there would report the previous reply.
                done = not tab.busy and smoke_done[0]
                if tab.busy:
                    smoke_done[0] = True
                if tab.error:
                    done = True
                if (done or frames > SMOKE_FRAMES * 40) and frames > SMOKE_FRAMES:
                    runner.app_shall_exit = True
                return
            if smoke and frames > SMOKE_FRAMES:
                # Wait for the panel's own background work before ending the run, so the
                # screenshot shows the panel as the user sees it rather than mid-load.
                panel = dict(panels).get(wanted)
                ready = getattr(panel, 'smoke_ready', None)
                if ready is None or ready() or frames > SMOKE_FRAMES * 80:
                    runner.app_shall_exit = True

        def capture_config():
            """What Save configuration writes: the active conversation, as a chat call."""
            tab = session_ui.find(session_ui.selected) or (session_ui.tabs[0] if session_ui.tabs else None)
            if tab is None:
                raise ValueError('Open a conversation before saving a configuration')
            document = tab.document
            settings = {key: value for key, value in (document.get('settings') or {}).items()
                        if not key.startswith('_')}
            parameters = {'message': tab.input or '', 'conversation': tab.id,
                          'provider': document.get('providerId', ''),
                          'transport': document.get('transport', ''),
                          'model': document.get('model', ''),
                          'system_prompt': document.get('systemPrompt', ''),
                          'preset': document.get('presetId', ''),
                          'settings': settings}
            for key in ('temperature', 'top_p', 'top_k', 'max_tokens', 'seed', 'repeat_penalty',
                        'context_tokens', 'history_limit', 'engine', 'threads', 'keep_loaded'):
                if settings.get(key) is not None:
                    parameters[key] = settings[key]
            if settings.get('loras'):
                parameters['loras'] = settings['loras']
            return {'operationId': 'chat', 'parameters': parameters}

        def restore_config(value):
            """Loading fills the form of a tab. It never starts a turn."""
            parameters = value.get('parameters', {})
            conversation_id = parameters.get('conversation', '')
            tab = session_ui.find(conversation_id) if conversation_id else None
            if tab is None:
                tab = session_ui.new_tab()
            settings = dict(parameters.get('settings') or {})
            # A saved configuration carries every declared field, including the ones the
            # schema filled with their default. Writing those back into the conversation
            # would add settings the user never chose and make a second save differ from the
            # first, so a value equal to its default is left out.
            defaults = {key: spec.get('default') for key, spec in
                        chat_schema()['properties'].items()}
            for key in ('temperature', 'top_p', 'top_k', 'max_tokens', 'seed', 'repeat_penalty',
                        'context_tokens', 'history_limit', 'engine', 'threads', 'keep_loaded'):
                value = parameters.get(key)
                if value is None:
                    continue
                if key not in (parameters.get('settings') or {}) and value == defaults.get(key):
                    continue
                settings[key] = value
            if parameters.get('loras'):
                settings['loras'] = parameters['loras']
            session_ui.update_document(tab, providerId=parameters.get('provider', ''),
                                      transport=parameters.get('transport', ''),
                                      model=parameters.get('model', ''),
                                      systemPrompt=parameters.get('system_prompt', ''),
                                      presetId=parameters.get('preset', ''),
                                      settings=settings)
            tab.input = parameters.get('message', '')
            session_ui.selected = tab.id

        configure_generation(runtime, capture_config, restore_config)
        runner.callbacks.show_gui = gui
        run(runner)
        if smoke:
            saved = save_smoke_screenshot('chat-turn' if smoke_message else wanted)
            print('smoke tab %s rendered %d frames; screenshot: %s'
                  % (wanted, frames, saved or 'not captured'))
            if smoke_message:
                tab = session_ui.find(session_ui.selected) or session_ui.tabs[0]
                messages = tab.document.get('messages', [])
                print('conversation %s now holds %d messages; last reply: %r'
                      % (tab.id, len(messages),
                         (messages[-1].get('text') if messages else '')[:160]))
                if tab.error:
                    print('the scripted turn reported: %s' % tab.error)


if __name__ == '__main__':
    main()
