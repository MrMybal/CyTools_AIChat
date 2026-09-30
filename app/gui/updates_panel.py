"""The Updates tab: three separate streams, staged and verified before anything is replaced.

The application, the llama.cpp engine and the model weights are updated independently. This
panel never touches `data/`: conversations, presets and weights stay where they are through
an update and through a rollback.

No repository is invented. If no application repository is configured, the panel says so and
offers to configure one rather than pretending an update source exists.
"""
import webbrowser

from imgui_bundle import ImVec2

from cytools_core import CyToolError
from ui_common import imgui, label, tr

from aichat import maintenance
from .widgets import Async, wrapped

_state = Async()
_check = None
_jobs = {}
_message = ''
_form = {}


def refresh(force=False):
    if force or (not _state.ready and not _state.running):
        _state.start(maintenance.state, 'update-state')


def poll(interface):
    global _message
    finished = []
    for key, job in list(_jobs.items()):
        try:
            current = interface.runtime.get_job(interface.actor, job['jobId'])
        except CyToolError:
            finished.append(key)
            continue
        _jobs[key] = current
        if current['state'] not in ('Queued', 'Running'):
            finished.append(key)
            if current['state'] == 'Failed' and current.get('error'):
                _message = '%s: %s' % (current['error'].get('code', 'Error'),
                                       current['error'].get('message', ''))
            elif current['state'] == 'Completed':
                outputs = current.get('outputs') or {}
                if outputs.get('restartRequired'):
                    _message = tr('Done. Close and reopen the application to run the new version.')
                else:
                    _message = tr('Finished: ') + key
    for key in finished:
        _jobs.pop(key, None)
    if finished:
        refresh(True)


def start(interface, key, operation, parameters):
    global _message
    try:
        _jobs[key] = interface.submit(operation, parameters)
        _message = ''
    except (CyToolError, ValueError) as exc:
        _message = str(exc)


def draw(interface):
    global _message
    refresh()
    poll(interface)
    state = _state.take({}) or {}
    settings = state.get('settings', {})
    if _message:
        imgui.text_colored((0.75, 0.85, 0.95, 1.0), _message)
        imgui.same_line()
        if imgui.small_button(label('Dismiss###dismiss-updates')):
            _message = ''
    imgui.text('%s %s' % (tr('Installed application version:'), state.get('current', '?')))
    imgui.text_disabled(tr('Data is never part of an update: ') + str(state.get('dataUntouched', '')))
    imgui.separator()
    draw_sources(interface, settings)
    imgui.separator()
    draw_check(interface)
    imgui.separator()
    draw_application(interface, state)
    imgui.separator()
    draw_weights()


def draw_sources(interface, settings):
    imgui.separator_text(label('Update sources'))
    application = _form.setdefault('application', settings.get('applicationRepository', ''))
    engine_repository = _form.setdefault('engine', settings.get('engineRepository', ''))
    imgui.set_next_item_width(380)
    changed, value = imgui.input_text(label('Application repository (owner/name)'), application)
    if changed:
        _form['application'] = value
    if not settings.get('applicationRepository'):
        imgui.same_line()
        imgui.text_colored((0.9, 0.7, 0.4, 1.0), tr('not configured'))
    imgui.set_next_item_width(380)
    changed, value = imgui.input_text(label('Engine repository (owner/name)'), engine_repository)
    if changed:
        _form['engine'] = value
    automatic = _form.setdefault('automatic', bool(settings.get('automaticCheck')))
    changed, automatic = imgui.checkbox(label('Check for updates when the application starts'),
                                        automatic)
    if changed:
        _form['automatic'] = automatic
    if imgui.button(label('Save the sources')):
        start(interface, 'settings', 'update_settings',
              {'application_repository': _form['application'].strip(),
               'engine_repository': _form['engine'].strip(),
               'automatic_check': 'on' if _form['automatic'] else 'off'})
    wrapped(tr('This Tool does not guess a repository to download code from. Until an '
               'application repository is configured, that stream stays unavailable. The engine '
               'repository is only consulted to report what exists upstream: the engine is '
               'installed from the build pinned in app/engine-assets.json, with its published '
               'size and digest checked first.'))


def draw_check(interface):
    global _check
    imgui.separator_text(label('Check'))
    if _check is None:
        _check = Async()
    if imgui.button(label('Check now')):
        _check.start(lambda: maintenance.check('all'), 'check')
    imgui.same_line()
    if _check.running:
        imgui.text_disabled(tr('Asking GitHub...'))
    if _check.error:
        imgui.text_colored((0.9, 0.5, 0.45, 1.0), _check.error)
    for row in (_check.take([]) or []):
        imgui.push_id('stream-' + row['stream'])
        imgui.text('%s: %s -> %s' % (tr(row['stream']), row.get('installed', ''),
                                          row.get('available') or tr('unknown')))
        if row.get('updateAvailable'):
            imgui.same_line()
            imgui.text_colored((0.6, 0.85, 0.65, 1.0), tr('update available'))
        if row.get('notes'):
            wrapped(tr(row['notes']))
        imgui.pop_id()


def draw_application(interface, state):
    imgui.separator_text(label('Application'))
    staged = state.get('staged') or {}
    job = _jobs.get('download') or _jobs.get('apply') or _jobs.get('rollback')
    if job and job.get('state') in ('Queued', 'Running'):
        progress = job.get('progress') or {}
        imgui.progress_bar(min(1.0, float(progress.get('percent', 0)) / 100.0), ImVec2(-1, 0),
                           '%s  %s' % (job['state'], progress.get('currentStep', '')))
        if imgui.small_button(label('Cancel###cancel-update')):
            try:
                interface.runtime.cancel(interface.actor, job['jobId'])
            except CyToolError:
                pass
        return
    if imgui.button(label('Download and verify')):
        start(interface, 'download', 'update_download', {'stream': 'application'})
    imgui.same_line()
    imgui.begin_disabled(not staged.get('version'))
    if imgui.button(label('Apply the staged update')):
        start(interface, 'apply', 'update_apply', {'stream': 'application'})
    imgui.end_disabled()
    imgui.same_line()
    imgui.begin_disabled(not (state.get('lastApplied') or {}).get('backup'))
    if imgui.button(label('Roll back')):
        start(interface, 'rollback', 'update_rollback', {'stream': 'application'})
    imgui.end_disabled()
    if staged.get('version'):
        imgui.text_colored((0.6, 0.85, 0.65, 1.0),
                           '%s %s (%s)' % (tr('Staged and verified:'), staged['version'],
                                           staged.get('asset', '')))
    else:
        imgui.text_disabled(tr('Nothing is staged. A download is verified in runtime/updates '
                               'before it can be applied.'))
    applied = state.get('lastApplied') or {}
    if applied.get('backup'):
        imgui.text_disabled('%s %s · %s' % (tr('Kept previous version:'),
                                                 applied.get('previousVersion', ''),
                                                 applied['backup']))
    if state.get('backups'):
        imgui.text_disabled(tr('Backups: ') + ', '.join(state['backups'][-4:]))


def draw_weights():
    imgui.separator_text(label('Model weights'))
    wrapped(tr('Weights are a separate stream with their own catalogue, revisions and licences. '
               'They are managed in the Models tab and are never replaced by an application or '
               'engine update.'))
    if imgui.small_button(label('Open the llama.cpp releases')):
        webbrowser.open('https://github.com/ggml-org/llama.cpp/releases')
