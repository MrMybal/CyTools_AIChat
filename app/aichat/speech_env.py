"""The two private speech environments declared in app/speech-engines.json.

An environment is created at its final path (runtime/engines/stt or runtime/engines/tts) with
the base interpreter of the Tool's own runtime; a venv is never moved afterwards, because its
scripts hold absolute paths. PyTorch is installed first from the index declared for it and
pinned by a constraints file, so a later dependency cannot replace the CUDA build with a CPU
wheel. The last step imports every declared module, and runs the declared check, inside the
new environment: nothing is recorded as installed before that passes.

Nothing here touches data/: removing an environment leaves the speech models and voices in
place, and reinstalling it finds them again.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from cytools_core import CyToolError

from . import paths
from .paths import read_json, write_json

RECEIPT = 'cytools-engine.json'


def spec():
    data = read_json(paths.APP / 'speech-engines.json', {})
    if not data.get('engines'):
        raise CyToolError('MissingDependency', 'app/speech-engines.json is missing or empty.')
    return data


def engine_spec(name):
    engines = spec()['engines']
    if name not in engines:
        raise CyToolError('InvalidParameters', 'Unknown speech environment: %s' % name)
    return engines[name]


def root(name):
    return paths.ROOT / engine_spec(name)['directory']


def python(name):
    return root(name) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def base_interpreter():
    # A venv's own interpreter cannot reliably create another venv: use the real one.
    return getattr(sys, '_base_executable', None) or sys.executable


def status(name):
    info = engine_spec(name)
    receipt = read_json(root(name) / RECEIPT)
    installed = python(name).is_file() and bool(receipt.get('modules'))
    return {'engine': name, 'label': info['label'], 'directory': str(root(name)),
            'installed': installed, 'families': info.get('families', []),
            'estimatedBytes': info.get('estimatedBytes', 0),
            'cuda': bool(receipt.get('cuda')) if installed else False,
            'cpuOnly': bool(receipt.get('cpuOnly')) if installed else False,
            'device': receipt.get('device', '') if installed else '',
            'torch': receipt.get('torch', '') if installed else '',
            'installedAt': receipt.get('installedAt', '') if installed else ''}


def statuses():
    return {name: status(name) for name in spec()['engines']}


def for_family(family):
    for name, info in spec()['engines'].items():
        if family in info.get('families', []):
            return name
    raise CyToolError('InvalidParameters', 'No speech environment runs the %s family.' % family)


def _run(context, command, log, step, start, end):
    """Run one installation step, mapping its duration onto a slice of the progress bar."""
    context.progress(start, currentStep=step)
    log.write(('\n=== %s %s ===\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), step)).encode())
    log.flush()
    environment = {**os.environ, 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                   'PIP_KEYRING_PROVIDER': 'disabled', 'PYTHONIOENCODING': 'utf-8'}
    environment.pop('CYTOOLS_TOKEN', None)
    process = subprocess.Popen([str(part) for part in command], stdin=subprocess.DEVNULL,
                               stdout=log, stderr=log, env=environment,
                               creationflags=0x08000000 if os.name == 'nt' else 0)
    started = time.monotonic()
    try:
        while process.poll() is None:
            context.cancellation.check()
            # pip gives no reliable overall progress; advance slowly inside the slice so the
            # bar shows life without claiming a precision it does not have.
            elapsed = time.monotonic() - started
            context.progress(start + (end - start) * (1 - 1 / (1 + elapsed / 60.0)),
                             currentStep=step)
            context.cancellation.sleep(1.0)
    except BaseException:
        process.kill()
        process.wait()
        raise
    if process.returncode != 0:
        raise CyToolError('InstallFailed', '%s failed (exit code %d). See data/logs/%s.'
                          % (step, process.returncode, Path(log.name).name))


def verify(name):
    info = engine_spec(name)
    script = (
        'import importlib, json, sys\n'
        'report = {"python": sys.version.split()[0], "modules": {}}\n'
        'for name in %r:\n'
        '    try:\n'
        '        module = importlib.import_module(name)\n'
        '        report["modules"][name] = getattr(module, "__version__", "ok")\n'
        '    except Exception as exc:\n'
        '        report["modules"][name] = "ERROR: %%s: %%s" %% (type(exc).__name__, exc)\n'
        'try:\n'
        '    %s\n'
        '    report["check"] = "ok"\n'
        'except Exception as exc:\n'
        '    report["check"] = "ERROR: %%s: %%s" %% (type(exc).__name__, exc)\n'
        'import torch\n'
        'report["torch"] = torch.__version__\n'
        'report["cuda"] = torch.cuda.is_available()\n'
        'report["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"\n'
        'print(json.dumps(report))\n'
    ) % (info.get('verify', []), info.get('check') or 'pass')
    environment = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                   'PYTHONIOENCODING': 'utf-8'}
    environment.pop('CYTOOLS_TOKEN', None)
    output = subprocess.run([str(python(name)), '-c', script], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', env=environment,
                            cwd=str(paths.ROOT), creationflags=0x08000000 if os.name == 'nt' else 0)
    lines = [line for line in output.stdout.strip().splitlines() if line.startswith('{')]
    if output.returncode != 0 or not lines:
        raise CyToolError('InstallFailed', 'The new environment does not start: %s'
                          % output.stderr.strip()[-1500:])
    report = json.loads(lines[-1])
    failed = {key: value for key, value in report['modules'].items()
              if str(value).startswith('ERROR')}
    if str(report.get('check', '')).startswith('ERROR'):
        failed['check'] = report['check']
    if failed:
        raise CyToolError('InstallFailed', 'Modules that do not import in the %s environment: %s'
                          % (name, json.dumps(failed)))
    return report


def install(context, name, device='cuda'):
    info = engine_spec(name)
    torch_spec = info.get('torch') or {}
    block = torch_spec['cpu'] if device == 'cpu' and 'cpu' in torch_spec else torch_spec
    # The speech-to-text environment only declares a CPU build: it runs there by design.
    wants_cuda = any('+cu' in package for package in block.get('packages', []))
    target = root(name)
    paths.LOGS.mkdir(parents=True, exist_ok=True)
    with (paths.LOGS / ('speech-install-%s.log' % name)).open('ab') as log:
        if not python(name).is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            _run(context, [base_interpreter(), '-m', 'venv', target], log,
                 'Creating the %s environment' % name, 1, 4)
        interpreter = python(name)
        (target / RECEIPT).unlink(missing_ok=True)
        _run(context, [interpreter, '-m', 'pip', 'install', '--upgrade', 'pip', 'wheel'], log,
             'Updating pip', 4, 8)
        constraints = target / 'cytools-constraints.txt'
        if block.get('packages'):
            _run(context, [interpreter, '-m', 'pip', 'install', '--index-url', block['index'],
                           *block['packages']], log, 'Installing PyTorch', 8, 55)
            constraints.write_text('\n'.join(package.split('+')[0]
                                             for package in block['packages']) + '\n',
                                   encoding='utf-8')
        command = [interpreter, '-m', 'pip', 'install', '-r', paths.APP / info['requirements']]
        if constraints.is_file():
            command += ['-c', constraints]
        _run(context, command, log, 'Installing the speech libraries', 55, 90)
        if info.get('withoutDependencies'):
            command = [interpreter, '-m', 'pip', 'install', '--no-deps',
                       *info['withoutDependencies']]
            _run(context, command, log, 'Installing %s' % ', '.join(info['withoutDependencies']),
                 90, 94)
    context.progress(95, currentStep='Checking the %s environment' % name)
    report = verify(name)
    if wants_cuda and not report.get('cuda'):
        raise CyToolError('MissingGPU', 'CUDA is not available in the new environment (torch %s). '
                                        'Install it for the CPU instead.' % report.get('torch'))
    report.update(cpuOnly=not report.get('cuda'),
                  installedAt=time.strftime('%Y-%m-%dT%H:%M:%S'))
    write_json(target / RECEIPT, report)
    context.progress(100, currentStep='Installed')
    return status(name)


def remove(name):
    target = root(name)
    existed = target.is_dir()
    if existed:
        shutil.rmtree(target)
    return {'engine': name, 'removed': existed}
