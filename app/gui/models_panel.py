"""The Models tab: the llama.cpp engine, the downloadable weights, and what is loaded now.

Everything here runs as a job on the same Runtime as a chat turn, so a download reports real
progress, can be cancelled, and keeps the window responsive. An entry is shown as installed
only once its digest matched: a partially downloaded file is reported as partial, never as
available.
"""
import webbrowser

from imgui_bundle import ImVec2

from cytools_core import CyToolError
from ui_common import imgui, label, tr

from aichat import catalog, engine, library
from .widgets import Async, bytes_label, status_dot, wrapped

_catalogue = Async()
_engines = Async()
_jobs = {}
_message = ''
_accepted = {}


def refresh(force=False):
    if force or (not _catalogue.ready and not _catalogue.running):
        _catalogue.start(lambda: catalog.listing(), 'catalogue')
    if force or (not _engines.ready and not _engines.running):
        _engines.start(lambda: engine.describe(), 'engines')


def poll(interface):
    """Follow the jobs this panel started, and refresh the listings when one finishes."""
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
                _message = tr('Finished: ') + key
    if finished:
        for key in finished:
            _jobs.pop(key, None)
        refresh(True)


def start(interface, key, operation, parameters):
    global _message
    try:
        _jobs[key] = interface.submit(operation, parameters)
        _message = ''
    except (CyToolError, ValueError) as exc:
        _message = str(exc)


def smoke_ready():
    return (_catalogue.ready or bool(_catalogue.error)) and (_engines.ready or bool(_engines.error))


def draw(interface):
    global _message
    refresh()
    poll(interface)
    if _message:
        imgui.text_colored((0.75, 0.8, 0.9, 1.0), _message)
        imgui.same_line()
        if imgui.small_button(label('Dismiss###dismiss-models')):
            _message = ''
    draw_resident(interface)
    imgui.separator()
    draw_engines(interface)
    imgui.separator()
    draw_catalogue(interface)


def draw_resident(interface):
    resident = interface.runtime.aichat.resident
    health = resident.health()
    imgui.separator_text(label('Loaded local model'))
    if not health['loaded']:
        imgui.text_disabled(tr('No local model is loaded. One is started on the first turn of a '
                               'conversation using the local provider.'))
        return
    imgui.text('%s: %s' % (tr('Model'), health['model']))
    imgui.text_disabled('%s %s · %s %s · PID %s · %s s'
                        % (tr('device'), health['device'], tr('context'),
                           health['contextTokens'], health['pid'], health['uptimeSeconds']))
    for item in health.get('loras', []):
        imgui.push_id('resident-lora-%d' % item['id'])
        imgui.set_next_item_width(220)
        changed, value = imgui.slider_float(label('Strength###live'), float(item['scale']),
                                            -2.0, 2.0)
        if changed:
            try:
                resident.set_scales([{'strength': value} if index == item['id']
                                     else {'strength': other['scale']}
                                     for index, other in enumerate(health['loras'])])
            except (CyToolError, OSError) as exc:
                imgui.text_colored((0.9, 0.5, 0.45, 1.0), str(exc)[:120])
        imgui.same_line()
        imgui.text_disabled(item['path'])
        imgui.pop_id()
    if imgui.button(label('Unload the model')):
        start(interface, 'unload', 'resident_unload', {})


