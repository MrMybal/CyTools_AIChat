"""The Providers tab: what was found on this machine, and the keys or endpoints it needs.

An API key typed here is written straight to the credential store by this process. It never
becomes a job parameter, so it cannot end up in the job history, in a saved configuration,
in an event or in the application log. The field only ever shows what is being typed; a
stored key is never read back into the interface, only its presence and protection.
"""
import webbrowser

from imgui_bundle import ImVec2

from cytools_core import CyToolError
from ui_common import imgui, label, tr

from aichat import credentials
from .widgets import Async, status_dot, wrapped

_detect = Async()
_entry = {}
_message = ''
_base_urls = {}

KEY_PROVIDERS = ('openai', 'openrouter', 'anthropic', 'openai-compatible')
ENDPOINT_PROVIDERS = ('openai-compatible', 'ollama', 'openai', 'openrouter', 'anthropic')
HELP_PAGES = {
    'openai': 'https://platform.openai.com/api-keys',
    'openrouter': 'https://openrouter.ai/keys',
    'anthropic': 'https://console.anthropic.com/settings/keys',
    'codex': 'https://developers.openai.com/codex/cli',
    'claude-code': 'https://docs.claude.com/en/docs/claude-code/overview',
    'ollama': 'https://ollama.com/download',
    'antigravity': 'https://antigravity.google/',
    'opencode': 'https://opencode.ai/',
}


def refresh(interface, force=False):
    if force or (not _detect.ready and not _detect.running):
        _detect.start(lambda: interface.runtime.aichat.detect(), 'detect')


def smoke_ready():
    """Detection runs in the background; a screenshot taken before it lands proves nothing."""
    return _detect.ready or bool(_detect.error)


def draw(interface):
    global _message
    refresh(interface)
    if imgui.button(label('Detect again')):
        refresh(interface, True)
    imgui.same_line()
    if _detect.running:
        imgui.text_disabled(tr('Detecting...'))
    else:
        imgui.text_disabled(tr('Detection spawns each agent CLI once and queries each endpoint. '
                               'Nothing is sent to a model.'))
    if _message:
        imgui.text_colored((0.6, 0.85, 0.65, 1.0), _message)
        imgui.same_line()
        if imgui.small_button(label('Dismiss###dismiss-provider')):
            _message = ''
    if _detect.error:
        imgui.text_colored((0.9, 0.5, 0.45, 1.0), _detect.error)
    imgui.separator()
    reports = {row['id']: row for row in (_detect.take([]) or [])}
    for provider_id in interface.runtime.aichat.ids():
        provider = interface.runtime.aichat.get(provider_id)
        report = reports.get(provider_id, {})
        draw_provider(interface, provider, report)


def draw_provider(interface, provider, report):
    imgui.push_id(provider.id)
    status = report.get('status', tr('not detected yet'))
    status_dot(bool(report.get('available')), unknown=not report)
    opened = imgui.collapsing_header('%s  —  %s###header' % (provider.name, tr(status)))
    if opened:
        imgui.indent()
        wrapped(tr(provider.documentation))
        imgui.text_disabled('%s: %s' % (tr('Transports'),
                                        ', '.join(provider.transports) or tr('none implemented')))
        if getattr(provider, 'untested', ()):
            imgui.text_disabled(tr('Wired but never validated by this project: ')
                                + ', '.join(provider.untested))
        kind = tr('Session provider: it keeps the history and is resumed by identifier.') \
            if provider.kind == 'session' else \
            tr('Stateless provider: the stored transcript is sent on every turn.')
        imgui.text_disabled(kind)
        if report.get('version'):
            imgui.text_disabled('%s: %s' % (tr('Version'), str(report['version'])[:120]))
        if report.get('command'):
            imgui.text_disabled('%s: %s' % (tr('Command'), report['command']))
        if report.get('detail'):
            wrapped(report['detail'])
        if provider.id in ENDPOINT_PROVIDERS:
            draw_endpoint(interface, provider)
        if provider.id in KEY_PROVIDERS:
            draw_key(interface, provider)
        if provider.id in HELP_PAGES and imgui.small_button(label('Open the official page')):
            webbrowser.open(HELP_PAGES[provider.id])
        imgui.unindent()
    imgui.pop_id()


def draw_endpoint(interface, provider):
    current = _base_urls.get(provider.id)
    if current is None:
        current = _base_urls[provider.id] = provider.settings.get('base_url') \
            or provider.default_base_url
    imgui.set_next_item_width(420)
    changed, value = imgui.input_text(label('Base URL'), current)
    if changed:
        _base_urls[provider.id] = value
    imgui.same_line()
    if imgui.small_button(label('Use this endpoint')):
        provider.settings['base_url'] = _base_urls[provider.id].strip()
        refresh(interface, True)
    imgui.text_disabled(tr('Applies for this session. The default is ')
                        + (provider.default_base_url or tr('not set')))


def draw_key(interface, provider):
    global _message
    state = credentials.status(provider.id)
    imgui.text_disabled('%s: %s (%s)' % (tr('API key'),
                                         tr('configured') if state['configured'] else tr('none'),
                                         tr(state['protection'])))
    if state['source'] == 'environment':
        imgui.text_disabled(tr('Taken from the environment variable ')
                            + state['environmentVariable']
                            + tr('. Nothing is stored by the Tool.'))
        return
    value = _entry.get(provider.id, '')
    imgui.set_next_item_width(420)
    changed, value = imgui.input_text(label('New key###key'), value,
                                      imgui.InputTextFlags_.password)
    if changed:
        _entry[provider.id] = value
    imgui.same_line()
    imgui.begin_disabled(not _entry.get(provider.id, '').strip())
    if imgui.button(label('Store')):
        try:
            credentials.store(provider.id, _entry[provider.id].strip())
            _entry[provider.id] = ''
            _message = tr('The key was stored for ') + provider.name
            refresh(interface, True)
        except CyToolError as exc:
            _message = str(exc)
    imgui.end_disabled()
    if state['configured']:
        imgui.same_line()
        if imgui.button(label('Remove the stored key')):
            credentials.clear(provider.id)
            _message = tr('The stored key was removed for ') + provider.name
            refresh(interface, True)
    if not credentials.protected():
        imgui.text_colored((0.9, 0.7, 0.4, 1.0),
                           tr('No OS secret store is available here: the key is written to a '
                              'file readable by this account only, and is not encrypted.'))
