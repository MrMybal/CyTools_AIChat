"""Cancel a real local inference and check that the budget comes back only once it stopped.

The pytest suite cancels a stub provider, which proves the job machinery. This proves the
part that matters for a real model: a long generation on the llama.cpp server is interrupted
mid-stream, the socket is closed, the server survives, the reservation is released, and the
next turn still works — so cancelling is not a way to leave the GPU half-held.

    runtime/python/Scripts/python.exe app/tests/acceptance_cancel.py [--engine cuda|cpu]

Writes data/reports/cancellation.json.
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
from tool import create_runtime  # noqa: E402

MODEL = 'qwen25-1_5b'
LONG_PROMPT = ('Write a long, detailed essay about the history of file formats. '
               'Do not stop before you have written several hundred words.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='cuda', choices=['cpu', 'cuda'])
    arguments = parser.parse_args()
    paths.ensure_tree()
    if not catalog.installed(MODEL):
        raise SystemExit('Install %s first (model_install).' % MODEL)

    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'engine': arguments.engine,
              'model': MODEL}
    with create_runtime(ROOT / 'data/jobs') as runtime:
        actor = runtime.authenticate(runtime.create_client(
            'acceptance-cancel',
            ['network', 'processSpawn', 'filesystemExternal', 'manageResources'])['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']
        resident = runtime.aichat.resident
        conversation = conversations.create(title='Cancellation acceptance')['id']

        base = {'conversation': conversation, 'provider': 'llamacpp', 'model': MODEL,
                'engine': arguments.engine, 'keep_loaded': True, 'max_tokens': 2000,
                'temperature': 0.8, 'history_limit': 1}

        # A first short turn loads the model, so the cancellation below lands during the
        # generation rather than during the model load.
        warmup = runtime.submit(actor, session, 'chat', dict(base, message='Say OK.',
                                                             max_tokens=10))
        warmup = runtime.wait(actor, warmup['jobId'], timeout=600)
        report['warmup'] = {'state': warmup['state'],
                            'text': (warmup.get('outputs') or {}).get('text', '')}
        report['residentBeforeCancel'] = resident.health()
        pid_before = resident.health().get('pid')

        job = runtime.submit(actor, session, 'chat', dict(base, message=LONG_PROMPT))
        streamed = 0
        cursor = 0
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            batch = runtime.events(actor, cursor)
            cursor = batch['cursor']
            for event in batch['events']:
                if event['type'] == 'ChatDelta':
                    streamed += len(event['data'].get('text', ''))
            if streamed > 80:
                break
            time.sleep(0.05)
        report['charactersBeforeCancel'] = streamed
        requested = time.monotonic()
        runtime.cancel(actor, job['jobId'])
        final = runtime.wait(actor, job['jobId'], timeout=120)
        report['cancelledAfterSeconds'] = round(time.monotonic() - requested, 3)
        report['cancelledJob'] = {'state': final['state'],
                                  'error': (final.get('error') or {}).get('code')}

        status = runtime.status()
        report['runningJobsAfterCancel'] = status['runningJobs']
        reservations = list(status['resources']['reservations'])
        report['reservationsAfterCancel'] = reservations
        # The resident model keeps its reservation on purpose: `keep_loaded` means the
        # weights stay in memory for the next turn, and a budget released while the process
        # still holds the GPU would be a lie. What must be gone is the job's own reservation.
        report['jobReservationReleased'] = job['jobId'] not in reservations
        report['onlyResidentStillReserved'] = set(reservations) <= {'worker:llamacpp-server'}
        report['residentAfterCancel'] = resident.health()
        report['residentStillLoaded'] = resident.health()['loaded']

        stored = conversations.load(conversation)
        report['transcriptAfterCancel'] = [
            {'role': m['role'], 'failed': bool(m.get('failed')), 'error': m.get('error', ''),
             'characters': len(m.get('text', ''))} for m in stored['messages']]
        # The cancelled turn must leave a trace: the message that was typed, and a reply
        # marked as cancelled holding whatever had been streamed before the stop.
        report['cancelledTurnRecorded'] = any(
            m['failed'] and m['error'] == 'Cancelled' for m in report['transcriptAfterCancel'])

        # The point of the whole exercise: the Tool is still usable afterwards.
        after = runtime.submit(actor, session, 'chat',
                               dict(base, message='Say DONE.', max_tokens=10))
        after = runtime.wait(actor, after['jobId'], timeout=600)
        report['turnAfterCancel'] = {'state': after['state'],
                                     'text': (after.get('outputs') or {}).get('text', '')}
        report['sameServerProcess'] = resident.health().get('pid') == pid_before
        conversations.delete(conversation)

    report['verdict'] = (
        'Cancellation stops the generation, releases the budget and leaves the Tool usable.'
        if report['cancelledJob']['state'] == 'Cancelled'
        and report['jobReservationReleased'] and report['onlyResidentStillReserved']
        and report['cancelledTurnRecorded']
        and report['turnAfterCancel']['state'] == 'Completed'
        else 'Something did not behave as specified; read the report.')
    destination = paths.REPORTS / 'cancellation.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: report[key] for key in
                      ('verdict', 'charactersBeforeCancel', 'cancelledAfterSeconds',
                       'cancelledJob', 'runningJobsAfterCancel', 'reservationsAfterCancel',
                       'jobReservationReleased', 'onlyResidentStillReserved',
                       'residentStillLoaded', 'cancelledTurnRecorded', 'turnAfterCancel',
                       'sameServerProcess', 'transcriptAfterCancel')}, indent=2, ensure_ascii=False))
    print('report:', destination)
    return 0 if report['verdict'].startswith('Cancellation') else 1


if __name__ == '__main__':
    raise SystemExit(main())
