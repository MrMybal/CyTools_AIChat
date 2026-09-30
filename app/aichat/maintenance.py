"""GitHub updates for three independent streams: the application, the engine, the weights.

The three move at different speeds, under different licences, and are never replaced
together. Weights are not handled here at all: they have their own catalogue, revisions and
licence acceptance in `catalog.py`. What remains is the application (this folder's `app/`)
and the llama.cpp engine under `runtime/engines`.

An update is staged under `runtime/updates`, verified *there* and only then activated.
Verification covers the configured provenance, the Tool identity, the runtime ABI marker,
the asset size, the published digest when the release carries one, and the containment of
the archive. A staged tree is compiled, never imported: running code from a candidate
update in order to decide whether to install it would defeat the check.

`data/` is never part of a replacement. The previous version is kept under
`runtime/backups`, and a rollback restores it. Nothing is activated while a job is running,
and no command string coming from a remote release is ever executed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from cytools_core import CyToolError, load_manifest
from cytools_core.downloads import DownloadManager

from . import paths
from .engine import safe_extract
from .paths import TOOL_ID, read_json, write_json


# Directories are resolved when they are needed rather than captured at import time, so a
# test can exercise a real staging, activation and rollback on a copy of the tree instead of
# on the installation it is running from.
def settings_file():
    return paths.SETTINGS / 'updates.json'


def updates_dir():
    return paths.RUNTIME / 'updates'


def backups_dir():
    return paths.RUNTIME / 'backups'


def state_file():
    return paths.SETTINGS / 'update-state.json'


ENGINE_REPOSITORY = 'ggml-org/llama.cpp'
MAX_ASSET_BYTES = 768 * 1024 ** 2
# Bumped whenever the application stops being loadable by the runtime already installed here.
RUNTIME_ABI = 'python311-cytools09-imgui192-aichat01'
USER_AGENT = 'CyTools-AIChat'


def repository(value):
    value = str(value or '').strip()
    value = value.removeprefix('https://github.com/').removesuffix('.git').rstrip('/')
    if not value:
        return ''
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value) or '..' in value:
        raise CyToolError('InvalidParameters', 'Expected a GitHub repository as owner/name.')
    return value


def settings():
    stored = read_json(settings_file(), {})
    return {'applicationRepository': repository(stored.get('applicationRepository', '')),
            'engineRepository': repository(stored.get('engineRepository', '')) or ENGINE_REPOSITORY,
            'automaticCheck': bool(stored.get('automaticCheck', False)),
            'lastCheck': stored.get('lastCheck', ''),
            'runtimeAbi': RUNTIME_ABI}


def configure(application_repository=None, engine_repository=None, automatic_check=None):
    current = settings()
    if application_repository is not None and application_repository != '':
        current['applicationRepository'] = repository(application_repository)
    if engine_repository is not None and engine_repository != '':
        current['engineRepository'] = repository(engine_repository)
    if automatic_check in ('on', 'off'):
        current['automaticCheck'] = automatic_check == 'on'
    write_json(settings_file(), current)
    return settings()


def github(path, repo=''):
    url = 'https://api.github.com/' + path
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT,
                                                   'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CyToolError('NotFound',
                              'The repository or release was not found%s.'
                              % (' for ' + repo if repo else ''))
        if exc.code in (403, 429):
            raise CyToolError('RateLimited',
                              'GitHub refused the request (HTTP %d). Unauthenticated API calls '
                              'are rate limited; try again later.' % exc.code)
        raise CyToolError('NetworkError', 'GitHub returned HTTP %d.' % exc.code)
    except urllib.error.URLError as exc:
        raise CyToolError('NetworkError', 'Cannot reach GitHub: %s' % exc.reason)


def current_version():
    return load_manifest(paths.APP / 'CyTool.json')['version']


def parse_version(value):
    parts = re.findall(r'\d+', str(value or ''))
    return tuple(int(p) for p in parts[:4]) or (0,)


# ------------------------------------------------------------------ checking

def check(stream='all'):
    report = []
    current = settings()
    if stream in ('all', 'application'):
        report.append(check_application(current))
    if stream in ('all', 'engine'):
        report.append(check_engine(current))
    write_json(settings_file(), {**current, 'lastCheck': time.strftime('%Y-%m-%dT%H:%M:%S')})
    return report


def check_application(current=None):
    current = current or settings()
    installed = current_version()
    row = {'stream': 'application', 'installed': installed,
           'repository': current['applicationRepository'], 'available': '',
           'updateAvailable': False, 'asset': '', 'sizeBytes': 0, 'digest': '', 'notes': ''}
    if not current['applicationRepository']:
        row['notes'] = ('No application repository is configured. This Tool does not invent one: '
                        'set it in Updates if you publish releases of it, otherwise the '
                        'application stream stays unavailable.')
        return row
    release = github('repos/%s/releases/latest' % current['applicationRepository'],
                     current['applicationRepository'])
    row['available'] = release.get('tag_name', '')
    assets = [a for a in release.get('assets', []) if str(a.get('name', '')).endswith('.zip')]
    if not assets:
        row['notes'] = ('The latest release publishes no .zip asset. The expected format is a zip '
                        'holding an app/ directory with CyTool.json at its root.')
        return row
    asset = assets[0]
    row.update(asset=asset['name'], sizeBytes=int(asset.get('size', 0)),
               digest=str(asset.get('digest', '')),
               updateAvailable=parse_version(row['available']) > parse_version(installed))
    if int(asset.get('size', 0)) > MAX_ASSET_BYTES:
        row['notes'] = 'The published asset is larger than this Tool will download.'
        row['updateAvailable'] = False
    return row


def check_engine(current=None):
    from . import engine
    current = current or settings()
    installed = [item for item in engine.describe()['builds'] if item['installed']]
    pinned = engine.catalogue().get('release', '')
    release = github('repos/%s/releases/latest' % current['engineRepository'],
                     current['engineRepository'])
    latest = release.get('tag_name', '')
    return {'stream': 'engine', 'installed': ', '.join(i['version'] for i in installed) or 'none',
            'pinned': pinned, 'repository': current['engineRepository'],
            'available': latest, 'updateAvailable': bool(latest and latest != pinned),
            'notes': ('The engine is pinned to %s with published sizes and digests. A newer '
                      'llama.cpp tag exists upstream, but moving to it means pinning its assets '
                      'in app/engine-assets.json: this Tool will not download a build whose '
                      'digest it cannot check in advance.' % pinned) if latest != pinned else ''}


# ------------------------------------------------------------------ staging

def staging_path(stream):
    return updates_dir() / stream


def verify_application_tree(root):
    """Everything that must hold before a staged tree is allowed anywhere near app/."""
    candidates = [p for p in root.rglob('CyTool.json') if p.parent.name == 'app']
    if not candidates:
        candidates = [p for p in root.rglob('CyTool.json')]
    if len(candidates) != 1:
        raise CyToolError('InvalidArchive',
                          'The archive must contain exactly one app/CyTool.json, found %d.'
                          % len(candidates))
    app_root = candidates[0].parent
    document = load_manifest(candidates[0])
    if document['id'] != TOOL_ID:
        raise CyToolError('InvalidArchive',
                          'This release belongs to another Tool (%s).' % document['id'])
    release = read_json(app_root / 'release.json', {})
    abi = release.get('runtimeAbi', '')
    if abi and abi != RUNTIME_ABI:
        raise CyToolError('IncompatibleRuntime',
                          'The release targets runtime %s; this installation is %s. Install the '
                          'matching full package instead.' % (abi, RUNTIME_ABI))
    if not (app_root / 'tool.py').is_file() or not (app_root / 'desktop.py').is_file():
        raise CyToolError('InvalidArchive', 'The staged application is missing its entry points.')
    compiled = subprocess.run([sys.executable, '-m', 'compileall', '-q', str(app_root)],
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              timeout=300, creationflags=0x08000000 if os.name == 'nt' else 0)
    if compiled.returncode:
        raise CyToolError('InvalidArchive',
                          'The staged application does not compile:\n' + (compiled.stdout or '')[-1500:])
    return {'path': str(app_root), 'version': document['version'], 'toolId': document['id'],
            'runtimeAbi': abi or 'not declared', 'operations': len(document['operations'])}


def download_application(context, version=''):
    current = settings()
    if not current['applicationRepository']:
        raise CyToolError('NotConfigured',
                          'Configure the application repository in Updates first. This Tool will '
                          'not guess a repository to download code from.')
    path = ('repos/%s/releases/tags/%s' % (current['applicationRepository'], version)
            if version else 'repos/%s/releases/latest' % current['applicationRepository'])
    release = github(path, current['applicationRepository'])
    tag = release.get('tag_name', version)
    assets = [a for a in release.get('assets', []) if str(a.get('name', '')).endswith('.zip')]
    if not assets:
        raise CyToolError('NotFound', 'That release publishes no .zip asset.')
    asset = assets[0]
    size = int(asset.get('size', 0))
    if size > MAX_ASSET_BYTES:
        raise CyToolError('InvalidArchive', 'The published asset is larger than this Tool will download.')
    digest = str(asset.get('digest', '') or '').removeprefix('sha256:')
    context.progress(5, currentStep='Downloading %s' % asset['name'])
    receipt = DownloadManager(paths.RUNTIME / 'downloads/updates').download(
        asset['name'], asset['browser_download_url'], sha256=digest or None, size=size or None,
        revision=tag, cancellation=context.cancellation,
        progress=lambda n, t: context.progress(min(70, 5 + 65 * n / max(t, 1)),
                                               currentStep='Downloading %s' % asset['name']))
    target = staging_path('application')
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    context.progress(75, currentStep='Extracting into runtime/updates')
    safe_extract(receipt['path'], target, budget=MAX_ASSET_BYTES * 4)
    context.progress(85, currentStep='Verifying the staged application')
    report = verify_application_tree(target)
    if not digest:
        report['digestNote'] = ('The release published no digest, so only its size and contents '
                                'were checked. A checksum published beside a release is not an '
                                'independent signature either.')
    write_json(target / 'staged.json', {'stream': 'application', 'version': report['version'],
                                        'tag': tag, 'asset': asset['name'], 'sha256': digest,
                                        'appRoot': report['path'], 'staged': time.time()})
    context.progress(100, currentStep='Staged and verified')
    return {'staged': True, 'stream': 'application', 'version': report['version'],
            'path': str(target), 'report': report}


def download_engine(context, version=''):
    """The engine stream installs a pinned build; it never fetches an unpinned tag."""
    from . import engine
    build = version or ('cuda' if engine.status('cuda')['installed'] else 'cpu')
    if build not in engine.catalogue()['builds']:
        raise CyToolError('InvalidParameters',
                          'The engine stream takes a build id (cpu or cuda), pinned in '
                          'app/engine-assets.json. Known: %s'
                          % ', '.join(sorted(engine.catalogue()['builds'])))
    result = engine.install(context, build)
    return {'staged': True, 'stream': 'engine', 'version': result['version'],
            'path': result['path'],
            'report': {'note': 'The engine is installed directly from its pinned, digest-checked '
                               'assets; there is no separate activation step for it.',
                       'build': build, 'devices': result.get('devices', '')[:400]}}


# ------------------------------------------------------------------ activation

def busy(runtime):
    return [job for job in runtime._jobs.values()
            if job['state'] in ('Queued', 'Running')] if runtime is not None else []


def apply(context, runtime, stream='application'):
    if stream == 'engine':
        return {'applied': False, 'stream': 'engine', 'version': '', 'backup': '',
                'restartRequired': False}
    target = staging_path('application')
    staged = read_json(target / 'staged.json', {})
    if not staged.get('appRoot'):
        raise CyToolError('NotFound', 'No verified application update is staged.')
    running = [job for job in busy(runtime) if job['jobId'] != context.job_id]
    if running:
        raise CyToolError('Busy',
                          'An update is never activated while a job is running. Wait for %d job(s) '
                          'to finish.' % len(running))
    source = Path(staged['appRoot'])
    if not source.is_dir() or not source.resolve().is_relative_to(updates_dir().resolve()):
        raise CyToolError('InvalidState', 'The staged application is no longer where it was verified.')
    context.progress(20, currentStep='Re-verifying the staged application')
    report = verify_application_tree(source.parent)
    backups_dir().mkdir(parents=True, exist_ok=True)
    backup = backups_dir() / ('app-%s-%d' % (current_version(), time.time_ns()))
    context.progress(50, currentStep='Keeping the current version')
    # A copy, not a move: if anything fails below, the running application is still in place.
    shutil.copytree(paths.APP, backup, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    context.progress(70, currentStep='Activating')
    staged_copy = paths.APP.parent / ('app.incoming-%d' % time.time_ns())
    shutil.copytree(source, staged_copy, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    previous = paths.APP.parent / ('app.previous-%d' % time.time_ns())
    try:
        paths.APP.rename(previous)
        staged_copy.rename(paths.APP)
    except OSError as exc:
        # Windows refuses to rename a directory holding an open file. Put everything back.
        if previous.is_dir() and not paths.APP.is_dir():
            previous.rename(paths.APP)
        shutil.rmtree(staged_copy, ignore_errors=True)
        raise CyToolError('Busy',
                          'The application folder is in use and could not be replaced (%s). Close '
                          'the window and apply the update at the next start.' % exc)
    shutil.rmtree(previous, ignore_errors=True)
    write_json(state_file(),
               {'stream': 'application', 'version': report['version'], 'backup': str(backup),
                'applied': time.strftime('%Y-%m-%dT%H:%M:%S'), 'previousVersion': current_version()})
    context.progress(100, currentStep='Applied; restart to run the new version')
    return {'applied': True, 'stream': 'application', 'version': report['version'],
            'backup': str(backup), 'restartRequired': True}


def rollback(context, runtime, stream='application'):
    if stream == 'engine':
        raise CyToolError('Unsupported',
                          'Engine builds are installed side by side; select the other build in '
                          'the conversation instead of rolling back.')
    state = read_json(state_file(), {})
    backup = state.get('backup', '')
    if not backup or not Path(backup).is_dir():
        raise CyToolError('NotFound', 'No kept version is available to restore.')
    running = [job for job in busy(runtime) if job['jobId'] != context.job_id]
    if running:
        raise CyToolError('Busy', 'Wait for running jobs to finish before restoring a version.')
    source = Path(backup).resolve()
    if not source.is_relative_to(backups_dir().resolve()):
        raise CyToolError('InvalidState', 'The kept version is outside runtime/backups.')
    context.progress(30, currentStep='Restoring the kept version')
    incoming = paths.APP.parent / ('app.restore-%d' % time.time_ns())
    shutil.copytree(source, incoming, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    previous = paths.APP.parent / ('app.replaced-%d' % time.time_ns())
    try:
        paths.APP.rename(previous)
        incoming.rename(paths.APP)
    except OSError as exc:
        if previous.is_dir() and not paths.APP.is_dir():
            previous.rename(paths.APP)
        shutil.rmtree(incoming, ignore_errors=True)
        raise CyToolError('Busy', 'The application folder is in use (%s).' % exc)
    shutil.rmtree(previous, ignore_errors=True)
    restored = read_json(paths.APP / 'CyTool.json', {}).get('version', '')
    write_json(state_file(),
               {**state, 'rolledBackAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'version': restored})
    context.progress(100, currentStep='Restored; restart to run it')
    return {'restored': True, 'stream': 'application', 'version': restored, 'restartRequired': True}


def state():
    return {'settings': settings(), 'current': current_version(),
            'staged': read_json(staging_path('application') / 'staged.json', {}),
            'lastApplied': read_json(state_file(), {}),
            'backups': sorted(item.name for item in backups_dir().glob('app-*'))
                       if backups_dir().is_dir() else [],
            'dataUntouched': str(paths.DATA)}
