"""The Speech tab: environments, speech models, voices and speech settings.

Everything that installs, transcribes or speaks runs as a job on the same Runtime as a chat
turn, like the Models tab. Reading the state (what is installed, which voices exist) happens
in the background so the window never waits for the speech worker to start.

Drawn with CyUI: collapsible sections, a property table for the settings, cards for models and
environments, icon buttons with tooltips.
"""
import webbrowser

from imgui_bundle import ImVec2

import cyui
from cytools_core import CyToolError
from ui_common import imgui, tr

from .audio import input_devices
from .state import active
from .widgets import Async, bytes_label, card, combo

LANGUAGES = ['auto', 'fr', 'en', 'es', 'de', 'it', 'pt', 'nl', 'pl']
DEVICES = ['auto', 'cuda', 'cpu']

_status = Async()
_voices = Async()
_jobs = {}
_accepted = {}
_form = {'name': '', 'language': 'fr', 'transcript': '', 'import': '', 'try': '',
         'recording': ''}
_microphones = None


def refresh(interface, force=False):
    speech = interface.runtime.aichat_speech
    if force or (not _status.ready and not _status.running):
        _status.start(speech.status, 'speech-status')
    if force or (not _voices.ready and not _voices.running):
        _voices.start(lambda: speech.voice_list(None), 'voices')


def start(interface, key, operation, parameters):
    try:
        _jobs[key] = interface.submit(operation, parameters)
    except (CyToolError, ValueError) as exc:
        cyui.notify(str(exc), 'error', 8.0)


def poll(interface):
    finished = False
    for key, job in list(_jobs.items()):
        try:
            current = _jobs[key] = interface.runtime.get_job(interface.actor, job['jobId'])
        except CyToolError:
            _jobs.pop(key, None)
            continue
        if active(current):
            continue
        _jobs.pop(key, None)
        finished = True
        if current['state'] == 'Failed':
            error = current.get('error') or {}
            cyui.notify('%s: %s' % (error.get('code', 'Error'), error.get('message', '')),
                        'error', 8.0)
        elif current['state'] == 'Completed':
            outputs = current.get('outputs') or {}
            if key == 'settings':
                interface.speech_settings = outputs.get('settings') or interface.speech_settings
            else:
                cyui.notify(tr('Finished: ') + key, 'success')
    if finished:
        refresh(interface, True)


def smoke_ready():
    return (_status.ready or bool(_status.error)) and (_voices.ready or bool(_voices.error))


def draw(interface):
    refresh(interface)
    poll(interface)
    cyui.panel_header(tr('Speech'), tr('Dictation and reading aloud, on this machine.'))
    cyui.divider()
    status = _status.take({}) or {}
    if not status:
        if _status.error:
            cyui.callout('error', _status.error)
        else:
            cyui.spinner('##speech-loading', 6)
            imgui.same_line()
            cyui.text_faint(tr('Reading the speech state...'))
        return
    if not imgui.begin_child('##speech-page', ImVec2(0, 0)):
        imgui.end_child()
        return
    draw_readiness(status)
    if cyui.begin_section(tr('Speech settings') + '###settings'):
        draw_settings(interface, status)
        cyui.end_section()
    if cyui.begin_section(tr('Try a voice') + '###try'):
        draw_try(interface)
        cyui.end_section()
    if cyui.begin_section(tr('Voices') + '###voices'):
        draw_voices(interface)
        cyui.end_section()
    if cyui.begin_section(tr('Speech models') + '###models'):
        draw_models(interface, status)
        cyui.end_section()
    if cyui.begin_section(tr('Speech environments') + '###environments'):
        draw_engines(interface, status)
        cyui.end_section()
    imgui.end_child()


def draw_readiness(status):
    """What is still missing for dictation and for reading, said once at the top."""
    engines = status.get('engines') or {}
    models = status.get('models', [])
    missing = []
    if not (engines.get('stt') or {}).get('installed'):
        missing.append(tr('the speech-to-text environment'))
    if not any(row['kind'] == 'stt' and row['installed'] for row in models):
        missing.append(tr('a speech-to-text model'))
    if not (engines.get('tts') or {}).get('installed'):
        missing.append(tr('the voice environment'))
    if not any(row['kind'] == 'tts' and row['installed'] and not row.get('component') for row in models):
        missing.append(tr('a voice model'))
    if missing:
        cyui.callout('warning', tr('Still to install: ') + ', '.join(missing) + '.')
        cyui.space(4)


