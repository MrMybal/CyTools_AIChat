"""Behaviour tests for CyTools_AIChat.

Everything here runs against fixtures: no provider is contacted, no weight is downloaded and
no model is loaded. The turns go through the real Runtime with a stub provider swapped into
the registry, so the job lifecycle, the stored conversation, the streamed events, the
cancellation path and the client isolation are the real ones.

    runtime/python/Scripts/python.exe -m pytest app/tests -q
"""
import json
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from cytools_core import CyToolError, load_manifest  # noqa: E402

from aichat import conversations, credentials, engine, maintenance, paths, presets  # noqa: E402
from aichat.gguf_header import GGUFError, adapter_kind, describe  # noqa: E402
from aichat.providers.base import SESSION, STATELESS, ChatResult, Delta, Provider  # noqa: E402


# --------------------------------------------------------------------------- fixtures

@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Point the whole Tool at a temporary tree so a test never touches real data."""
    for name in ('CONVERSATIONS', 'PRESETS', 'SETTINGS', 'LOGS', 'REPORTS', 'EXPORTS',
                 'LLM_MODELS', 'LORA_MODELS', 'SPEECH_MODELS', 'VOICES', 'SPEECH', 'INPUTS'):
        monkeypatch.setattr(paths, name, tmp_path / name.lower())
    monkeypatch.setattr(paths, 'DATA', tmp_path / 'data')
    monkeypatch.setattr(conversations, 'CONVERSATIONS', tmp_path / 'conversations')
    monkeypatch.setattr(conversations, 'TABS', tmp_path / 'settings/tabs.json')
    monkeypatch.setattr(presets, 'PRESETS', tmp_path / 'presets')
    monkeypatch.setattr(credentials, 'STORE', tmp_path / 'settings/credentials.json')
    for directory in ('conversations', 'presets', 'settings', 'exports'):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    return tmp_path


class StubProvider(Provider):
    """A provider that answers from memory, so a turn can be tested without a model."""

    id = 'llamacpp'
    name = 'Stub'
    transports = ('local-server',)

    def __init__(self, kind=STATELESS, reply='stub reply', delay=0.0, fail=None):
        super().__init__({})
        self.kind = kind
        self.reply = reply
        self.delay = delay
        self.fail = fail
        self.seen = []
        self.cancelled = threading.Event()

    def detect(self):
        return {'id': self.id, 'name': self.name, 'available': True, 'status': 'Ready'}

    def chat(self, request, on_delta):
        self.seen.append({'prompt': request.prompt, 'messages': list(request.messages),
                          'system': request.system_prompt, 'native': request.native_id,
                          'settings': {k: v for k, v in request.settings.items()
                                       if not k.startswith('_')}})
        if self.fail:
            raise CyToolError(self.fail, 'stub failure')
        for piece in self.reply.split(' '):
            request.check()
            on_delta(Delta.TEXT, piece + ' ')
            if self.delay:
                time.sleep(self.delay)
        return ChatResult(self.reply, native_id='native-1' if self.kind == SESSION else '',
                          model=request.model, transport='local-server', seconds=0.01)


@pytest.fixture()
def runtime(workspace, monkeypatch):
    from tool import create_runtime
    monkeypatch.setenv('CYTOOLS_TOKEN', '')
    instance = create_runtime(workspace / 'jobs')
    instance.start()
    try:
        yield instance
    finally:
        instance.close(timeout=20)


def client(runtime, name='test'):
    actor = runtime.authenticate(runtime.create_client(
        name, ['network', 'processSpawn', 'filesystemExternal', 'manageResources'])['token'])
    return actor, runtime.create_session(actor, temporary=False)['sessionId']


def run(runtime, actor, session, operation, parameters, timeout=60):
    job = runtime.submit(actor, session, operation, parameters)
    return runtime.wait(actor, job['jobId'], timeout=timeout)


# --------------------------------------------------------------------------- manifest

def test_manifest_is_valid_and_every_operation_is_registered(runtime):
    document = load_manifest(APP / 'CyTool.json')
    assert document['id'] == 'cy.tool.aichat'
    declared = {item['id'] for item in document['operations']}
    assert declared <= set(runtime._handlers), \
        'Declared but not registered: %s' % sorted(declared - set(runtime._handlers))


def test_platforms_separate_declared_from_tested():
    document = load_manifest(APP / 'CyTool.json')
    for platform in document['platforms']:
        if platform['status'] == 'Supported':
            assert platform.get('tested'), \
                'A Supported platform must carry what was actually executed on it'


# --------------------------------------------------------------------------- conversations

def test_conversation_round_trip(workspace):
    document = conversations.create(provider_id='llamacpp', model='m')
    conversations.append(document['id'], 'user', 'Bonjour, comment vas-tu aujourd hui ?')
    conversations.append(document['id'], 'assistant', 'Bien.', model='m')
    stored = conversations.load(document['id'])
    assert [m['role'] for m in stored['messages']] == ['user', 'assistant']
    assert stored['title'].startswith('Bonjour')
    assert conversations.history(stored) == [
        {'role': 'user', 'content': 'Bonjour, comment vas-tu aujourd hui ?'},
        {'role': 'assistant', 'content': 'Bien.'}]


def test_failed_messages_are_stored_but_never_sent_back_as_context(workspace):
    document = conversations.create()
    conversations.append(document['id'], 'user', 'question')
    conversations.append(document['id'], 'assistant', '', failed=True, error='Timeout')
    stored = conversations.load(document['id'])
    assert len(stored['messages']) == 2
    assert conversations.history(stored) == [{'role': 'user', 'content': 'question'}]


def test_delete_keeps_a_backup_of_the_transcript(workspace):
    document = conversations.create(title='keep me')
    conversations.append(document['id'], 'user', 'text')
    result = conversations.delete(document['id'])
    assert result['deleted'] and Path(result['backup']).is_file()
    assert json.loads(Path(result['backup']).read_text('utf-8'))['title'] == 'keep me'
    with pytest.raises(CyToolError):
        conversations.load(document['id'])


def test_tabs_survive_and_drop_unknown_conversations(workspace):
    first = conversations.create()['id']
    second = conversations.create()['id']
    conversations.set_tabs([first, second, 'c-does-not-exist'], second)
    state = conversations.tabs()
    assert state['open'] == [first, second] and state['active'] == second
    conversations.delete(second)
    assert conversations.tabs() == {'open': [first], 'active': first}


def test_native_sessions_are_recorded_per_provider_and_transport(workspace):
    document = conversations.create()
    conversations.set_native(document['id'], 'codex', 'app-server', 'thread-1')
    conversations.set_native(document['id'], 'claude-code', 'cli-jsonl', 'session-2')
    stored = conversations.load(document['id'])
    assert conversations.get_native(stored, 'codex', 'app-server') == 'thread-1'
    assert conversations.get_native(stored, 'codex', 'cli-jsonl') is None
    conversations.forget_native(document['id'], 'codex', 'app-server')
    stored = conversations.load(document['id'])
    assert conversations.get_native(stored, 'codex', 'app-server') is None
    assert conversations.get_native(stored, 'claude-code', 'cli-jsonl') == 'session-2'


def test_export_markdown_and_json(workspace):
    document = conversations.create(provider_id='ollama', model='qwen')
    conversations.append(document['id'], 'user', 'hello')
    conversations.append(document['id'], 'assistant', 'world')
    markdown = conversations.export(document['id'], workspace / 'exports/a.md', 'markdown')
    text = Path(markdown['file']).read_text('utf-8')
    assert 'hello' in text and 'world' in text and 'ollama' in text
    data = conversations.export(document['id'], workspace / 'exports/a.json', 'json')
    assert json.loads(Path(data['file']).read_text('utf-8'))['id'] == document['id']
    with pytest.raises(CyToolError):
        conversations.export(document['id'], workspace / 'exports/a.txt', 'rtf')


def test_conversation_identifier_rejects_a_path(workspace):
    with pytest.raises(CyToolError):
        conversations.load('../../etc/passwd')
    with pytest.raises(CyToolError):
        conversations.create(conversation_id='a/b')


# --------------------------------------------------------------------------- presets

def test_preset_round_trip_and_unknown_setting(workspace):
    saved = presets.save('', 'Mine', 'be brief', {'temperature': 0.4, 'max_tokens': 100})
    loaded = presets.load(saved['id'])
    assert loaded['systemPrompt'] == 'be brief' and loaded['settings']['temperature'] == 0.4
    with pytest.raises(CyToolError):
        presets.save('', 'Bad', '', {'nonsense': 1})
    presets.delete(saved['id'])
    with pytest.raises(CyToolError):
        presets.load(saved['id'])


def test_builtin_presets_are_listed_and_cannot_be_deleted(workspace):
    rows = presets.listing()
    assert any(row['id'] == 'plain-assistant' for row in rows)
    with pytest.raises(CyToolError) as error:
        presets.delete('plain-assistant')
    assert error.value.code == 'ReadOnly'


# --------------------------------------------------------------------------- credentials

def test_credential_status_never_returns_the_key(workspace, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    credentials.store('openai', 'sk-secret-value-123456')
    state = credentials.status('openai')
    assert state['configured'] and state['source'] == 'stored'
    assert 'sk-secret-value-123456' not in json.dumps(state)
    assert credentials.resolve('openai') == 'sk-secret-value-123456'
    credentials.clear('openai')
    assert credentials.status('openai')['configured'] is False


def test_environment_variable_wins_over_the_stored_key(workspace, monkeypatch):
    credentials.store('openai', 'stored-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'environment-key')
    assert credentials.resolve('openai') == 'environment-key'
    assert credentials.status('openai')['source'] == 'environment'


def test_stored_key_is_not_readable_as_plain_text_on_windows(workspace, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    credentials.store('openai', 'sk-plain-text-should-not-appear')
    raw = credentials.STORE.read_text('utf-8')
    if credentials.protected():
        assert 'sk-plain-text-should-not-appear' not in raw
    else:
        # Without an OS secret store the file is only permission-protected, and the status
        # says so rather than claiming encryption.
        assert credentials.status('openai')['encrypted'] is False


# --------------------------------------------------------------------------- GGUF header

def test_gguf_header_rejects_a_file_that_is_not_gguf(tmp_path):
    fake = tmp_path / 'not.gguf'
    fake.write_bytes(b'NOPE' + b'\0' * 64)
    with pytest.raises(GGUFError):
        adapter_kind(fake)


def test_gguf_header_reads_an_installed_model_if_one_is_present():
    from aichat import catalog
    installed = [row for row in catalog.listing() if row['installed']
                 and row['kind'] in ('model', 'lora')]
    if not installed:
        pytest.skip('No weights installed; this check needs a real GGUF file.')
    for row in installed:
        header = describe(catalog.file_path(row['id']))
        assert header['ggufVersion'] in (2, 3)
        assert (header['adapterType'] == 'lora') == (row['kind'] == 'lora')


# --------------------------------------------------------------------------- archives

def test_safe_extract_refuses_traversal(tmp_path):
    archive = tmp_path / 'evil.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('../escaped.txt', 'nope')
    with pytest.raises(CyToolError) as error:
        engine.safe_extract(archive, tmp_path / 'out')
    assert error.value.code == 'InvalidArchive'
    assert not (tmp_path / 'escaped.txt').exists()


def test_safe_extract_refuses_an_absolute_name(tmp_path):
    archive = tmp_path / 'abs.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('/etc/passwd', 'nope')
    with pytest.raises(CyToolError):
        engine.safe_extract(archive, tmp_path / 'out')


def test_safe_extract_accepts_a_normal_archive(tmp_path):
    archive = tmp_path / 'fine.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('build/llama-server.exe', 'binary')
    engine.safe_extract(archive, tmp_path / 'out')
    assert (tmp_path / 'out/build/llama-server.exe').read_text() == 'binary'


def test_update_verification_refuses_another_tools_release(tmp_path):
    staged = tmp_path / 'staged/app'
    staged.mkdir(parents=True)
    manifest = json.loads((APP / 'CyTool.json').read_text('utf-8'))
    manifest['id'] = 'cy.tool.somethingelse'
    (staged / 'CyTool.json').write_text(json.dumps(manifest), encoding='utf-8')
    (staged / 'tool.py').write_text('', encoding='utf-8')
    (staged / 'desktop.py').write_text('', encoding='utf-8')
    with pytest.raises(CyToolError) as error:
        maintenance.verify_application_tree(tmp_path / 'staged')
    assert error.value.code == 'InvalidArchive'


def test_update_verification_refuses_a_foreign_runtime_abi(tmp_path):
    staged = tmp_path / 'staged/app'
    staged.mkdir(parents=True)
    (staged / 'CyTool.json').write_text((APP / 'CyTool.json').read_text('utf-8'), encoding='utf-8')
    (staged / 'tool.py').write_text('', encoding='utf-8')
    (staged / 'desktop.py').write_text('', encoding='utf-8')
    (staged / 'release.json').write_text(json.dumps({'runtimeAbi': 'python399-future'}),
                                         encoding='utf-8')
    with pytest.raises(CyToolError) as error:
        maintenance.verify_application_tree(tmp_path / 'staged')
    assert error.value.code == 'IncompatibleRuntime'


def test_update_repository_parsing():
    assert maintenance.repository('https://github.com/owner/name.git') == 'owner/name'
    assert maintenance.repository('') == ''
    with pytest.raises(CyToolError):
        maintenance.repository('not-a-repository')
    with pytest.raises(CyToolError):
        maintenance.repository('../../etc/passwd')


# --------------------------------------------------------------------------- turns

def test_a_stateless_turn_stores_the_reply_and_sends_the_transcript(runtime):
    stub = StubProvider(STATELESS, reply='first answer')
    runtime.aichat.providers['llamacpp'] = stub
    actor, session = client(runtime)
    job = run(runtime, actor, session, 'chat',
              {'message': 'one', 'provider': 'llamacpp', 'model': 'm',
               'system_prompt': 'be terse'})
    assert job['state'] == 'Completed', job.get('error')
    conversation = job['outputs']['conversationId']
    assert job['outputs']['text'] == 'first answer'
    assert job['outputs']['kind'] == 'stateless'

    stub.reply = 'second answer'
    again = run(runtime, actor, session, 'chat',
                {'message': 'two', 'conversation': conversation, 'provider': 'llamacpp'})
    assert again['state'] == 'Completed'
    # The second call must carry the first exchange, and must not repeat the new message.
    assert stub.seen[1]['messages'] == [{'role': 'user', 'content': 'one'},
                                        {'role': 'assistant', 'content': 'first answer'}]
    assert stub.seen[1]['prompt'] == 'two'
    assert stub.seen[1]['system'] == 'be terse'
    stored = conversations.load(conversation)
    assert [m['text'] for m in stored['messages']] == ['one', 'first answer', 'two',
                                                       'second answer']


def test_a_session_turn_resumes_instead_of_replaying_the_transcript(runtime):
    stub = StubProvider(SESSION, reply='ack')
    runtime.aichat.providers['llamacpp'] = stub
    actor, session = client(runtime)
    first = run(runtime, actor, session, 'chat', {'message': 'one', 'provider': 'llamacpp'})
    conversation = first['outputs']['conversationId']
    assert first['outputs']['nativeSessionId'] == 'native-1'
    run(runtime, actor, session, 'chat',
        {'message': 'two', 'conversation': conversation, 'provider': 'llamacpp'})
    assert stub.seen[1]['messages'] == []
    assert stub.seen[1]['native'] == 'native-1'


def test_a_stale_stored_transport_does_not_block_the_conversation(runtime):
    """Changing a conversation's provider can leave a transport the new one does not speak."""
    stub = StubProvider(STATELESS, reply='ok')
    runtime.aichat.providers['llamacpp'] = stub
    document = conversations.create(provider_id='openai-compatible',
                                    transport='chat-completions', model='m')
    actor, session = client(runtime)
    job = run(runtime, actor, session, 'chat',
              {'message': 'x', 'conversation': document['id'], 'provider': 'llamacpp'})
    assert job['state'] == 'Completed', job.get('error')
    assert job['outputs']['transport'] == 'local-server'
    # An explicitly requested transport is still refused when it is wrong.
    bad = runtime.submit(actor, session, 'chat',
                         {'message': 'y', 'conversation': document['id'],
                          'provider': 'llamacpp', 'transport': 'chat-completions'})
    bad = runtime.wait(actor, bad['jobId'], timeout=30)
    assert bad['state'] == 'Failed'
    assert bad['error']['code'] == 'InvalidParameters'


