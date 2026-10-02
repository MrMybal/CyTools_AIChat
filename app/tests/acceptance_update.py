"""Stage, verify, activate and roll back an application update on a temporary copy.

No public release of this Tool exists, so the remote half of the update path — asking GitHub
what is published and downloading it — cannot be claimed as tested. What *can* be tested is
everything the Tool does with an archive once it has one, and that is what this script does,
against a real zip it builds itself:

  * a valid release is staged, verified and activated, and the version really changes;
  * `data/` is untouched by the activation and by the rollback;
  * the previous version is kept and the rollback restores it;
  * an archive containing a path traversal is refused;
  * an archive belonging to another Tool is refused;
  * an archive declaring a different runtime ABI is refused;
  * an archive whose code does not compile is refused;
  * an archive without its licence notices is refused;
  * the licence and the notices are deployed beside app/ and restored by a rollback.

Everything happens inside a temporary copy of `app/`, never on the installation running the
script, so a failure here cannot damage the Tool.

    runtime/python/Scripts/python.exe app/tests/acceptance_update.py

Writes data/reports/update-acceptance.json.
"""
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

from cytools_core import CyToolError  # noqa: E402

from aichat import maintenance, paths  # noqa: E402

IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', 'packages', 'locales')


class Context:
    """The small part of JobContext this code path uses, without a running Runtime."""

    class Cancellation:
        def check(self):
            return None

        def sleep(self, seconds):
            time.sleep(seconds)

    def __init__(self):
        self.cancellation = self.Cancellation()
        self.job_id = 'acceptance-update'
        self.steps = []

    def progress(self, percent, **fields):
        self.steps.append((percent, fields.get('currentStep', '')))

    def log(self, message, level='Info'):
        self.steps.append((None, '%s: %s' % (level, message)))


def build_release(destination, source_app, version, *, tool_id=None, runtime_abi=None,
                  traversal=False, broken_code=False, notices=True):
    """Write a release zip shaped the way the Tool expects: an app/ directory at its root."""
    manifest = json.loads((source_app / 'CyTool.json').read_text('utf-8'))
    manifest['version'] = version
    if tool_id:
        manifest['id'] = tool_id
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for item in sorted(source_app.rglob('*')):
            if item.is_dir() or '__pycache__' in item.parts or item.suffix == '.pyc':
                continue
            if item.name in ('CyTool.json', 'release.json'):
                continue  # both are written below with the fixture's values
            bundle.writestr('app/' + item.relative_to(source_app).as_posix(),
                            item.read_bytes())
        bundle.writestr('app/CyTool.json', json.dumps(manifest, indent=2))
        release = {'runtimeAbi': runtime_abi or maintenance.RUNTIME_ABI, 'version': version}
        bundle.writestr('app/release.json', json.dumps(release))
        if broken_code:
            bundle.writestr('app/broken_module.py', 'def oops(:\n')
        if traversal:
            bundle.writestr('../escaped.txt', 'this must never be written')
        if notices:
            bundle.writestr('LICENSE', 'licence text of release %s' % version)
            for name in maintenance.REQUIRED_NOTICES:
                source = ROOT / 'LICENCES' / name
                bundle.writestr('LICENCES/' + name,
                                source.read_bytes() if source.is_file() else b'notice')
    return destination


def stage(tree, archive):
    """Do what download_application does once the bytes are on disk."""
    target = maintenance.staging_path('application')
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    maintenance.safe_extract(archive, target, budget=maintenance.MAX_ASSET_BYTES * 4)
    report = maintenance.verify_application_tree(target)
    paths.write_json(target / 'staged.json',
                     {'stream': 'application', 'version': report['version'], 'tag': report['version'],
                      'asset': archive.name, 'sha256': '', 'appRoot': report['path'],
                      'staged': time.time()})
    return report


def refused(function, *arguments):
    try:
        function(*arguments)
    except CyToolError as exc:
        return {'refused': True, 'code': exc.code, 'message': str(exc)[:200]}
    return {'refused': False, 'code': '', 'message': 'ACCEPTED, which it should not have been'}


