"""The Models tab: the llama.cpp engine, the downloadable weights, and what is loaded now.

Everything here runs as a job on the same Runtime as a chat turn, so a download reports real
progress, can be cancelled, and keeps the window responsive. An entry is shown as installed
only once its digest matched: a partially downloaded file is reported as partial, never as
available.

Drawn with CyUI: sections, cards with status badges, the licence acceptance as a switch.
"""
import webbrowser

from imgui_bundle import ImVec2

import cyui
from cytools_core import CyToolError
from ui_common import imgui, tr

from aichat import catalog, engine
from .state import active
from .widgets import Async, bytes_label, card

_catalogue = Async()
_engines = Async()
_jobs = {}
_accepted = {}
_view = {'filter': 0, 'search': ''}
FILTERS = ('All', 'Installed', 'Models', 'LoRA')


def refresh(force=False):
    if force or (not _catalogue.ready and not _catalogue.running):
        # Speech models have their own tab; this one lists the chat weights.
        _catalogue.start(lambda: [row for row in catalog.listing()
                                  if row['kind'] in ('model', 'lora')], 'catalogue')
    if force or (not _engines.ready and not _engines.running):
        _engines.start(lambda: engine.describe(), 'engines')


def poll(interface):
    """Follow the jobs this panel started, and refresh the listings when one finishes."""
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
                cyui.notify(tr('Finished: ') + key, 'success')
    if finished:
        for key in finished:
            _jobs.pop(key, None)
        refresh(True)


def start(interface, key, operation, parameters):
    try:
        _jobs[key] = interface.submit(operation, parameters)
    except (CyToolError, ValueError) as exc:
        cyui.notify(str(exc), 'error', 8.0)


def smoke_ready():
    return (_catalogue.ready or bool(_catalogue.error)) and (_engines.ready or bool(_engines.error))


def draw(interface):
    refresh()
    poll(interface)
    cyui.panel_header(tr('Local models'), tr('The llama.cpp engine, the GGUF weights and LoRA '
                                             'adapters run on this machine.'))
    cyui.divider()
    if not imgui.begin_child('##models-page', ImVec2(0, 0)):
        imgui.end_child()
        return
    if cyui.begin_section(tr('Loaded local model') + '###loaded'):
        draw_resident(interface)
        cyui.end_section()
    if cyui.begin_section(tr('llama.cpp engine') + '###engine'):
        draw_engines(interface)
        cyui.end_section()
    if cyui.begin_section(tr('Models and LoRA adapters') + '###catalogue'):
        draw_catalogue(interface)
        cyui.end_section()
    imgui.end_child()


def draw_resident(interface):
    resident = interface.runtime.aichat.resident
    health = resident.health()
    if not health['loaded']:
        cyui.text_faint(tr('No local model is loaded. One is started on the first turn of a '
                           'conversation using the local provider.'))
        return
    with card('##resident'):
        cyui.status_dot(cyui.palette().success)
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.heading(str(health['model']).split('\\')[-1].split('/')[-1], 3)
        imgui.same_line()
        cyui.badge(str(health['device']).upper(), 'info')
        unload = tr('Unload the model') + '###unload'
        imgui.same_line()
        cyui.align_right(cyui.button_width(unload))
        if cyui.button(unload):
            start(interface, 'unload', 'resident_unload', {})
        if cyui.begin_properties('##resident-facts'):
            cyui.property(tr('Context'))
            imgui.text('%s %s' % (health['contextTokens'], tr('tokens')))
            cyui.property(tr('Process'))
            imgui.text('PID %s  ·  %s s' % (health['pid'], health['uptimeSeconds']))
            for item in health.get('loras', []):
                imgui.push_id('resident-lora-%d' % item['id'])
                cyui.property(str(item['path']).split('\\')[-1].split('/')[-1],
                                  tr('Changed on the running server, without reloading the model.'))
                changed, value = cyui.slider_bar('##live', float(item['scale']), -2.0, 2.0,
                                                 tr('strength') + ' %.2f', -1)
                if changed:
                    try:
                        resident.set_scales([{'strength': value} if index == item['id']
                                             else {'strength': other['scale']}
                                             for index, other in enumerate(health['loras'])])
                    except (CyToolError, OSError) as exc:
                        cyui.notify(str(exc)[:200], 'error')
                imgui.pop_id()
            cyui.end_properties()


