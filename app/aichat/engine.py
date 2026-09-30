"""The private llama.cpp engine: download, verification, extraction and status.

The engine is a pinned llama.cpp release downloaded from GitHub and unpacked under
`runtime/engines/`. It is private to this Tool: nothing is taken from another CyTool, from a
system-wide install or from the user profile, so removing this folder removes the engine and
updating another Tool cannot change the one used here.

Two builds are offered. The CPU build is small and runs anywhere; the CUDA build needs an
NVIDIA GPU and its runtime libraries, and is only recorded as installed after
`llama-server --list-devices` really reported a CUDA device on this machine.

Archives are extracted with `safe_extract`, which refuses absolute names, parent traversal,
links and oversized sets, because an archive fetched over the network is untrusted input
even when it comes from the expected repository.
"""
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path, PurePosixPath

from cytools_core import CyToolError
from cytools_core.downloads import DownloadManager

from .paths import APP, ROOT, RUNTIME, SETTINGS, read_json, write_json

ASSETS = APP / 'engine-assets.json'
MAX_ARCHIVE_BYTES = 2 * 1024 ** 3
MAX_ENTRIES = 4000
EXECUTABLE = 'llama-server.exe' if os.name == 'nt' else 'llama-server'


def catalogue():
    data = read_json(ASSETS, {})
    if not data.get('builds'):
        raise CyToolError('MissingDependency', 'app/engine-assets.json is missing or empty.')
    return data


def build(name):
    builds = catalogue()['builds']
    if name not in builds:
        raise CyToolError('NotFound', 'Unknown engine build: %s. Known: %s'
                          % (name, ', '.join(sorted(builds))))
    return builds[name]