def draw_engines(interface):
    imgui.separator_text(label('llama.cpp engine'))
    description = _engines.take({}) or {}
    if not description:
        imgui.text_disabled(tr('Reading the engine state...'))
        return
    imgui.text_disabled('%s %s · %s' % (tr('Pinned release'), description.get('release', ''),
                                             description.get('repository', '')))
    wrapped(tr(description.get('notes', '')))
    for build in description.get('builds', []):
        imgui.push_id('engine-' + build['id'])
        status_dot(build['installed'])
        imgui.text('%s — %s' % (build['name'],
                                     tr('installed') if build['installed'] else tr('not installed')))
        imgui.text_disabled('%s · %s · %s' % (bytes_label(build['sizeBytes']),
                                                        build['license'], build['requires']))
        job = _jobs.get('engine-' + build['id'])
        if job:
            draw_job_progress(interface, 'engine-' + build['id'], job)
        elif build['installed']:
            if imgui.small_button(label('Remove###remove-engine')):
                start(interface, 'engine-' + build['id'], 'engine_remove', {'build': build['id']})
            imgui.same_line()
            imgui.text_disabled(build['path'])
        else:
            if imgui.small_button(label('Install###install-engine')):
                start(interface, 'engine-' + build['id'], 'engine_install', {'build': build['id']})
            imgui.same_line()
            if imgui.small_button(label('Open the release page')):
                webbrowser.open(build['source'])
        if build.get('devices'):
            if imgui.tree_node(label('Detected devices')):
                wrapped(build['devices'][:1500])
                imgui.tree_pop()
        imgui.pop_id()
        imgui.separator()


def draw_catalogue(interface):
    imgui.separator_text(label('Models and LoRA adapters'))
    rows = _catalogue.take([]) or []
    if not rows:
        imgui.text_disabled(tr('Reading the catalogue...'))
        return
    imgui.text_disabled(tr('Weights live in data/models and are never replaced by an update. '
                           'Accept the licence on the model page before downloading.'))
    for row in rows:
        imgui.push_id('model-' + row['id'])
        status_dot(row['installed'], unknown=not row['installed'] and row['presentBytes'] > 0)
        state = tr('installed') if row['installed'] else (
            tr('partially downloaded') if row['presentBytes'] else tr('not installed'))
        imgui.text('%s  —  %s' % (row['name'], state))
        imgui.text_disabled('%s · %s · %s · %s'
                            % (tr('LoRA adapter') if row['kind'] == 'lora' else tr('Model'),
                               bytes_label(row['sizeBytes']), row['license'],
                               row['repository']))
        if row.get('notes'):
            wrapped(tr(row['notes']))
        if row.get('baseModel'):
            imgui.text_disabled(tr('Requires the base model: ') + row['baseModel'])
        job = _jobs.get('model-' + row['id'])
        if job:
            draw_job_progress(interface, 'model-' + row['id'], job)
        else:
            draw_model_actions(interface, row)
        imgui.pop_id()
        imgui.separator()


def draw_model_actions(interface, row):
    key = 'model-' + row['id']
    if not row['installed']:
        accepted = _accepted.get(row['id'], row['licenseAccepted'])
        changed, accepted = imgui.checkbox(
            label('I accepted this licence on the model page###accept'), bool(accepted))
        if changed:
            _accepted[row['id']] = accepted
        imgui.begin_disabled(not accepted)
        if imgui.small_button(label('Download###download')):
            start(interface, key, 'model_install',
                  {'model': row['id'], 'accept_license': True})
        imgui.end_disabled()
        imgui.same_line()
        if row['presentBytes']:
            imgui.text_disabled('%s / %s %s' % (bytes_label(row['presentBytes']),
                                                bytes_label(row['sizeBytes']),
                                                tr('already downloaded; it resumes')))
    else:
        if imgui.small_button(label('Verify and repair###repair')):
            start(interface, key, 'model_repair', {'model': row['id']})
        imgui.same_line()
        if imgui.small_button(label('Remove###uninstall')):
            start(interface, key, 'model_uninstall', {'model': row['id']})
        imgui.same_line()
        imgui.text_disabled(row['path'])
    if row.get('source'):
        imgui.same_line()
        if imgui.small_button(label('Model page###page')):
            webbrowser.open(row['source'])


def draw_job_progress(interface, key, job):
    progress = job.get('progress') or {}
    imgui.progress_bar(min(1.0, float(progress.get('percent', 0)) / 100.0), ImVec2(-1, 0),
                       '%s  %s' % (job.get('state', ''), progress.get('currentStep', '')))
    if job.get('state') in ('Queued', 'Running') and imgui.small_button(label('Cancel###cancel-job')):
        try:
            interface.runtime.cancel(interface.actor, job['jobId'])
        except CyToolError:
            pass
