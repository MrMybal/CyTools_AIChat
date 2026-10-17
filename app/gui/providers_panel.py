"""The Providers tab: what was found on this machine, and the keys or endpoints it needs.

An API key typed here is written straight to the credential store by this process. It never
becomes a job parameter, so it cannot end up in the job history, in a saved configuration,
in an event or in the application log. The field only ever shows what is being typed; a
stored key is never read back into the interface, only its presence and protection.

Each provider is a CyUI card: its state at a glance, the details on demand.
"""
import webbrowser

from imgui_bundle import ImVec2

import cyui
from cytools_core import CyToolError
from ui_common import imgui, tr

from aichat import credentials
from .widgets import Async, card

_detect = Async()
_entry = {}
_base_urls = {}
_expanded = {}

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


def status_tone(report):
    if not report:
        return 'neutral'
    if report.get('available'):
        return 'success'
    status = str(report.get('status', ''))
    if status == 'NotImplemented':
        return 'neutral'
    if 'Authentication' in status:
        return 'warning'
    return 'error'


def draw(interface):
    refresh(interface)
    cyui.panel_header(tr('Providers'), tr('Agent command lines, HTTP endpoints and the local '
                                          'model found on this machine.'))
    label = tr('Detect again')
    width = cyui.button_width(label) + imgui.get_font_size() * 2
    imgui.same_line()
    cyui.align_right(width)
    with cyui.scoped_disabled(_detect.running):
        if cyui.icon_text_button(cyui.icon.refresh, label + '###detect', 'primary',
                                 (width, 0)):
            refresh(interface, True)
    cyui.tooltip(tr('Detection spawns each agent CLI once and queries each endpoint. Nothing is '
                    'sent to a model.'))
    if _detect.running:
        cyui.spinner('##detecting', 6)
        imgui.same_line()
        cyui.text_faint(tr('Detecting...'))
    if _detect.error:
        cyui.callout('error', _detect.error)
    cyui.divider()
    reports = {row['id']: row for row in (_detect.take([]) or [])}
    if imgui.begin_child('##providers-list', ImVec2(0, 0)):
        for provider_id in interface.runtime.aichat.ids():
            provider = interface.runtime.aichat.get(provider_id)
            draw_provider(interface, provider, reports.get(provider_id, {}))
    imgui.end_child()


def draw_provider(interface, provider, report):
    imgui.push_id(provider.id)
    tone = status_tone(report)
    expanded = _expanded.get(provider.id, False)
    with card('##provider'):
        cyui.status_dot(cyui.tone_colour(tone) if report else cyui.palette().textFaint)
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.heading(provider.name, 3)
        imgui.same_line(0, cyui.dp(8))
        cyui.badge(tr(report.get('status', 'not detected yet')).upper(), tone)
        imgui.same_line()
        cyui.badge(tr('SESSION').upper() if provider.kind == 'session' else tr('STATELESS'),
                   'info' if provider.kind == 'session' else 'neutral')
        if provider.id in KEY_PROVIDERS and not credentials.status(provider.id)['configured']:
            imgui.same_line()
            cyui.badge(tr('NO API KEY').upper(), 'warning')
        if report.get('version'):
            imgui.same_line(0, cyui.dp(10))
            imgui.align_text_to_frame_padding()
            cyui.text_faint(str(report['version'])[:60])
        buttons = 2 if provider.id in HELP_PAGES else 1
        imgui.same_line()
        cyui.align_right(buttons * (imgui.get_frame_height() + cyui.dp(2) + imgui.get_style().item_spacing.x))
        if provider.id in HELP_PAGES:
            if cyui.icon_button(cyui.icon.globe, tr('Open the official page')):
                webbrowser.open(HELP_PAGES[provider.id])
            imgui.same_line()
        if cyui.icon_button(cyui.icon.chevron_up if expanded else cyui.icon.chevron_down,
                            tr('Hide the details') if expanded else tr('Show the details')):
            _expanded[provider.id] = not expanded
        if report.get('detail') and not report.get('available'):
            cyui.text_faint(str(report['detail']))
        if expanded:
            draw_details(interface, provider, report)
    cyui.space(2)
    imgui.pop_id()