def test_history_limit_trims_what_is_sent_without_touching_what_is_stored(runtime):
    stub = StubProvider(STATELESS, reply='ok')
    runtime.aichat.providers['llamacpp'] = stub
    actor, session = client(runtime)
    job = run(runtime, actor, session, 'chat', {'message': 'a', 'provider': 'llamacpp'})
    conversation = job['outputs']['conversationId']
    for message in ('b', 'c'):
        run(runtime, actor, session, 'chat',
            {'message': message, 'conversation': conversation, 'provider': 'llamacpp',
             'history_limit': 2})
    assert len(stub.seen[-1]['messages']) == 2
    assert len(conversations.load(conversation)['messages']) == 6


def test_a_preset_fills_only_what_the_call_did_not_set(runtime):
    stub = StubProvider(STATELESS)
    runtime.aichat.providers['llamacpp'] = stub
    presets.save('unit', 'Unit', 'preset prompt', {'temperature': 0.1, 'max_tokens': 50})
    actor, session = client(runtime)
    run(runtime, actor, session, 'chat',
        {'message': 'x', 'provider': 'llamacpp', 'preset': 'unit', 'temperature': 1.5})
    settings = stub.seen[0]['settings']
    assert settings['temperature'] == 1.5, 'an explicit value must win over the preset'
    assert settings['max_tokens'] == 50, 'the preset must fill what was not given'
    assert stub.seen[0]['system'] == 'preset prompt'


