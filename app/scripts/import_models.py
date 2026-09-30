"""Copy catalogue weights that another CyTool already downloaded, into this one.

Downloading a file a second time when a neighbouring Tool already holds it is avoidable.
This script copies it instead — and it copies, it never links. Two
Tools that share a file are no longer independent: uninstalling a model in one would break
the other, and a Tool must stay removable on its own. So each file is duplicated in full and
then verified against the SHA-256 this Tool's own catalogue pins, which is also what makes
the copy trustworthy: a truncated or altered file is deleted rather than recorded.

    runtime/python/Scripts/python.exe app/scripts/import_models.py --from PATH_TO_OTHER_TOOL
    runtime/python/Scripts/python.exe app/scripts/import_models.py --from PATH --models a b c
    runtime/python/Scripts/python.exe app/scripts/import_models.py --from PATH --list

Licence acceptance is carried over only when the source Tool recorded that this user really
accepted it; otherwise `--accept-licenses` is required and means you are accepting them here.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from aichat import catalog, library, paths  # noqa: E402

CHUNK = 8 * 1024 * 1024


def source_file(source_root, identifier, filename, kind):
    """Where the other Tool keeps that file. Both layouts in use here are checked."""
    folder = 'lora' if kind == 'lora' else 'llm'
    candidates = [source_root / 'data/models' / folder / identifier / filename,
                  source_root / 'data/models' / identifier / filename]
    return next((path for path in candidates if path.is_file()), None)


def source_licence_accepted(source_root, identifier):
    """Did the user already accept this licence in the source Tool, on this machine?"""
    for name in ('license-llm-%s.json' % identifier, 'license-%s.json' % identifier):
        record = paths.read_json(source_root / 'data/settings' / name, {})
        if record.get('accepted'):
            return True
    return False


def survey(source_root, wanted=()):
    rows = []
    for identifier, info in catalog.kinds().items():
        if wanted and identifier not in wanted:
            continue
        item = info['files'][0]
        found = source_file(source_root, identifier, item['name'], info['kind'])
        rows.append({'id': identifier, 'name': info['name'], 'kind': info['kind'],
                     'sizeBytes': item['size'], 'sha256': item['sha256'],
                     'alreadyInstalled': catalog.installed(identifier),
                     'source': str(found) if found else '',
                     'licenceAcceptedInSource': source_licence_accepted(source_root, identifier)})
    return rows


def copy_with_progress(source, destination, total, label):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + '.importing')
    copied = 0
    started = time.monotonic()
    last = 0.0
    with source.open('rb') as reader, partial.open('wb') as writer:
        while chunk := reader.read(CHUNK):
            writer.write(chunk)
            copied += len(chunk)
            now = time.monotonic()
            if now - last > 0.5:
                last = now
                rate = copied / max(now - started, 0.001) / 1024 ** 2
                print('\r  %s  %5.1f%%  %6.0f MiB/s' % (label, 100 * copied / max(total, 1), rate),
                      end='', flush=True)
    print('\r  %s  100.0%%  copied in %.1fs%s' % (label, time.monotonic() - started, ' ' * 12))
    partial.replace(destination)
    return copied


def import_one(row, accept_licenses):
    identifier = row['id']
    info = catalog.entry(identifier)
    item = info['files'][0]
    destination = catalog.directory(identifier) / item['name']
    source = Path(row['source'])
    if source.stat().st_size != item['size']:
        return {'id': identifier, 'imported': False,
                'reason': 'the source file is %d bytes, the catalogue pins %d'
                          % (source.stat().st_size, item['size'])}
    if not (row['licenceAcceptedInSource'] or accept_licenses):
        return {'id': identifier, 'imported': False,
                'reason': 'the source Tool has no record of this licence being accepted; '
                          'pass --accept-licenses to accept it here'}
    copy_with_progress(source, destination, item['size'], '%-26s' % info['name'][:26])
    print('  verifying the copy...', end='', flush=True)
    digest = catalog.digest(destination)
    if digest != item['sha256']:
        destination.unlink(missing_ok=True)
        return {'id': identifier, 'imported': False,
                'reason': 'the copy does not match the pinned digest; it was deleted'}
    paths.write_json(catalog.receipt_path(destination),
                     {'sha256': digest, 'size': item['size'], 'revision': info['revision'],
                      'repository': info['repo'], 'name': item['name'],
                      'importedFrom': str(source)})
    paths.write_json(paths.SETTINGS / ('license-%s.json' % identifier),
                     {'accepted': True, 'license': info.get('license', ''),
                      'revision': info['revision'],
                      'acceptedVia': 'carried over from %s' % source.parents[3]
                                     if row['licenceAcceptedInSource'] else 'accepted at import'})
    reference = library.register_catalogue_entry(identifier)
    print(' ok, registered as %s' % reference['id'])
    return {'id': identifier, 'imported': True, 'path': str(destination),
            'libraryId': reference['id'], 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from', dest='source', required=True,
                        help='Root of the other CyTool, the folder holding app/ and data/')
    parser.add_argument('--models', nargs='*', default=[],
                        help='Catalogue ids to import. Empty means every one that is available.')
    parser.add_argument('--list', action='store_true', help='Report what could be imported')
    parser.add_argument('--accept-licenses', action='store_true',
                        help='Accept the licences of the imported models here')
    arguments = parser.parse_args()

    source_root = Path(arguments.source).resolve()
    if not (source_root / 'data/models').is_dir():
        raise SystemExit('No data/models under %s' % source_root)
    paths.ensure_tree()
    rows = survey(source_root, set(arguments.models))

    available = [row for row in rows if row['source'] and not row['alreadyInstalled']]
    print('Source: %s' % source_root)
    for row in rows:
        state = ('already installed here' if row['alreadyInstalled'] else
                 ('available to import' if row['source'] else 'not present in the source'))
        print('  %-24s %-46s %6.2f GiB  %s' % (row['id'], row['name'][:46],
                                               row['sizeBytes'] / 1024 ** 3, state))
    if arguments.list:
        return 0
    if not available:
        print('\nNothing to import.')
        return 0

    needed = sum(row['sizeBytes'] for row in available)
    free = shutil.disk_usage(paths.DATA).free
    print('\n%d file(s), %.1f GiB to copy, %.1f GiB free on the target disk.'
          % (len(available), needed / 1024 ** 3, free / 1024 ** 3))
    if needed * 1.05 > free:
        raise SystemExit('Not enough free space. Free some room or import fewer models.')

    results = []
    for row in available:
        print('\n%s' % row['name'])
        results.append(import_one(row, arguments.accept_licenses))
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'source': str(source_root),
              'results': results}
    destination = paths.REPORTS / 'model-import.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    imported = [item for item in results if item['imported']]
    print('\nImported %d of %d. Report: %s' % (len(imported), len(results), destination))
    for item in results:
        if not item['imported']:
            print('  refused: %s - %s' % (item['id'], item['reason']))
    return 0 if len(imported) == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
