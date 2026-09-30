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

from cytools_core import CyToolError

from aichat import conversations, presets

POLL_SECONDS = 0.05
ACTIVE_STATES = ('Queued', 'Running')


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

    # ------------------------------------------------------------------ view

    @property
    def title(self):
        return self.document.get('title') or self.id

    @property
    def busy(self):
        return bool(self.job and self.job.get('state') in ACTIVE_STATES)

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
        for event in batch['events']:
            if event.get('type') not in ('ChatDelta', 'ChatTurnStarted', 'ChatTurnCompleted',
                                         'ChatTurnFailed'):
                continue
            conversation_id = (event.get('data') or {}).get('conversationId')
            tab = self.find(conversation_id)
            if tab is not None:
                tab.apply(event)
        for tab in self.tabs:
            if tab.job and tab.job.get('state') in ACTIVE_STATES:
                try:
                    tab.job = self.runtime.get_job(self.actor, tab.job['jobId'])
                except CyToolError:
                    tab.job = None
                    continue
                if tab.job['state'] not in ACTIVE_STATES:
                    tab.dirty = True
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