def test_streamed_deltas_reach_the_event_stream(runtime):
    runtime.aichat.providers['llamacpp'] = StubProvider(STATELESS, reply='alpha beta gamma')
    actor, session = client(runtime)
    job = run(runtime, actor, session, 'chat', {'message': 'x', 'provider': 'llamacpp'})
    events = runtime.events(actor, 0)['events']
    kinds = [event['type'] for event in events]
    assert 'ChatTurnStarted' in kinds and 'ChatTurnCompleted' in kinds
    streamed = ''.join(event['data'].get('text', '') for event in events
                       if event['type'] == 'ChatDelta')
    assert streamed.strip() == 'alpha beta gamma'
    assert job['outputs']['text'] == 'alpha beta gamma'


def test_a_failed_turn_records_the_error_in_the_conversation(runtime):
    runtime.aichat.providers['llamacpp'] = StubProvider(STATELESS, fail='AuthenticationRequired')
    actor, session = client(runtime)
    job = runtime.submit(actor, session, 'chat', {'message': 'x', 'provider': 'llamacpp'})
    job = runtime.wait(actor, job['jobId'], timeout=30)
    assert job['state'] == 'Failed'
    assert job['error']['code'] == 'AuthenticationRequired'
    conversation = conversations.listing()[0]
    stored = conversations.load(conversation['id'])
    assert stored['messages'][-1]['failed'] is True
    assert stored['messages'][-1]['error'] == 'AuthenticationRequired'


