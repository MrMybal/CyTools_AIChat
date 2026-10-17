"""The Chat tab: the conversation list on the left, one tab per open conversation.

Several conversations are open at once and each one streams into its own transcript, so a
long reply from a local model does not stop another tab from talking to a remote provider.
Closing a tab only closes the tab; the conversation stays in the list and on disk.

Speech: the microphone button dictates into the message box (it never sends by itself), and the
speaker button on a reply reads it with the voice chosen in the Speech tab.

Drawn with CyUI (app/cyui): palette roles, one primary button (Send), icon buttons with
tooltips, cards for messages and settings, property tables, empty states.
"""
from imgui_bundle import ImVec2

import cyui
from cytools_core import CyToolError
from ui_common import imgui, label, tr

from aichat import conversations, credentials, library, presets
from .widgets import Async, card, combo, selectable_text, wrapped

SIDEBAR_WIDTH = 280.0
INPUT_LINES = 4

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


def role_colour(role):
    """Speakers are a series, not a state: categorical colours, never the accent.

    The categorical set is bright; on a light theme it is darkened so a name never reads
    light-on-light.
    """
    colour = {'user': cyui.categorical(1), 'assistant': cyui.categorical(2)}.get(role)
    if colour is None:
        return cyui.palette().textDim
    return cyui.darker(colour, 0.45) if cyui.is_light() else colour


def draw(interface):
    draw_sidebar(interface)
    imgui.same_line(0, cyui.dp(6))
    if imgui.begin_child('##aichat-tabs', ImVec2(0, 0)):
        draw_tabs(interface)
    imgui.end_child()


# ---------------------------------------------------------------------- sidebar

def conversation_row(title, subtitle, active, badge_text=''):
    """A CyUI sidebar row with a second, faint line: the title, then the provider and count."""
    p = cyui.palette()
    width = imgui.get_content_region_avail().x
    line = imgui.get_font_size()
    height = imgui.get_frame_height() + cyui.dp(8) + line
    origin = imgui.get_cursor_screen_pos()
    clicked = imgui.invisible_button('##row', ImVec2(width, height))
    hovered = imgui.is_item_hovered()
    draw = imgui.get_window_draw_list()
    rounding = imgui.get_style().frame_rounding + cyui.dp(2)
    corner = ImVec2(origin.x + width, origin.y + height)
    if active:
        draw.add_rect_filled(origin, corner, cyui.alpha(p.accent, 0.16), rounding)
        draw.add_rect(origin, corner, cyui.alpha(p.accent, 0.45), rounding)
    elif hovered:
        draw.add_rect_filled(origin, corner, p.bg3, rounding)
    x = origin.x + cyui.dp(10)
    y = origin.y + (height - line * 2.0) * 0.5
    room = corner.x - x - cyui.dp(8)
    if badge_text:
        with cyui.scoped_font(cyui.bold_font(), 0.74):
            size = imgui.calc_text_size(badge_text)
            b_max = ImVec2(corner.x - cyui.dp(8), y + size.y + cyui.dp(4))
            b_min = ImVec2(b_max.x - size.x - cyui.dp(10), y)
            draw.add_rect_filled(b_min, b_max, p.accent, height)
            draw.add_text(ImVec2(b_min.x + cyui.dp(5), b_min.y + cyui.dp(2)), p.accentText, badge_text)
        room = b_min.x - x - cyui.dp(6)
    with cyui.scoped_font(cyui.bold_font() if active else None, 1.0):
        cyui.clipped_text(draw, ImVec2(x, y), room, p.text if active or hovered else p.textDim, title)
    with cyui.scoped_font(None, 0.86):
        cyui.clipped_text(draw, ImVec2(x, y + line + cyui.dp(1)), corner.x - x - cyui.dp(8),
                          p.textFaint, subtitle)
    imgui.dummy(ImVec2(0, cyui.dp(1)))
    return clicked