def draw_details(interface, provider, report):
    cyui.space(2)
    imgui.text_wrapped(tr(provider.documentation))
    cyui.space(4)
    if cyui.begin_properties('##facts'):
        cyui.property(tr('Transports'))
        imgui.text_wrapped(', '.join(provider.transports) or tr('none implemented'))
        cyui.property(tr('History'))
        imgui.text_wrapped(tr('Session provider: it keeps the history and is resumed by identifier.')
                           if provider.kind == 'session' else
                           tr('Stateless provider: the stored transcript is sent on every turn.'))
        if getattr(provider, 'untested', ()):
            cyui.property(tr('Not validated'))
            cyui.text_coloured(cyui.palette().warning, ', '.join(provider.untested))
        if report.get('command'):
            cyui.property(tr('Command'))
            cyui.text_mono(report['command'])
        if report.get('version'):
            cyui.property(tr('Version'))
            imgui.text_wrapped(str(report['version'])[:160])
        if provider.id in ENDPOINT_PROVIDERS:
            draw_endpoint(interface, provider)
        if provider.id in KEY_PROVIDERS:
            draw_key(interface, provider)
        cyui.end_properties()
    if provider.id in KEY_PROVIDERS and not credentials.protected():
        cyui.callout('warning', tr('No OS secret store is available here: the key is written to '
                                      'a file readable by this account only, and is not '
                                      'encrypted.'))


def draw_endpoint(interface, provider):
    current = _base_urls.get(provider.id)
    if current is None:
        current = _base_urls[provider.id] = provider.settings.get('base_url') \
            or provider.default_base_url
    cyui.property(tr('Base URL'), tr('Applies for this session. The default is ')
                      + (provider.default_base_url or tr('not set')))
    apply_label = tr('Use') + '###use-endpoint'
    imgui.set_next_item_width(imgui.get_content_region_avail().x - cyui.button_width(apply_label)
                              - imgui.get_style().item_spacing.x)
    changed, value = imgui.input_text('##base-url', current)
    if changed:
        _base_urls[provider.id] = value
    imgui.same_line()
    if cyui.button(apply_label):
        provider.settings['base_url'] = _base_urls[provider.id].strip()
        refresh(interface, True)
        cyui.notify(tr('Endpoint updated for this session.'), 'info')


def draw_key(interface, provider):
    state = credentials.status(provider.id)
    cyui.property(tr('API key'))
    if state['configured']:
        cyui.badge(tr('CONFIGURED').upper(), 'success')
        imgui.same_line()
        cyui.text_faint(tr(state['protection']))
    else:
        cyui.badge(tr('NONE').upper(), 'warning')
    if state['source'] == 'environment':
        cyui.property(tr('Source'))
        imgui.text_wrapped(tr('Taken from the environment variable ') + state['environmentVariable']
                           + tr('. Nothing is stored by the Tool.'))
        return
    cyui.property(tr('New key'))
    store_label = tr('Store') + '###store-key'
    remove_room = (imgui.get_frame_height() + cyui.dp(2) + imgui.get_style().item_spacing.x) \
        if state['configured'] else 0.0
    imgui.set_next_item_width(imgui.get_content_region_avail().x - cyui.button_width(store_label)
                              - imgui.get_style().item_spacing.x - remove_room)
    changed, value = imgui.input_text_with_hint('##key', tr('paste the key here'),
                                                _entry.get(provider.id, ''),
                                                imgui.InputTextFlags_.password)
    if changed:
        _entry[provider.id] = value
    imgui.same_line()
    with cyui.scoped_disabled(not _entry.get(provider.id, '').strip()):
        if cyui.button(store_label):
            try:
                credentials.store(provider.id, _entry[provider.id].strip())
                _entry[provider.id] = ''
                cyui.notify(tr('The key was stored for ') + provider.name, 'success')
                refresh(interface, True)
            except CyToolError as exc:
                cyui.notify(str(exc), 'error')
    if state['configured']:
        imgui.same_line()
        if cyui.icon_button(cyui.icon.trash, tr('Remove the stored key')):
            credentials.clear(provider.id)
            cyui.notify(tr('The stored key was removed for ') + provider.name, 'warning')
            refresh(interface, True)