def test_a_cancelled_turn_keeps_what_had_already_been_streamed(runtime):
    """Cancelling must record the partial reply, not erase the turn.

    The failure handler flushes the stream before writing the record, and
    `JobContext.progress` re-checks the cancellation token, so a flush that asks for a
    progress update raises a second time and loses the record.
    """
    runtime.aichat.providers['llamacpp'] = StubProvider(
        STATELESS, reply=' '.join(['word'] * 400), delay=0.02)
    actor, session = client(runtime)
    job = runtime.submit(actor, session, 'chat', {'message': 'x', 'provider': 'llamacpp'})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if runtime.get_job(actor, job['jobId'])['state'] == 'Running':
            break
        time.sleep(0.02)
    time.sleep(0.3)
    runtime.cancel(actor, job['jobId'])
    assert runtime.wait(actor, job['jobId'], timeout=30)['state'] == 'Cancelled'
    stored = conversations.load(conversations.listing()[0]['id'])
    last = stored['messages'][-1]
    assert last['role'] == 'assistant' and last['failed'] is True
    assert last['error'] == 'Cancelled'
    assert last['text'].startswith('word'), 'the streamed part must be kept'


def test_cancelling_a_turn_stops_it_and_frees_the_budget(runtime):
    runtime.aichat.providers['llamacpp'] = StubProvider(
        STATELESS, reply=' '.join(['word'] * 400), delay=0.02)
    actor, session = client(runtime)
    job = runtime.submit(actor, session, 'chat', {'message': 'x', 'provider': 'llamacpp'})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if runtime.get_job(actor, job['jobId'])['state'] == 'Running':
            break
        time.sleep(0.02)
    runtime.cancel(actor, job['jobId'])
    final = runtime.wait(actor, job['jobId'], timeout=30)
    assert final['state'] == 'Cancelled'
    # The budget must come back only once the turn really stopped, which is what the ledger
    # holding no reservation for that job proves.
    status = runtime.status()
    assert status['runningJobs'] == 0
    assert job['jobId'] not in status['resources']['reservations']
    assert status['resources']['available'] == status['resources']['capacity']
    # The message the user typed stays in the transcript so the turn can be tried again.
    stored = conversations.load(final['parameters'].get('conversation')
                                or conversations.listing()[0]['id'])
    assert stored['messages'][0]['text'] == 'x'


def test_continuing_a_remote_conversation_reserves_no_gpu(runtime):
    """A turn reserves its own overhead, never the weights.

    Continuing a conversation normally leaves `provider` and `model` out, and reading them
    back from the stored document is what stops a remote turn from being estimated as a
    local one. Neither kind reserves the device: that belongs to the resident worker.
    """
    document = conversations.create(provider_id='openai-compatible', model='remote-model')
    estimate = runtime.estimate_resources('chat', {'message': 'x', 'conversation': document['id']})
    assert 'vramBytes' not in estimate
    assert estimate['ramBytes'] <= 1024 ** 3
    # A local turn must not reserve the weights either: the resident worker holds them for
    # as long as its process runs. Counting them again here doubles the requirement and
    # refuses a 20B model that fits on the card.
    local = conversations.create(provider_id='llamacpp', model='gpt-oss-20b-heretic')
    estimate = runtime.estimate_resources('chat', {'message': 'x', 'conversation': local['id']})
    assert 'vramBytes' not in estimate, 'the worker reserves the device, not the job'
    assert estimate['ramBytes'] <= 1024 ** 3


def test_unknown_provider_and_missing_message_give_useful_errors(runtime):
    actor, session = client(runtime)
    with pytest.raises((CyToolError, ValueError)):
        runtime.submit(actor, session, 'chat', {'provider': 'llamacpp'})
    job = runtime.submit(actor, session, 'chat', {'message': 'x'})
    job = runtime.wait(actor, job['jobId'], timeout=30)
    assert job['state'] == 'Failed'
    assert job['error']['code'] == 'InvalidParameters'


def test_one_client_cannot_read_or_cancel_another_clients_turn(runtime):
    runtime.aichat.providers['llamacpp'] = StubProvider(STATELESS, reply='private')
    first_actor, first_session = client(runtime, 'first')
    second_actor, _ = client(runtime, 'second')
    job = run(runtime, first_actor, first_session, 'chat',
              {'message': 'x', 'provider': 'llamacpp'})
    with pytest.raises(CyToolError):
        runtime.get_job(second_actor, job['jobId'])
    with pytest.raises(CyToolError):
        runtime.cancel(second_actor, job['jobId'])


def test_conversation_operations_over_the_runtime(runtime):
    actor, session = client(runtime)
    created = run(runtime, actor, session, 'conversation_create',
                  {'title': 'from the runtime', 'provider': 'ollama'})
    conversation = created['outputs']['conversation']['id']
    listed = run(runtime, actor, session, 'conversation_list', {})
    assert any(row['id'] == conversation for row in listed['outputs']['conversations'])
    read = run(runtime, actor, session, 'conversation_read', {'conversation': conversation})
    assert read['outputs']['conversation']['title'] == 'from the runtime'
    removed = run(runtime, actor, session, 'conversation_delete', {'conversation': conversation})
    assert removed['outputs']['deleted'] is True


