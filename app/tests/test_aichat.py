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
                 'LLM_MODELS', 'LORA_MODELS'):
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
    installed = [row for row in catalog.listing() if row['installed']]
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
