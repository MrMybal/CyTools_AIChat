"""Conversations kept on disk, one readable JSON document per conversation.

A conversation survives the application: closing a tab, restarting the Tool or updating
`app/` never touches `data/`. The file is the source of truth for the transcript shown in
the interface, for the export and for the AI clients reading it through MCP or the CLI.

Two families of providers are stored side by side. A stateless provider (an OpenAI
compatible endpoint, Ollama, the local llama.cpp server) receives the whole message list on
every turn, so the transcript here *is* the context. A session provider (Codex, Claude
Code, Antigravity, OpenCode) keeps the history on its own side and is resumed with the
native identifier recorded in `native`; the transcript is then a faithful mirror kept for
display and export, and `native` is what actually carries the memory. The distinction is
written into each message so a reader never has to guess which one produced it.
"""
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from cytools_core import CyToolError

from .paths import CONVERSATIONS, SETTINGS, read_json, write_json

FORMAT = 'cytools-aichat-conversation'
SCHEMA_VERSION = 1
TABS = SETTINGS / 'tabs.json'
MAX_TITLE = 80

_lock = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value=''):
    """Accept an existing id or mint one. Ids become file names, so they stay restricted."""
    value = str(value or '').strip()
    if not value:
        return 'c-' + uuid.uuid4().hex[:16]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise CyToolError('InvalidParameters',
                          'A conversation id uses letters, digits, hyphen and underscore only.')
    return value


def path_for(conversation_id):
    return CONVERSATIONS / (identifier(conversation_id) + '.json')


def blank(conversation_id='', title='', provider_id='', transport='', model=''):
    return {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION,
            'id': identifier(conversation_id), 'title': title or 'New conversation',
            'created': now(), 'updated': now(),
            'providerId': provider_id, 'transport': transport, 'model': model,
            'systemPrompt': '', 'presetId': '', 'settings': {}, 'native': {},
            'messages': []}


def valid(document):
    return (isinstance(document, dict) and document.get('format') == FORMAT
            and isinstance(document.get('messages'), list))


def load(conversation_id):
    document = read_json(path_for(conversation_id))
    if not valid(document):
        raise CyToolError('NotFound', 'Unknown conversation: ' + str(conversation_id))
    if document.get('schemaVersion') != SCHEMA_VERSION:
        raise CyToolError('UnsupportedVersion',
                          'This conversation was written by another version of the Tool.')
    return document


def exists(conversation_id):
    try:
        return path_for(conversation_id).is_file()
    except CyToolError:
        return False


def save(document):
    document['updated'] = now()
    write_json(path_for(document['id']), document)
    return document


def create(title='', provider_id='', transport='', model='', system_prompt='', settings=None,
           preset_id='', conversation_id=''):
    with _lock:
        document = blank(conversation_id, title, provider_id, transport, model)
        if conversation_id and exists(conversation_id):
            raise CyToolError('Conflict', 'A conversation with this id already exists.')
        document['systemPrompt'] = system_prompt or ''
        document['presetId'] = preset_id or ''
        document['settings'] = dict(settings or {})
        return save(document)


def summary(document):
    last = next((m for m in reversed(document['messages']) if m.get('role') == 'assistant'), None)
    return {'id': document['id'], 'title': document.get('title', ''),
            'created': document.get('created', ''), 'updated': document.get('updated', ''),
            'providerId': document.get('providerId', ''), 'transport': document.get('transport', ''),
            'model': document.get('model', ''), 'messageCount': len(document['messages']),
            'lastMessage': (last or {}).get('text', '')[:200],
            'hasNativeSession': bool(document.get('native'))}


def listing():
    rows = []
    for item in sorted(CONVERSATIONS.glob('*.json')):
        document = read_json(item)
        if valid(document) and document.get('schemaVersion') == SCHEMA_VERSION:
            rows.append(summary(document))
    rows.sort(key=lambda row: row.get('updated', ''), reverse=True)
    return rows


def delete(conversation_id):
    with _lock:
        target = path_for(conversation_id)
        if not target.is_file():
            raise CyToolError('NotFound', 'Unknown conversation: ' + str(conversation_id))
        # The document is kept as a timestamped backup: closing a tab is a frequent gesture
        # and a misplaced click must not destroy a transcript nobody can produce again.
        backup = CONVERSATIONS / 'deleted' / ('%s-%d.json' % (identifier(conversation_id), time.time_ns()))
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.replace(backup)
        close_tab(conversation_id)
        return {'id': conversation_id, 'deleted': True, 'backup': str(backup)}


