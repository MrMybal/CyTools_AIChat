"""The provider registry: every way this Tool can reach a model, in one place.

Three families live here. Agent command lines reuse an account the user already signed into
elsewhere. HTTP endpoints take an API key or a base URL. The local family runs GGUF weights
on this machine through the Tool's own llama.cpp server, and is the only one where a LoRA
adapter applies.

The registry is built once per runtime and shared by the CLI, MCP and the interface, so a
model loaded for the desktop window is the same one an AI client talks to: there is never a
second scheduler or a second resident model in another process.
"""
import concurrent.futures
import threading

from cytools_core import CyToolError

from .agentcli import DECLARED_ONLY, IMPLEMENTED, AgentCliProvider, DeclaredProvider
from .base import SESSION, STATELESS, ChatRequest, ChatResult, Delta, Provider
from .httpchat import (AnthropicProvider, CustomOpenAIProvider, OllamaProvider, OpenAIProvider,
                       OpenRouterProvider)
from .llamacpp import LlamaCppProvider

HTTP_PROVIDERS = (OpenAIProvider, OpenRouterProvider, CustomOpenAIProvider, AnthropicProvider,
                  OllamaProvider)

__all__ = ['Registry', 'ChatRequest', 'ChatResult', 'Delta', 'Provider', 'SESSION', 'STATELESS']


class Registry:
    def __init__(self, runtime, resident=None, settings=None):
        from ..resident import Resident
        self.runtime = runtime
        self.settings = dict(settings or {})
        self.resident = resident if resident is not None else Resident(runtime)
        self.lock = threading.RLock()
        self.providers = {}
        self._build()

    def _build(self):
        from ..paths import DATA
        workspace = DATA / 'agent-workspace'
        workspace.mkdir(parents=True, exist_ok=True)
        agent_settings = {'workspace': str(workspace), **self.settings.get('agents', {})}
        for provider_id in IMPLEMENTED:
            try:
                self.providers[provider_id] = AgentCliProvider(provider_id, agent_settings)
            except CyToolError:
                self.providers[provider_id] = DeclaredProvider(provider_id)
        for provider_id in DECLARED_ONLY:
            self.providers[provider_id] = DeclaredProvider(provider_id)
        for factory in HTTP_PROVIDERS:
            instance = factory(self.settings.get(factory.id, {}))
            self.providers[instance.id] = instance
        local = LlamaCppProvider(self.resident, self.settings.get('llamacpp', {}))
        self.providers[local.id] = local

    # ------------------------------------------------------------------ access

    def get(self, provider_id):
        provider = self.providers.get(str(provider_id))
        if provider is None:
            raise CyToolError('NotFound',
                              'Unknown provider: %s. Known: %s'
                              % (provider_id, ', '.join(sorted(self.providers))))
        return provider

    def ids(self):
        return list(self.providers)

    def descriptors(self):
        return [self.providers[key].descriptor() for key in self.providers]

    def _detect_one(self, key):
        try:
            return self.providers[key].detect()
        except CyToolError as exc:
            return {'id': key, 'name': self.providers[key].name, 'available': False,
                    'status': 'Error', 'detail': str(exc)}
        except Exception as exc:  # a provider must never take the inventory down with it
            return {'id': key, 'name': self.providers[key].name, 'available': False,
                    'status': 'Error', 'detail': repr(exc)[:300]}

    def detect(self, provider_id=''):
        """Probe every provider at once.

        Each probe spawns a command line or waits on a socket; run one after another they
        keep the inventory pending for several seconds. They are independent, so they run
        together, and the report keeps the declared order.
        """
        if provider_id:
            return [self._detect_one(self.get(provider_id).id)]
        keys = list(self.providers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(keys) or 1)) as pool:
            return list(pool.map(self._detect_one, keys))

    def close(self):
        with self.lock:
            for provider in self.providers.values():
                try:
                    provider.close()
                except Exception:
                    pass
