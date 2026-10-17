"""The Updates tab: three separate streams, staged and verified before anything is replaced.

The application, the llama.cpp engine and the model weights are updated independently. This
panel never touches `data/`: conversations, presets and weights stay where they are through
an update and through a rollback.

No repository is invented. If no application repository is configured, the panel says so and
offers to configure one rather than pretending an update source exists.

Drawn with CyUI: a property table for the sources, a card per stream, callouts for states.
"""
import webbrowser

from imgui_bundle import ImVec2

import cyui
from cytools_core import CyToolError
from ui_common import imgui, tr

from aichat import maintenance
from .state import active
from .widgets import Async

_state = Async()
_check = None
_jobs = {}
_form = {}


def refresh(force=False):
    if force or (not _state.ready and not _state.running):
        _state.start(maintenance.state, 'update-state')


def poll(interface):
    finished = []
    for key, job in list(_jobs.items()):
        try:
            current = interface.runtime.get_job(interface.actor, job['jobId'])
        except CyToolError:
            finished.append(key)
            continue
        _jobs[key] = current
        if not active(current):
            finished.append(key)
            if current['state'] == 'Failed' and current.get('error'):
                cyui.notify('%s: %s' % (current['error'].get('code', 'Error'),
                                        current['error'].get('message', '')), 'error', 8.0)
            elif current['state'] == 'Completed':
                outputs = current.get('outputs') or {}
                if outputs.get('restartRequired'):
                    cyui.notify(tr('Done. Close and reopen the application to run the new version.'),
                                'success', 10.0)
                else:
                    cyui.notify(tr('Finished: ') + key, 'success')
    for key in finished:
        _jobs.pop(key, None)
    if finished:
        refresh(True)


def start(interface, key, operation, parameters):
    try:
        _jobs[key] = interface.submit(operation, parameters)
    except (CyToolError, ValueError) as exc:
        cyui.notify(str(exc), 'error', 8.0)


def draw(interface):
    refresh()
    poll(interface)
    state = _state.take({}) or {}
    settings = state.get('settings', {})
    cyui.panel_header(tr('Updates'), tr('Data is never part of an update: ')
                      + str(state.get('dataUntouched', '')))
    imgui.same_line()
    badge = '%s %s' % (tr('Version').upper(), state.get('current', '?'))
    cyui.align_right(imgui.calc_text_size(badge).x + cyui.dp(12))
    cyui.badge(badge, 'accent')
    cyui.divider()
    if not imgui.begin_child('##updates-page', ImVec2(0, 0)):
        imgui.end_child()
        return
    if cyui.begin_section(tr('Update sources') + '###sources'):
        draw_sources(interface, settings)
        cyui.end_section()
    if cyui.begin_section(tr('Check') + '###check'):
        draw_check()
        cyui.end_section()
    if cyui.begin_section(tr('Application') + '###application'):
        draw_application(interface, state)
        cyui.end_section()
    if cyui.begin_section(tr('Model weights') + '###weights'):
        draw_weights()
        cyui.end_section()
    imgui.end_child()


def draw_sources(interface, settings):
    application = _form.setdefault('application', settings.get('applicationRepository', ''))
    engine_repository = _form.setdefault('engine', settings.get('engineRepository', ''))
    if not settings.get('applicationRepository'):
        cyui.callout('warning', tr('This Tool does not guess a repository to download code from. '
                                      'Until an application repository is configured, that stream '
                                      'stays unavailable.'))
        cyui.space(4)
    if cyui.begin_properties('##sources'):
        cyui.property(tr('Application repository'), tr('owner/name on GitHub'))
        changed, value = imgui.input_text_with_hint('##application-repository', 'owner/name',
                                                    application)
        if changed:
            _form['application'] = value
        cyui.property(tr('Engine repository'), tr('Only consulted to report what exists upstream: '
                                                      'the engine is installed from the build pinned '
                                                      'in app/engine-assets.json, with its published '
                                                      'size and digest checked first.'))
        changed, value = imgui.input_text_with_hint('##engine-repository', 'owner/name',
                                                    engine_repository)
        if changed:
            _form['engine'] = value
        cyui.property(tr('Check when the application starts'))
        automatic = _form.setdefault('automatic', bool(settings.get('automaticCheck')))
        changed, automatic = cyui.toggle_switch('##automatic', automatic)
        if changed:
            _form['automatic'] = automatic
        cyui.end_properties()
    if cyui.icon_text_button(cyui.icon.save, tr('Save the sources') + '###save-sources'):
        start(interface, 'settings', 'update_settings',
              {'application_repository': _form['application'].strip(),
               'engine_repository': _form['engine'].strip(),
               'automatic_check': 'on' if _form['automatic'] else 'off'})