def draw_engines(interface):
    description = _engines.take({}) or {}
    if not description:
        cyui.spinner('##engines-loading', 6)
        imgui.same_line()
        cyui.text_faint(tr('Reading the engine state...'))
        return
    cyui.text_faint('%s %s  ·  %s' % (tr('Pinned release'), description.get('release', ''),
                                      description.get('repository', '')))
    for build in description.get('builds', []):
        imgui.push_id('engine-' + build['id'])
        with card('##engine'):
            cyui.status_dot(cyui.palette().success if build['installed'] else cyui.palette().textFaint)
            imgui.same_line()
            imgui.align_text_to_frame_padding()
            cyui.heading(build['name'], 3)
            imgui.same_line()
            cyui.badge(tr('INSTALLED').upper() if build['installed'] else tr('NOT INSTALLED'),
                       'success' if build['installed'] else 'neutral')
            key = 'engine-' + build['id']
            job = _jobs.get(key)
            if not job:
                action = tr('Remove') if build['installed'] else tr('Install')
                imgui.same_line()
                cyui.align_right(cyui.button_width(action) + imgui.get_frame_height()
                                 + cyui.dp(2) + imgui.get_style().item_spacing.x)
                if cyui.icon_button(cyui.icon.globe, tr('Open the release page')):
                    webbrowser.open(build['source'])
                imgui.same_line()
                if build['installed']:
                    if cyui.button(action + '###remove-engine'):
                        start(interface, key, 'engine_remove', {'build': build['id']})
                elif cyui.button(action + '###install-engine'):
                    start(interface, key, 'engine_install', {'build': build['id']})
            cyui.text_faint('%s  ·  %s  ·  %s' % (bytes_label(build['sizeBytes']), build['license'],
                                                  tr(build['requires'])))
            if build['installed']:
                cyui.text_faint(build['path'])
            if job:
                draw_job_progress(interface, job)
            if build.get('devices'):
                if imgui.tree_node(tr('Detected devices') + '###devices'):
                    cyui.text_mono(build['devices'][:1500])
                    imgui.tree_pop()
        cyui.space(2)
        imgui.pop_id()


def visible_rows(rows):
    choice = FILTERS[_view['filter']]
    needle = _view['search'].strip().lower()
    for row in rows:
        if choice == 'Installed' and not row['installed']:
            continue
        if choice == 'Models' and row['kind'] != 'model':
            continue
        if choice == 'LoRA' and row['kind'] != 'lora':
            continue
        if needle and needle not in (row['name'] + ' ' + row['id']).lower():
            continue
        yield row


def draw_catalogue(interface):
    rows = _catalogue.take([]) or []
    if not rows:
        cyui.spinner('##catalogue-loading', 6)
        imgui.same_line()
        cyui.text_faint(tr('Reading the catalogue...'))
        return
    _, _view['filter'] = cyui.segmented('##model-filter', [tr(item) for item in FILTERS],
                                        _view['filter'])
    imgui.same_line()
    _, _view['search'] = cyui.search_field('##model-search', _view['search'],
                                           tr('Search models'), -1)
    cyui.text_faint(tr('Weights live in data/models and are never replaced by an update. Accept '
                       'the licence on the model page before downloading.'))
    cyui.space(4)
    shown = list(visible_rows(rows))
    if not shown:
        cyui.empty_state(tr('Nothing matches'), tr('Change the filter or the search.'), cyui.icon.search)
    for row in shown:
        imgui.push_id('model-' + row['id'])
        draw_model_card(interface, row)
        cyui.space(2)
        imgui.pop_id()


