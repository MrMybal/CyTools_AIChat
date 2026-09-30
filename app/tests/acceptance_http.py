"""Exercise the OpenAI-compatible provider against a real HTTP endpoint.

The adapter behind `openai-compatible` is the same one `openai` and `openrouter` use, so
testing it against a real server tests all three request paths; what is left untested with a
commercial endpoint is the account, the billing and the model catalogue, not the protocol.

The endpoint here is a llama.cpp server this script starts itself, on the loopback
interface, with no API key: from the Tool's point of view it is indistinguishable from
LM Studio, vLLM or a company gateway. A server started by the script keeps the result
reproducible without a paid key.

    runtime/python/Scripts/python.exe app/tests/acceptance_http.py [--engine cuda|cpu]

Writes data/reports/http-provider.json.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from aichat import catalog, conversations, engine, paths  # noqa: E402
from tool import create_runtime  # noqa: E402

MODEL = 'qwen25-1_5b'


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def wait_ready(port, process, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit('llama-server stopped while starting; see the log.')
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/health' % port, timeout=3) as answer:
                if json.load(answer).get('status') == 'ok':
                    return True
        except (OSError, ValueError, urllib.error.URLError):
            time.sleep(0.25)
    raise SystemExit('The endpoint did not become ready in time.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='cuda', choices=['cpu', 'cuda'])
    arguments = parser.parse_args()
    paths.ensure_tree()
    if not catalog.installed(MODEL):
        raise SystemExit('Install %s first (model_install).' % MODEL)
    server = engine.server_path(engine.available_build(arguments.engine))
    port = free_port()
    log = (paths.LOGS / 'http-acceptance-server.log').open('wb')
    command = [str(server), '-m', str(catalog.file_path(MODEL)), '--host', '127.0.0.1',
               '--port', str(port), '-c', '4096', '--no-webui', '--no-mmproj-auto',
               '-ngl', '999' if arguments.engine == 'cuda' else '0', '-np', '1']
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                               creationflags=0x08000000 if os.name == 'nt' else 0)
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'endpoint': 'http://127.0.0.1:%d/v1' % port,
              'server': str(server), 'engine': arguments.engine,
              'note': 'A llama.cpp server started by this script, with no API key, standing '
                      'in for any OpenAI-compatible endpoint.'}
    try:
        wait_ready(port, process)
        base_url = 'http://127.0.0.1:%d/v1' % port
        with create_runtime(ROOT / 'data/jobs') as runtime:
            actor = runtime.authenticate(runtime.create_client(
                'acceptance-http',
                ['network', 'processSpawn', 'filesystemExternal', 'manageResources'])['token'])
            session = runtime.create_session(actor, temporary=False)['sessionId']
            provider = runtime.aichat.get('openai-compatible')
            provider.settings['base_url'] = base_url

            models = provider.list_models()
            report['models'] = models
            model_id = models[0]['id'] if models else 'local'

            conversation = conversations.create(title='HTTP provider acceptance')['id']
            first = runtime.submit(actor, session, 'chat', {
                'conversation': conversation, 'message': 'Answer with exactly: HTTP_OK',
                'provider': 'openai-compatible', 'model': model_id,
                'max_tokens': 40, 'temperature': 0.0,
                'settings': {'base_url': base_url}})
            first = runtime.wait(actor, first['jobId'], timeout=300)
            report['firstJob'] = {'state': first['state'],
                                  'error': first.get('error'),
                                  'text': (first.get('outputs') or {}).get('text', ''),
                                  'transport': (first.get('outputs') or {}).get('transport', '')}

            # A second turn proves the transcript is what carries the context for a
            # stateless provider: nothing is remembered on the server side.
            second = runtime.submit(actor, session, 'chat', {
                'conversation': conversation,
                'message': 'What token did you just answer with? Reply with that token only.',
                'max_tokens': 40, 'temperature': 0.0,
                'settings': {'base_url': base_url}})
            second = runtime.wait(actor, second['jobId'], timeout=300)
            report['secondJob'] = {'state': second['state'],
                                   'text': (second.get('outputs') or {}).get('text', '')}

            events = runtime.events(actor, 0)['events']
            streamed = ''.join(event['data'].get('text', '') for event in events
                               if event['type'] == 'ChatDelta')
            report['streamedCharacters'] = len(streamed)
            report['storedMessages'] = [
                {'role': m['role'], 'text': m['text'][:120]}
                for m in conversations.load(conversation)['messages']]

            # A wrong endpoint must fail with a network error, not a stack trace.
            broken = runtime.submit(actor, session, 'chat', {
                'message': 'x', 'provider': 'openai-compatible', 'model': model_id,
                'settings': {'base_url': 'http://127.0.0.1:1/v1'}})
            broken = runtime.wait(actor, broken['jobId'], timeout=120)
            report['unreachableEndpoint'] = {'state': broken['state'],
                                             'code': (broken.get('error') or {}).get('code')}
            conversations.delete(conversation)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        log.close()

    destination = paths.REPORTS / 'http-provider.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: report[key] for key in
                      ('endpoint', 'firstJob', 'secondJob', 'streamedCharacters',
                       'unreachableEndpoint')}, indent=2, ensure_ascii=False))
    print('models advertised by the endpoint:', [row['id'] for row in report.get('models', [])])
    print('report:', destination)
    return 0 if report['firstJob']['state'] == 'Completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
