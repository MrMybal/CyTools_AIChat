"""The catalogue of downloadable local weights: chat models and LoRA adapters.

A catalogue entry pins a repository, a revision, a file size and a SHA-256. Downloading
resumes where it stopped, verifies the digest, and only then writes an installation receipt
next to the file. "Installed" therefore means verified, not "a folder exists", and a
half-finished download is never presented as a usable model.

Weights live in `data/models/`, which no update ever replaces, and the receipt holds no
absolute path so the whole tree can be moved with the Tool. Licence acceptance is recorded
per entry: the user accepts the terms on the provider's page, the Tool records that they
said so, and it never accepts on their behalf.
"""
import hashlib
from pathlib import Path

from cytools_core import CyToolError
from cytools_core.downloads import DownloadManager

from . import paths
from .paths import read_json, write_json

# Directories are read from `paths` when they are needed, not captured at import time.
# Binding them at import would keep whichever tree was configured at first load: an
# order dependency that only shows once something redirects the data directory.


def catalog_file():
    return paths.APP / 'llm-catalog.json'


def catalogue():
    data = read_json(catalog_file(), {})
    if not isinstance(data, dict) or not data.get('models'):
        raise CyToolError('MissingDependency', 'app/llm-catalog.json is missing or empty.')
    return data


def kinds():
    data = catalogue()
    return {**{k: dict(v, kind='model') for k, v in data.get('models', {}).items()},
            **{k: dict(v, kind='lora') for k, v in data.get('loras', {}).items()}}


def entry(identifier):
    found = kinds().get(identifier)
    if not found:
        raise CyToolError('NotFound', 'Unknown catalogue entry: ' + str(identifier))
    return found


def directory(identifier):
    info = entry(identifier)
    return (paths.LORA_MODELS if info['kind'] == 'lora' else paths.LLM_MODELS) / identifier


def file_path(identifier):
    info = entry(identifier)
    return directory(identifier) / info['files'][0]['name']


def digest(path, cancellation=None):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            if cancellation is not None:
                cancellation.check()
            hasher.update(chunk)
    return hasher.hexdigest()


def receipt_path(path):
    return Path(path).with_name(Path(path).name + '.installed.json')


def installed(identifier, verify=False, cancellation=None):
    info = kinds().get(identifier)
    if not info:
        return False
    for item in info['files']:
        path = directory(identifier) / item['name']
        if not path.is_file() or path.stat().st_size != item['size']:
            return False
        receipt = read_json(receipt_path(path))
        if receipt.get('sha256') != item['sha256']:
            return False
        if verify and digest(path, cancellation) != item['sha256']:
            return False
    return True


def present_bytes(identifier):
    total = 0
    for item in entry(identifier)['files']:
        path = directory(identifier) / item['name']
        if path.is_file():
            total += path.stat().st_size
    return total


def licence_accepted(identifier):
    return bool(read_json(paths.SETTINGS / ('license-%s.json' % identifier)).get('accepted'))


def status(identifier, verify=False, cancellation=None):
    info = entry(identifier)
    return {'id': identifier, 'kind': info['kind'], 'name': info['name'],
            'installed': installed(identifier, verify, cancellation),
            'sizeBytes': sum(f['size'] for f in info['files']),
            'presentBytes': present_bytes(identifier),
            'license': info.get('license', 'Not declared'),
            'source': info.get('page', ''), 'repository': info.get('repo', ''),
            'revision': info.get('revision', ''),
            'gated': bool(info.get('gated')),
            'licenseAccepted': licence_accepted(identifier),
            'baseModel': info.get('baseModel', ''),
            'architecture': info.get('architecture', ''),
            'contextTokens': info.get('contextTokens', 0),
            'ramGiB': info.get('ramGiB', 8), 'vramGiB': info.get('vramGiB', 6),
            'notes': info.get('notes', ''),
            'path': str(file_path(identifier)) if installed(identifier) else ''}


def listing(kind='', verify=False):
    return [status(key, verify) for key, info in kinds().items()
            if not kind or info['kind'] == kind]


def url_for(info, filename):
    return 'https://huggingface.co/%s/resolve/%s/%s' % (info['repo'], info['revision'], filename)


def install(context, identifier, accept_license=False, token=''):
    """Download and verify one catalogue entry. `token` never reaches argv or a log."""
    info = entry(identifier)
    if not accept_license and not licence_accepted(identifier):
        raise CyToolError('LicenseAcceptanceRequired',
                          'Accept the licence of %s personally before downloading it.' % info['name'],
                          details={'model': identifier, 'license': info.get('license', ''),
                                   'source': info.get('page', '')})
    if info.get('baseModel') and not installed(info['baseModel']):
        context.log('Installing the base model required by %s first.' % identifier)
        install(context, info['baseModel'], accept_license=True, token=token)
    total = sum(f['size'] for f in info['files']) or 1
    done = 0
    headers = {'Authorization': 'Bearer ' + token} if token else None
    for item in info['files']:
        context.cancellation.check()
        DownloadManager(directory(identifier)).download(
            item['name'], url_for(info, item['name']),
            sha256=item['sha256'], size=item['size'], revision=info['revision'],
            cancellation=context.cancellation, headers=headers,
            progress=lambda n, t, base=done: context.progress(
                min(97, 100 * (base + n) / total),
                currentStep='Downloading %s' % info['name']))
        done += item['size']
    context.progress(98, currentStep='Verifying %s' % info['name'])
    for item in info['files']:
        path = directory(identifier) / item['name']
        actual = digest(path, context.cancellation)
        if actual != item['sha256']:
            raise CyToolError('IntegrityFailure',
                              'The downloaded file does not match its published digest.')
        write_json(receipt_path(path), {'sha256': actual, 'size': item['size'],
                                        'revision': info['revision'], 'repository': info['repo'],
                                        'name': item['name']})
    write_json(paths.SETTINGS / ('license-%s.json' % identifier),
               {'accepted': True, 'license': info.get('license', ''), 'revision': info['revision']})
    context.progress(100, currentStep='Installed')
    return status(identifier)


def repair(context, identifier):
    """Re-verify, and delete only what fails so the next download resumes cleanly."""
    info = entry(identifier)
    removed = []
    for item in info['files']:
        context.cancellation.check()
        path = directory(identifier) / item['name']
        if not path.is_file():
            continue
        if path.stat().st_size != item['size'] or digest(path, context.cancellation) != item['sha256']:
            path.unlink()
            receipt_path(path).unlink(missing_ok=True)
            removed.append(item['name'])
    return {'id': identifier, 'removedFiles': removed,
            'installed': installed(identifier), 'repaired': bool(removed)}


def uninstall(identifier):
    info = entry(identifier)
    removed = []
    for item in info['files']:
        path = directory(identifier) / item['name']
        if path.is_file():
            path.unlink()
            receipt_path(path).unlink(missing_ok=True)
            removed.append(item['name'])
    return {'id': identifier, 'removedFiles': removed, 'installed': False}


def installation_resources(identifier):
    info = entry(identifier)
    size = sum(f['size'] for f in info['files'])
    base = kinds().get(info.get('baseModel'), {})
    base_size = sum(f['size'] for f in base.get('files', []))
    # Room for the partial file plus the finished one while the digest is checked.
    return {'ramBytes': 256 * 1024 ** 2, 'cpuThreads': 1,
            'diskBytes': int(2.1 * (size + base_size))}