def test_provider_inventory_reports_every_declared_provider(runtime):
    actor, session = client(runtime)
    job = run(runtime, actor, session, 'list_providers', {}, timeout=180)
    reports = job['outputs']['providers']
    document = load_manifest(APP / 'CyTool.json')
    declared = set(next(op for op in document['operations']
                        if op['id'] == 'chat')['inputSchema']['properties']['provider']['enum'])
    declared.discard('')
    assert {row['id'] for row in reports} == declared
    for row in reports:
        assert 'status' in row and 'available' in row


# --------------------------------------------------------------------------- CyToolsCore 0.10

def test_installed_sdk_is_the_mit_release():
    import importlib.metadata as metadata
    distribution = metadata.distribution('cytools-core')
    version = tuple(int(part) for part in distribution.version.split('.')[:3])
    assert version >= (0, 10, 1), 'exclusion groups and the MIT notices need CyToolsCore 0.10.1'
    declared = (distribution.metadata.get('License-Expression')
                or distribution.metadata.get('License') or '')
    assert 'MIT' in declared


def test_release_verification_requires_the_licence_notices(tmp_path):
    staged = tmp_path / 'staged/app'
    staged.mkdir(parents=True)
    for name in ('CyTool.json', 'release.json'):
        (staged / name).write_text((APP / name).read_text('utf-8'), encoding='utf-8')
    (staged / 'tool.py').write_text('', encoding='utf-8')
    (staged / 'desktop.py').write_text('', encoding='utf-8')
    with pytest.raises(CyToolError) as error:
        maintenance.verify_application_tree(tmp_path / 'staged')
    assert error.value.code == 'InvalidArchive' and 'LICENCES' in str(error.value)
    notices = tmp_path / 'staged/LICENCES'
    notices.mkdir()
    for name in maintenance.REQUIRED_NOTICES:
        (notices / name).write_text('notice', encoding='utf-8')
    report = maintenance.verify_application_tree(tmp_path / 'staged')
    assert set(maintenance.REQUIRED_NOTICES) <= set(report['notices'])


def test_maintenance_operations_declare_exclusive_groups_and_chat_does_not():
    document = load_manifest(APP / 'CyTool.json')
    groups = {op['id']: set(op.get('exclusiveGroups', [])) for op in document['operations']}
    assert groups['model_install'] & groups['model_repair'] & groups['model_uninstall']
    assert groups['engine_install'] & groups['engine_remove']
    assert groups['update_download'] & groups['update_apply'] & groups['update_rollback']
    # Turns stay out of every group: tabs talking to different providers run together.
    assert not groups['chat']


def test_operations_sharing_a_group_never_overlap(runtime, monkeypatch):
    from aichat import catalog, library
    spans = []

    def slow(label, result):
        def run(*args, **kwargs):
            started = time.monotonic()
            time.sleep(0.4)
            spans.append((started, time.monotonic(), label))
            return dict(result)
        return run

    monkeypatch.setattr(catalog, 'repair', slow('repair', {
        'id': 'qwen25-1_5b', 'removedFiles': [], 'installed': True, 'repaired': False}))
    monkeypatch.setattr(catalog, 'uninstall', slow('uninstall', {
        'id': 'qwen25-1_5b', 'removedFiles': [], 'installed': False}))
    monkeypatch.setattr(catalog, 'file_path', lambda identifier: Path('unused'))
    monkeypatch.setattr(library, 'unregister_path', lambda path: 0)
    actor, session = client(runtime)
    first = runtime.submit(actor, session, 'model_repair', {'model': 'qwen25-1_5b'})
    second = runtime.submit(actor, session, 'model_uninstall', {'model': 'qwen25-1_5b'})
    for job in (first, second):
        final = runtime.wait(actor, job['jobId'], timeout=30)
        assert final['state'] == 'Completed', final.get('error')
    (_, first_end, _), (second_start, _, _) = sorted(spans)
    assert second_start >= first_end, 'two operations of the same group ran at the same time'


def test_turns_in_different_tabs_still_run_together(runtime):
    spans = []

    class Timed(StubProvider):
        def chat(self, request, on_delta):
            started = time.monotonic()
            time.sleep(0.4)
            spans.append((started, time.monotonic()))
            return ChatResult('ok', model=request.model, transport='local-server', seconds=0.4)

    runtime.aichat.providers['llamacpp'] = Timed(STATELESS)
    actor, session = client(runtime)
    jobs = [runtime.submit(actor, session, 'chat', {'message': 'x', 'provider': 'llamacpp'})
            for _ in range(2)]
    for job in jobs:
        assert runtime.wait(actor, job['jobId'], timeout=30)['state'] == 'Completed'
    (_, first_end), (second_start, _) = sorted(spans)
    assert second_start < first_end, 'turns were serialised: tabs no longer talk at the same time'


# --------------------------------------------------------------------------- speech

def _wav(path, seconds=1.0, rate=16000):
    import math
    import struct
    import wave
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        frames = int(seconds * rate)
        output.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(i / 8.0)))
                                    for i in range(frames)))
    return path


def _installed_rows(monkeypatch, *identifiers):
    from aichat import catalog, speech
    rows = {kind: [dict(catalog.status(key), installed=True) for key in identifiers
                   if catalog.entry(key)['kind'] == kind] for kind in ('stt', 'tts')}
    monkeypatch.setattr(speech.Speech, '_installed', staticmethod(lambda kind: rows[kind]))


def test_speech_catalogue_entries_are_pinned_and_complete():
    from aichat import catalog
    rows = {key: info for key, info in catalog.kinds().items() if info['kind'] in ('stt', 'tts')}
    assert {'phonon-2', 'parakeet-tdt-0.6b-v3', 'xtts-v2', 'f5-tts-french', 'f5-tts-v1-base',
            'vocos-mel-24khz'} <= set(rows)
    for key, info in rows.items():
        assert len(info['revision']) == 40, key
        names = [item['name'] for item in info['files']]
        assert len(names) == len(set(names)), key
        for item in info['files']:
            assert len(item['sha256']) == 64 and item['size'] > 0, (key, item['name'])
        if info.get('family') == 'f5':
            assert info['checkpoint'] in names and info['baseModel'] == 'vocos-mel-24khz'
            assert info['architecture'] in ('F5TTS_Base', 'F5TTS_v1_Base')
    phonon = rows['phonon-2']
    assert phonon['archive'] in [item['name'] for item in phonon['files']]
    assert len(phonon['containerSha256']) == 64
    # A file may come from another repository, at another path than its local name.
    tokenizer = next(item for item in phonon['files'] if item['name'] == 'tokenizer.json')
    assert catalog.url_for(phonon, tokenizer).startswith(
        'https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/resolve/')
    f5 = rows['f5-tts-v1-base']
    assert catalog.url_for(f5, f5['files'][0]).endswith('/F5TTS_v1_Base/model_1250000.safetensors')