# ---------------------------------------------------------------------- settings

def draw_settings(interface, status):
    settings = interface.speech_settings
    models = status.get('models', [])
    stt = [''] + [row['id'] for row in models if row['kind'] == 'stt' and row['installed']]
    tts = [''] + [row['id'] for row in models if row['kind'] == 'tts' and row['installed']
                  and not row.get('component')]
    names = {row['id']: row['name'] for row in models}
    automatic = tr('Automatic')
    changes = {}
    if not cyui.begin_properties('##speech-settings'):
        return
    cyui.property(tr('Speech to text'), tr('Automatic picks Parakeet for French and other '
                                                'languages, Phonon-2 for English.'))
    changed, value = combo('##stt-model', stt, settings.get('sttModel', ''),
                           lambda item: names.get(item, automatic))
    if changed:
        changes['stt_model'] = value
    cyui.property(tr('Voice model'))
    changed, model = combo('##tts-model', tts, settings.get('ttsModel', ''),
                           lambda item: names.get(item, automatic))
    if changed:
        changes['tts_model'] = model
        changes['voice'] = ''
    family = next((row.get('family') for row in models
                   if row['id'] == (model if changed else settings.get('ttsModel'))), '')
    listing = _voices.take([]) or []
    usable = [''] + [voice['id'] for voice in listing if not family or family in voice['families']]
    voice_names = {voice['id']: voice['name'] for voice in listing}
    cyui.property(tr('Voice'), tr('XTTS-v2 can use its studio voices or a clip. F5-TTS always '
                                      'imitates a clip.'))
    changed, chosen = combo('##voice', usable, settings.get('voice', ''),
                            lambda item: voice_names.get(item, automatic))
    if changed:
        changes['voice'] = chosen
    cyui.property(tr('Language'))
    changed, value = combo('##language', LANGUAGES, settings.get('language', 'auto'),
                           lambda item: tr('Guess from the text') if item == 'auto' else item)
    if changed:
        changes['language'] = value
    cyui.property(tr('Speed'))
    changed, value = cyui.slider_bar('##speed', float(settings.get('speed', 1.0)), 0.5, 2.0,
                                     '%.2fx', -1)
    if changed:
        settings['speed'] = round(value, 2)
    if imgui.is_item_deactivated() or (changed and not imgui.is_item_active()):
        changes['speed'] = settings['speed']
    cyui.property(tr('Voice device'))
    current = DEVICES.index(settings.get('ttsDevice', 'auto')) \
        if settings.get('ttsDevice', 'auto') in DEVICES else 0
    changed, index = cyui.segmented('##tts-device', [tr('Automatic'), 'CUDA (GPU)', 'CPU'],
                                    current, -1)
    if changed:
        changes['tts_device'] = DEVICES[index]
    cyui.property(tr('Read new replies aloud'))
    changed, value = cyui.toggle_switch('##auto-read-settings', bool(settings.get('autoRead')))
    if changed:
        changes['auto_read'] = value
    cyui.property(tr('Show the words while I speak'),
                      tr('The sentence being spoken may still change; it is fixed at the next '
                         'pause. Off: the words appear once you stop.'))
    changed, value = cyui.toggle_switch('##live-dictation', bool(settings.get('liveDictation', True)))
    if changed:
        changes['live_dictation'] = value
    cyui.property(tr('Microphone'))
    draw_microphone(interface)
    cyui.end_properties()
    if changes:
        names_map = {'stt_model': 'sttModel', 'tts_model': 'ttsModel', 'voice': 'voice',
                     'language': 'language', 'speed': 'speed', 'tts_device': 'ttsDevice',
                     'auto_read': 'autoRead', 'live_dictation': 'liveDictation'}
        for key, value in changes.items():
            settings[names_map[key]] = value
        start(interface, 'settings', 'speech_settings', changes)


