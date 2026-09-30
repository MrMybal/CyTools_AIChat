"""A llama.cpp server owned by this Tool, kept loaded between replies.

Chat is a sequence of short turns, so reloading several gigabytes of weights for every
message would make the Tool unusable. The server is therefore started once and reused while
the model, the device and the LoRA set stay the same; changing any of them restarts it,
because silently answering with a different configuration than the one displayed would be
worse than a pause.

The process is bound to the loopback interface on a random port behind a per-launch bearer
token, so another program on the machine cannot send turns to it. On Windows it is attached
to a job object, which means it cannot outlive the Tool even if the Tool is killed. The SDK
reservation is held for as long as the process really runs and released only once it has
actually stopped, never merely when cancellation was requested.
"""
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

from cytools_core import CyToolError

from . import engine
from .paths import LOGS

HEALTH_TIMEOUT = 300.0
STOP_GRACE = 6.0


class Resident:
    worker_id = 'llamacpp-server'

    def __init__(self, runtime):
        self.runtime = runtime
        self.process = None
        self.job_handle = None
        self.log = None
        self.key = None
        self.token = ''
        self.url = ''
        self.adapters = []
        self.lock = threading.RLock()
        self.started_at = 0.0
        runtime.register_worker(self.worker_id, self)

    # ------------------------------------------------------------------ lifecycle

    @property
    def state(self):
        """The vocabulary the Core's worker registry expects, alongside `release`.

        `Runtime.status()` reads `.state` on every registered worker, so a worker that only
        implements `release` makes the whole status call fail. A loaded server is reported
        as Busy because it is holding a reservation, which is exactly what the status is
        being asked about.
        """
        with self.lock:
            if self.process is None:
                return 'Stopped'
            return 'Busy' if self.process.poll() is None else 'Failed'

    def health(self):
        with self.lock:
            if self.process is not None and self.process.poll() is not None:
                self.stop()
            if self.process is None:
                return {'loaded': False, 'pid': None, 'model': '', 'device': '', 'loras': [],
                        'contextTokens': 0, 'uptimeSeconds': 0}
            return {'loaded': True, 'pid': self.process.pid, 'model': self.key[0],
                    'device': self.key[1], 'contextTokens': self.key[3],
                    'loras': [{'id': index, 'path': item['path'], 'scale': item['scale']}
                              for index, item in enumerate(self.adapters)],
                    'uptimeSeconds': round(time.monotonic() - self.started_at, 1)}

    def release(self, level):
        """Called by the Core when a client asks for resources back."""
        if level in ('Model', 'Worker', 'All'):
            self.stop()

    def stop(self):
        with self.lock:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=STOP_GRACE)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                self.process = None
            if self.job_handle is not None:
                self.job_handle.Close()
                self.job_handle = None
            if self.log is not None:
                self.log.close()
                self.log = None
            self.key = None
            self.token = ''
            self.url = ''
            self.adapters = []
            # Released only now: the budget stays reserved while the process really runs.
            self.runtime.ledger.release('worker:' + self.worker_id)

    def close(self):
        self.stop()

    # ------------------------------------------------------------------ requests

    def request(self, path, payload=None, timeout=30, method=''):
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = urllib.request.Request(
            self.url + path, data=body, method=method or ('POST' if body is not None else 'GET'),
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode('utf-8', 'replace')
        return json.loads(text) if text.strip() else {}

    def open_stream(self, path, payload, timeout):
        request = urllib.request.Request(
            self.url + path, data=json.dumps(payload).encode('utf-8'), method='POST',
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
                     'Accept': 'text/event-stream'})
        return urllib.request.urlopen(request, timeout=timeout)

    # ------------------------------------------------------------------ start

    def plan(self, settings):
        """Resolve the exact command this configuration needs, before touching a process."""
        model_path = settings['model_path']
        if not os.path.isfile(model_path):
            raise CyToolError('MissingModel',
                              'The selected GGUF file is missing: %s' % model_path)
        build = engine.available_build(settings.get('engine', 'auto'))
        spec = engine.build(build)
        device = spec.get('device', 'cpu')
        adapters = list(settings.get('loras') or [])
        key = (str(model_path), device, build, int(settings.get('context_tokens') or 8192),
               int(settings.get('threads') or 0),
               tuple(sorted((a['path'], round(float(a.get('strength', 1.0)), 4)) for a in adapters)),
               os.path.getmtime(model_path))
        return build, spec, device, adapters, key

    def ensure(self, context, settings):
        """Start the server, or report that the already-loaded one matches. Returns `reused`."""
        build, spec, device, adapters, key = self.plan(settings)
        with self.lock:
            if self.health()['loaded'] and key == self.key:
                return True
            self.stop()
            server = engine.server_path(build)
            needs = {'ramBytes': int(float(settings.get('ram_gib') or 8) * 1024 ** 3),
                     'cpuThreads': 0}
            device_index = ''
            if device == 'cuda':
                devices = self.runtime.ledger.capacity.get('vramBytes', {})
                if not devices:
                    raise CyToolError('MissingGPU',
                                      'No NVIDIA GPU was detected. Install the CPU engine or '
                                      'select the CPU engine for this conversation.')
                device_index = max(devices, key=devices.get)
                needs['vramBytes'] = {device_index:
                                      int(float(settings.get('vram_gib') or 6) * 1024 ** 3)}
                needs['ramBytes'] = min(needs['ramBytes'], 4 * 1024 ** 3)
            if not self.runtime.reserve_worker(self.worker_id, needs):
                raise CyToolError('InsufficientResources',
                                  'Not enough memory is available for this model. Unload it, '
                                  'pick a smaller one, or switch the engine to CPU.')
            try:
                self._launch(context, server, spec, device, device_index, adapters, settings, key)
            except BaseException:
                self.stop()
                raise
            return False

    def _launch(self, context, server, spec, device, device_index, adapters, settings, key):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        self.token = secrets.token_urlsafe(32)
        self.url = 'http://127.0.0.1:%d' % port
        LOGS.mkdir(parents=True, exist_ok=True)
        self.log = (LOGS / 'llama-server.log').open('ab')
        command = [str(server), '-m', str(settings['model_path']),
                   '--host', '127.0.0.1', '--port', str(port),
                   '-c', str(int(settings.get('context_tokens') or 8192)),
                   '-ngl', '999' if device == 'cuda' else '0',
                   '-np', '1', '--no-webui', '--no-mmproj-auto',
                   '--reasoning-format', 'deepseek']
        threads = int(settings.get('threads') or 0)
        if threads > 0:
            command += ['-t', str(threads)]
        if adapters:
            # Adapters are loaded at their default weight and scaled straight afterwards
            # through /lora-adapters. The alternative, --lora-scaled, takes its scale as
            # `PATH:SCALE`, and a Windows path already contains a colon; going through the
            # endpoint avoids that ambiguity and uses the same mechanism as the live
            # strength control, so there is only one code path to trust.
            command += ['--lora', ','.join(str(adapter['path']) for adapter in adapters)]
        environment = {**os.environ, 'LLAMA_API_KEY': self.token}
        if device == 'cuda' and device_index != '':
            environment['CUDA_VISIBLE_DEVICES'] = str(device_index)
        self.log.write(('\n=== %s starting %s ===\n'
                        % (time.strftime('%Y-%m-%d %H:%M:%S'), ' '.join(command[:3]))).encode())
        self.log.flush()
        self.process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log,
            env=environment, creationflags=0x08000000 if os.name == 'nt' else 0,
            start_new_session=os.name != 'nt')
        if os.name == 'nt':
            self._attach_job_object()
        self.adapters = [{'path': str(a['path']), 'scale': float(a.get('strength', 1.0))}
                         for a in adapters]
        self.key = key
        self.started_at = time.monotonic()
        deadline = time.monotonic() + HEALTH_TIMEOUT
        while time.monotonic() < deadline:
            context.cancellation.check()
            if self.process.poll() is not None:
                raise CyToolError('WorkerCrashed',
                                  'llama-server stopped while loading the model. See '
                                  'data/logs/llama-server.log.')
            try:
                if self.request('/health', timeout=3).get('status') == 'ok':
                    if adapters:
                        self.set_scales(adapters)
                    return
            except (OSError, ValueError, urllib.error.URLError):
                pass
            context.cancellation.sleep(0.2)
        raise CyToolError('Timeout', 'Loading the model timed out after %d seconds.'
                          % int(HEALTH_TIMEOUT))

    def _attach_job_object(self):
        try:
            import win32api
            import win32con
            import win32job
        except ImportError:  # pragma: no cover - pywin32 is declared in requirements.txt
            return
        self.job_handle = win32job.CreateJobObject(None, '')
        limits = win32job.QueryInformationJobObject(self.job_handle,
                                                    win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self.job_handle,
                                         win32job.JobObjectExtendedLimitInformation, limits)
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, self.process.pid)
        try:
            win32job.AssignProcessToJobObject(self.job_handle, handle)
        finally:
            handle.Close()

    # ------------------------------------------------------------------ adapters

    def loaded_adapters(self):
        if self.process is None:
            return []
        try:
            return self.request('/lora-adapters', timeout=10)
        except (OSError, ValueError):
            return []

    def set_scales(self, adapters):
        """Change adapter weights on the running server, without reloading the model."""
        if self.process is None:
            raise CyToolError('InvalidState', 'No model is loaded.')
        payload = [{'id': index, 'scale': float(item.get('strength', item.get('scale', 1.0)))}
                   for index, item in enumerate(adapters)]
        self.request('/lora-adapters', payload, timeout=30)
        for index, item in enumerate(payload):
            if index < len(self.adapters):
                self.adapters[index]['scale'] = item['scale']
        return self.loaded_adapters()

    def properties(self):
        if self.process is None:
            return {}
        try:
            return self.request('/props', timeout=10)
        except (OSError, ValueError):
            return {}
