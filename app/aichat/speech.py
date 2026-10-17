"""Speech to text and text to speech, run by two resident workers.

Each worker is `aichat/speech_worker.py` started with the interpreter of its own environment
(runtime/engines/stt or runtime/engines/tts) and kept alive between requests, so a model is
loaded once and the next dictation or reading starts straight away. Like the llama.cpp server,
a worker is attached to a Windows job object and cannot outlive the Tool, and the SDK
reservation for the model it holds lasts exactly as long as its process runs.

The worker never sees a secret: the Tool's token and the provider keys are removed from its
environment, and it runs offline on weights the catalogue already verified.
"""
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from cytools_core import CyToolError

from . import catalog, credentials, paths, speech_env, speech_text, voices
from .resident import attach_job_object

START_TIMEOUT = 180.0
STOP_GRACE = 5.0
# Live dictation: how often the recording is looked at, and how much new audio is worth
# transcribing the open sentence again. A pause this long closes a sentence.
LIVE_POLL = 0.15
LIVE_STEP = 0.5
PAUSE_SECONDS = 0.6
MAX_SEGMENT_SECONDS = 20.0
# Reading a reply progressively: the first piece is kept short so the voice starts quickly.
FIRST_PIECE = 110
FRAME_SECONDS = 0.03
STT_PREFERENCE = {'en': ('phonon-2', 'parakeet-tdt-0.6b-v3'),
                  '': ('parakeet-tdt-0.6b-v3', 'phonon-2')}


def write_pcm_wav(path, audio, rate):
    import wave

    import numpy as np
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype('<i2')
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(int(rate))
        output.writeframes(pcm.tobytes())


def _levels(audio, rate):
    import numpy as np
    frame = max(1, int(rate * FRAME_SECONDS))
    count = len(audio) // frame
    if count == 0:
        return np.zeros(0, dtype=np.float32), frame
    blocks = audio[:count * frame].reshape(count, frame)
    return np.sqrt(np.mean(np.square(blocks), axis=1)), frame


def _voiced(levels):
    import numpy as np
    # Relative to the quiet part of this very recording, so a noisy room or a low microphone
    # gain moves the threshold with it; never below a floor that silence cannot reach, and
    # never above a level speech always passes, or a stretch with no pause at all (whose
    # quietest part is still speech) would be taken for silence.
    floor = float(np.percentile(levels, 20)) if len(levels) else 0.0
    return levels > min(0.025, max(0.006, 3.0 * floor))


def has_speech(audio, rate, final=True):
    """Whether a stretch is worth transcribing.

    While the user is still speaking, the open sentence waits for a second of audio holding
    about half a second of speech: on less, the model guesses, and the guess flickers on screen
    before the next pass corrects it. The last pass takes even a single short word.
    """
    levels, _ = _levels(audio, rate)
    voiced = int(_voiced(levels).sum())
    if final:
        return len(audio) >= rate * 0.3 and voiced >= 5
    return len(audio) >= rate * 1.0 and voiced >= 15