def draw_microphone(interface):
    global _microphones
    if _microphones is None:
        _microphones = input_devices()
    if not _microphones:
        cyui.text_coloured(cyui.palette().warning, tr('No microphone was found on this machine.'))
        return
    values = [None] + [number for number, _ in _microphones]
    names = dict(_microphones)
    changed, value = combo('##microphone', values, interface.microphone,
                           lambda item: tr('Default microphone') if item is None else names[item])
    if changed:
        interface.microphone = value


# ---------------------------------------------------------------------- try a sentence

def draw_try(interface):
    with card('##try-card'):
        changed, value = imgui.input_text_multiline(
            '##try-text', _form['try'],
            ImVec2(-1, imgui.get_text_line_height() * 3 + imgui.get_style().frame_padding.y * 2),
            imgui.InputTextFlags_.word_wrap)
        if changed:
            _form['try'] = value
        if interface.reading('try'):
            if cyui.icon_text_button(cyui.icon.stop, tr('Stop') + '###try-stop'):
                interface.stop_reading('try')
            if interface.player.current != 'try':
                imgui.same_line()
                cyui.spinner('##try-preparing', 6)
                imgui.same_line()
                cyui.text_faint(tr('Preparing the voice...'))
        else:
            with cyui.scoped_disabled(not _form['try'].strip()):
                if cyui.icon_text_button(cyui.icon.volume, tr('Speak') + '###try-speak',
                                         'primary'):
                    interface.speech_error = ''
                    interface.read_text('try', _form['try'])
            imgui.same_line()
            imgui.align_text_to_frame_padding()
            cyui.text_faint(tr('Uses the voice model, voice, language and speed set above.'))
        if interface.speech_error:
            cyui.callout('error', interface.speech_error)


# ---------------------------------------------------------------------- voices

def draw_voices(interface):
    listing = _voices.take([]) or []
    if _voices.error:
        cyui.callout('error', _voices.error[:300])
    cyui.text_faint(tr('XTTS-v2 can use its studio voices or a clip. F5-TTS always imitates a clip '
                       'and needs the words spoken in it; they are found by speech to text when you '
                       'leave them empty. A clip of 6 to 12 seconds of clear speech works best.'))
    clips = [voice for voice in listing if voice['kind'] != 'studio']
    studio = [voice for voice in listing if voice['kind'] == 'studio']
    if not clips:
        cyui.text_faint(tr('No voice clip yet. Record or import one below.'))
    for voice in clips:
        imgui.push_id('voice-' + voice['id'])
        with card('##voice'):
            imgui.align_text_to_frame_padding()
            cyui.heading(voice['name'], 3)
            imgui.same_line()
            cyui.badge(tr(voice['kind']).upper(), 'info' if voice['kind'] == 'recorded'
                       else 'neutral')
            if voice['language']:
                imgui.same_line()
                cyui.badge(voice['language'].upper())
            count = 2 if voice['kind'] == 'recorded' else 1
            imgui.same_line()
            cyui.align_right(count * (imgui.get_frame_height() + cyui.dp(2)
                                      + imgui.get_style().item_spacing.x))
            key = 'clip-' + voice['id']
            if interface.player.current == key and interface.player.playing:
                if cyui.icon_button(cyui.icon.stop, tr('Stop'), True):
                    interface.player.stop()
            elif cyui.icon_button(cyui.icon.play, tr('Listen to the clip')):
                if not interface.player.play(voice['clip'], key):
                    cyui.notify(interface.player.error, 'error')
            if voice['kind'] == 'recorded':
                imgui.same_line()
                if cyui.icon_button(cyui.icon.trash, tr('Delete this voice (moved to data/voices/deleted)'),
                                    active_colour=cyui.palette().error):
                    start(interface, 'delete-' + voice['id'], 'voice_delete', {'voice': voice['id']})
            if voice.get('transcript'):
                cyui.text_faint('"%s"' % voice['transcript'][:200])
        cyui.space(2)
        imgui.pop_id()
    if studio:
        cyui.text_faint(tr('XTTS-v2 studio voices: %d, chosen in the Voice list above.') % len(studio))
    cyui.space(4)
    draw_new_voice(interface)


