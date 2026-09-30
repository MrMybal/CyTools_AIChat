"""Reusable system prompts and sampling presets.

A preset is a named, versioned JSON document holding a system prompt and the sampling
values a conversation starts from. It never carries a credential, a file path or a model
weight, so it can be exported, reviewed and shared without leaking anything. Applying a
preset fills a conversation; it does not start a turn and it does not lock the fields,
which stay editable per conversation afterwards.
"""
import re
import uuid
from datetime import datetime, timezone

from cytools_core import CyToolError

from .paths import APP, PRESETS, read_json, write_json

FORMAT = 'cytools-aichat-preset'
SCHEMA_VERSION = 1
BUILTIN = APP / 'presets.json'

# Sampling fields a preset may carry. Anything else is refused rather than silently
# dropped, so a preset written for a future version fails loudly instead of half-applying.
FIELDS = {'temperature': float, 'top_p': float, 'top_k': int, 'max_tokens': int,
          'repeat_penalty': float, 'seed': int, 'context_tokens': int, 'history_limit': int}


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value=''):
    value = str(value or '').strip()
    if not value:
        return 'p-' + uuid.uuid4().hex[:12]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise CyToolError('InvalidParameters',
                          'A preset id uses letters, digits, hyphen and underscore only.')
    return value


def path_for(preset_id):
    return PRESETS / (identifier(preset_id) + '.json')


def normalise_settings(values):
    values = values or {}
    if not isinstance(values, dict):
        raise CyToolError('InvalidParameters', 'Preset settings must be an object.')
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise CyToolError('InvalidParameters',
                          'Unknown preset setting: ' + ', '.join(sorted(unknown)))
    result = {}
    for key, value in values.items():
        if value is None:
            continue
        try:
            result[key] = FIELDS[key](value)
        except (TypeError, ValueError):
            raise CyToolError('InvalidParameters',
                              'Preset setting %s expects a %s.' % (key, FIELDS[key].__name__))
    return result


def valid(document):
    return isinstance(document, dict) and document.get('format') == FORMAT


def builtin():
    """Presets shipped with the application. They live in app/ and are read-only copies."""
    rows = read_json(BUILTIN, [])
    return [row for row in rows if isinstance(row, dict) and row.get('id')] if isinstance(rows, list) else []


def save(preset_id, name, system_prompt='', settings=None, description=''):
    document = {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'id': identifier(preset_id),
                'name': str(name or '').strip() or 'Preset', 'description': str(description or ''),
                'systemPrompt': str(system_prompt or ''),
                'settings': normalise_settings(settings), 'updated': now()}
    write_json(path_for(document['id']), document)
    return document


def load(preset_id):
    document = read_json(path_for(preset_id))
    if valid(document):
        if document.get('schemaVersion') != SCHEMA_VERSION:
            raise CyToolError('UnsupportedVersion',
                              'This preset was written by another version of the Tool.')
        return document
    for row in builtin():
        if row['id'] == preset_id:
            return {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'builtin': True,
                    'id': row['id'], 'name': row.get('name', row['id']),
                    'description': row.get('description', ''),
                    'systemPrompt': row.get('systemPrompt', ''),
                    'settings': normalise_settings(row.get('settings')), 'updated': ''}
    raise CyToolError('NotFound', 'Unknown preset: ' + str(preset_id))


def listing():
    rows = []
    seen = set()
    for item in sorted(PRESETS.glob('*.json')):
        document = read_json(item)
        if valid(document) and document.get('schemaVersion') == SCHEMA_VERSION:
            rows.append({**document, 'builtin': False})
            seen.add(document['id'])
    for row in builtin():
        if row['id'] not in seen:
            rows.append({'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'builtin': True,
                         'id': row['id'], 'name': row.get('name', row['id']),
                         'description': row.get('description', ''),
                         'systemPrompt': row.get('systemPrompt', ''),
                         'settings': normalise_settings(row.get('settings')), 'updated': ''})
    rows.sort(key=lambda row: (row.get('builtin', False), row.get('name', '').lower()))
    return rows


def delete(preset_id):
    target = path_for(preset_id)
    if not target.is_file():
        # A built-in preset has no file to remove; saying so is clearer than reporting success.
        if any(row['id'] == preset_id for row in builtin()):
            raise CyToolError('ReadOnly', 'A preset shipped with the application cannot be deleted.')
        raise CyToolError('NotFound', 'Unknown preset: ' + str(preset_id))
    target.unlink()
    return {'id': preset_id, 'deleted': True}