def draw_sidebar(interface):
    global _filter, _confirm_delete
    p = cyui.palette()
    with cyui.scoped_color(imgui.Col_.child_bg, p.bg0), \
            cyui.scoped_var(imgui.StyleVar_.window_padding, cyui.dp2(10, 10)):
        shown = imgui.begin_child('##aichat-conversations', ImVec2(cyui.dp(SIDEBAR_WIDTH), 0),
                                  child_flags=imgui.ChildFlags_.always_use_window_padding)
    if not shown:
        imgui.end_child()
        return
    try:
        rows = conversations.listing()
    except CyToolError as exc:
        cyui.callout('error', str(exc))
        imgui.end_child()
        return
    cyui.overline(tr('CONVERSATIONS'), p.textFaint)
    imgui.same_line()
    cyui.badge(str(len(rows)))
    cyui.space(4)
    if cyui.icon_text_button(cyui.icon.add, tr('New conversation') + '###new-conversation',
                             size=(-1, 0)):
        interface.new_tab()
    cyui.space(2)
    _, _filter = cyui.search_field('##filter', _filter, tr('Search conversations'), -1)
    cyui.space(4)
    needle = _filter.strip().lower()
    shown_rows = [row for row in rows if not needle or needle in row['title'].lower()]
    if not shown_rows:
        cyui.empty_state(tr('No conversation') if not rows else tr('Nothing matches'),
                         tr('Press New conversation to start.') if not rows
                         else tr('Try another word.'), cyui.icon.search if rows else cyui.icon.mail)
    busy = {tab.id for tab in interface.tabs if tab.busy}
    for row in shown_rows:
        imgui.push_id(row['id'])
        subtitle = '%s  ·  %d %s' % (row['providerId'] or tr('no provider'), row['messageCount'],
                                     tr('messages'))
        if conversation_row(row['title'], subtitle, row['id'] == interface.selected,
                            tr('busy').upper() if row['id'] in busy else ''):
            interface.open_tab(row['id'])
        cyui.tooltip('%s\n%s  ·  %s\n%s' % (row['title'], row['providerId'] or tr('no provider'),
                                            row['model'] or tr('no model'), row['updated'][:19]))
        if imgui.begin_popup_context_item('##menu'):
            if imgui.menu_item(label('Open in a tab'), '', False)[0]:
                interface.open_tab(row['id'])
            if imgui.menu_item(label('Export to Markdown'), '', False)[0]:
                export(interface, row['id'], 'markdown')
            if imgui.menu_item(label('Export to JSON'), '', False)[0]:
                export(interface, row['id'], 'json')
            imgui.separator()
            if imgui.menu_item(label('Delete'), '', False)[0]:
                _confirm_delete = row['id']
            imgui.end_popup()
        imgui.pop_id()
    imgui.end_child()
    draw_delete_confirmation(interface)


def draw_delete_confirmation(interface):
    global _confirm_delete
    if not _confirm_delete:
        return
    shown, still_open = cyui.begin_modal(tr('Delete this conversation?') + '###delete-conversation',
                                         True)
    if not shown:
        _confirm_delete = ''
        return
    imgui.text_wrapped(tr('The transcript is moved to data/conversations/deleted and kept there. '
                          'It is not sent anywhere and it is not erased.'))
    answer = cyui.modal_buttons(tr('Delete') + '###confirm-delete', tr('Cancel') + '###cancel-delete',
                                danger=True)
    if answer == 1:
        try:
            interface.delete_conversation(_confirm_delete)
            cyui.notify(tr('Conversation moved to data/conversations/deleted.'), 'success')
        except CyToolError as exc:
            interface.error = str(exc)
    if answer or not still_open:
        _confirm_delete = ''
    cyui.end_modal()


def export(interface, conversation_id, fmt):
    try:
        interface.submit('conversation_export', {'conversation': conversation_id, 'format': fmt})
        cyui.notify(tr('Export started; the file appears in data/exports.'), 'info')
    except CyToolError as exc:
        interface.error = str(exc)


# ---------------------------------------------------------------------- tabs

def draw_tabs(interface):
    if interface.message:
        cyui.notify(interface.message, 'info')
        interface.message = ''
    if interface.error:
        cyui.callout('error', interface.error)
        if cyui.ghost_button(tr('Dismiss') + '###dismiss-error'):
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