def draw_new_voice(interface):
    with card('##add-voice', tr('Add a voice')):
        if cyui.begin_properties('##new-voice'):
            cyui.property(tr('Name'))
            changed, value = imgui.input_text('##voice-name', _form['name'])
            if changed:
                _form['name'] = value
            cyui.property(tr('Language of the clip'))
            changed, value = combo('##voice-language', LANGUAGES[1:], _form['language'], str)
            if changed:
                _form['language'] = value
            cyui.property(tr('Words spoken (optional)'),
                              tr('Leave empty: speech to text finds them.'))
            changed, value = imgui.input_text('##voice-words', _form['transcript'])
            if changed:
                _form['transcript'] = value
            cyui.property(tr('From the microphone'))
            draw_voice_recorder(interface)
            cyui.property(tr('From a file'), tr('Paste the full path of a WAV, FLAC, OGG or MP3 '
                                                     'file.'))
            import_label = tr('Import this file') + '###import-voice'
            imgui.set_next_item_width(imgui.get_content_region_avail().x
                                      - cyui.button_width(import_label) - imgui.get_style().item_spacing.x)
            changed, value = imgui.input_text_with_hint('##voice-file', 'C:\\...\\voice.wav',
                                                        _form['import'])
            if changed:
                _form['import'] = value
            imgui.same_line()
            with cyui.scoped_disabled(not _form['import'].strip() or 'add-voice' in _jobs):
                if cyui.button(import_label):
                    add_voice(interface, _form['import'].strip().strip('"'))
            cyui.end_properties()
        job = _jobs.get('add-voice')
        if job:
            draw_progress(interface, job)


def draw_voice_recorder(interface):
    recorder = interface.recorder
    if 'add-voice' in _jobs:
        cyui.text_faint(tr('Saving the voice...'))
        return
    if recorder.recording and recorder.purpose == 'voice':
        if cyui.icon_button(cyui.icon.microphone, tr('Stop recording'), True, cyui.palette().error) or recorder.reached_limit():
            _form['recording'] = recorder.stop()
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.text_dim('%.1f / %.0f s' % (recorder.seconds, recorder.limit))
        imgui.same_line()
        cyui.progress_bar(min(1.0, recorder.level * 6.0), (cyui.dp(100), cyui.dp(6)),
                          tone='success')
        return
    with cyui.scoped_disabled(recorder.recording):
        if cyui.icon_text_button(cyui.icon.microphone, tr('Record a clip') + '###record-voice'):
            if not recorder.start('voice', 20.0, interface.microphone):
                cyui.notify(recorder.error, 'error')
    if _form['recording']:
        imgui.same_line()
        if cyui.icon_button(cyui.icon.play, tr('Listen to the recording')):
            interface.player.play(_form['recording'], 'recording')
        imgui.same_line()
        if cyui.icon_text_button(cyui.icon.save, tr('Save the voice') + '###save-voice',
                                 'primary'):
            add_voice(interface, _form['recording'])
            _form['recording'] = ''


def add_voice(interface, audio):
    start(interface, 'add-voice', 'voice_add',
          {'audio': audio, 'name': _form['name'], 'language': _form['language'],
           'transcript': _form['transcript']})


# ---------------------------------------------------------------------- models