def segment_end(audio, rate):
    """Where the open segment can be closed, in samples, or None to keep it open.

    A segment closes in the middle of a pause that follows speech. One that runs on without a
    pause is cut at its quietest point past the limit, so a long monologue never makes every
    pass slower than the last.
    """
    import numpy as np
    levels, frame = _levels(audio, rate)
    if len(levels) == 0:
        return None
    voiced = _voiced(levels)
    if not voiced.any():
        return None
    trailing = len(voiced) - 1 - int(np.flatnonzero(voiced)[-1])
    duration = len(audio) / float(rate)
    if trailing * FRAME_SECONDS >= PAUSE_SECONDS and duration >= 1.5:
        return (len(levels) - trailing // 2) * frame
    if duration >= MAX_SEGMENT_SECONDS:
        window = int(6.0 / FRAME_SECONDS)
        start = max(1, len(levels) - window)
        return (start + int(np.argmin(levels[start:]))) * frame
    return None


class SpeechWorker:
    def __init__(self, runtime, engine):
        self.runtime = runtime
        self.engine = engine
        self.worker_id = 'speech-' + engine
        self.process = None
        self.job_handle = None
        self.log = None
        self.replies = None
        self.lock = threading.RLock()
        self.counter = 0
        self.loaded = None          # (model id, device) the worker holds
        self.hello = {}
        runtime.register_worker(self.worker_id, self)

    # ------------------------------------------------------------------ lifecycle

    @property
    def state(self):
        if self.process is None:
            return 'Stopped'
        return 'Busy' if self.process.poll() is None else 'Failed'

    def health(self):
        alive = self.process is not None and self.process.poll() is None
        return {'engine': self.engine, 'running': alive,
                'pid': self.process.pid if alive else None,
                'model': self.loaded[0] if alive and self.loaded else '',
                'device': self.loaded[1] if alive and self.loaded else ''}

    def release(self, level):
        if level in ('Model', 'Worker', 'All'):
            self.stop()

    def stop(self):
        with self.lock:
            if self.process is not None:
                if self.process.poll() is None:
                    try:
                        self.process.stdin.write('{"command": "quit"}\n')
                        self.process.stdin.flush()
                        self.process.wait(timeout=STOP_GRACE)
                    except (OSError, ValueError, subprocess.TimeoutExpired):
                        self.process.kill()
                        self.process.wait()
                self.process = None
            if self.job_handle is not None:
                self.job_handle.Close()
                self.job_handle = None
            if self.log is not None:
                self.log.close()
                self.log = None
            self.loaded = None
            # Released only now: the budget stays reserved while the process really runs.
            self.runtime.ledger.release('worker:' + self.worker_id)

    close = stop

    def _start(self, context):
        if not speech_env.status(self.engine)['installed']:
            raise CyToolError('MissingDependency',
                              'The %s environment is not installed. Install it from the Speech '
                              'tab, or with the speech_engine_install operation.' % self.engine)
        environment = {key: value for key, value in os.environ.items()
                       if key != 'CYTOOLS_TOKEN' and key not in credentials.ENVIRONMENT.values()}
        environment.update(PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='1',
                           TRANSFORMERS_OFFLINE='1', PYTHONNOUSERSITE='1')
        paths.LOGS.mkdir(parents=True, exist_ok=True)
        self.log = (paths.LOGS / ('speech-%s.log' % self.engine)).open('ab')
        self.log.write(('\n=== %s starting the %s worker ===\n'
                        % (time.strftime('%Y-%m-%d %H:%M:%S'), self.engine)).encode())
        self.log.flush()
        self.process = subprocess.Popen(
            [str(speech_env.python(self.engine)), '-u', str(paths.APP / 'aichat/speech_worker.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, env=environment,
            cwd=str(paths.ROOT), text=True, encoding='utf-8', errors='replace', bufsize=1,
            creationflags=0x08000000 if os.name == 'nt' else 0)
        if os.name == 'nt':
            self.job_handle = attach_job_object(self.process.pid)
        self.replies = queue.Queue()
        threading.Thread(target=self._read, args=(self.process, self.replies),
                         name='speech-%s-reader' % self.engine, daemon=True).start()
        try:
            self.hello = self._exchange(context, {'command': 'hello'}, START_TIMEOUT)
        except BaseException:
            # A worker that cannot say hello is not left half started for the next request.
            self.stop()
            raise

    @staticmethod
    def _read(process, replies):
        for line in process.stdout:
            line = line.strip()
            if line.startswith('{'):
                try:
                    replies.put(json.loads(line))
                except ValueError:
                    continue
        replies.put(None)

    def _exchange(self, context, request, timeout, on_event=None):
        self.counter += 1
        request = dict(request, id=self.counter)
        try:
            self.process.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
            self.process.stdin.flush()
        except OSError as exc:
            self.stop()
            raise CyToolError('WorkerCrashed', 'The %s worker stopped. See data/logs/speech-%s.log.'
                              % (self.engine, self.engine)) from exc
        deadline = time.monotonic() + timeout
        cancelled = None
        while True:
            try:
                if context is not None and cancelled is None:
                    context.cancellation.check()
            except BaseException as exc:
                if not request.get('cancelFile'):
                    # The worker may be in the middle of a long synthesis: stopping it is the
                    # only way to honour the cancellation now. The next request starts afresh.
                    self.stop()
                    raise
                # A request that can be stopped between pieces is asked to stop, so the model
                # stays loaded for the next reading; the worker answers after the current piece.
                cancelled = exc
                Path(request['cancelFile']).parent.mkdir(parents=True, exist_ok=True)
                Path(request['cancelFile']).write_bytes(b'')
                deadline = time.monotonic() + 60.0
            try:
                answer = self.replies.get(timeout=0.2)
            except queue.Empty:
                if time.monotonic() > deadline:
                    self.stop()
                    if cancelled is not None:
                        raise cancelled
                    raise CyToolError('Timeout', 'The %s worker did not answer in %d seconds.'
                                      % (self.engine, int(timeout)))
                continue
            if answer is None:
                self.stop()
                raise CyToolError('WorkerCrashed', 'The %s worker stopped. See data/logs/speech-%s.log.'
                                  % (self.engine, self.engine))
            if answer.get('id') != request['id']:
                continue
            if answer.get('event'):
                if on_event is not None and cancelled is None:
                    on_event(answer)
                continue
            if cancelled is not None:
                raise cancelled
            if not answer.get('ok'):
                error = answer.get('error') or {}
                raise CyToolError(error.get('code', 'WorkerError'), error.get('message', ''))
            return answer.get('result') or {}

    def call(self, context, request, timeout=900.0, on_event=None):
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self.stop()
                self._start(context)
            return self._exchange(context, request, timeout, on_event)

    def reserve_for(self, model_id, device, ram_gib, vram_gib):
        """Hold the budget of the model this worker is about to load, replacing the last one."""
        if self.loaded == (model_id, device):
            return
        self.runtime.ledger.release('worker:' + self.worker_id)
        needs = {'ramBytes': int(ram_gib * 1024 ** 3), 'cpuThreads': 0}
        if device == 'cuda':
            devices = self.runtime.ledger.capacity.get('vramBytes', {})
            if devices:
                index = max(devices, key=devices.get)
                needs['vramBytes'] = {index: int(vram_gib * 1024 ** 3)}
                needs['ramBytes'] = min(needs['ramBytes'], 3 * 1024 ** 3)
        if not self.runtime.reserve_worker(self.worker_id, needs):
            raise CyToolError('InsufficientResources',
                              'Not enough memory is free for %s. Unload the chat model or the '
                              'other speech model, or use the CPU.' % model_id)


class Speech:
    """The two workers, and what the operations ask of them."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.workers = {'stt': SpeechWorker(runtime, 'stt'), 'tts': SpeechWorker(runtime, 'tts')}
        self._speakers = None

    def close(self):
        for worker in self.workers.values():
            worker.stop()

    unload_all = close

    # ------------------------------------------------------------------ status

    def status(self):
        listing = catalog.listing()
        return {'engines': speech_env.statuses(),
                'models': [row for row in listing if row['kind'] in catalog.SPEECH_KINDS],
                'workers': {name: worker.health() for name, worker in self.workers.items()},
                'settings': voices.settings()}

    # ------------------------------------------------------------------ model choice

    @staticmethod
    def _installed(kind):
        return [row for row in catalog.listing(kind)
                if row['installed'] and not row.get('component')]

    def stt_model(self, requested='', language=''):
        installed = {row['id'] for row in self._installed('stt')}
        chosen = requested or voices.settings()['sttModel']
        if chosen:
            if chosen not in installed:
                raise CyToolError('MissingModel', 'The speech-to-text model %s is not installed.'
                                  % chosen)
            return chosen
        for identifier in STT_PREFERENCE.get(language, STT_PREFERENCE['']):
            if identifier in installed:
                return identifier
        raise CyToolError('MissingModel', 'No speech-to-text model is installed. Install Parakeet '
                                          'TDT 0.6B v3 (French) or Phonon-2 (English) from the '
                                          'Speech tab.')

    def tts_model(self, requested='', language=''):
        installed = self._installed('tts')
        chosen = requested or voices.settings()['ttsModel']
        if chosen:
            if chosen not in {row['id'] for row in installed}:
                raise CyToolError('MissingModel', 'The voice model %s is not installed.' % chosen)
            return chosen
        speaking = [row['id'] for row in installed if language in row.get('languages', [])]
        if speaking:
            return speaking[0]
        if installed:
            return installed[0]['id']
        raise CyToolError('MissingModel', 'No voice model is installed. Install XTTS-v2 or an '
                                          'F5-TTS model from the Speech tab.')

    # ------------------------------------------------------------------ speech to text

    def transcribe(self, context, audio, model='', language=''):
        identifier = self.stt_model(model, language)
        info = catalog.entry(identifier)
        worker = self.workers['stt']
        worker.reserve_for(identifier, 'cpu', info.get('ramGiB', 5), 0)
        context.progress(10, currentStep='Transcribing with %s' % info['name'])
        result = worker.call(context, {
            'command': 'transcribe', 'model': identifier, 'format': info['format'],
            'directory': str(catalog.directory(identifier)), 'audio': str(audio),
            'device': 'cpu', 'archive': info.get('archive', ''),
            'unpack': info.get('unpack', ''), 'containerSha256': info.get('containerSha256', '')})
        worker.loaded = (identifier, 'cpu')
        return {'text': result['text'], 'model': identifier,
                'audioSeconds': result['audioSeconds'], 'seconds': result['seconds'],
                'loadSeconds': result['loadSeconds']}

    # ------------------------------------------------------------------ live dictation

    def transcribe_live(self, context, stream, done, rate, model='', language='',
                        max_seconds=600.0):
        """Transcribe a recording while it is being made, publishing the text as it grows.

        The window appends 16-bit PCM to `stream` as the microphone delivers it and creates
        `done` when the user stops. The audio is cut into segments at pauses: a closed segment
        is transcribed once and its words are final; the open one, the sentence being spoken,
        is transcribed again whenever enough new audio has arrived, so its words may still
        change. Each pass publishes a `DictationPartial` event; the job returns the whole text.
        """
        import numpy as np
        identifier = self.stt_model(model, language)
        info = catalog.entry(identifier)
        worker = self.workers['stt']
        worker.reserve_for(identifier, 'cpu', info.get('ramGiB', 5), 0)
        segment_file = context.path('work/segment.wav')
        segment_file.parent.mkdir(parents=True, exist_ok=True)

        def decode(audio):
            write_pcm_wav(segment_file, audio, rate)
            result = worker.call(context, {
                'command': 'transcribe', 'model': identifier, 'format': info['format'],
                'directory': str(catalog.directory(identifier)), 'audio': str(segment_file),
                'device': 'cpu', 'archive': info.get('archive', ''),
                'unpack': info.get('unpack', ''),
                'containerSha256': info.get('containerSha256', '')})
            worker.loaded = (identifier, 'cpu')
            return result['text'].strip()

        context.progress(5, currentStep='Loading %s' % info['name'])
        # The model loads while the user starts talking; the first pass then catches up with
        # everything said so far, since the open sentence is always transcribed whole.
        load = worker.call(context, {
            'command': 'load_stt', 'model': identifier, 'format': info['format'],
            'directory': str(catalog.directory(identifier)), 'device': 'cpu',
            'archive': info.get('archive', ''), 'unpack': info.get('unpack', ''),
            'containerSha256': info.get('containerSha256', '')}).get('loadSeconds', 0.0)
        worker.loaded = (identifier, 'cpu')
        deadline = time.monotonic() + 10.0
        while not stream.is_file():
            if time.monotonic() > deadline:
                raise CyToolError('NotFound', 'The live recording never started.')
            context.cancellation.sleep(0.1)
        committed, partial = [], ''
        offset = examined = passes = 0
        started = time.monotonic()
        while True:
            finished = done.is_file()
            raw = stream.read_bytes()
            audio = np.frombuffer(raw[:len(raw) // 2 * 2], dtype='<i2').astype(np.float32) / 32768.0
            active = audio[offset:]
            if finished or len(active) - examined >= rate * LIVE_STEP:
                cut = None if finished else segment_end(active, rate)
                if cut:
                    words = decode(active[:cut])
                    if words:
                        committed.append(words)
                    offset += cut
                    active = audio[offset:]
                    partial = ''
                partial = decode(active) if has_speech(active, rate, finished) else partial
                examined = len(active)
                passes += 1
                context.emit('DictationPartial', {
                    'text': ' '.join(committed + ([partial] if partial else [])),
                    'committed': ' '.join(committed), 'partial': partial,
                    'audioSeconds': round(len(audio) / float(rate), 2), 'final': finished})
                context.progress(min(95, 10 + int(len(audio) / float(rate))),
                                 currentStep='Listening')
            if finished:
                if partial:
                    committed.append(partial)
                break
            if time.monotonic() - started > max_seconds:
                raise CyToolError('Timeout', 'The live dictation ran longer than %d seconds.'
                                  % int(max_seconds))
            context.cancellation.sleep(LIVE_POLL)
        for path in (stream, done):
            path.unlink(missing_ok=True)
        return {'text': ' '.join(committed), 'model': identifier,
                'audioSeconds': round(len(audio) / float(rate), 2), 'passes': passes,
                'seconds': round(time.monotonic() - started, 2), 'loadSeconds': load}

    # ------------------------------------------------------------------ voices

    def speakers(self, context=None):
        """XTTS-v2 studio voices, read once from its speaker file."""
        if self._speakers is None:
            if not catalog.installed('xtts-v2') or not speech_env.status('tts')['installed']:
                return []
            result = self.workers['tts'].call(context, {
                'command': 'speakers', 'directory': str(catalog.directory('xtts-v2'))}, 120)
            self._speakers = result.get('speakers', [])
        return self._speakers

    def f5_example(self):
        if not speech_env.status('tts')['installed']:
            return ''
        hello = self.workers['tts'].hello
        if hello:
            return hello.get('f5Example', '')
        candidate = speech_env.root('tts') / 'Lib/site-packages/f5_tts/infer/examples/basic/basic_ref_en.wav'
        return str(candidate) if candidate.is_file() else ''

    def voice_list(self, context=None):
        studio = []
        try:
            studio = voices.studio(self.speakers(context))
        except CyToolError:
            pass
        return voices.recorded() + voices.samples(self.f5_example()) + studio

    def resolve_voice(self, context, identifier, family, language):
        listing = self.voice_list(context)
        usable = [voice for voice in listing if family in voice['families']]
        if not identifier:
            # A sensible default: a sample in the language being spoken, then any voice the
            # model can use. XTTS falls back to a studio voice, which needs no recording.
            preferred = [voice for voice in usable if voice['kind'] == 'sample'
                         and voice['language'] == language]
            studio = [voice for voice in usable if voice['kind'] == 'studio']
            ordered = preferred + ([] if family == 'f5' else studio) + usable
            if not ordered:
                raise CyToolError('VoiceRequired', 'F5-TTS clones a voice: record or import one in '
                                                   'the Speech tab first.')
            voice = ordered[0]
        else:
            voice = next((item for item in listing if item['id'] == identifier), None)
            if voice is None:
                raise CyToolError('NotFound', 'Unknown voice: %s' % identifier)
            if family not in voice['families']:
                raise CyToolError('InvalidParameters', 'The voice %s cannot be used by this model: '
                                                       'F5-TTS needs a recorded clip.' % voice['name'])
        if voice['kind'] == 'studio':
            return voice, {'speaker': voice['name']}
        if family == 'f5' and not voice['transcript']:
            context.progress(15, currentStep='Finding the words of the voice clip')
            words = self.transcribe(context, voice['clip'], language=voice['language'])['text']
            if not words:
                raise CyToolError('VoiceRequired', 'No words were heard in the clip of %s.'
                                  % voice['name'])
            voices.remember_transcript(voice['id'], words)
            voice = dict(voice, transcript=words)
        return voice, {'clip': voice['clip'], 'transcript': voice['transcript']}

    # ------------------------------------------------------------------ text to speech

    def speak(self, context, text, *, model='', voice='', language='', speed=None, output=None,
              device='', progressive=False):
        preferences = voices.settings()
        # Markdown is read as words, not as symbols; a reply that is only code says nothing.
        text = speech_text.speakable(text)
        if not text:
            raise CyToolError('InvalidParameters', 'There is nothing to read aloud in this text: '
                                                   'it holds only code, links or formatting.')
        language = voices.language_for(text, language)
        identifier = self.tts_model(model, language)
        info = catalog.entry(identifier)
        engine = speech_env.status('tts')
        wanted = device or preferences['ttsDevice'] or 'auto'
        chosen_device = ('cuda' if engine['cuda'] else 'cpu') if wanted == 'auto' else wanted
        chosen, voice_spec = self.resolve_voice(context, voice or preferences['voice'],
                                                info['family'], language)
        speed = float(speed if speed is not None else preferences['speed'])
        if output is None:
            key = hashlib.sha256(json.dumps([text, identifier, chosen['id'], language, speed],
                                            ensure_ascii=False).encode('utf-8')).hexdigest()[:16]
            output = paths.SPEECH / ('%s.wav' % key)
        output = Path(output)
        if output.is_file():
            return self._spoken(output, identifier, chosen, language, cached=True)
        request = {'command': 'speak', 'model': identifier, 'family': info['family'],
                   'directory': str(catalog.directory(identifier)), 'device': chosen_device,
                   'text': text, 'language': language, 'voice': voice_spec, 'speed': speed,
                   'output': str(output), 'scratch': str(paths.SPEECH / 'clips'),
                   'pieces': speech_text.sentences(text, language,
                                                   first=FIRST_PIECE if progressive else 0)}
        on_event = None
        if progressive:
            # Each sentence is written to data/speech/pieces as soon as it exists and announced
            # by a SpeechPiece event; the window plays it and deletes the file. The cancel file
            # lets a stop end the reading after the current sentence, model still loaded.
            prefix = 'job-%s' % context.job_id
            request.update(pieceDir=str(paths.SPEECH / 'pieces'), piecePrefix=prefix,
                           cancelFile=str(paths.SPEECH / 'pieces' / (prefix + '.cancel')))

            def on_event(event):
                context.emit('SpeechPiece', {key: event[key] for key in
                                             ('index', 'count', 'sampleRate', 'durationSeconds')}
                             | {'audio': event['path']})
        if info['family'] == 'f5':
            vocoder = info.get('baseModel', 'vocos-mel-24khz')
            if not catalog.installed(vocoder):
                raise CyToolError('MissingModel', 'The vocoder F5-TTS needs is not installed. '
                                                  'Reinstall the F5 model.')
            request.update(architecture=info['architecture'], checkpoint=info['checkpoint'],
                           vocoder=str(catalog.directory(vocoder)))
        worker = self.workers['tts']
        worker.reserve_for(identifier, chosen_device, info.get('ramGiB', 6), info.get('vramGiB', 4))
        context.progress(30, currentStep='Speaking with %s' % info['name'])
        try:
            result = worker.call(context, request, on_event=on_event)
        finally:
            if request.get('cancelFile'):
                Path(request['cancelFile']).unlink(missing_ok=True)
        worker.loaded = (identifier, chosen_device)
        return self._spoken(output, identifier, chosen, language, cached=False,
                            seconds=result['seconds'], device=result['device'])

    @staticmethod
    def _spoken(output, identifier, voice, language, cached, seconds=0.0, device=''):
        import wave
        with wave.open(str(output), 'rb') as clip:
            duration = clip.getnframes() / float(clip.getframerate() or 1)
        return {'audio': str(output), 'durationSeconds': round(duration, 2), 'model': identifier,
                'voice': voice['id'], 'voiceName': voice['name'], 'language': language,
                'cached': cached, 'seconds': seconds, 'device': device}