def composer_height():
    style = imgui.get_style()
    return (imgui.get_text_line_height() * INPUT_LINES + style.frame_padding.y * 2
            + imgui.get_frame_height_with_spacing() + style.item_spacing.y * 2)


def draw_conversation(interface, tab):
    draw_header(interface, tab)
    p = cyui.palette()
    with cyui.scoped_color(imgui.Col_.child_bg, p.bg0), \
            cyui.scoped_var(imgui.StyleVar_.window_padding, cyui.dp2(12, 10),
                            imgui.StyleVar_.child_rounding, cyui.dp(cyui.metrics().rounding_large)):
        shown = imgui.begin_child('##transcript', ImVec2(0, -composer_height()),
                                  child_flags=imgui.ChildFlags_.always_use_window_padding)
    if shown:
        draw_transcript(interface, tab)
    imgui.end_child()
    draw_composer(interface, tab)


# ---------------------------------------------------------------------- header

def field_label(text):
    imgui.align_text_to_frame_padding()
    cyui.text_dim(text)
    imgui.same_line(0, cyui.dp(4))


def draw_header(interface, tab):
    document = tab.document
    provider = interface.runtime.aichat.providers.get(document.get('providerId', ''))
    cyui.begin_toolbar('##conversation-toolbar')
    width = max(cyui.dp(110), imgui.get_content_region_avail().x / 6)
    field_label(tr('Provider'))
    ids = [''] + provider_ids(interface)
    changed, provider_id = combo('##provider', ids, document.get('providerId', ''),
                                 lambda value: provider_label(interface, value), width)
    if changed:
        interface.update_document(tab, providerId=provider_id, transport='', model='')
    transports = [''] + list(provider.transports) if provider else ['']
    if len(transports) > 2:
        imgui.same_line()
        field_label(tr('Transport'))
        changed, transport = combo('##transport', transports, document.get('transport', ''),
                                   lambda value: value or tr('default'), width * 0.8)
        if changed:
            interface.update_document(tab, transport=transport)
    imgui.same_line()
    field_label(tr('Model'))
    draw_model_selector(interface, tab, width * 1.3)
    imgui.same_line()
    field_label(tr('Preset'))
    preset_ids = [''] + [item['id'] for item in interface.presets]
    names = {item['id']: item['name'] for item in interface.presets}
    changed, preset_id = combo('##preset', preset_ids, document.get('presetId', ''),
                               lambda value: names.get(value, tr('none')), width * 0.8)
    if changed:
        apply_preset(interface, tab, preset_id)
    imgui.same_line()
    cyui.align_right(imgui.get_frame_height() + cyui.dp(2))
    if cyui.icon_button(cyui.icon.settings, tr('Conversation settings: system prompt, sampling, '
                                           'local engine and LoRA'), tab.show_settings):
        tab.show_settings = not tab.show_settings
    cyui.end_toolbar()
    draw_provider_state(provider)
    if tab.show_settings:
        draw_settings(interface, tab)


def draw_provider_state(provider):
    if provider is None:
        cyui.text_faint(tr('Choose a provider and a model, then write below.'))
        return
    if provider.kind == 'session':
        cyui.badge(tr('SESSION').upper(), 'info')
        cyui.tooltip(tr('The provider keeps the history; this Tool stores a copy and resumes its '
                        'session.'))
        imgui.same_line()
        cyui.text_faint(tr('The provider keeps the history; this Tool stores a copy and resumes '
                           'its session.'))
    else:
        cyui.badge(tr('STATELESS').upper(), 'neutral')
        cyui.tooltip(tr('This Tool sends the stored transcript on every turn; it is the context.'))
        imgui.same_line()
        cyui.text_faint(tr('This Tool sends the stored transcript on every turn; it is the '
                           'context.'))
    if provider.id in credentials.ENVIRONMENT or provider.requires_api_key:
        if not credentials.status(provider.id)['configured']:
            imgui.same_line()
            cyui.badge(tr('NO API KEY').upper(), 'warning')
            cyui.tooltip(tr('Enter a key for this provider in the Providers tab.'))