def draw_models(interface, status):
    cyui.text_faint(tr('Weights live in data/models/speech and are never replaced by an update.'))
    cyui.space(2)
    for row in status.get('models', []):
        if row.get('component'):
            continue
        imgui.push_id('speech-model-' + row['id'])
        with card('##speech-model'):
            partial = not row['installed'] and row['presentBytes'] > 0
            tone = 'success' if row['installed'] else ('warning' if partial else 'neutral')
            cyui.status_dot(cyui.tone_colour(tone) if tone != 'neutral' else cyui.palette().textFaint)
            imgui.same_line()
            imgui.align_text_to_frame_padding()
            cyui.heading(row['name'], 3)
            imgui.same_line()
            cyui.badge(tr('INSTALLED').upper() if row['installed'] else
                       (tr('PARTIAL') if partial else tr('NOT INSTALLED')), tone)
            imgui.same_line()
            cyui.badge(tr('DICTATION').upper() if row['kind'] == 'stt' else tr('VOICE'), 'info')
            key = 'model-' + row['id']
            buttons = 2 if row['installed'] and key not in _jobs else 1
            imgui.same_line()
            cyui.align_right(buttons * (imgui.get_frame_height() + cyui.dp(2)
                                        + imgui.get_style().item_spacing.x))
            if cyui.icon_button(cyui.icon.globe, tr('Model page')) and row.get('source'):
                webbrowser.open(row['source'])
            if buttons == 2:
                imgui.same_line()
                if cyui.icon_button(cyui.icon.trash, tr('Remove the files of this model'),
                                    active_colour=cyui.palette().error):
                    start(interface, key, 'model_uninstall', {'model': row['id']})
            cyui.text_faint('%s  ·  %s  ·  %s' % (bytes_label(row['sizeBytes']), row['license'],
                                                  ', '.join(row['languages'][:10])))
            if row.get('notes'):
                with cyui.scoped_color(imgui.Col_.text, cyui.palette().textDim):
                    imgui.text_wrapped(tr(row['notes']))
            job = _jobs.get(key)
            if job:
                draw_progress(interface, job)
            elif not row['installed']:
                accepted = _accepted.get(row['id'], row['licenseAccepted'])
                changed, accepted = cyui.toggle_switch(tr('I accepted this licence on the model page')
                                                       + '###accept', bool(accepted))
                if changed:
                    _accepted[row['id']] = accepted
                imgui.same_line()
                with cyui.scoped_disabled(not accepted):
                    if cyui.icon_text_button(cyui.icon.download, tr('Download') + '###download'):
                        start(interface, key, 'model_install',
                              {'model': row['id'], 'accept_license': True})
        cyui.space(2)
        imgui.pop_id()


# ---------------------------------------------------------------------- environments

def draw_engines(interface, status):
    workers = status.get('workers', {})
    for name, engine in (status.get('engines') or {}).items():
        imgui.push_id('speech-engine-' + name)
        with card('##speech-engine'):
            cyui.status_dot(cyui.palette().success if engine['installed'] else cyui.palette().textFaint)
            imgui.same_line()
            imgui.align_text_to_frame_padding()
            cyui.heading(tr(engine['label']), 3)
            imgui.same_line()
            cyui.badge(tr('INSTALLED').upper() if engine['installed'] else tr('NOT INSTALLED'),
                       'success' if engine['installed'] else 'neutral')
            worker = workers.get(name) or {}
            if worker.get('running'):
                imgui.same_line()
                cyui.badge(tr('LOADED').upper(), 'accent')
                cyui.tooltip('%s (%s)' % (worker.get('model') or '-', worker.get('device') or '-'))
            key = 'engine-' + name
            job = _jobs.get(key)
            if engine['installed']:
                cyui.text_faint('torch %s  ·  %s  ·  %s' % (engine['torch'], engine['device'],
                                                            engine['directory']))
            else:
                cyui.text_faint('%s %s' % (tr('About'), bytes_label(engine['estimatedBytes'])))
            if job:
                draw_progress(interface, job)
            else:
                if engine['installed']:
                    if cyui.icon_text_button(cyui.icon.repair, tr('Repair') + '###repair-engine'):
                        start(interface, key, 'speech_engine_install', {'engine': name, 'device': 'cuda'})
                    imgui.same_line()
                    if cyui.danger_button(tr('Remove') + '###remove-engine'):
                        start(interface, key, 'speech_engine_remove', {'engine': name})
                else:
                    if cyui.icon_text_button(cyui.icon.download, tr('Install') + '###install-engine'):
                        start(interface, key, 'speech_engine_install', {'engine': name, 'device': 'cuda'})
                    if name == 'tts':
                        imgui.same_line()
                        if cyui.button(tr('Install for the CPU') + '###install-cpu'):
                            start(interface, key, 'speech_engine_install',
                                  {'engine': name, 'device': 'cpu'})
        cyui.space(2)
        imgui.pop_id()
    if any(worker.get('running') for worker in workers.values()):
        if cyui.button(tr('Unload the speech models') + '###unload-speech'):
            start(interface, 'unload', 'speech_unload', {})


def draw_progress(interface, job):
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
