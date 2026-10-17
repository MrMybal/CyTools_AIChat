"""State of the desktop window: the open tabs, and what is streaming into each of them.

The window owns no model and no scheduler. It submits jobs to the same Runtime the CLI and
MCP use, and it follows their progress through the authenticated event stream, which is why
a conversation continued from an AI client shows up here on the next poll.

Each tab keeps its own live buffer so several conversations can stream at the same time
without their tokens landing in the wrong transcript: a `ChatDelta` event carries the
conversation it belongs to, and it is routed by that, never by whichever tab is on screen.
"""
import threading
import time
import uuid
from pathlib import Path

from cytools_core import CyToolError

from aichat import conversations, paths, presets, voices

from .audio import Player, Recorder, read_wav

POLL_SECONDS = 0.05
# A job is active until it reaches one of these. Listing the active states instead would miss
# Preparing, WaitingForResources, LoadingModel and Cancelling, and a turn waiting for memory
# would look finished.
TERMINAL_STATES = ('Completed', 'Failed', 'Cancelled')


def active(job):
    return bool(job) and job.get('state') not in TERMINAL_STATES


def join_words(before, words):
    """What was already typed, then the dictated words, with one space between."""
    before, words = (before or '').rstrip(), (words or '').strip()
    return before + ' ' + words if before and words else (before or words)


class Tab:
    """One open conversation."""

    def __init__(self, conversation_id):
        self.id = conversation_id
        self.document = conversations.load(conversation_id)
        self.input = ''
        self.job = None
        self.live = []
        self.live_thinking = []
        self.status = ''
        self.error = ''
        self.dirty = False
        self.scroll_to_bottom = True
        self.show_thinking = False
        self.show_settings = False
        self.read_when_loaded = False

    # ------------------------------------------------------------------ view

    @property
    def title(self):
        return self.document.get('title') or self.id

    @property
    def busy(self):
        return active(self.job)

    def live_text(self):
        return ''.join(self.live)

    def reload(self):
        self.document = conversations.load(self.id)

    # ------------------------------------------------------------------ streaming

    def apply(self, event):
        data = event.get('data') or {}
        if data.get('conversationId') != self.id:
            return False
        kind = event.get('type')
        if kind == 'ChatTurnStarted':
            self.live = []
            self.live_thinking = []
            self.status = 'Waiting for the provider'
            self.error = ''
        elif kind == 'ChatDelta':
            if data.get('text'):
                self.live.append(data['text'])
            if data.get('thinking'):
                self.live_thinking.append(data['thinking'])
            if data.get('status'):
                self.status = data['status']
            self.scroll_to_bottom = True
        elif kind == 'ChatTurnFailed':
            self.error = '%s: %s' % (data.get('code', 'Error'), data.get('message', ''))
            self.status = ''
        elif kind == 'ChatTurnCompleted':
            self.status = ''
            self.dirty = True
        else:
            return False
        return True