def draw_model_card(interface, row):
    with card('##model'):
        partial = not row['installed'] and row['presentBytes'] > 0
        tone = 'success' if row['installed'] else ('warning' if partial else 'neutral')
        cyui.status_dot(cyui.tone_colour(tone) if tone != 'neutral' else cyui.palette().textFaint)
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.heading(row['name'], 3)
        imgui.same_line()
        cyui.badge(tr('INSTALLED').upper() if row['installed'] else
                   (tr('PARTIAL') if partial else tr('NOT INSTALLED')), tone)
        if row['kind'] == 'lora':
            imgui.same_line()
            cyui.badge('LORA', 'info')
        draw_card_buttons(interface, row)
        cyui.text_faint('%s  ·  %s  ·  %s' % (bytes_label(row['sizeBytes']), row['license'],
                                              row['repository']))
        if row.get('notes'):
            with cyui.scoped_color(imgui.Col_.text, cyui.palette().textDim):
                imgui.text_wrapped(tr(row['notes']))
        if row.get('baseModel'):
            cyui.text_faint(tr('Requires the base model: ') + row['baseModel'])
        job = _jobs.get('model-' + row['id'])
        if job:
            draw_job_progress(interface, job)
        elif not row['installed']:
            draw_download(interface, row, partial)
        else:
            cyui.text_faint(row['path'])


def draw_card_buttons(interface, row):
    """Model page, then verify and remove for an installed entry, on the right of the title."""
    key = 'model-' + row['id']
    count = 1 + (2 if row['installed'] and key not in _jobs else 0)
    imgui.same_line()
    cyui.align_right(count * (imgui.get_frame_height() + cyui.dp(2) + imgui.get_style().item_spacing.x))
    if cyui.icon_button(cyui.icon.globe, tr('Model page')) and row.get('source'):
        webbrowser.open(row['source'])
    if row['installed'] and key not in _jobs:
        imgui.same_line()
        if cyui.icon_button(cyui.icon.repair, tr('Verify and repair: re-hash the files and delete only '
                                             'what does not match')):
            start(interface, key, 'model_repair', {'model': row['id']})
        imgui.same_line()
        if cyui.icon_button(cyui.icon.trash, tr('Remove the files of this entry'),
                            active_colour=cyui.palette().error):
            start(interface, key, 'model_uninstall', {'model': row['id']})


def draw_download(interface, row, partial):
    accepted = _accepted.get(row['id'], row['licenseAccepted'])
    changed, accepted = cyui.toggle_switch(tr('I accepted this licence on the model page')
                                           + '###accept', bool(accepted))
    if changed:
        _accepted[row['id']] = accepted
    imgui.same_line()
    label = (tr('Resume the download') if partial else tr('Download')) + '###download'
    with cyui.scoped_disabled(not accepted):
        if cyui.icon_text_button(cyui.icon.download, label):
            start(interface, 'model-' + row['id'], 'model_install',
                  {'model': row['id'], 'accept_license': True})
    if partial:
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.text_faint('%s / %s' % (bytes_label(row['presentBytes']), bytes_label(row['sizeBytes'])))


def draw_job_progress(interface, job):
    progress = job.get('progress') or {}
    percent = progress.get('percent')
    room = imgui.get_frame_height() + cyui.dp(2) + imgui.get_style().item_spacing.x
    cyui.progress_bar(min(1.0, float(percent) / 100.0) if percent else -1.0,
                      (imgui.get_content_region_avail().x - room, imgui.get_frame_height()),
                      '%s  %s' % (tr(job.get('state', '')), tr(progress.get('currentStep', ''))))
    imgui.same_line()
    if active(job) and cyui.icon_button(cyui.icon.close, tr('Cancel')):
        try:
            interface.runtime.cancel(interface.actor, job['jobId'])
        except CyToolError:
            pass
