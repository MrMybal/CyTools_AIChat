"""Load every installed local model in turn and make it answer.

Copying a file and checking its digest proves the bytes arrived. It does not prove the
engine can load that architecture, that the weights fit in the device, or that the chat
template produces an answer rather than a wall of tags. This script does the only thing
that proves it: for each installed model it starts the server, sends one short prompt on
the real runtime, and records the architecture, the device, the load time and the reply.

Each model is unloaded before the next one, so the measurements are not a chain of
leftovers and a 20B failure cannot be blamed on the previous model still holding VRAM.

    runtime/python/Scripts/python.exe app/tests/acceptance_models.py [--engine cuda|cpu]
                                                                    [--models a b c]

Writes data/reports/local-models.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from aichat import catalog, conversations, paths  # noqa: E402
from aichat.gguf_header import describe  # noqa: E402
from tool import create_runtime  # noqa: E402

# A real question with a modest budget rather than a three-word reply: with this shape a
# reasoning model can spend the whole budget thinking and answer nothing.
PROMPT = "Reponds en une phrase : qu'est-ce qu'un fichier GGUF ?"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='cuda', choices=['cpu', 'cuda'])
    parser.add_argument('--models', nargs='*', default=[])
    arguments = parser.parse_args()
    paths.ensure_tree()

    wanted = set(arguments.models)
    installed = [row for row in catalog.listing('model')
                 if row['installed'] and (not wanted or row['id'] in wanted)]
    if not installed:
        raise SystemExit('No local model is installed.')

    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'engine': arguments.engine,
              'prompt': PROMPT, 'models': []}
    with create_runtime(ROOT / 'data/jobs') as runtime:
        actor = runtime.authenticate(runtime.create_client(
            'acceptance-models',
            ['network', 'processSpawn', 'filesystemExternal', 'manageResources'])['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']
        resident = runtime.aichat.resident

        for row in installed:
            header = {}
            try:
                header = describe(catalog.file_path(row['id']))
            except Exception as exc:
                header = {'error': str(exc)}
            entry = {'id': row['id'], 'name': row['name'],
                     'architecture': header.get('architecture', ''),
                     'sizeGiB': round(row['sizeBytes'] / 1024 ** 3, 2),
                     'declaredContextTokens': row.get('contextTokens', 0),
                     'license': row['license']}
            conversation = conversations.create(title='Model check: ' + row['id'])['id']
            started = time.monotonic()
            job = runtime.submit(actor, session, 'chat', {
                'conversation': conversation, 'message': PROMPT, 'provider': 'llamacpp',
                'model': row['id'], 'engine': arguments.engine, 'keep_loaded': True,
                'max_tokens': 120, 'temperature': 0.2, 'history_limit': 1})
            job = runtime.wait(actor, job['jobId'], timeout=1800)
            outputs = job.get('outputs') or {}
            entry.update(state=job['state'],
                         totalSeconds=round(time.monotonic() - started, 2),
                         generationSeconds=outputs.get('seconds'),
                         reply=' '.join((outputs.get('text') or '').split())[:200],
                         thinkingCharacters=outputs.get('thinkingCharacters'),
                         error=(job.get('error') or {}).get('code'),
                         errorMessage=(job.get('error') or {}).get('message', '')[:300])
            health = resident.health()
            entry['device'] = health.get('device', '')
            entry['contextTokens'] = health.get('contextTokens', 0)
            print('%-24s %-10s %-9s %6.1fs  %s'
                  % (row['id'], entry['architecture'], entry['state'], entry['totalSeconds'],
                     entry['reply'][:60] or entry.get('errorMessage', '')[:60]))
            report['models'].append(entry)
            conversations.delete(conversation)
            # Unload between models: the next one must load on a clean device.
            resident.stop()

    report['loaded'] = sum(1 for m in report['models'] if m['state'] == 'Completed')
    report['failed'] = [m['id'] for m in report['models'] if m['state'] != 'Completed']
    report['verdict'] = ('Every installed model loads and answers on this machine.'
                         if not report['failed'] else
                         'These models did not answer: ' + ', '.join(report['failed']))
    destination = paths.REPORTS / 'local-models.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('\n%s' % report['verdict'])
    print('report:', destination)
    return 0 if not report['failed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