def test_speech_models_live_apart_from_chat_weights(workspace):
    from aichat import catalog
    assert catalog.directory('xtts-v2') == paths.SPEECH_MODELS / 'xtts-v2'
    assert catalog.file_path('phonon-2') == paths.SPEECH_MODELS / 'phonon-2'


def test_language_is_guessed_from_the_text():
    from aichat import voices
    assert voices.guess_language("Bonjour, je voudrais réserver une table pour ce soir.") == 'fr'
    assert voices.guess_language('Hello, I would like to book a table for tonight.') == 'en'
    assert voices.guess_language('12345', fallback='fr') == 'fr'


def test_speech_settings_are_kept_and_checked(workspace):
    from aichat import voices
    stored = voices.configure(language='fr', speed=5, autoRead=True)
    assert stored['speed'] == 2.0 and stored['language'] == 'fr' and stored['autoRead'] is True
    assert voices.settings()['language'] == 'fr'
    with pytest.raises(CyToolError):
        voices.configure(language='not a language')


def test_a_voice_is_kept_with_its_clip_and_deleting_moves_it(workspace, tmp_path):
    from aichat import voices
    source = _wav(tmp_path / 'outside' / 'ma voix.wav')
    identifier = voices.add(source, 'Ma voix', 'fr', 'Bonjour à tous.')
    listed = next(voice for voice in voices.recorded() if voice['id'] == identifier)
    assert listed['transcript'] == 'Bonjour à tous.' and Path(listed['clip']).is_file()
    assert source.is_file()
    result = voices.delete(identifier)
    assert result['deleted'] and Path(result['keptIn']).is_dir()
    assert all(voice['id'] != identifier for voice in voices.recorded())


def test_transcribe_imports_the_file_and_never_hands_over_the_original(runtime, monkeypatch,
                                                                       tmp_path):
    from aichat import speech
    _installed_rows(monkeypatch, 'parakeet-tdt-0.6b-v3', 'phonon-2')
    seen = []

    def call(self, context, request, timeout=900.0, on_event=None):
        seen.append(request)
        return {'text': 'bonjour', 'audioSeconds': 1.0, 'seconds': 0.1, 'loadSeconds': 0.0}

    monkeypatch.setattr(speech.SpeechWorker, 'call', call)
    monkeypatch.setattr(speech.SpeechWorker, 'reserve_for', lambda *args: None)
    original = _wav(tmp_path / 'élément externe' / 'dictée.wav')
    actor, session = client(runtime)
    final = run(runtime, actor, session, 'transcribe', {'audio': str(original)})
    assert final['state'] == 'Completed', final.get('error')
    assert final['outputs']['text'] == 'bonjour'
    # French by default: the multilingual model, unless English is asked for.
    assert final['outputs']['model'] == 'parakeet-tdt-0.6b-v3'
    assert Path(seen[0]['audio']) != original and original.is_file()
    english = run(runtime, actor, session, 'transcribe', {'audio': str(original), 'language': 'en'})
    assert english['outputs']['model'] == 'phonon-2'


def test_speak_reads_the_stored_reply_and_reuses_the_audio(runtime, monkeypatch, workspace):
    from aichat import speech
    _installed_rows(monkeypatch, 'xtts-v2')
    monkeypatch.setattr(speech.Speech, 'speakers', lambda self, context=None: ['Studio One'])
    monkeypatch.setattr(speech.Speech, 'f5_example', lambda self: '')
    monkeypatch.setattr(speech.SpeechWorker, 'reserve_for', lambda *args: None)
    monkeypatch.setattr(speech.speech_env, 'status',
                        lambda name: {'installed': True, 'cuda': False})
    calls = []

    def call(self, context, request, timeout=900.0, on_event=None):
        calls.append(request)
        _wav(Path(request['output']), seconds=0.5, rate=24000)
        return {'output': request['output'], 'sampleRate': 24000, 'durationSeconds': 0.5,
                'seconds': 0.2, 'loadSeconds': 0.0, 'device': 'cpu'}

    monkeypatch.setattr(speech.SpeechWorker, 'call', call)
    document = conversations.create(title='speech')
    message = conversations.append(document['id'], 'assistant', 'Bonjour, voici la réponse.')
    actor, session = client(runtime)
    parameters = {'conversation': document['id'], 'message': message['id'],
                  'text': 'something the caller made up'}
    first = run(runtime, actor, session, 'speak', parameters)
    assert first['state'] == 'Completed', first.get('error')
    assert calls[0]['text'] == 'Bonjour, voici la réponse.'
    assert calls[0]['language'] == 'fr' and calls[0]['voice'] == {'speaker': 'Studio One'}
    assert Path(first['outputs']['audio']).parent == paths.SPEECH
    second = run(runtime, actor, session, 'speak', parameters)
    assert second['outputs']['cached'] is True and len(calls) == 1


def test_an_f5_voice_without_words_is_transcribed_once(workspace, monkeypatch, tmp_path):
    from aichat import speech, voices
    identifier = voices.add(_wav(tmp_path / 'clip.wav'), 'Clip', 'fr', '')
    manager = speech.Speech.__new__(speech.Speech)
    manager._speakers = []
    monkeypatch.setattr(speech.Speech, 'f5_example', lambda self: '')
    heard = []

    def transcribe(self, context, audio, model='', language=''):
        heard.append(audio)
        return {'text': 'les mots du clip'}

    monkeypatch.setattr(speech.Speech, 'transcribe', transcribe)

    class Context:
        def progress(self, *args, **kwargs):
            pass

    voice, spec = manager.resolve_voice(Context(), identifier, 'f5', 'fr')
    assert spec['transcript'] == 'les mots du clip' and len(heard) == 1
    manager.resolve_voice(Context(), identifier, 'f5', 'fr')
    assert len(heard) == 1