def draw_check():
    global _check
    if _check is None:
        _check = Async()
    with cyui.scoped_disabled(_check.running):
        if cyui.icon_text_button(cyui.icon.sync, tr('Check now') + '###check-now', 'primary'):
            _check.start(lambda: maintenance.check('all'), 'check')
    if _check.running:
        imgui.same_line()
        cyui.spinner('##checking', 6)
        imgui.same_line()
        cyui.text_faint(tr('Asking GitHub...'))
    if _check.error:
        cyui.callout('error', _check.error)
    rows = _check.take([]) or []
    if rows and cyui.begin_properties('##streams'):
        for row in rows:
            imgui.push_id('stream-' + row['stream'])
            cyui.property(tr(row['stream']), tr(row['notes']) if row.get('notes') else None)
            imgui.text('%s  ->  %s' % (row.get('installed', '') or '-',
                                       row.get('available') or tr('unknown')))
            if row.get('updateAvailable'):
                imgui.same_line()
                cyui.badge(tr('UPDATE AVAILABLE').upper(), 'success')
            imgui.pop_id()
        cyui.end_properties()


def draw_application(interface, state):
    staged = state.get('staged') or {}
    job = _jobs.get('download') or _jobs.get('apply') or _jobs.get('rollback')
    if active(job):
        progress = job.get('progress') or {}
        percent = progress.get('percent')
        room = imgui.get_frame_height() + cyui.dp(2) + imgui.get_style().item_spacing.x
        cyui.progress_bar(min(1.0, float(percent) / 100.0) if percent else -1.0,
                          (imgui.get_content_region_avail().x - room, imgui.get_frame_height()),
                          '%s  %s' % (tr(job['state']), tr(progress.get('currentStep', ''))))
        imgui.same_line()
        if cyui.icon_button(cyui.icon.close, tr('Cancel')):
            try:
                interface.runtime.cancel(interface.actor, job['jobId'])
            except CyToolError:
                pass
        return
    if staged.get('version'):
        cyui.callout('success', '%s %s (%s)' % (tr('Staged and verified:'), staged['version'],
                                                   staged.get('asset', '')))
    else:
        cyui.text_faint(tr('Nothing is staged. A download is verified in runtime/updates before it '
                           'can be applied.'))
    cyui.space(2)
    if cyui.icon_text_button(cyui.icon.download, tr('Download and verify') + '###download-update'):
        start(interface, 'download', 'update_download', {'stream': 'application'})
    imgui.same_line()
    with cyui.scoped_disabled(not staged.get('version')):
        if cyui.icon_text_button(cyui.icon.check, tr('Apply the staged update') + '###apply-update',
                                 'primary' if staged.get('version') else 'secondary'):
            start(interface, 'apply', 'update_apply', {'stream': 'application'})
    imgui.same_line()
    applied = state.get('lastApplied') or {}
    with cyui.scoped_disabled(not applied.get('backup')):
        if cyui.icon_text_button(cyui.icon.undo, tr('Roll back') + '###rollback'):
            start(interface, 'rollback', 'update_rollback', {'stream': 'application'})
    if applied.get('backup'):
        cyui.text_faint('%s %s  ·  %s' % (tr('Kept previous version:'),
                                          applied.get('previousVersion', ''), applied['backup']))
    if state.get('backups'):
        cyui.text_faint(tr('Backups: ') + ', '.join(state['backups'][-4:]))


def draw_weights():
    cyui.text_faint(tr('Weights are a separate stream with their own catalogue, revisions and '
                       'licences. They are managed in the Models tab and are never replaced by an '
                       'application or engine update.'))
    if cyui.link_text(tr('Open the llama.cpp releases') + '###llama-releases'):
        webbrowser.open('https://github.com/ggml-org/llama.cpp/releases')
