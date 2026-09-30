"""Evidence that the local provider really loads a GGUF LoRA and really applies its weight.

Running a prompt with an adapter and seeing a different answer proves nothing on its own: a
different prompt, a different seed or ordinary sampling noise would do the same. This script
therefore holds everything else fixed — same model, same prompt, same seed, temperature 0 —
and varies only the adapter scale:

  1. the base model with no adapter at all;
  2. the same server with the adapter loaded at scale 0, which must reproduce the base reply;
  3. the same server with the adapter at scale 1, which must change it.

Step 2 is the real control. If loading the adapter changed the reply while its weight was
zero, the adapter would not be what caused the change in step 3. The server is also asked
what it has loaded, so the claim does not rest on the output alone.

    runtime/python/Scripts/python.exe app/tests/acceptance_local.py [--engine cuda|cpu]

The report is written to data/reports/local-lora.json.
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

from aichat import catalog, conversations, library, paths  # noqa: E402
from tool import create_runtime  # noqa: E402

MODEL = 'qwen25-1_5b'
LORA = 'lora-qwen25-abliterated'
PROMPT = 'Write one short sentence about the sea.'


def turn(runtime, actor, session, conversation, loras, engine):
    parameters = {'message': PROMPT, 'conversation': conversation, 'provider': 'llamacpp',
                  'model': MODEL, 'max_tokens': 60, 'temperature': 0.0, 'top_k': 1,
                  'seed': 12345, 'engine': engine, 'keep_loaded': True, 'history_limit': 1}
    if loras:
        parameters['loras'] = loras
    job = runtime.submit(actor, session, 'chat', parameters)
    job = runtime.wait(actor, job['jobId'], timeout=600)
    if job['state'] != 'Completed':
        raise SystemExit('Turn failed: %s %s' % (job['state'], job.get('error')))
    return job['outputs']['text'].strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='cuda', choices=['cpu', 'cuda'])
    arguments = parser.parse_args()

    paths.ensure_tree()
    if not catalog.installed(MODEL) or not catalog.installed(LORA):
        raise SystemExit('Install %s and %s first (model_install).' % (MODEL, LORA))
    adapter = next((item for item in library.adapters()
                    if item['path'] == str(catalog.file_path(LORA))), None)
    if adapter is None:
        raise SystemExit('The adapter is not registered in the model library.')

    report = {'engine': arguments.engine, 'model': MODEL, 'lora': adapter['id'],
              'loraName': adapter['name'], 'prompt': PROMPT,
              'header': library.describe(catalog.file_path(LORA)),
              'startedAt': time.strftime('%Y-%m-%dT%H:%M:%S')}

    with create_runtime(ROOT / 'data/jobs') as runtime:
        actor = runtime.authenticate(runtime.create_client(
            'acceptance', ['network', 'processSpawn', 'filesystemExternal', 'manageResources'])['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']
        resident = runtime.aichat.resident

        base_conversation = conversations.create(title='LoRA control: base')['id']
        report['base'] = turn(runtime, actor, session, base_conversation, [], arguments.engine)
        report['residentWithoutAdapter'] = resident.health()

        zero_conversation = conversations.create(title='LoRA control: scale 0')['id']
        report['scale0'] = turn(runtime, actor, session, zero_conversation,
                                [{'id': adapter['id'], 'strength': 0.0}], arguments.engine)
        report['adaptersReportedByServer'] = resident.loaded_adapters()
        report['residentWithAdapter'] = resident.health()

        full_conversation = conversations.create(title='LoRA control: scale 1')['id']
        report['scale1'] = turn(runtime, actor, session, full_conversation,
                                [{'id': adapter['id'], 'strength': 1.0}], arguments.engine)
        report['adaptersAtFullScale'] = resident.loaded_adapters()

        # The live control: change the weight on the running server, no reload.
        report['liveScaleChange'] = resident.set_scales([{'strength': 0.0}])
        live_conversation = conversations.create(title='LoRA control: live scale 0')['id']
        report['scale1ThenLive0'] = turn(runtime, actor, session, live_conversation,
                                         [{'id': adapter['id'], 'strength': 0.0}],
                                         arguments.engine)
        for conversation in (base_conversation, zero_conversation, full_conversation,
                             live_conversation):
            conversations.delete(conversation)

    report['adapterLoaded'] = bool(report['adaptersReportedByServer'])
    report['scale0MatchesBase'] = report['scale0'] == report['base']
    report['scale1DiffersFromBase'] = report['scale1'] != report['base']
    report['verdict'] = ('The adapter is loaded and its weight changes the reply.'
                         if report['adapterLoaded'] and report['scale0MatchesBase']
                         and report['scale1DiffersFromBase'] else
                         'Inconclusive: read the three replies below.')
    destination = paths.REPORTS / 'local-lora.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: report[key] for key in
                      ('verdict', 'adapterLoaded', 'scale0MatchesBase', 'scale1DiffersFromBase',
                       'base', 'scale0', 'scale1', 'scale1ThenLive0')}, indent=2,
                     ensure_ascii=False))
    print('Report: %s' % destination)
    return 0 if report['adapterLoaded'] and report['scale0MatchesBase'] \
        and report['scale1DiffersFromBase'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
