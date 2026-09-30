"""A real MCP session over stdio: discover the tools, hold a conversation, read it back.

Nothing here is simulated. The script starts `app/tool.py mcp` as a subprocess, speaks the
official MCP protocol to it, and drives the same asynchronous job contract an AI client
would: a call returns a job descriptor, the client polls `cy_get_job`, and the business
outputs are read only once the job reports Completed.

It also checks the central property of the design: the conversation an AI client creates
over MCP is the same document the desktop window opens, because both go through one runtime.

    runtime/python/Scripts/python.exe app/tests/acceptance_mcp.py [--provider ID] [--model ID]

Writes data/reports/mcp-acceptance.json.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

DONE = ('Completed', 'Failed', 'Cancelled')


async def payload(session, name, arguments):
    # Business operations take their arguments under "parameters"; the cy_* protocol tools
    # take theirs directly.
    wrapped = arguments if name.startswith('cy_') else {'parameters': arguments}
    result = await session.call_tool(name, wrapped)
    if result.isError:
        raise RuntimeError('%s: %s' % (name, result.content[0].text))
    return json.loads(result.content[0].text)


async def run(session, operation, parameters, timeout=900):
    job = await payload(session, 'op_' + operation, parameters)
    if 'jobId' not in job:
        return job
    deadline = time.monotonic() + timeout
    while job['state'] not in DONE:
        if time.monotonic() > deadline:
            raise TimeoutError(operation + ' timed out')
        await asyncio.sleep(0.2)
        job = await payload(session, 'cy_get_job', {'jobId': job['jobId']})
    if job['state'] != 'Completed':
        raise RuntimeError('%s: %s' % (operation, json.dumps(job.get('error'))))
    return job['outputs']


async def main(arguments):
    server = StdioServerParameters(
        command=str(ROOT / 'runtime/python/Scripts/python.exe'),
        args=[str(APP / 'tool.py'), 'mcp'], cwd=str(ROOT))
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)

            described = await payload(session, 'cy_describe_operation', {'operationId': 'chat'})
            providers = (await run(session, 'list_providers', {}, timeout=300))['providers']
            presets = (await run(session, 'preset_list', {}))['presets']

            created = (await run(session, 'conversation_create',
                                 {'title': 'MCP acceptance',
                                  'provider': arguments.provider,
                                  'model': arguments.model}))['conversation']
            first = await run(session, 'chat',
                              {'conversation': created['id'], 'message': arguments.message,
                               'provider': arguments.provider, 'model': arguments.model,
                               'max_tokens': 120, 'temperature': 0.2})
            second = await run(session, 'chat',
                               {'conversation': created['id'],
                                'message': 'Repeat your previous answer exactly.',
                                'max_tokens': 120, 'temperature': 0.2})
            transcript = (await run(session, 'conversation_read',
                                    {'conversation': created['id']}))['conversation']
            exported = await run(session, 'conversation_export',
                                 {'conversation': created['id'], 'format': 'markdown'})
            listing = (await run(session, 'conversation_list', {}))['conversations']
            resident = await run(session, 'resident_status', {})

    report = {
        'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'transport': 'MCP over stdio, real client session',
        'toolCount': len(names),
        'operationTools': [name for name in names if name.startswith('op_')],
        'protocolTools': [name for name in names if name.startswith('cy_')],
        'chatSchemaFields': sorted(described['inputSchema']['properties']),
        'providers': [{'id': row['id'], 'status': row.get('status'),
                       'available': row.get('available')} for row in providers],
        'presets': [row['id'] for row in presets],
        'conversationId': created['id'],
        'firstReply': first['text'][:400],
        'secondReply': second['text'][:400],
        'kind': first['kind'],
        'nativeSessionId': first.get('nativeSessionId', ''),
        'usage': first.get('usage', {}),
        'storedMessages': [{'role': m['role'], 'text': m['text'][:160]}
                           for m in transcript['messages']],
        'export': exported['file'],
        'conversationVisibleInListing': any(row['id'] == created['id'] for row in listing),
        'resident': resident['resident'],
    }
    output = ROOT / 'data/reports/mcp-acceptance.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('tools exposed: %d (%d operations, %d protocol)'
          % (len(names), len(report['operationTools']), len(report['protocolTools'])))
    print('provider %s / model %s, kind=%s' % (arguments.provider, arguments.model,
                                               report['kind']))
    print('first reply :', ' '.join(report['firstReply'].split())[:160])
    print('second reply:', ' '.join(report['secondReply'].split())[:160])
    print('stored messages:', len(report['storedMessages']),
          '| visible in the conversation list:', report['conversationVisibleInListing'])
    print('export:', report['export'])
    print('report:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', default='llamacpp')
    parser.add_argument('--model', default='qwen25-1_5b')
    parser.add_argument('--message', default='Answer with exactly three words.')
    raise SystemExit(asyncio.run(main(parser.parse_args())) or 0)