def safe_extract(archive, destination, budget=MAX_ARCHIVE_BYTES):
    """Extract a zip refusing traversal, absolute names, duplicates, links and oversized sets."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > MAX_ENTRIES:
            raise CyToolError('InvalidArchive', 'The archive holds too many entries.')
        for item in entries:
            name = item.filename
            pure = PurePosixPath(name)
            if '\\' in name or ':' in name or pure.is_absolute() or '..' in pure.parts:
                raise CyToolError('InvalidArchive', 'Forbidden path in archive: ' + name)
            if any(part.endswith(('.', ' ')) for part in pure.parts):
                raise CyToolError('InvalidArchive', 'Forbidden path in archive: ' + name)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise CyToolError('InvalidArchive', 'The archive contains a symbolic link.')
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise CyToolError('InvalidArchive', 'Archive entry escapes the destination: ' + name)
            if name.lower() in seen:
                raise CyToolError('InvalidArchive', 'Duplicate entry in archive: ' + name)
            seen.add(name.lower())
            total += item.file_size
            if total > budget:
                raise CyToolError('InvalidArchive', 'The archive expands beyond the allowed size.')
        bundle.extractall(destination)
    return destination


def installed_record(name):
    return read_json(SETTINGS / ('engine-%s.json' % name), {})


def resolve_inside_runtime(relative):
    """A recorded path is only ever accepted when it still points inside runtime/."""
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(RUNTIME.resolve()):
        raise CyToolError('InvalidParameters', 'The recorded engine path escapes runtime/.')
    return path


def server_path(name):
    record = installed_record(name)
    if not record.get('server'):
        raise CyToolError('MissingDependency',
                          'The %s engine is not installed. Install it in the Models tab.' % name)
    path = resolve_inside_runtime(record['server'])
    if not path.is_file():
        raise CyToolError('MissingDependency',
                          'The %s engine is recorded but its executable is missing.' % name)
    return path


def status(name=''):
    if not name:
        return {key: status(key) for key in catalogue()['builds']}
    spec = build(name)
    record = installed_record(name)
    present = False
    path = ''
    if record.get('server'):
        try:
            candidate = resolve_inside_runtime(record['server'])
            present = candidate.is_file()
            path = str(candidate)
        except CyToolError:
            present = False
    return {'id': name, 'name': spec.get('name', name), 'installed': present, 'path': path,
            'version': record.get('version', ''), 'release': spec.get('release', ''),
            'device': spec.get('device', ''), 'platform': spec.get('platform', ''),
            'sizeBytes': sum(int(a.get('size', 0)) for a in spec.get('assets', [])),
            'license': spec.get('license', ''), 'source': spec.get('source', ''),
            'devices': record.get('devices', ''),
            'requires': spec.get('requires', '')}


def install(context, name, progress_range=(0, 95)):
    spec = build(name)
    if spec.get('platform') and spec['platform'] != ('windows-x64' if os.name == 'nt' else 'linux-x64'):
        raise CyToolError('UnsupportedPlatform',
                          'The %s build targets %s.' % (name, spec['platform']))
    target = RUNTIME / 'engines' / ('%s-%s-%d' % (name, spec.get('release', 'build'), time.time_ns()))
    target.mkdir(parents=True)
    total = sum(int(asset.get('size', 0)) for asset in spec['assets']) or 1
    done = 0
    low, high = progress_range
    for asset in spec['assets']:
        context.cancellation.check()
        receipt = DownloadManager(RUNTIME / 'downloads/engines').download(
            asset['name'], asset['url'],
            sha256=str(asset.get('sha256', '')).removeprefix('sha256:') or None,
            size=int(asset['size']) if asset.get('size') else None,
            revision=spec.get('release', ''),
            cancellation=context.cancellation,
            progress=lambda n, t, base=done: context.progress(
                min(high - 5, low + (high - low - 5) * (base + n) / total),
                currentStep='Downloading %s' % asset['name']))
        context.cancellation.check()
        context.progress(min(high, low + (high - low) * (done + int(asset.get('size', 0))) / total),
                         currentStep='Extracting %s' % asset['name'])
        safe_extract(receipt['path'], target)
        done += int(asset.get('size', 0))
    found = sorted(target.rglob(EXECUTABLE))
    if len(found) != 1:
        raise CyToolError('InvalidArchive',
                          'Expected exactly one %s in the package, found %d.' % (EXECUTABLE, len(found)))
    server = found[0]
    devices = ''
    if spec.get('device') == 'cuda':
        probe = subprocess.run([str(server), '--list-devices'], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=120,
                               creationflags=0x08000000 if os.name == 'nt' else 0)
        devices = (probe.stdout or '') + (probe.stderr or '')
        if probe.returncode or 'CUDA' not in devices:
            raise CyToolError('MissingGPU',
                              'The CUDA engine was unpacked but no CUDA device answered. '
                              'Check the NVIDIA driver, or use the CPU engine.')
    write_json(SETTINGS / ('engine-%s.json' % name),
               {'server': str(server.relative_to(ROOT)), 'version': spec.get('release', ''),
                'installed': True, 'devices': devices[:4000], 'directory': str(target.relative_to(ROOT))})
    context.progress(high, currentStep='Engine installed')
    return status(name)


def remove(name):
    """Forget an engine build and delete only the directory this Tool created for it."""
    record = installed_record(name)
    directory = record.get('directory')
    removed = False
    if directory:
        path = resolve_inside_runtime(directory)
        if path.is_dir() and path.parent == (RUNTIME / 'engines').resolve():
            import shutil
            shutil.rmtree(path, ignore_errors=True)
            removed = True
    write_json(SETTINGS / ('engine-%s.json' % name), {})
    return {'id': name, 'removed': removed}


def available_build(preferred='auto'):
    """Pick the build a turn should use: the requested one, or the best installed one."""
    builds = catalogue()['builds']
    if preferred and preferred != 'auto':
        if preferred not in builds:
            raise CyToolError('NotFound', 'Unknown engine build: ' + str(preferred))
        return preferred
    for name, spec in sorted(builds.items(), key=lambda item: 0 if item[1].get('device') == 'cuda' else 1):
        if status(name)['installed']:
            return name
    raise CyToolError('MissingDependency',
                      'No llama.cpp engine is installed. Install one in the Models tab.')


def describe():
    data = catalogue()
    return {'release': data.get('release', ''), 'repository': data.get('repository', ''),
            'builds': [status(name) for name in data['builds']],
            'notes': data.get('notes', '')}


if __name__ == '__main__':  # pragma: no cover - small operator helper
    print(json.dumps(describe(), indent=2))
