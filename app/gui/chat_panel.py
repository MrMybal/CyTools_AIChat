"""The Chat tab: the conversation list on the left, one tab per open conversation.

Several conversations are open at once and each one streams into its own transcript, so a
long reply from a local model does not stop another tab from talking to a remote provider.
Closing a tab only closes the tab; the conversation stays in the list and on disk.
"""
from imgui_bundle import ImVec2

from cytools_core import CyToolError
from ui_common import imgui, label, tr

from aichat import conversations, credentials, library, presets
from .widgets import Async, bytes_label, combo, copy_button, status_dot, wrapped

SIDEBAR_WIDTH = 270.0
INPUT_HEIGHT = 92.0
ROLE_COLOURS = {'user': (0.55, 0.78, 1.0, 1.0), 'assistant': (0.62, 0.92, 0.70, 1.0),
                'system': (0.75, 0.75, 0.75, 1.0)}

_providers = Async()
_models = {}
_filter = ''
_confirm_delete = ''


def provider_reports(interface):
    """Detection is a background call; until it lands the list shows the plain identifiers."""
    if not _providers.ready and not _providers.running:
        _providers.start(lambda: interface.runtime.aichat.detect(), 'providers')
    return _providers.take([]) or []


def provider_ids(interface):
    return interface.runtime.aichat.ids()


def catalogue_entry(model):
    """The catalogue row for a model id, or an empty one for a registered local file."""
    if not model or model.startswith('local:'):
        return {}
    try:
        from aichat import catalog
        return catalog.entry(model)
    except CyToolError:
        return {}


def provider_label(interface, provider_id):
    if not provider_id:
        return tr('Choose a provider')
    provider = interface.runtime.aichat.providers.get(provider_id)
    return provider.name if provider else provider_id


def models_for(interface, provider_id, transport):
    key = '%s/%s' % (provider_id, transport)
    task = _models.get(key)
    if task is None:
        task = _models[key] = Async()
    return task


def draw(interface):
    draw_sidebar(interface)
    imgui.same_line()
    if imgui.begin_child('##aichat-tabs', ImVec2(0, 0)):
        draw_tabs(interface)
    imgui.end_child()


# ---------------------------------------------------------------------- sidebar

def draw_sidebar(interface):
    global _filter, _confirm_delete
    if not imgui.begin_child('##aichat-conversations', ImVec2(SIDEBAR_WIDTH, 0),
                             child_flags=imgui.ChildFlags_.borders):
        imgui.end_child()
        return
    if imgui.button(label('New conversation'), ImVec2(-1, 0)):
        interface.new_tab()
    imgui.set_next_item_width(-1)
    _, _filter = imgui.input_text(label('##filter'), _filter)
    if imgui.is_item_hovered():
        imgui.set_tooltip(tr('Filter conversations by title'))
    imgui.separator()
    needle = _filter.strip().lower()
    try:
        rows = conversations.listing()
    except CyToolError as exc:
        wrapped(str(exc))
        imgui.end_child()
        return
    open_ids = {tab.id for tab in interface.tabs}
    for row in rows:
        if needle and needle not in row['title'].lower():
            continue
        imgui.push_id(row['id'])
        opened = row['id'] in open_ids
        selected = row['id'] == interface.selected
        if imgui.selectable(row['title'][:46] + ('###row'), selected)[0]:
            interface.open_tab(row['id'])
        if imgui.is_item_hovered():
            imgui.set_tooltip('%s\n%s · %s\n%s' % (
                row['title'], row['providerId'] or tr('no provider'),
                row['model'] or tr('no model'), row['updated'][:19]))
        imgui.text_disabled('%s%s · %d %s' % ('* ' if opened else '',
                                                    row['providerId'] or '—',
                                                    row['messageCount'], tr('messages')))
        if imgui.begin_popup_context_item('##menu'):
            if imgui.menu_item(label('Open in a tab'), '', False)[0]:
                interface.open_tab(row['id'])
            if imgui.menu_item(label('Export to Markdown'), '', False)[0]:
                export(interface, row['id'], 'markdown')
            if imgui.menu_item(label('Export to JSON'), '', False)[0]:
                export(interface, row['id'], 'json')
            if imgui.menu_item(label('Delete'), '', False)[0]:
                _confirm_delete = row['id']
            imgui.end_popup()
        imgui.pop_id()
        imgui.separator()
    imgui.end_child()
    draw_delete_confirmation(interface)


