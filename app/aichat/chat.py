"""One chat turn, from the job parameters to the reply stored in the conversation.

This module is the single place a turn is executed, whichever transport asked for it: the
desktop window, the CLI and MCP all end up here, so a conversation looks the same whoever
wrote into it.

Streamed tokens are published as `ChatDelta` events rather than one event per token. The
Core keeps a bounded event buffer, and a long reply emitted token by token would push older
events out of it and make the interface miss the beginning of its own stream. Batching every
few dozen milliseconds keeps the window responsive and the buffer meaningful.
"""
import time

from cytools_core import CyToolError

from . import conversations, presets
from .providers import ChatRequest, Delta

FLUSH_SECONDS = 0.08
FLUSH_CHARACTERS = 160
# A reply of this many characters is treated as "about done" for the progress estimate when
# the provider gives no token budget. It is an estimate and the step label says so.
ASSUMED_REPLY_CHARACTERS = 2400


class Streamer:
    """Accumulates deltas and publishes them in batches with a stable sequence number."""

    def __init__(self, context, conversation_id, message_id):
        self.context = context
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.text = []
        self.thinking = []
        self.pending = []
        self.pending_thinking = []
        self.sequence = 0
        self.last_flush = 0.0
        self.expected = ASSUMED_REPLY_CHARACTERS
        self.last_percent = 10

    def __call__(self, kind, value):
        if kind == Delta.TEXT:
            self.text.append(value)
            self.pending.append(value)
        elif kind == Delta.THINKING:
            self.thinking.append(value)
            self.pending_thinking.append(value)
        elif kind in (Delta.STATUS, Delta.TOOL):
            self.flush(force=True, status=value)
            return
        size = sum(len(part) for part in self.pending) + sum(len(p) for p in self.pending_thinking)
        if size >= FLUSH_CHARACTERS or time.monotonic() - self.last_flush >= FLUSH_SECONDS:
            self.flush()

    def flush(self, force=False, status='', quiet=False):
        """Publish what has accumulated.

        `quiet` skips the progress update. `JobContext.progress` re-checks the cancellation
        token and raises, so a flush from a failure handler would throw a second exception
        and abandon the recording of the first one.
        """
        if not force and not self.pending and not self.pending_thinking:
            return
        payload = {'conversationId': self.conversation_id, 'messageId': self.message_id,
                   'sequence': self.sequence, 'text': ''.join(self.pending),
                   'thinking': ''.join(self.pending_thinking),
                   'totalCharacters': sum(len(part) for part in self.text)}
        if status:
            payload['status'] = status
        self.sequence += 1
        self.pending = []
        self.pending_thinking = []
        self.last_flush = time.monotonic()
        self.context.emit('ChatDelta', payload)
        if quiet:
            return
        percent = min(90, 10 + int(80 * payload['totalCharacters'] / max(self.expected, 1)))
        if percent > self.last_percent or status:
            self.last_percent = max(self.last_percent, percent)
            self.context.progress(self.last_percent,
                                  currentStep=status or 'Receiving the reply (estimated)',
                                  currentStepIndex=2, stepCount=3)

    def result(self):
        return ''.join(self.text), ''.join(self.thinking)


def resolve_conversation(parameters):
    """Find the conversation the turn belongs to, creating it when the caller asked for one."""
    conversation_id = str(parameters.get('conversation') or '').strip()
    if conversation_id:
        if not conversations.exists(conversation_id):
            raise CyToolError('NotFound', 'Unknown conversation: ' + conversation_id)
        return conversations.load(conversation_id)
    return conversations.create(provider_id=parameters.get('provider', ''),
                                transport=parameters.get('transport', ''),
                                model=parameters.get('model', ''),
                                system_prompt=parameters.get('system_prompt', ''),
                                preset_id=parameters.get('preset', ''))


def merge_settings(document, parameters):
    """Preset first, then the conversation, then what this call explicitly asked for.

    An explicit parameter always wins: a preset completes a request, it never overrides a
    value the caller wrote down.
    """
    values = {}
    preset_id = parameters.get('preset') or document.get('presetId') or ''
    system_prompt = document.get('systemPrompt', '')
    if preset_id:
        preset = presets.load(preset_id)
        values.update(preset['settings'])
        if not system_prompt:
            system_prompt = preset.get('systemPrompt', '')
    values.update(document.get('settings') or {})
    explicit = parameters.get('settings') or {}
    if not isinstance(explicit, dict):
        raise CyToolError('InvalidParameters', 'settings must be an object.')
    values.update({key: value for key, value in explicit.items() if value is not None})
    for key in ('temperature', 'top_p', 'top_k', 'max_tokens', 'seed', 'repeat_penalty',
                'context_tokens', 'history_limit', 'reasoning_effort'):
        if parameters.get(key) not in (None, ''):
            values[key] = parameters[key]
    if parameters.get('loras'):
        values['loras'] = parameters['loras']
    if parameters.get('system_prompt'):
        system_prompt = parameters['system_prompt']
    return values, system_prompt, preset_id