def append(conversation_id, role, text, **fields):
    if role not in ('user', 'assistant', 'system'):
        raise CyToolError('InvalidParameters', 'Unknown message role: ' + str(role))
    with _lock:
        document = load(conversation_id)
        message = {'id': 'm-' + uuid.uuid4().hex[:12], 'role': role, 'text': text,
                   'created': now()}
        message.update({key: value for key, value in fields.items() if value not in (None, '')})
        document['messages'].append(message)
        if role == 'user' and document.get('title') in ('', 'New conversation'):
            document['title'] = derive_title(text)
        save(document)
        return message


def update_message(conversation_id, message_id, **fields):
    with _lock:
        document = load(conversation_id)
        for message in document['messages']:
            if message['id'] == message_id:
                message.update(fields)
                save(document)
                return message
        raise CyToolError('NotFound', 'Unknown message: ' + str(message_id))


def derive_title(text):
    """A title is a convenience, never a rewrite: the words typed, cut on a boundary."""
    flat = ' '.join(str(text or '').split())
    if len(flat) <= MAX_TITLE:
        return flat or 'New conversation'
    cut = flat[:MAX_TITLE]
    return (cut.rsplit(' ', 1)[0] if ' ' in cut else cut) + '...'


def set_fields(conversation_id, **fields):
    allowed = {'title', 'providerId', 'transport', 'model', 'systemPrompt', 'presetId', 'settings'}
    unknown = set(fields) - allowed
    if unknown:
        raise CyToolError('InvalidParameters',
                          'Unknown conversation field: ' + ', '.join(sorted(unknown)))
    with _lock:
        document = load(conversation_id)
        document.update(fields)
        return save(document)


def native_key(provider_id, transport):
    return '%s/%s' % (provider_id, transport or '')


def get_native(document, provider_id, transport):
    return (document.get('native') or {}).get(native_key(provider_id, transport)) or None


def set_native(conversation_id, provider_id, transport, native_id):
    with _lock:
        document = load(conversation_id)
        document.setdefault('native', {})[native_key(provider_id, transport)] = native_id
        return save(document)


def forget_native(conversation_id, provider_id='', transport=''):
    """Drop the provider-side session so the next turn starts a fresh one."""
    with _lock:
        document = load(conversation_id)
        if provider_id:
            document.get('native', {}).pop(native_key(provider_id, transport), None)
        else:
            document['native'] = {}
        return save(document)


def history(document, limit=0):
    """The message list a stateless provider receives, oldest first, system prompt excluded."""
    messages = [{'role': m['role'], 'content': m['text']}
                for m in document['messages']
                if m.get('role') in ('user', 'assistant') and m.get('text')
                and not m.get('failed')]
    return messages[-limit:] if limit and limit > 0 else messages


# ------------------------------------------------------------------ open tabs

def tabs():
    stored = read_json(TABS, {})
    open_ids = [i for i in stored.get('open', []) if isinstance(i, str) and exists(i)]
    active = stored.get('active') if stored.get('active') in open_ids else (open_ids[0] if open_ids else '')
    return {'open': open_ids, 'active': active or ''}


def set_tabs(open_ids, active=''):
    known = []
    for item in open_ids:
        if item not in known and exists(item):
            known.append(item)
    write_json(TABS, {'open': known,
                      'active': active if active in known else (known[0] if known else '')})
    return tabs()


def open_tab(conversation_id, active=True):
    state = tabs()
    if conversation_id not in state['open']:
        state['open'].append(conversation_id)
    return set_tabs(state['open'], conversation_id if active else state['active'])


def close_tab(conversation_id):
    state = tabs()
    remaining = [i for i in state['open'] if i != conversation_id]
    active = state['active'] if state['active'] != conversation_id else ''
    return set_tabs(remaining, active)


# ------------------------------------------------------------------ export

def export(conversation_id, destination, fmt='markdown'):
    document = load(conversation_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'json':
        write_json(destination, document)
    elif fmt == 'markdown':
        lines = ['# ' + document.get('title', document['id']), '',
                 '- Conversation: `%s`' % document['id'],
                 '- Provider: `%s`' % (document.get('providerId') or 'not set'),
                 '- Transport: `%s`' % (document.get('transport') or 'not set'),
                 '- Model: `%s`' % (document.get('model') or 'not set'),
                 '- Updated: %s' % document.get('updated', ''), '']
        if document.get('systemPrompt'):
            lines += ['## System prompt', '', document['systemPrompt'], '']
        for message in document['messages']:
            who = {'user': 'User', 'assistant': 'Assistant', 'system': 'System'}[message['role']]
            header = '## %s — %s' % (who, message.get('created', ''))
            if message.get('model'):
                header += ' (`%s`)' % message['model']
            lines += [header, '', message.get('text', ''), '']
        destination.write_text('\n'.join(lines), encoding='utf-8')
    else:
        raise CyToolError('InvalidParameters', 'Unknown export format: ' + str(fmt))
    return {'file': str(destination), 'format': fmt,
            'mimeType': 'application/json' if fmt == 'json' else 'text/markdown'}