def test_the_speech_worker_gets_no_token_and_no_key(workspace, monkeypatch):
    from aichat import speech
    monkeypatch.setenv('CYTOOLS_TOKEN', 'secret-token')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-secret')
    monkeypatch.setattr(speech.speech_env, 'status', lambda name: {'installed': True})
    captured = {}

    class Stop(Exception):
        pass

    def popen(command, **options):
        captured.update(options['env'])
        raise Stop()

    monkeypatch.setattr(speech.subprocess, 'Popen', popen)

    class Runtime:
        def register_worker(self, *args):
            pass

    worker = speech.SpeechWorker(Runtime(), 'tts')
    with pytest.raises(Stop):
        worker._start(None)
    worker.log.close()
    assert 'CYTOOLS_TOKEN' not in captured and 'OPENAI_API_KEY' not in captured
    assert captured['HF_HUB_OFFLINE'] == '1'


def _speech_like(seconds, rate=16000):
    import numpy as np
    t = np.arange(int(seconds * rate)) / rate
    # A tone with a syllable-like envelope: voiced for the energy detector, not silence.
    return (0.3 * np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)


def test_a_sentence_is_closed_in_the_middle_of_a_pause():
    import numpy as np
    from aichat import speech
    rate = 16000
    audio = np.concatenate([_speech_like(2.0), np.zeros(int(0.8 * rate), np.float32)])
    cut = speech.segment_end(audio, rate)
    assert cut is not None and 2.0 * rate < cut < len(audio)
    # Still speaking, or a pause too short to be one: the sentence stays open.
    assert speech.segment_end(_speech_like(2.0), rate) is None
    short = np.concatenate([_speech_like(2.0), np.zeros(int(0.2 * rate), np.float32)])
    assert speech.segment_end(short, rate) is None
    # Nothing but silence is never sent to the model.
    assert not speech.has_speech(np.zeros(rate * 2, np.float32), rate)
    # While speaking, half a second is not enough to show a guess; the last pass takes it.
    assert not speech.has_speech(_speech_like(0.5), rate, final=False)
    assert speech.has_speech(_speech_like(0.5), rate, final=True)


def test_live_dictation_publishes_the_words_and_returns_the_whole_text(runtime, monkeypatch):
    import wave
    import numpy as np
    from aichat import speech
    _installed_rows(monkeypatch, 'parakeet-tdt-0.6b-v3')
    monkeypatch.setattr(speech.SpeechWorker, 'reserve_for', lambda *args: None)
    monkeypatch.setattr(speech, 'LIVE_POLL', 0.05)
    decoded = []

    def call(self, context, request, timeout=900.0, on_event=None):
        if request['command'] == 'load_stt':
            return {'loadSeconds': 0.0, 'device': 'cpu'}
        with wave.open(request['audio'], 'rb') as clip:
            seconds = clip.getnframes() / float(clip.getframerate())
        decoded.append(seconds)
        return {'text': 'phrase de %.0f secondes' % seconds, 'audioSeconds': seconds,
                'seconds': 0.0, 'loadSeconds': 0.0}

    monkeypatch.setattr(speech.SpeechWorker, 'call', call)
    rate = 16000
    folder = paths.INPUTS / 'dictation'
    folder.mkdir(parents=True, exist_ok=True)
    stream = folder / 'live-test.pcm'
    stream.write_bytes(b'')
    actor, session = client(runtime)
    job = runtime.submit(actor, session, 'transcribe_live', {'stream': stream.name, 'rate': rate})
    first = np.concatenate([_speech_like(3.0), np.zeros(int(0.9 * rate), np.float32)])
    with stream.open('ab') as output:
        output.write((first * 32767).astype('<i2').tobytes())
    # The second sentence is spoken only once the first one was closed at the pause, as it is
    # when a person talks; writing everything at once would leave nothing to follow live.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        events = [event for event in runtime.events(actor, 0)['events']
                  if event['type'] == 'DictationPartial' and event['jobId'] == job['jobId']]
        if any(event['data']['committed'] for event in events):
            break
        time.sleep(0.05)
    with stream.open('ab') as output:
        output.write((_speech_like(2.0) * 32767).astype('<i2').tobytes())
    (folder / (stream.name + '.done')).write_bytes(b'')
    final = runtime.wait(actor, job['jobId'], timeout=60)
    assert final['state'] == 'Completed', final.get('error')
    # The first sentence was closed at the pause and transcribed on its own.
    assert final['outputs']['text'].startswith('phrase de 3 secondes phrase de 2 secondes')
    partials = [event for event in runtime.events(actor, 0)['events']
                if event['type'] == 'DictationPartial' and event['jobId'] == job['jobId']]
    assert partials and partials[-1]['data']['final'] is True
    assert not stream.exists() and not (folder / (stream.name + '.done')).exists()


def test_live_dictation_only_follows_its_own_recordings(runtime):
    actor, session = client(runtime)
    for name in ('../outside.pcm', 'C:/Windows/win.ini', 'notes.txt'):
        final = run(runtime, actor, session, 'transcribe_live', {'stream': name, 'rate': 16000})
        assert final['state'] == 'Failed' and final['error']['code'] == 'InvalidParameters'


def test_the_window_treats_every_unfinished_job_as_running():
    from gui.state import active
    for state in ('Created', 'Queued', 'WaitingForResources', 'Preparing', 'LoadingModel',
                  'Running', 'Paused', 'Cancelling'):
        assert active({'state': state}), state
    for state in ('Completed', 'Failed', 'Cancelled'):
        assert not active({'state': state}), state
    assert not active(None)


def test_a_markdown_reply_is_read_as_words():
    from aichat.speech_text import speakable
    reply = ("## Résultat\n\nCeci est un **test** de lecture. Le fichier `gui/audio.py` compte.\n\n"
             "- premier point\n- un [lien](https://example.com) et https://example.org/x\n\n"
             "```python\nprint('jamais lu')\n```\n\n| Modèle | Langue |\n|---|---|\n| XTTS | fr |\n")
    spoken = speakable(reply)
    for absent in ('`', '**', '#', 'http', 'jamais lu', '|', '---', 'print'):
        assert absent not in spoken, absent
    assert spoken.startswith('Résultat. Ceci est un test de lecture.')
    assert 'gui audio.py' in spoken and 'Premier point.' not in spoken and 'premier point.' in spoken
    assert 'Modèle, Langue.' in spoken
    assert speakable('```\nonly code\n```') == ''