def main():
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'note': 'Run on a temporary copy of app/. The remote half of the update path '
                      '(GitHub release discovery and download) is not covered: no release of '
                      'this Tool is published.'}
    with tempfile.TemporaryDirectory(prefix='aichat-update-') as temporary:
        tree = Path(temporary)
        shutil.copytree(APP, tree / 'app', ignore=IGNORE)
        # The real app/ holds files the copy needs to stay loadable by verify/compile.
        for name in ('locales',):
            shutil.copytree(APP / name, tree / 'app' / name, dirs_exist_ok=True)
        (tree / 'data/settings').mkdir(parents=True)
        (tree / 'data/conversations').mkdir(parents=True)
        keepsake = tree / 'data/conversations/keep-me.json'
        keepsake.write_text('{"proof": "data must survive an update"}', encoding='utf-8')
        (tree / 'runtime').mkdir()
        (tree / 'LICENSE').write_text('licence text of the installed version', encoding='utf-8')

        original_app, original_root = paths.APP, paths.ROOT
        original_data, original_runtime = paths.DATA, paths.RUNTIME
        original_settings = paths.SETTINGS
        paths.APP, paths.ROOT = tree / 'app', tree
        paths.DATA, paths.RUNTIME = tree / 'data', tree / 'runtime'
        paths.SETTINGS = tree / 'data/settings'
        try:
            report['installedVersionBefore'] = maintenance.current_version()

            good = build_release(tree / 'good.zip', APP, '9.9.9')
            staged = stage(tree, good)
            report['staged'] = {'version': staged['version'], 'toolId': staged['toolId'],
                                'runtimeAbi': staged['runtimeAbi'],
                                'operations': staged['operations']}

            context = Context()
            applied = maintenance.apply(context, None, 'application')
            report['applied'] = applied
            report['installedVersionAfterApply'] = maintenance.current_version()
            report['dataSurvivedApply'] = keepsake.is_file()
            report['backupKept'] = Path(applied['backup']).is_dir()
            report['noticesDeployed'] = all((tree / 'LICENCES' / name).is_file()
                                            for name in maintenance.REQUIRED_NOTICES)
            report['licenceReplaced'] = (tree / 'LICENSE').read_text('utf-8') == \
                'licence text of release 9.9.9'

            restored = maintenance.rollback(Context(), None, 'application')
            report['rolledBack'] = restored
            report['installedVersionAfterRollback'] = maintenance.current_version()
            report['dataSurvivedRollback'] = keepsake.is_file()
            report['licenceRestored'] = (tree / 'LICENSE').read_text('utf-8') == \
                'licence text of the installed version'
            # The notices did not exist before the update: a rollback leaves them in place.
            report['noticesKeptAfterRollback'] = (tree / 'LICENCES/SOURCES.txt').is_file()

            traversal = build_release(tree / 'traversal.zip', APP, '9.9.8', traversal=True)
            report['traversalRefused'] = refused(
                maintenance.safe_extract, traversal, tree / 'out-traversal')
            report['traversalFileNotWritten'] = not (tree / 'escaped.txt').exists()

            foreign = build_release(tree / 'foreign.zip', APP, '9.9.7',
                                    tool_id='cy.tool.somethingelse')
            report['foreignToolRefused'] = refused(stage, tree, foreign)

            abi = build_release(tree / 'abi.zip', APP, '9.9.6', runtime_abi='python399-future')
            report['foreignRuntimeRefused'] = refused(stage, tree, abi)

            broken = build_release(tree / 'broken.zip', APP, '9.9.5', broken_code=True)
            report['brokenCodeRefused'] = refused(stage, tree, broken)

            bare = build_release(tree / 'bare.zip', APP, '9.9.4', notices=False)
            report['missingNoticesRefused'] = refused(stage, tree, bare)
        finally:
            paths.APP, paths.ROOT = original_app, original_root
            paths.DATA, paths.RUNTIME = original_data, original_runtime
            paths.SETTINGS = original_settings

    report['verdict'] = (
        'Staging, verification, activation and rollback behave as specified.'
        if report['installedVersionAfterApply'] == '9.9.9'
        and report['installedVersionAfterRollback'] == report['installedVersionBefore']
        and report['dataSurvivedApply'] and report['dataSurvivedRollback']
        and report['noticesDeployed'] and report['licenceReplaced']
        and report['licenceRestored'] and report['noticesKeptAfterRollback']
        and all(report[key]['refused'] for key in ('traversalRefused', 'foreignToolRefused',
                                                   'foreignRuntimeRefused', 'brokenCodeRefused',
                                                   'missingNoticesRefused'))
        else 'Something did not behave as specified; read the report.')
    destination = paths.REPORTS / 'update-acceptance.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: report[key] for key in
                      ('verdict', 'installedVersionBefore', 'installedVersionAfterApply',
                       'installedVersionAfterRollback', 'dataSurvivedApply',
                       'dataSurvivedRollback', 'backupKept', 'traversalRefused',
                       'traversalFileNotWritten', 'foreignToolRefused', 'foreignRuntimeRefused',
                       'brokenCodeRefused', 'missingNoticesRefused', 'noticesDeployed',
                       'licenceReplaced', 'licenceRestored', 'noticesKeptAfterRollback')},
                     indent=2, ensure_ascii=False))
    print('report:', destination)
    return 0 if report['verdict'].startswith('Staging') else 1


if __name__ == '__main__':
    raise SystemExit(main())