def draw_model_selector(interface, tab, width):
    document = tab.document
    provider_id = document.get('providerId', '')
    transport = document.get('transport', '')
    task = models_for(interface, provider_id, transport)
    rows = task.take([]) or []
    refresh = imgui.get_frame_height() + cyui.dp(2)
    if rows:
        ids = [''] + [row['id'] for row in rows]
        names = {row['id']: row.get('name') or row['id'] for row in rows}
        changed, model = combo('##model', ids, document.get('model', ''),
                               lambda value: names.get(value, value or tr('not set')), width)
        if changed:
            interface.update_document(tab, model=model)
    else:
        imgui.set_next_item_width(width)
        changed, model = imgui.input_text_with_hint('##model', tr('model identifier'),
                                                    document.get('model', ''))
        if changed:
            interface.update_document(tab, model=model)
    cyui.tooltip(tr('Type a model identifier, or press the refresh button to ask the provider.'))
    imgui.same_line(0, cyui.dp(2))
    if task.running:
        cyui.spinner('##models-loading', 7)
    elif cyui.icon_button(cyui.icon.refresh, tr('Ask the provider for its models'),
                          size=(refresh, 0)):
        if provider_id:
            provider = interface.runtime.aichat.get(provider_id)
            task.start(lambda: provider.list_models(transport), 'models')
    if task.error:
        imgui.same_line()
        cyui.badge(tr('ERROR').upper(), 'error')
        cyui.tooltip(task.error)


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


# ---------------------------------------------------------------------- settings

def draw_settings(interface, tab):
    document = tab.document
    settings = dict(document.get('settings') or {})
    dirty = False
    with card('##settings-card', tr('Conversation settings')):
        cyui.text_faint(tr('System prompt'))
        changed, prompt = imgui.input_text_multiline(
            '##system', document.get('systemPrompt', ''),
            ImVec2(-1, imgui.get_text_line_height() * 3 + imgui.get_style().frame_padding.y * 2))
        if changed:
            interface.update_document(tab, systemPrompt=prompt)
        cyui.space(4)
        if cyui.begin_properties('##sampling'):
            dirty = sampling_rows(settings) or dirty
            cyui.end_properties()
        provider = interface.runtime.aichat.providers.get(document.get('providerId', ''))
        if provider is not None and provider.supports_lora:
            cyui.space(4)
            if cyui.begin_section(tr('Local engine') + '###local-engine'):
                dirty = draw_local_settings(interface, tab, settings) or dirty
                cyui.end_section()
    if dirty:
        interface.update_document(tab, settings=settings)


def sampling_rows(settings):
    dirty = False

    def slider(key, title, minimum, maximum, default, fmt, help_text=None, integer=False):
        nonlocal dirty
        cyui.property(tr(title), tr(help_text) if help_text else None)
        current = settings.get(key, default)
        if integer:
            changed, value = imgui.slider_int('##' + key, int(current), int(minimum), int(maximum))
        else:
            changed, value = cyui.slider_bar('##' + key, float(current), minimum, maximum, fmt, -1)
        if changed:
            settings[key] = int(value) if integer else round(float(value), 3)
            dirty = True

    slider('temperature', 'Temperature', 0.0, 2.0, 0.7, '%.2f',
           'Higher is more varied, lower is more predictable.')
    slider('top_p', 'Top P', 0.0, 1.0, 0.95, '%.2f')
    slider('max_tokens', 'Max tokens', 16, 32768, 2048, '', 'The longest reply allowed.',
           integer=True)
    slider('history_limit', 'History limit', 0, 200, 0, '',
           '0 sends the whole conversation. A session provider ignores this.', integer=True)
    return dirty