def resolve_transport(provider, parameters, document):
    """Honour an explicit transport; do not let a leftover one block the conversation.

    A conversation stores the transport it last used. Changing its provider can leave a
    transport that the new provider does not speak — `chat-completions` kept from an HTTP
    endpoint while the provider is now the local model, say. Refusing the turn over a value
    the caller did not ask for this time would be a dead end, so a stale stored transport
    falls back to the provider's default. A transport passed explicitly is still checked and
    refused if it is wrong, because that one is a real request.
    """
    explicit = str(parameters.get('transport') or '').strip()
    if explicit:
        return provider.transport_for(explicit)
    stored = str(document.get('transport') or '').strip()
    if stored and stored in provider.transports:
        return stored
    return provider.transport_for('')


def run_turn(registry, context, parameters, resolved=None):
    document = resolve_conversation(parameters)
    conversation_id = document['id']
    provider_id = (parameters.get('provider') or document.get('providerId') or '').strip()
    if not provider_id:
        raise CyToolError('InvalidParameters',
                          'Choose a provider for this conversation (see list_providers).')
    provider = registry.get(provider_id)
    transport = resolve_transport(provider, parameters, document)
    model = (parameters.get('model') or document.get('model') or '').strip()
    settings, system_prompt, preset_id = merge_settings(document, parameters)
    settings['_context'] = context
    # Model references and adapters already resolved to real paths by the model
    # library wrapper. Only the local provider can act on them.
    settings['_resolved'] = resolved or {}

    conversations.set_fields(conversation_id, providerId=provider_id, transport=transport,
                             model=model, systemPrompt=system_prompt, presetId=preset_id,
                             settings={k: v for k, v in settings.items() if not k.startswith('_')})

    context.progress(5, currentStep='Preparing the turn', currentStepIndex=1, stepCount=3)
    user_message = conversations.append(conversation_id, 'user', parameters['message'],
                                        providerId=provider_id, model=model)
    document = conversations.load(conversation_id)

    native_id = conversations.get_native(document, provider_id, transport) or ''
    history = []
    if provider.kind == 'stateless':
        limit = int(settings.get('history_limit') or 0)
        # The message just appended is sent as the prompt, so it is dropped from the history
        # first; the limit is applied afterwards, otherwise it would silently count one short.
        earlier = conversations.history(document)[:-1]
        history = earlier[-limit:] if limit else earlier

    request = ChatRequest(prompt=parameters['message'], messages=history,
                          system_prompt=system_prompt, model=model, transport=transport,
                          settings=settings, native_id=native_id,
                          cancellation=context.cancellation, workspace=context.workspace)
    placeholder = 'a-' + user_message['id'][2:]
    streamer = Streamer(context, conversation_id, placeholder)
    if settings.get('max_tokens'):
        streamer.expected = max(200, int(settings['max_tokens']) * 4)
    context.emit('ChatTurnStarted', {'conversationId': conversation_id, 'messageId': placeholder,
                                     'providerId': provider_id, 'transport': transport,
                                     'model': model, 'kind': provider.kind})
    started = time.monotonic()
    try:
        result = provider.chat(request, streamer)
    except CyToolError as exc:
        # The partial reply is kept: a cancelled or failed turn that silently vanished from
        # the transcript would leave the user wondering whether anything happened at all.
        streamer.flush(force=True, quiet=True)
        partial, _ = streamer.result()
        conversations.append(conversation_id, 'assistant', partial, failed=True,
                             error=exc.code, errorMessage=str(exc), providerId=provider_id,
                             transport=transport, model=model,
                             partialCharacters=len(partial) or None,
                             seconds=round(time.monotonic() - started, 3))
        context.emit('ChatTurnFailed', {'conversationId': conversation_id,
                                        'messageId': placeholder, 'code': exc.code,
                                        'message': str(exc),
                                        'partialCharacters': len(partial)})
        raise
    streamer.flush(force=True)
    streamed, thinking = streamer.result()
    text = result['text'] or streamed
    context.progress(95, currentStep='Storing the reply', currentStepIndex=3, stepCount=3)
    message = conversations.append(
        conversation_id, 'assistant', text, providerId=provider_id, transport=transport,
        model=result.get('model') or model, usage=result.get('usage') or None,
        seconds=result.get('seconds'), kind=provider.kind,
        thinkingCharacters=len(thinking) or None,
        systemPromptFolded=result.get('systemPromptFolded') or None,
        loras=result.get('loras') or None)
    if result.get('nativeId'):
        conversations.set_native(conversation_id, provider_id, transport, result['nativeId'])
    transcript = context.path('outputs/reply.md')
    transcript.write_text(text, encoding='utf-8')
    context.emit('ChatTurnCompleted', {'conversationId': conversation_id,
                                       'messageId': message['id'], 'characters': len(text),
                                       'seconds': result.get('seconds', 0)})
    context.progress(100, currentStep='Reply stored', currentStepIndex=3, stepCount=3)
    return {'conversationId': conversation_id, 'messageId': message['id'], 'text': text,
            'providerId': provider_id, 'transport': transport,
            'model': result.get('model') or model, 'kind': provider.kind,
            'usage': result.get('usage') or {}, 'seconds': result.get('seconds', 0.0),
            'nativeSessionId': result.get('nativeId', ''),
            'thinkingCharacters': len(thinking),
            'file': str(transcript), 'mimeType': 'text/markdown'}
