"""Every path the Tool uses, resolved from the root it was installed in.

Nothing is stored in the user profile and nothing is shared with another CyTool: a
conversation, a model or a LoRA belongs to this installation only. Writes go through
`write_json`, which replaces the file atomically so an interrupted save can never leave a
half-written conversation behind.
"""
import json
import os
import uuid
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
DATA = ROOT / 'data'
RUNTIME = ROOT / 'runtime'

CONVERSATIONS = DATA / 'conversations'
PRESETS = DATA / 'presets'
SETTINGS = DATA / 'settings'
LOGS = DATA / 'logs'
REPORTS = DATA / 'reports'
EXPORTS = DATA / 'exports'
LLM_MODELS = DATA / 'models/llm'
LORA_MODELS = DATA / 'models/lora'

TOOL_ID = 'cy.tool.aichat'


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(temp, path)
    return path


def ensure_tree():
    for directory in (CONVERSATIONS, PRESETS, SETTINGS, LOGS, REPORTS, EXPORTS,
                      LLM_MODELS, LORA_MODELS, DATA / 'jobs', DATA / 'inputs',
                      RUNTIME / 'engines', RUNTIME / 'downloads', RUNTIME / 'updates'):
        directory.mkdir(parents=True, exist_ok=True)