def draw_local_settings(interface, tab, settings):
    dirty = False
    entry = catalogue_entry(tab.document.get('model', ''))
    if cyui.begin_properties('##local-engine-properties'):
        cyui.property(tr('Engine'))
        engines = ['auto', 'cuda', 'cpu']
        changed, index = cyui.segmented('##engine', [tr('Automatic'), 'CUDA (GPU)', 'CPU'],
                                        engines.index(settings.get('engine', 'auto'))
                                        if settings.get('engine', 'auto') in engines else 0, -1)
        if changed:
            settings['engine'] = engines[index]
            dirty = True
        help_text = None
        if entry.get('contextTokens'):
            help_text = '%s %s %s' % (tr('This model declares a window of'), entry['contextTokens'],
                                      tr('tokens; a larger request is capped to it.'))
        cyui.property(tr('Context tokens'), help_text)
        changed, value = imgui.slider_int('##context', int(settings.get('context_tokens', 8192)),
                                          512, 131072)
        if changed:
            settings['context_tokens'] = value
            dirty = True
        cyui.property(tr('Keep loaded'), tr('Keep the model in memory after the reply so the '
                                                'next turn starts at once.'))
        changed, value = cyui.toggle_switch('##keep-loaded', bool(settings.get('keep_loaded', True)))
        if changed:
            settings['keep_loaded'] = value
            dirty = True
        cyui.property(tr('Reasoning effort'), tr('Only a reasoning model uses this. Its thinking '
                                                     'is streamed separately and is never stored '
                                                     'as the reply.'))
        levels = ['', 'default', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
        current = settings.get('reasoning_effort', '')
        catalogue_value = entry.get('reasoningEffort', '')
        changed, value = combo('##reasoning', levels, current,
                               lambda item: item or ('%s (%s)' % (tr('From the catalogue'),
                                                                  catalogue_value)
                                                     if catalogue_value else tr('From the catalogue')))
        if changed:
            if value:
                settings['reasoning_effort'] = value
            else:
                settings.pop('reasoning_effort', None)
            dirty = True
        cyui.end_properties()
    adapters = library.adapters()
    cyui.space(4)
    cyui.section_title(tr('LoRA adapters'))
    if not adapters:
        cyui.text_faint(tr('No LoRA adapter is registered. Install one in Models, or add a local '
                           '.gguf adapter in the model library.'))
        return dirty
    cyui.text_faint(tr('LoRA adapters apply to the local model only. Changing which ones are '
                       'loaded restarts the server; changing a strength does not.'))
    selected = {item['id']: float(item.get('strength', 1.0))
                for item in settings.get('loras') or []}
    if cyui.begin_properties('##loras'):
        for adapter in adapters:
            imgui.push_id(adapter['id'])
            active = adapter['id'] in selected
            cyui.property(adapter['name'])
            changed, active = cyui.toggle_switch('##use', active)
            if changed:
                if active:
                    selected[adapter['id']] = 1.0
                else:
                    selected.pop(adapter['id'], None)
                dirty = True
            if active:
                imgui.same_line()
                changed, strength = cyui.slider_bar('##strength', selected[adapter['id']], -2.0, 2.0,
                                                    tr('strength') + ' %.2f', -1)
                if changed:
                    selected[adapter['id']] = round(strength, 3)
                    dirty = True
            imgui.pop_id()
        cyui.end_properties()
    if dirty:
        settings['loras'] = [{'id': key, 'strength': value} for key, value in selected.items()]
    return dirty


# ---------------------------------------------------------------------- transcript

def draw_transcript(interface, tab):
    document = tab.document
    messages = document.get('messages', [])
    if not messages and not tab.live and not tab.busy:
        cyui.empty_state(tr('No message yet'), tr('Write below and press Send (Ctrl+Enter).'),
                         cyui.icon.edit)
    for message in messages:
        draw_message(interface, tab, message)
    live = tab.live_text()
    if live or tab.busy:
        draw_live(tab, live)
    if tab.error:
        cyui.callout('error', tab.error)
    if tab.scroll_to_bottom:
        # Cards measure their height on the frame they first appear, so the bottom is only known
        # a couple of frames later: keep scrolling down until then.
        imgui.set_scroll_here_y(1.0)
        tab.scroll_frames = getattr(tab, 'scroll_frames', 0) + 1
        if tab.scroll_frames >= 3:
            tab.scroll_to_bottom = False
            tab.scroll_frames = 0


def message_header(role, details):
    imgui.align_text_to_frame_padding()
    with cyui.scoped_font(cyui.bold_font(), 1.0):
        cyui.text_coloured(role_colour(role), {'user': tr('You'), 'assistant': tr('Assistant'),
                                               'system': tr('System')}.get(role, role))
    if details:
        imgui.same_line(0, cyui.dp(8))
        imgui.align_text_to_frame_padding()
        cyui.text_faint('  ·  '.join(str(part) for part in details if part))


def draw_message(interface, tab, message):
    role = message.get('role', 'assistant')
    imgui.push_id(message['id'])
    details = [message.get('created', '')[:16].replace('T', ' ')]
    if message.get('model'):
        details.append(message['model'])
    if message.get('seconds'):
        details.append('%.1f s' % message['seconds'])
    usage = message.get('usage') or {}
    tokens = usage.get('total', usage).get('totalTokens') if isinstance(usage, dict) else None
    if tokens:
        details.append('%s tokens' % tokens)
    with card('##message'):
        message_header(role, details)
        draw_message_actions(interface, tab, message, role)
        if message.get('failed'):
            # A cancelled turn usually holds what had already been streamed. Showing the text as
            # well as the reason is the difference between "it stopped here" and "nothing happened".
            if message.get('text'):
                selectable_text(message['id'], message['text'])
            cyui.callout('error', '%s: %s' % (tr(message.get('error', 'Error')),
                                                 message.get('errorMessage', '')))
        else:
            # Selectable: part of a reply can be copied, not only the whole message.
            selectable_text(message['id'], message.get('text', ''))
        if message.get('systemPromptFolded'):
            cyui.text_faint(tr('The system prompt was folded into this message: this provider has '
                               'no separate system field.'))
        if message.get('loras'):
            cyui.text_faint(tr('Adapters: ') + ', '.join(
                '%s @ %s' % (item.get('name', item.get('id')), item.get('strength'))
                for item in message['loras']))
    cyui.space(2)
    imgui.pop_id()


def draw_message_actions(interface, tab, message, role):
    """Icon buttons on the right of the message header."""
    buttons = 2 if role == 'assistant' and message.get('text') and not message.get('failed') else 1
    size = imgui.get_frame_height() + cyui.dp(2)
    imgui.same_line()
    cyui.align_right(buttons * (size + imgui.get_style().item_spacing.x))
    if cyui.icon_button(cyui.icon.copy, tr('Copy the whole message')):
        imgui.set_clipboard_text(message.get('text', ''))
        cyui.notify(tr('Message copied.'), 'success', 2.0)
    if buttons == 2:
        imgui.same_line()
        draw_read_button(interface, tab, message)


def draw_read_button(interface, tab, message):
    key = 'read-' + message['id']
    if not interface.reading(key):
        if cyui.icon_button(cyui.icon.volume, tr('Read aloud')):
            interface.read_message(tab, message)
        return
    preparing = interface.player.current != key
    if cyui.icon_button(cyui.icon.stop, tr('Preparing the voice...') if preparing else tr('Stop reading'),
                        True):
        interface.stop_reading(key)


def draw_live(tab, live):
    with card('##live'):
        message_header('assistant', [])
        imgui.same_line()
        cyui.spinner('##live-spinner', 6)
        if tab.status:
            imgui.same_line()
            cyui.text_faint(tr(tab.status))
        if tab.live_thinking:
            _, tab.show_thinking = cyui.toggle_switch(tr('Show reasoning') + '###thinking',
                                                      tab.show_thinking)
            if tab.show_thinking:
                with cyui.scoped_color(imgui.Col_.text, cyui.palette().textFaint):
                    wrapped(''.join(tab.live_thinking))
        if live:
            wrapped(live)
        else:
            cyui.text_faint(tr('Waiting for the first tokens...'))


# ---------------------------------------------------------------------- composer

def draw_dictation(interface, tab):
    """Record / Stop, then the words land in the message box. Nothing is sent by itself."""
    recorder = interface.recorder
    job = interface.speech_job(interface.dictation_key(tab))
    recording = recorder.recording and recorder.purpose == 'dictation'
    if recording:
        if cyui.icon_button(cyui.icon.microphone, tr('Stop dictation'), True, cyui.palette().error) or recorder.reached_limit():
            interface.stop_dictation(tab)
            return
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.text_dim('%.1f / %.0f s' % (recorder.seconds, recorder.limit))
        imgui.same_line()
        cyui.progress_bar(min(1.0, recorder.level * 6.0), (cyui.dp(80), cyui.dp(6)),
                          tone='success')
    elif job is not None:
        cyui.spinner('##dictation-finishing', 7)
        cyui.tooltip(tr('Finishing the dictation...'))
    else:
        with cyui.scoped_disabled(recorder.recording):
            if cyui.icon_button(cyui.icon.microphone, tr('Dictate: record the microphone; the words are '
                                                     'added to the message. Models and voices are '
                                                     'set in the Speech tab.')):
                interface.start_dictation(tab)


def draw_composer(interface, tab):
    document = tab.document
    ready = bool(document.get('providerId'))
    dictating = interface.dictating(tab)
    style = imgui.get_style()
    # While words are being dictated the box is filled by the dictation: typing at the same time
    # would be overwritten by the next recognised words.
    with cyui.scoped_disabled(tab.busy or dictating):
        changed, value = imgui.input_text_multiline(
            '##composer', tab.input,
            ImVec2(-1, imgui.get_text_line_height() * INPUT_LINES + style.frame_padding.y * 2),
            imgui.InputTextFlags_.word_wrap)
        if changed:
            tab.input = value
        send_shortcut = imgui.is_item_active() and imgui.is_key_down(imgui.Key.mod_ctrl) \
            and imgui.is_key_pressed(imgui.Key.enter, False)
    draw_dictation(interface, tab)
    imgui.same_line()
    changed, value = cyui.toggle_switch(tr('Read replies aloud') + '###auto-read',
                                        bool(interface.speech_settings.get('autoRead')))
    if changed:
        interface.speech_settings['autoRead'] = value
        try:
            interface.submit('speech_settings', {'auto_read': value})
        except (CyToolError, ValueError) as exc:
            tab.error = str(exc)
    cyui.toolbar_separator()
    with cyui.scoped_disabled(not document.get('messages')):
        if cyui.icon_button(cyui.icon.copy, tr('Copy the whole conversation')):
            imgui.set_clipboard_text('\n\n'.join('%s: %s' % (item['role'], item.get('text', ''))
                                                 for item in document.get('messages', [])))
            cyui.notify(tr('Conversation copied.'), 'success', 2.0)
        imgui.same_line()
        if cyui.icon_button(cyui.icon.export_file, tr('Export to Markdown (data/exports)')):
            export(interface, tab.id, 'markdown')
    imgui.same_line()
    with cyui.scoped_disabled(not document.get('native')):
        if cyui.icon_button(cyui.icon.refresh, tr('New provider session: the next turn starts afresh '
                                              'on the provider side')):
            try:
                conversations.forget_native(tab.id)
                tab.reload()
                cyui.notify(tr('The next turn starts a fresh provider session.'), 'info')
            except CyToolError as exc:
                tab.error = str(exc)
    if not ready:
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.text_coloured(cyui.palette().warning, tr('Choose a provider before sending.'))
    if tab.busy:
        job = tab.job or {}
        progress = job.get('progress') or {}
        cancel = cyui.button_width(tr('Cancel'))
        imgui.same_line()
        bar = max(cyui.dp(60), imgui.get_content_region_avail().x - cancel - style.item_spacing.x)
        imgui.align_text_to_frame_padding()
        cyui.progress_bar(min(1.0, float(progress.get('percent', 0)) / 100.0) if progress.get('percent')
                          else -1.0, (bar, imgui.get_frame_height()),
                          tr(progress.get('currentStep') or job.get('state', '')))
        imgui.same_line()
        if cyui.danger_button(tr('Cancel') + '###cancel-turn'):
            interface.cancel(tab)
        return
    send = tr('Send')
    width = max(cyui.dp(96), cyui.button_width(send) + imgui.get_font_size() * 2)
    imgui.same_line()
    cyui.align_right(width)
    with cyui.scoped_disabled(not ready or not tab.input.strip() or dictating):
        if cyui.icon_text_button(cyui.icon.send, send + '###send', 'primary',
                                 (width, 0)) or (send_shortcut and ready and tab.input.strip()):
            interface.send(tab)
    cyui.tooltip(tr('Send (Ctrl+Enter)'))
