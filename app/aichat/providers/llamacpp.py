"""The local provider: GGUF weights and GGUF LoRA adapters served by llama.cpp.

Nothing leaves the machine here. The Tool starts its own llama.cpp server on the loopback
interface, keeps it loaded between turns, and streams tokens back as they are produced.
This is the only provider where a LoRA adapter applies, because it is the only one where
this Tool controls the loading of the weights.

An adapter is applied at load time with `--lora-scaled`, and its strength can then be
changed on the running server through `/lora-adapters` without reloading the model. Changing
the *set* of adapters, the model, the device or the context size restarts the server: those
cannot be swapped underneath a loaded model. llama.cpp refuses an adapter whose tensors do
not match the loaded architecture, so an adapter trained for another family fails loudly
instead of quietly producing noise.
"""
import json
import queue
import threading
import time

from cytools_core import CyToolError

from .. import engine
from .base import STATELESS, ChatResult, Delta, Provider

# Conservative default window: large enough for a real conversation, small enough that a
# 20B model still fits beside its KV cache on a 24 GB card.
DEFAULT_CONTEXT = 8192


class LlamaCppProvider(Provider):
    id = 'llamacpp'
    name = 'Local model (llama.cpp)'
    kind = STATELESS
    transports = ('local-server',)
    supports_model_list = True
    supports_lora = True
    requires_api_key = False
    documentation = ('GGUF weights running on this machine through a llama.cpp server owned by '
                     'the Tool. Supports GGUF LoRA adapters with an adjustable strength.')

    def __init__(self, resident, settings=None):
        super().__init__(settings)
        self.resident = resident
        self._response = None
        self._lock = threading.RLock()
        self._turn = threading.Lock()

    # ------------------------------------------------------------------ description

    def descriptor(self):
        value = super().descriptor()
        value.update(engines=engine.describe(), supportsDeviceChoice=True)
        return value

    def detect(self):
        engines = engine.describe()
        installed = [item for item in engines['builds'] if item['installed']]
        from .. import catalog
        models = [row for row in catalog.listing('model') if row['installed']]
        report = {'id': self.id, 'name': self.name, 'kind': self.kind,
                  'transports': list(self.transports),
                  'engines': engines['builds'], 'installedModels': len(models),
                  'resident': self.resident.health()}
        if not installed:
            report.update(available=False, status='NotInstalled',
                          detail='No llama.cpp engine is installed yet. Install one in Models.')
        elif not models and not self.library_models():
            report.update(available=False, status='NoModel',
                          detail='The engine is installed but no GGUF model is available yet.')
        else:
            report.update(available=True, status='Ready',
                          detail='Engine: ' + ', '.join(item['id'] for item in installed))
        return report

    def library_models(self):
        """GGUF references the user registered from anywhere on the machine."""
        try:
            import model_options
            return [item for item in model_options.catalog()['models'] if item['kind'] == 'model']
        except Exception:
            return []

    def list_models(self, transport=''):
        from .. import catalog
        rows = []
        for row in catalog.listing('model'):
            rows.append({'id': row['id'], 'name': row['name'],
                         'description': '%s, %.1f GiB%s'
                                        % (row['license'], row['sizeBytes'] / 1024 ** 3,
                                           '' if row['installed'] else ', not installed'),
                         'installed': row['installed'], 'source': 'catalog'})
        for item in self.library_models():
            rows.append({'id': 'local:' + item['id'], 'name': item['name'],
                         'description': 'Registered local file, %s' % item.get('license', 'Unknown'),
                         'installed': True, 'source': 'library'})
        return rows

    # ------------------------------------------------------------------ resolution

    def model_file(self, request):
        """Turn the selection into a real GGUF path.

        `model_profile` goes through the model library, which already validated the file and
        handed back an absolute path; that resolved value wins over the `model` field so the
        two can never disagree about which weights a turn ran on.
        """
        resolved = (request.settings.get('_resolved') or {}).get('model')
        if resolved:
            return str(resolved['path']), resolved.get('name', 'registered model')
        model = request.model
        if not model:
            raise CyToolError('InvalidParameters',
                              'Select a local model for this conversation, or register one in '
                              'the model library and pass it as model_profile.')
        if model.startswith('local:'):
            identifier = model.split(':', 1)[1]
            for item in self.library_models():
                if item['id'] == identifier:
                    import model_options
                    return str(model_options.validate_asset(item)), item['name']
            raise CyToolError('NotFound', 'Unknown registered model reference: ' + identifier)
        from .. import catalog
        if not catalog.installed(model):
            raise CyToolError('MissingModel',
                              'The model %s is not installed. Install it in the Models tab.' % model)
        return str(catalog.file_path(model)), catalog.entry(model)['name']

    def lora_files(self, request):
        """Resolve the adapters for this turn, from the model library or the catalogue."""
        from .. import catalog
        resolved = (request.settings.get('_resolved') or {}).get('loras') or []
        if resolved:
            return [{'path': str(item['path']), 'strength': float(item['strength']),
                     'name': item.get('name', item['id']), 'id': 'local:' + item['id']}
                    for item in resolved]
        adapters = []
        for item in request.settings.get('loras') or []:
            identifier = str(item.get('id', ''))
            strength = float(item.get('strength', 1.0))
            if not -4 <= strength <= 4:
                raise CyToolError('InvalidLoRA', 'Adapter strength must be between -4 and 4.')
            if identifier.startswith('local:'):
                reference = identifier.split(':', 1)[1]
                import model_options
                found = next((a for a in model_options.catalog()['models']
                              if a['id'] == reference and a['kind'] == 'lora'), None)
                if found is None:
                    raise CyToolError('NotFound', 'Unknown registered LoRA: ' + reference)
                adapters.append({'path': str(model_options.validate_asset(found)),
                                 'strength': strength, 'name': found['name'], 'id': identifier})
            else:
                if not catalog.installed(identifier):
                    raise CyToolError('MissingModel',
                                      'The LoRA %s is not installed.' % identifier)
                adapters.append({'path': str(catalog.file_path(identifier)), 'strength': strength,
                                 'name': catalog.entry(identifier)['name'], 'id': identifier})
        return adapters

    def server_settings(self, request):
        path, name = self.model_file(request)
        info = self.catalogue_entry(request)
        # A model that declares a 32k window cannot serve a 128k one, and llama.cpp would
        # either refuse to start or silently rope-scale it. Asking for more than the model
        # declares is therefore capped rather than passed through.
        declared = int(info.get('contextTokens') or 0)
        requested = int(request.settings.get('context_tokens') or DEFAULT_CONTEXT)
        context_tokens = min(requested, declared) if declared else requested
        return {'model_path': path, 'model_name': name,
                'engine': request.settings.get('engine') or 'auto',
                'context_tokens': context_tokens,
                'declared_context_tokens': declared,
                'threads': int(request.settings.get('threads') or 0),
                'ram_gib': info.get('ramGiB', 8), 'vram_gib': info.get('vramGiB', 6),
                'loras': self.lora_files(request)}

    def catalogue_entry(self, request):
        """The catalogue row for the selected model, or an empty one for a registered file."""
        from .. import catalog
        if not request.model or request.model.startswith('local:'):
            return {}
        try:
            return catalog.entry(request.model)
        except CyToolError:
            return {}

    # ------------------------------------------------------------------ one turn

    def chat(self, request, on_delta):
        # One slot on the server, therefore one turn at a time. Without this, two tabs
        # pointed at the local model would interleave their tokens in the same slot.
        with self._turn:
            return self._chat(request, on_delta)

    def _chat(self, request, on_delta):
        context = request.settings.get('_context')
        if context is None:
            raise CyToolError('InvalidState', 'The local provider must run inside a job.')
        settings = self.server_settings(request)
        on_delta(Delta.STATUS, 'Loading %s' % settings['model_name'])
        reused = self.resident.ensure(context, settings)
        on_delta(Delta.STATUS, 'Model resident' if reused else 'Model loaded')
        payload = {'messages': request.payload(), 'stream': True,
                   'cache_prompt': not settings['loras']}
        for key, field in (('temperature', 'temperature'), ('top_p', 'top_p'), ('top_k', 'top_k'),
                           ('max_tokens', 'max_tokens'), ('repeat_penalty', 'repeat_penalty'),
                           ('seed', 'seed'), ('min_p', 'min_p')):
            value = request.settings.get(key)
            if value is not None and value != '':
                payload[field] = value
        if payload.get('seed') in (-1, '-1'):
            payload.pop('seed')
        # A reasoning model spends tokens thinking before it answers. The catalogue records
        # how much of that each one is worth by default; an explicit setting overrides it.
        # The thinking itself is streamed on the reasoning channel and never stored as the
        # reply, so a low effort shortens the wait without truncating the answer.
        effort = request.settings.get('reasoning_effort') or self.catalogue_entry(request).get(
            'reasoningEffort')
        if effort == 'none':
            # There is no single switch for this; the behaviour depends on the chat template
            # family. Qwen and Gemma templates stop reasoning entirely with
            # enable_thinking=false and ignore reasoning_effort. The GPT-OSS harmony
            # template ignores enable_thinking and honours the effort level, whose lowest
            # value is 'minimal', not 'none'. Sending both makes "none" mean "as little
            # thinking as this model allows" on either family; the field a template does
            # not understand is ignored.
            payload.setdefault('chat_template_kwargs', {})['enable_thinking'] = False
            payload['reasoning_effort'] = 'minimal'
        elif effort:
            payload['reasoning_effort'] = effort
        started = time.monotonic()
        text, usage, thinking = self._stream(request, payload, on_delta)
        if not text.strip():
            if thinking:
                # A hybrid model can spend the whole budget reasoning and never reach its
                # answer. Saying "no text" would send the user looking for a broken model.
                raise CyToolError(
                    'ReasoningBudgetExhausted',
                    'The model spent its whole token budget thinking (%d characters of '
                    'reasoning) and produced no answer. Raise Max tokens, or set Reasoning '
                    'effort to "none" for this conversation.' % len(thinking))
            raise CyToolError('EmptyResponse', 'The local model returned no text.')
        result = ChatResult(text, model=request.model, usage=usage, transport='local-server',
                            seconds=time.monotonic() - started,
                            modelFile=settings['model_path'], reusedResident=reused,
                            contextTokens=settings['context_tokens'],
                            reasoningEffort=effort or '',
                            engine=engine.available_build(settings['engine']),
                            loras=[{'id': a['id'], 'name': a['name'], 'strength': a['strength']}
                                   for a in settings['loras']])
        if not request.settings.get('keep_loaded', True):
            self.resident.stop()
        return result

    def _stream(self, request, payload, on_delta):
        """Read the SSE stream on a reader thread so cancellation is never blocked on a socket.

        Returns the answer, the usage block, and the reasoning text seen on the side channel.
        The reasoning is never part of the answer, but knowing that there was some is what
        lets an empty reply be reported as a spent thinking budget instead of a silent model.
        """
        lines = queue.Queue()
        error = {}

        def reader(response):
            try:
                for raw in response:
                    lines.put(raw)
            except Exception as exc:  # the socket is closed by cancel(); that is not a failure
                error['reader'] = exc
            finally:
                lines.put(None)

        try:
            response = self.resident.open_stream('/v1/chat/completions', payload, timeout=120)
        except OSError as exc:
            self.resident.stop()
            raise CyToolError('WorkerCrashed',
                              'The local server did not accept the request: %s' % exc)
        with self._lock:
            self._response = response
        thread = threading.Thread(target=reader, args=(response,), daemon=True)
        thread.start()
        collected = []
        reasoning_seen = []
        usage = {}
        try:
            while True:
                request.check()
                try:
                    raw = lines.get(timeout=0.05)
                except queue.Empty:
                    continue
                if raw is None:
                    break
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                chunk = line[5:].strip()
                if chunk == '[DONE]':
                    break
                try:
                    data = json.loads(chunk)
                except ValueError:
                    raise CyToolError('ProtocolError', 'Malformed chunk from the local server.')
                if data.get('error'):
                    raise CyToolError('ProviderFailed', str(data['error'])[:600])
                if data.get('usage'):
                    usage = data['usage']
                for choice in data.get('choices', []):
                    delta = choice.get('delta') or {}
                    reasoning = delta.get('reasoning_content') or ''
                    if reasoning:
                        reasoning_seen.append(reasoning)
                        on_delta(Delta.THINKING, reasoning)
                    piece = delta.get('content') or ''
                    if piece:
                        collected.append(piece)
                        on_delta(Delta.TEXT, piece)
            if error.get('reader') and not collected:
                raise CyToolError('ProtocolError', 'The local stream failed: %s' % error['reader'])
            return ''.join(collected), usage, ''.join(reasoning_seen)
        finally:
            with self._lock:
                self._response = None
            try:
                response.close()
            except Exception:
                pass
            thread.join(timeout=2)

    def cancel(self):
        """Closing the socket stops the generation for that slot without killing the server."""
        with self._lock:
            response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def close(self):
        self.resident.stop()