def test_long_text_is_cut_below_the_xtts_limit_of_the_language():
    from aichat.speech_text import LIMITS, sentences
    text = 'Une phrase courte. ' * 3 + 'Une très longue phrase, avec des virgules, ' * 15 + 'fin.'
    pieces = sentences(text, 'fr')
    assert all(len(piece) <= LIMITS['fr'] for piece in pieces)
    assert pieces[0].startswith('Une phrase courte. Une phrase courte.')
    assert ' '.join(pieces).replace('  ', ' ') .split() == text.split()
    assert all(len(piece) <= LIMITS['ja'] for piece in sentences('あ' * 500, 'ja'))


def test_a_reply_with_only_code_is_refused_before_any_model_runs(runtime, monkeypatch):
    from aichat import speech
    _installed_rows(monkeypatch, 'xtts-v2')
    monkeypatch.setattr(speech.SpeechWorker, 'call', lambda *args, **kwargs: pytest.fail('ran'))
    actor, session = client(runtime)
    final = run(runtime, actor, session, 'speak', {'text': '```\nprint(1)\n```'})
    assert final['state'] == 'Failed' and final['error']['code'] == 'InvalidParameters'


def test_a_reading_is_announced_sentence_by_sentence(runtime, monkeypatch, workspace):
    from aichat import speech
    _installed_rows(monkeypatch, 'xtts-v2')
    monkeypatch.setattr(speech.Speech, 'speakers', lambda self, context=None: ['Studio One'])
    monkeypatch.setattr(speech.Speech, 'f5_example', lambda self: '')
    monkeypatch.setattr(speech.SpeechWorker, 'reserve_for', lambda *args: None)
    monkeypatch.setattr(speech.speech_env, 'status', lambda name: {'installed': True, 'cuda': False})
    seen = {}

    def call(self, context, request, timeout=900.0, on_event=None):
        seen.update(request)
        for index, piece in enumerate(request['pieces']):
            path = Path(request['pieceDir']) / ('%s-%03d.wav' % (request['piecePrefix'], index))
            _wav(path, seconds=0.2, rate=24000)
            on_event({'event': 'piece', 'index': index, 'count': len(request['pieces']),
                      'path': str(path), 'sampleRate': 24000, 'durationSeconds': 0.2})
        _wav(Path(request['output']), seconds=0.5, rate=24000)
        return {'output': request['output'], 'sampleRate': 24000, 'durationSeconds': 0.5,
                'seconds': 0.1, 'loadSeconds': 0.0, 'device': 'cpu'}

    monkeypatch.setattr(speech.SpeechWorker, 'call', call)
    text = ('Bonjour, voici une première phrase assez longue pour être lue seule et vite. '
            + 'Puis une suite, avec beaucoup de mots, qui continue encore longtemps. ' * 6)
    actor, session = client(runtime)
    final = run(runtime, actor, session, 'speak', {'text': text, 'progressive': True})
    assert final['state'] == 'Completed', final.get('error')
    pieces = [event['data'] for event in runtime.events(actor, 0)['events']
              if event['type'] == 'SpeechPiece' and event['jobId'] == final['jobId']]
    assert len(pieces) == len(seen['pieces']) >= 2
    assert [piece['index'] for piece in pieces] == list(range(len(pieces)))
    # The first sentence is kept short so the voice starts quickly.
    assert len(seen['pieces'][0]) <= speech.FIRST_PIECE
    assert seen['cancelFile'] and not Path(seen['cancelFile']).exists()


def test_stopping_a_reading_asks_the_worker_to_stop_instead_of_killing_it(monkeypatch, tmp_path):
    import queue as queues
    from aichat import speech

    class Process:
        pid = 1

        def __init__(self):
            self.stdin = self

        def write(self, text):
            pass

        def flush(self):
            pass

        def poll(self):
            return None

    class Cancellation:
        def check(self):
            raise CyToolError('Cancelled', 'stop')

    class Context:
        cancellation = Cancellation()

    worker = speech.SpeechWorker.__new__(speech.SpeechWorker)
    worker.engine, worker.counter, worker.process = 'tts', 0, Process()
    worker.replies = queues.Queue()
    stopped = []
    worker.stop = lambda: stopped.append(True)
    cancel_file = tmp_path / 'job.cancel'

    def answer_after_cancel():
        import time as clock
        while not cancel_file.exists():
            clock.sleep(0.01)
        worker.replies.put({'id': 1, 'ok': False, 'error': {'code': 'Cancelled', 'message': ''}})

    threading.Thread(target=answer_after_cancel, daemon=True).start()
    with pytest.raises(CyToolError) as error:
        worker._exchange(Context(), {'command': 'speak', 'cancelFile': str(cancel_file)}, 30)
    assert error.value.code == 'Cancelled' and cancel_file.exists() and not stopped


def test_the_player_plays_queued_sentences_end_to_end(monkeypatch):
    import numpy as np
    from gui.audio import Player
    player = Player()
    monkeypatch.setattr(player, '_open', lambda rate: setattr(player, 'rate', rate))
    player.append(np.ones(5, np.float32), 24000, 'read-1')
    player.append(np.full(4, 2.0, np.float32), 24000, 'read-1')
    out = np.zeros((7, 1), np.float32)
    player._callback(out, 7, None, None)
    assert out[:, 0].tolist() == [1, 1, 1, 1, 1, 2, 2] and player.playing
    out = np.zeros((4, 1), np.float32)
    player._callback(out, 4, None, None)
    assert out[:, 0].tolist() == [2, 2, 0, 0] and not player.playing
    # Another reading replaces the first one at once.
    player.append(np.ones(3, np.float32), 24000, 'read-1')
    player.append(np.full(3, 3.0, np.float32), 24000, 'read-2')
    out = np.zeros((3, 1), np.float32)
    player._callback(out, 3, None, None)
    assert out[:, 0].tolist() == [3, 3, 3] and player.current == 'read-2'