def draw_delete_confirmation(interface):
    global _confirm_delete
    if not _confirm_delete:
        return
    imgui.open_popup(tr('Delete this conversation?') + '###delete-conversation')
    opened, _ = imgui.begin_popup_modal(tr('Delete this conversation?') + '###delete-conversation',
                                        None, imgui.WindowFlags_.always_auto_resize)
    if opened:
        wrapped(tr('The transcript is moved to data/conversations/deleted and kept there. '
                   'It is not sent anywhere and it is not erased.'))
        if imgui.button(label('Delete')):
            try:
                interface.delete_conversation(_confirm_delete)
            except CyToolError as exc:
                interface.error = str(exc)
            _confirm_delete = ''
            imgui.close_current_popup()
        imgui.same_line()
        if imgui.button(label('Cancel')):
            _confirm_delete = ''
            imgui.close_current_popup()
        imgui.end_popup()


def export(interface, conversation_id, fmt):
    try:
        interface.submit('conversation_export', {'conversation': conversation_id, 'format': fmt})
        interface.message = tr('Export started; the file appears in data/exports.')
    except CyToolError as exc:
        interface.error = str(exc)


# ---------------------------------------------------------------------- tabs

def draw_tabs(interface):
    if interface.message:
        imgui.text_disabled(interface.message)
    if interface.error:
        imgui.text_colored((0.9, 0.5, 0.45, 1.0), interface.error)
        imgui.same_line()
        if imgui.small_button(label('Dismiss')):
            interface.error = ''
    flags = imgui.TabBarFlags_.reorderable | imgui.TabBarFlags_.auto_select_new_tabs \
        | imgui.TabBarFlags_.tab_list_popup_button | imgui.TabBarFlags_.fitting_policy_scroll
    if not imgui.begin_tab_bar('##aichat-conversation-tabs', flags):
        return
    closing = ''
    for tab in list(interface.tabs):
        imgui.push_id(tab.id)
        title = tab.title[:28] + ('...' if len(tab.title) > 28 else '')
        if tab.busy:
            title = '* ' + title
        item_flags = imgui.TabItemFlags_.set_selected if interface.selected == tab.id \
            and not imgui.is_any_item_active() else 0
        opened, keep = imgui.begin_tab_item(title + '###tab-' + tab.id, True, item_flags)
        if opened:
            if interface.selected != tab.id:
                interface.selected = tab.id
                interface.persist()
            draw_conversation(interface, tab)
            imgui.end_tab_item()
        if keep is False:
            closing = tab.id
        imgui.pop_id()
    if imgui.tab_item_button('+###new-tab', imgui.TabItemFlags_.trailing):
        interface.new_tab()
    imgui.end_tab_bar()
    if closing:
        interface.close_tab(closing)


def draw_conversation(interface, tab):
    draw_header(interface, tab)
    height = -(INPUT_HEIGHT + imgui.get_frame_height_with_spacing() * 2)
    if imgui.begin_child('##transcript', ImVec2(0, height), child_flags=imgui.ChildFlags_.borders):
        draw_transcript(interface, tab)
    imgui.end_child()
    draw_composer(interface, tab)


