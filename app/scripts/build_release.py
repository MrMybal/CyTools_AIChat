"""Build the application release archive: `app/` as the update stream expects it.

The archive is what `update_download` stages and `update_apply` activates: a zip holding an
`app/` directory with `CyTool.json` and `release.json` at its root. It is built from the
sources rather than assembled by hand, so what ships is what the tests ran against.

Not everything in `app/` belongs to the product. The working files used while developing
the Tool — the agent rules and the SDK guides addressed to an assistant — stay in the
repository and out of the archive, and so do caches, the SDK wheel and the nested test
caches. The exclusion is explicit here instead of relying on someone remembering it.

    runtime/python/Scripts/python.exe app/scripts/build_release.py [--out DIR] [--check]

The archive lands in runtime/build by default. `--check` extracts it again with the same
guard the updater uses and runs the updater's verification on the result, so a release that
the Tool itself would refuse is noticed before it is published.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

# Files and directories that are part of developing the Tool, not of running it.
EXCLUDED_FILES = {
    'AGENTS.md',                # rules for the assistants working on the code
    'CyToolsGuide.md',          # the SDK's guide addressed to an assistant creating a Tool
    'Docs/AgentGuide.md',
    'Docs/AgentPrompt.md',
    '.gitignore',
    'requirements-dev.txt',
}
EXCLUDED_DIRECTORIES = {'__pycache__', '.pytest_cache'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.whl', '.log', '.tmp', '.bak'}


def included(path):
    relative = path.relative_to(APP).as_posix()
    if relative in EXCLUDED_FILES:
        return False
    if any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(APP).parts):
        return False
    return path.suffix.lower() not in EXCLUDED_SUFFIXES


def build(destination):
    manifest = json.loads((APP / 'CyTool.json').read_text('utf-8-sig'))
    release = json.loads((APP / 'release.json').read_text('utf-8-sig'))
    if release.get('version') != manifest['version']:
        raise SystemExit('release.json says %s but CyTool.json says %s: align them first.'
                         % (release.get('version'), manifest['version']))
    destination.parent.mkdir(parents=True, exist_ok=True)
    names = []
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(APP.rglob('*')):
            if not path.is_file() or not included(path):
                continue
            arcname = 'app/' + path.relative_to(APP).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, path.read_bytes())
            names.append(arcname)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {'archive': str(destination), 'version': manifest['version'],
            'runtimeAbi': release.get('runtimeAbi', ''), 'files': len(names),
            'sizeBytes': destination.stat().st_size, 'sha256': digest, 'names': names}


def check(destination):
    """Extract with the updater's own guard and run its verification on the result."""
    from aichat import maintenance
    from aichat.engine import safe_extract
    with tempfile.TemporaryDirectory(prefix='aichat-release-') as temporary:
        target = Path(temporary) / 'staged'
        safe_extract(destination, target, budget=maintenance.MAX_ASSET_BYTES * 4)
        # Listed before verification: the compile pass inside verify_application_tree writes
        # __pycache__ into the staging tree, which is not part of what the archive holds.
        present = sorted(p.relative_to(target / 'app').as_posix()
                         for p in (target / 'app').rglob('*') if p.is_file())
        report = maintenance.verify_application_tree(target)
    leaked = [name for name in present
              if name in EXCLUDED_FILES or Path(name).suffix.lower() in EXCLUDED_SUFFIXES
              or any(part in EXCLUDED_DIRECTORIES for part in Path(name).parts)]
    return {'verified': True, 'toolId': report['toolId'], 'version': report['version'],
            'runtimeAbi': report['runtimeAbi'], 'operations': report['operations'],
            'filesExtracted': len(present), 'excludedFilesPresent': leaked}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', default=str(ROOT / 'runtime/build'))
    parser.add_argument('--check', action='store_true')
    arguments = parser.parse_args()
    manifest = json.loads((APP / 'CyTool.json').read_text('utf-8-sig'))
    destination = Path(arguments.out) / ('%s-%s-app.zip' % (manifest['name'], manifest['version']))
    result = build(destination)
    print('built %s: %d files, %d bytes, sha256 %s'
          % (result['archive'], result['files'], result['sizeBytes'], result['sha256']))
    if arguments.check:
        verdict = check(destination)
        print('verified by the updater: tool %s version %s, runtime %s, %d operations, %d files'
              % (verdict['toolId'], verdict['version'], verdict['runtimeAbi'],
                 verdict['operations'], verdict['filesExtracted']))
        if verdict['excludedFilesPresent']:
            print('EXCLUDED FILES FOUND IN THE ARCHIVE:', verdict['excludedFilesPresent'])
            return 1
        result['check'] = verdict
    report = ROOT / 'data/reports/release-build.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({**result, 'date': time.strftime('%Y-%m-%dT%H:%M:%S')},
                                 indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