class Interface:
    def __init__(self, runtime, actor, session):
        self.runtime = runtime
        self.actor = actor
        self.session = session
        self.tabs = []
        self.cursor = 0
        self.selected = ''
        self.message = ''
        self.error = ''
        self.lock = threading.RLock()
        self.last_poll = 0.0
        self.presets = []
        self.refresh_presets()
        # Speech: one microphone and one loudspeaker for the whole window.
        self.recorder = Recorder(paths.INPUTS / 'dictation')
        self.player = Player()
        self.microphone = None
        self.speech_jobs = {}
        self.speech_error = ''
        self.speech_settings = voices.settings()
        self.restore()

    # ------------------------------------------------------------------ tabs

    def restore(self):
        state = conversations.tabs()
        for conversation_id in state['open']:
            try:
                self.tabs.append(Tab(conversation_id))
            except CyToolError:
                continue
        self.selected = state['active'] or (self.tabs[0].id if self.tabs else '')
        if not self.tabs:
            self.new_tab()

    def persist(self):
        conversations.set_tabs([tab.id for tab in self.tabs], self.selected)

    def find(self, conversation_id):
        return next((tab for tab in self.tabs if tab.id == conversation_id), None)

    def new_tab(self, **fields):
        document = conversations.create(**fields)
        tab = Tab(document['id'])
        self.tabs.append(tab)
        self.selected = tab.id
        self.persist()
        return tab

    def open_tab(self, conversation_id):
        existing = self.find(conversation_id)
        if existing is None:
            existing = Tab(conversation_id)
            self.tabs.append(existing)
        self.selected = existing.id
        self.persist()
        return existing

    def close_tab(self, conversation_id):
        """Closing a tab never deletes the conversation; it stays in the list on the left."""
        tab = self.find(conversation_id)
        if tab is None:
            return
        if tab.busy:
            self.cancel(tab)
        self.tabs = [item for item in self.tabs if item.id != conversation_id]
        if self.selected == conversation_id:
            self.selected = self.tabs[-1].id if self.tabs else ''
        self.persist()
        if not self.tabs:
            self.new_tab()

    def delete_conversation(self, conversation_id):
        tab = self.find(conversation_id)
        if tab is not None and tab.busy:
            self.cancel(tab)
        self.tabs = [item for item in self.tabs if item.id != conversation_id]
        result = conversations.delete(conversation_id)
        if self.selected == conversation_id:
            self.selected = self.tabs[-1].id if self.tabs else ''
        if not self.tabs:
            self.new_tab()
        else:
            self.persist()
        return result

    # ------------------------------------------------------------------ jobs

    def submit(self, operation, parameters, **options):
        return self.runtime.submit(self.actor, self.session, operation, parameters, **options)

    def send(self, tab):
        text = tab.input.strip()
        if not text:
            return
        document = tab.document
        parameters = {'message': text, 'conversation': tab.id,
                      'provider': document.get('providerId', ''),
                      'transport': document.get('transport', ''),
                      'model': document.get('model', ''),
                      'system_prompt': document.get('systemPrompt', ''),
                      'preset': document.get('presetId', '')}
        settings = document.get('settings') or {}
        for key in ('temperature', 'top_p', 'top_k', 'max_tokens', 'seed', 'repeat_penalty',
                    'context_tokens', 'history_limit'):
            if settings.get(key) is not None:
                parameters[key] = settings[key]
        for key in ('engine', 'threads', 'keep_loaded'):
            if settings.get(key) is not None:
                parameters[key] = settings[key]
        if settings.get('loras'):
            parameters['loras'] = settings['loras']
        if settings.get('model_profile'):
            parameters['model_profile'] = settings['model_profile']
        try:
            tab.job = self.submit('chat', parameters)
            tab.input = ''
            tab.error = ''
            tab.live = []
            tab.live_thinking = []
            tab.status = 'Queued'
        except (CyToolError, ValueError) as exc:
            tab.error = str(exc)

    # ------------------------------------------------------------------ speech

    def dictation_key(self, tab):
        return 'dictation-' + tab.id

    def dictating(self, tab):
        """True while this tab's words are still coming in: recording, or the last pass."""
        entry = self.speech_jobs.get(self.dictation_key(tab))
        return bool(entry and entry['purpose'] == 'live') or \
            (self.recorder.recording and self.recorder.purpose == 'dictation'
             and getattr(self, 'dictation_tab', '') == tab.id)

    def start_dictation(self, tab):
        if self.recorder.recording or self.dictation_key(tab) in self.speech_jobs:
            return
        live = None
        if self.speech_settings.get('liveDictation', True):
            live = paths.INPUTS / 'dictation' / ('live-%s.pcm' % uuid.uuid4().hex[:16])
        if not self.recorder.start('dictation', 120.0, self.microphone, live=live):
            tab.error = self.recorder.error
            return
        self.dictation_tab = tab.id
        tab.error = ''
        if live is not None:
            tab.dictation_prefix = tab.input
            self.submit_speech(self.dictation_key(tab), 'transcribe_live',
                               {'stream': live.name, 'rate': self.recorder.rate},
                               tab=tab.id, purpose='live')
            if self.dictation_key(tab) not in self.speech_jobs:
                self.recorder.stop(keep=False)

    def stop_dictation(self, tab):
        audio = self.recorder.stop()
        if self.dictation_key(tab) in self.speech_jobs:
            return              # the live job reads what remains and returns the whole text
        if not audio:
            tab.error = 'Nothing was recorded: the recording was too short.'
            return
        self.submit_speech(self.dictation_key(tab), 'transcribe', {'audio': audio},
                           tab=tab.id, purpose='dictation')

    def apply_dictation(self, event):
        """Show the words of a live dictation in the message box as they are recognised."""
        for entry in self.speech_jobs.values():
            if entry['purpose'] == 'live' and entry['job']['jobId'] == event.get('jobId'):
                tab = self.find(entry.get('tab', ''))
                if tab is not None:
                    tab.input = join_words(getattr(tab, 'dictation_prefix', ''),
                                           (event.get('data') or {}).get('text', ''))
                return

    def read_message(self, tab, message):
        key = 'read-' + message['id']
        if self.reading(key):
            self.stop_reading(key)
            return
        self.submit_speech(key, 'speak', {'conversation': tab.id, 'message': message['id'],
                                          'progressive': True},
                           tab=tab.id, purpose='read')

    def read_text(self, key, text):
        if self.reading(key):
            self.stop_reading(key)
            return
        self.submit_speech(key, 'speak', {'text': text, 'progressive': True}, purpose='read')

    def reading(self, key):
        """True from the click until the last sentence has been played or the reading stopped."""
        entry = self.speech_jobs.get(key)
        return (self.player.current == key and self.player.playing) or             bool(entry and not entry.get('stopped'))

    def stop_reading(self, key):
        """Silence now; the job ends after the sentence being made and keeps the model loaded."""
        if self.player.current == key:
            self.player.stop()
        entry = self.speech_jobs.get(key)
        if entry and not entry.get('stopped'):
            entry['stopped'] = True
            try:
                self.runtime.cancel(self.actor, entry['job']['jobId'])
            except CyToolError:
                pass

    def apply_piece(self, event):
        """Play a sentence of a reading as soon as it exists, then delete its file."""
        data = event.get('data') or {}
        path = Path(data.get('audio', ''))
        for key, entry in self.speech_jobs.items():
            if entry['job']['jobId'] != event.get('jobId'):
                continue
            entry['pieces'] = entry.get('pieces', 0) + 1
            if not entry.get('stopped') and path.is_file():
                try:
                    audio, rate = read_wav(path)
                    if not self.player.append(audio, rate, key):
                        tab = self.find(entry.get('tab', ''))
                        if tab is not None:
                            tab.error = self.player.error
                except (OSError, ValueError):
                    pass
            break
        if path.is_file() and path.parent == paths.SPEECH / 'pieces':
            path.unlink(missing_ok=True)

    def submit_speech(self, key, operation, parameters, **details):
        if key in self.speech_jobs:
            return
        try:
            job = self.submit(operation, parameters)
        except (CyToolError, ValueError) as exc:
            tab = self.find(details.get('tab', ''))
            if tab is not None:
                tab.error = str(exc)
            return
        self.speech_jobs[key] = dict(details, job=job)

    def speech_job(self, key):
        entry = self.speech_jobs.get(key)
        return entry['job'] if entry else None

    def poll_speech(self):
        for key, entry in list(self.speech_jobs.items()):
            try:
                job = entry['job'] = self.runtime.get_job(self.actor, entry['job']['jobId'])
            except CyToolError:
                self.speech_jobs.pop(key, None)
                continue
            if active(job):
                continue
            self.speech_jobs.pop(key, None)
            # Pieces announced but never played (a stop, a closed tab) are not left behind.
            for leftover in (paths.SPEECH / 'pieces').glob('job-%s-*.wav' % job['jobId']):
                leftover.unlink(missing_ok=True)
            tab = self.find(entry.get('tab', ''))
            if job['state'] == 'Cancelled' or entry.get('stopped'):
                continue
            if job['state'] == 'Failed':
                error = job.get('error') or {}
                message = '%s: %s' % (error.get('code', 'Error'), error.get('message', ''))
                if tab is not None:
                    tab.error = message
                else:
                    self.speech_error = message
                continue
            if job['state'] != 'Completed':
                continue
            outputs = job.get('outputs') or {}
            if entry['purpose'] in ('dictation', 'live') and tab is not None:
                words = (outputs.get('text') or '').strip()
                prefix = getattr(tab, 'dictation_prefix', '') if entry['purpose'] == 'live' \
                    else tab.input
                tab.input = join_words(prefix, words)
                if not words:
                    tab.error = 'No words were heard in the recording.'
            elif entry['purpose'] == 'read' and outputs.get('audio') and not entry.get('pieces')                     and not entry.get('stopped'):
                # Read before: the whole file was reused and no piece was announced.
                if not self.player.play(outputs['audio'], key) and tab is not None:
                    tab.error = self.player.error

    def read_last_reply(self, tab):
        replies = [message for message in tab.document.get('messages', [])
                   if message.get('role') == 'assistant' and not message.get('failed')
                   and message.get('text')]
        if replies:
            self.read_message(tab, replies[-1])

    def cancel(self, tab):
        if tab.job:
            try:
                self.runtime.cancel(self.actor, tab.job['jobId'])
            except CyToolError as exc:
                tab.error = str(exc)

    # ------------------------------------------------------------------ polling

    def poll(self):
        """Drain the event stream and refresh the job of every tab that has one running."""
        now = time.monotonic()
        if now - self.last_poll < POLL_SECONDS:
            return
        self.last_poll = now
        try:
            batch = self.runtime.events(self.actor, self.cursor)
        except CyToolError:
            return
        self.cursor = batch['cursor']
        self.recorder.flush_live()
        for event in batch['events']:
            if event.get('type') == 'DictationPartial':
                self.apply_dictation(event)
                continue
            if event.get('type') == 'SpeechPiece':
                self.apply_piece(event)
                continue
            if event.get('type') not in ('ChatDelta', 'ChatTurnStarted', 'ChatTurnCompleted',
                                         'ChatTurnFailed'):
                continue
            conversation_id = (event.get('data') or {}).get('conversationId')
            tab = self.find(conversation_id)
            if tab is not None:
                tab.apply(event)
        for tab in self.tabs:
            if active(tab.job):
                try:
                    tab.job = self.runtime.get_job(self.actor, tab.job['jobId'])
                except CyToolError:
                    tab.job = None
                    continue
                if not active(tab.job):
                    tab.dirty = True
                    tab.read_when_loaded = (tab.job['state'] == 'Completed'
                                            and bool(self.speech_settings.get('autoRead')))
                    if tab.job['state'] == 'Failed' and tab.job.get('error'):
                        tab.error = '%s: %s' % (tab.job['error'].get('code', 'Error'),
                                                tab.job['error'].get('message', ''))
                    elif tab.job['state'] == 'Cancelled':
                        tab.status = 'Cancelled'
            if tab.dirty:
                tab.dirty = False
                try:
                    tab.reload()
                except CyToolError:
                    pass
                tab.live = []
                tab.live_thinking = []
                tab.scroll_to_bottom = True
                if tab.read_when_loaded:
                    tab.read_when_loaded = False
                    self.read_last_reply(tab)
        self.poll_speech()

    # ------------------------------------------------------------------ helpers

    def refresh_presets(self):
        try:
            self.presets = presets.listing()
        except CyToolError:
            self.presets = []

    def update_document(self, tab, **fields):
        try:
            tab.document = conversations.set_fields(tab.id, **fields)
        except CyToolError as exc:
            tab.error = str(exc)