def draw_header(interface, tab):
    document = tab.document
    # Each combo is followed by its own label, so the row needs room for both.
    width = max(120.0, imgui.get_content_region_avail().x / 4 - 95)
    ids = [''] + provider_ids(interface)
    changed, provider_id = combo(label('Provider'), ids, document.get('providerId', ''),
                                 lambda value: provider_label(interface, value), width)
    if changed:
        interface.update_document(tab, providerId=provider_id, transport='', model='')
    imgui.same_line()
    provider = interface.runtime.aichat.providers.get(document.get('providerId', ''))
    transports = [''] + list(provider.transports) if provider else ['']
    changed, transport = combo(label('Transport'), transports, document.get('transport', ''),
                               lambda value: value or tr('default'), width * 0.8)
    if changed:
        interface.update_document(tab, transport=transport)
    imgui.same_line()
    draw_model_selector(interface, tab, width)
    imgui.same_line()
    preset_ids = [''] + [item['id'] for item in interface.presets]
    names = {item['id']: item['name'] for item in interface.presets}
    changed, preset_id = combo(label('Preset'), preset_ids, document.get('presetId', ''),
                               lambda value: names.get(value, tr('none')), width * 0.8)
    if changed:
        apply_preset(interface, tab, preset_id)
    if provider is not None:
        kind = tr('The provider keeps the history; this Tool stores a copy and resumes its session.') \
            if provider.kind == 'session' else \
            tr('This Tool sends the stored transcript on every turn; it is the context.')
        imgui.text_disabled(kind)
        if provider.id in credentials.ENVIRONMENT or provider.requires_api_key:
            state = credentials.status(provider.id)
            if not state['configured']:
                imgui.same_line()
                imgui.text_colored((0.9, 0.7, 0.4, 1.0), tr('No API key configured'))
    draw_settings(interface, tab)


def draw_model_selector(interface, tab, width):
    document = tab.document
    provider_id = document.get('providerId', '')
    transport = document.get('transport', '')
    task = models_for(interface, provider_id, transport)
    rows = task.take([]) or []
    imgui.begin_group()
    if rows:
        ids = [''] + [row['id'] for row in rows]
        names = {row['id']: row.get('name') or row['id'] for row in rows}
        changed, model = combo(label('Model'), ids, document.get('model', ''),
                               lambda value: names.get(value, value or tr('not set')), width)
        if changed:
            interface.update_document(tab, model=model)
    else:
        imgui.set_next_item_width(width)
        changed, model = imgui.input_text(label('Model'), document.get('model', ''))
        if changed:
            interface.update_document(tab, model=model)
    if imgui.is_item_hovered():
        imgui.set_tooltip(tr('Type a model identifier, or press Refresh to ask the provider.'))
    imgui.same_line()
    if task.running:
        imgui.text_disabled(tr('Loading...'))
    elif imgui.small_button(label('Refresh###refresh-models')):
        if provider_id:
            provider = interface.runtime.aichat.get(provider_id)
            task.start(lambda: provider.list_models(transport), 'models')
    if task.error:
        imgui.text_colored((0.9, 0.6, 0.45, 1.0), task.error[:90])
    imgui.end_group()


def apply_preset(interface, tab, preset_id):
    if not preset_id:
        interface.update_document(tab, presetId='')
        return
    try:
        preset = presets.load(preset_id)
    except CyToolError as exc:
        tab.error = str(exc)
        return
    settings = dict(tab.document.get('settings') or {})
    settings.update(preset['settings'])
    interface.update_document(tab, presetId=preset_id, settings=settings,
                              systemPrompt=preset.get('systemPrompt', '')
                              or tab.document.get('systemPrompt', ''))


def draw_settings(interface, tab):
    document = tab.document
    if not imgui.collapsing_header(label('System prompt and settings')):
        return
    changed, prompt = imgui.input_text_multiline(
        label('System prompt###system'), document.get('systemPrompt', ''), ImVec2(-1, 70))
    if changed:
        interface.update_document(tab, systemPrompt=prompt)
    settings = dict(document.get('settings') or {})
    dirty = False
    width = max(120.0, imgui.get_content_region_avail().x / 4 - 20)

    def number(key, title, minimum, maximum, default, integer=False):
        nonlocal dirty
        current = settings.get(key, default)
        imgui.set_next_item_width(width)
        if integer:
            modified, value = imgui.slider_int(label(title), int(current), int(minimum),
                                               int(maximum))
        else:
            modified, value = imgui.slider_float(label(title), float(current), minimum, maximum)
        if modified:
            settings[key] = int(value) if integer else round(float(value), 3)
            dirty = True

    number('temperature', 'Temperature', 0.0, 2.0, 0.7)
    imgui.same_line()
    number('top_p', 'Top P', 0.0, 1.0, 0.95)
    imgui.same_line()
    number('max_tokens', 'Max tokens', 16, 32768, 2048, integer=True)
    imgui.same_line()
    number('history_limit', 'History limit', 0, 200, 0, integer=True)
    if imgui.is_item_hovered():
        imgui.set_tooltip(tr('0 sends the whole conversation. A session provider ignores this.'))
    provider = interface.runtime.aichat.providers.get(document.get('providerId', ''))
    if provider is not None and provider.supports_lora:
        dirty = draw_local_settings(interface, tab, settings) or dirty
    if dirty:
        interface.update_document(tab, settings=settings)


def draw_local_settings(interface, tab, settings):
    dirty = False
    imgui.separator_text(label('Local engine'))
    width = max(140.0, imgui.get_content_region_avail().x / 4 - 20)
    changed, value = combo(label('Engine'), ['auto', 'cuda', 'cpu'],
                           settings.get('engine', 'auto'),
                           lambda item: {'auto': tr('Automatic'), 'cuda': 'CUDA (GPU)',
                                         'cpu': 'CPU'}[item], width)
    if changed:
        settings['engine'] = value
        dirty = True
    imgui.same_line()
    imgui.set_next_item_width(width)
    changed, value = imgui.slider_int(label('Context tokens'),
                                      int(settings.get('context_tokens', 8192)), 512, 131072)
    if changed:
        settings['context_tokens'] = value
        dirty = True
    imgui.same_line()
    changed, value = imgui.checkbox(label('Keep loaded'), bool(settings.get('keep_loaded', True)))
    if changed:
        settings['keep_loaded'] = value
        dirty = True
    entry = catalogue_entry(tab.document.get('model', ''))
    if entry.get('contextTokens'):
        imgui.text_disabled('%s %s %s' % (tr('This model declares a window of'),
                                          entry['contextTokens'], tr('tokens; a larger request '
                                                                     'is capped to it.')))
    levels = ['', 'default', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
    current = settings.get('reasoning_effort', '')
    changed, value = combo(label('Reasoning effort'), levels, current,
                           lambda item: (tr('From the catalogue') if not item else item), width)
    if changed:
        if value:
            settings['reasoning_effort'] = value
        else:
            settings.pop('reasoning_effort', None)
        dirty = True
    if imgui.is_item_hovered():
        imgui.set_tooltip(tr('Only a reasoning model uses this. Its thinking is streamed '
                             'separately and is never stored as the reply.'))
    if not current and entry.get('reasoningEffort'):
        imgui.same_line()
        imgui.text_disabled('%s %s' % (tr('catalogue value:'), entry['reasoningEffort']))
    adapters = library.adapters()
    if not adapters:
        imgui.text_disabled(tr('No LoRA adapter is registered. Install one in Models, or add a '
                               'local .gguf adapter in the model library.'))
        return dirty
    selected = {item['id']: float(item.get('strength', 1.0))
                for item in settings.get('loras') or []}
    imgui.text_disabled(tr('LoRA adapters apply to the local model only. Changing which ones are '
                           'loaded restarts the server; changing a strength does not.'))
    for adapter in adapters:
        imgui.push_id(adapter['id'])
        active = adapter['id'] in selected
        changed, active = imgui.checkbox(adapter['name'] + '###use', active)
        if changed:
            if active:
                selected[adapter['id']] = 1.0
            else:
                selected.pop(adapter['id'], None)
            dirty = True
        if active:
            imgui.same_line()
            imgui.set_next_item_width(180)
            changed, strength = imgui.slider_float(label('Strength###strength'),
                                                   selected[adapter['id']], -2.0, 2.0)
            if changed:
                selected[adapter['id']] = round(strength, 3)
                dirty = True
        imgui.pop_id()
    if dirty:
        settings['loras'] = [{'id': key, 'strength': value} for key, value in selected.items()]
    return dirty


# ---------------------------------------------------------------------- transcript

def draw_transcript(interface, tab):
    document = tab.document
    messages = document.get('messages', [])
    if not messages and not tab.live:
        imgui.text_disabled(tr('No message yet. Write below and press Send.'))
    for message in messages:
        draw_message(message)
    live = tab.live_text()
    if live or tab.busy:
        imgui.separator()
        imgui.text_colored(ROLE_COLOURS['assistant'], tr('Assistant') + ' ...')
        if tab.live_thinking:
            changed, tab.show_thinking = imgui.checkbox(label('Show reasoning###thinking'),
                                                        tab.show_thinking)
            if tab.show_thinking:
                imgui.push_style_color(imgui.Col_.text, (0.6, 0.6, 0.65, 1.0))
                wrapped(''.join(tab.live_thinking))
                imgui.pop_style_color()
        wrapped(live or tr('Waiting for the first tokens...'))
    if tab.status:
        imgui.text_disabled(tab.status)
    if tab.error:
        imgui.text_colored((0.9, 0.5, 0.45, 1.0), tab.error)
    if tab.scroll_to_bottom:
        imgui.set_scroll_here_y(1.0)
        tab.scroll_to_bottom = False


def draw_message(message):
    role = message.get('role', 'assistant')
    imgui.push_id(message['id'])
    imgui.separator()
    imgui.text_colored(ROLE_COLOURS.get(role, ROLE_COLOURS['assistant']),
                       {'user': tr('You'), 'assistant': tr('Assistant'),
                        'system': tr('System')}.get(role, role))
    imgui.same_line()
    details = [message.get('created', '')[:19]]
    if message.get('model'):
        details.append(message['model'])
    if message.get('seconds'):
        details.append('%.1fs' % message['seconds'])
    usage = message.get('usage') or {}
    tokens = usage.get('total', usage).get('totalTokens') if isinstance(usage, dict) else None
    if tokens:
        details.append('%s tokens' % tokens)
    imgui.text_disabled(' · '.join(str(part) for part in details if part))
    imgui.same_line()
    copy_button(tr('Copy'), message.get('text', ''), message['id'])
    if message.get('failed'):
        # A cancelled turn usually holds what had already been streamed. Showing the text as
        # well as the reason is the difference between "it stopped here" and "nothing happened".
        if message.get('text'):
            wrapped(message['text'])
        imgui.text_colored((0.9, 0.5, 0.45, 1.0),
                           '%s: %s' % (tr(message.get('error', 'Error')),
                                       message.get('errorMessage', '')))
    else:
        wrapped(message.get('text', ''))
    if message.get('systemPromptFolded'):
        imgui.text_disabled(tr('The system prompt was folded into this message: this provider '
                               'has no separate system field.'))
    if message.get('loras'):
        imgui.text_disabled(tr('Adapters: ') + ', '.join(
            '%s @ %s' % (item.get('name', item.get('id')), item.get('strength'))
            for item in message['loras']))
    imgui.pop_id()


# ---------------------------------------------------------------------- composer

def draw_composer(interface, tab):
    document = tab.document
    ready = bool(document.get('providerId'))
    imgui.begin_disabled(tab.busy)
    changed, value = imgui.input_text_multiline(label('##composer'), tab.input,
                                                ImVec2(-1, INPUT_HEIGHT))
    if changed:
        tab.input = value
    imgui.end_disabled()
    if tab.busy:
        if imgui.button(label('Cancel'), ImVec2(120, 0)):
            interface.cancel(tab)
        imgui.same_line()
        job = tab.job or {}
        progress = (job.get('progress') or {})
        imgui.progress_bar(min(1.0, float(progress.get('percent', 0)) / 100.0), ImVec2(-1, 0),
                           '%s  %s' % (job.get('state', ''), progress.get('currentStep', '')))
    else:
        imgui.begin_disabled(not ready or not tab.input.strip())
        if imgui.button(label('Send'), ImVec2(120, 0)):
            interface.send(tab)
        imgui.end_disabled()
        imgui.same_line()
        if not ready:
            imgui.text_colored((0.9, 0.7, 0.4, 1.0),
                               tr('Choose a provider before sending.'))
        else:
            if imgui.small_button(label('Copy conversation')):
                imgui.set_clipboard_text('\n\n'.join(
                    '%s: %s' % (item['role'], item.get('text', ''))
                    for item in document.get('messages', [])))
            imgui.same_line()
            if imgui.small_button(label('Export Markdown')):
                export(interface, tab.id, 'markdown')
            imgui.same_line()
            if imgui.small_button(label('New provider session')):
                try:
                    conversations.forget_native(tab.id)
                    tab.reload()
                    interface.message = tr('The next turn starts a fresh provider session.')
                except CyToolError as exc:
                    tab.error = str(exc)
            if document.get('native'):
                imgui.same_line()
                imgui.text_disabled(tr('Provider session: ')
                                    + ', '.join(sorted(document['native'])))
