"""Speech worker: runs inside a private speech environment, never in the window's runtime.

`aichat/speech.py` starts it with the interpreter of `runtime/engines/stt` (speech to text)
or `runtime/engines/tts` (text to speech). It does not import cytools_core and never reaches
the network: the Tool hands it the folders of weights it already downloaded and verified, and
the Hugging Face libraries are switched to offline mode before they are imported.

Protocol: one JSON request per line on stdin, one JSON reply per line on stdout,
`{"id": n, "ok": true, "result": {...}}` or `{"id": n, "ok": false, "error": {...}}`.
The libraries print banners and progress bars; all of that is sent to stderr, which the Tool
writes to data/logs/speech-<engine>.log, so it can never corrupt a reply.

A model stays loaded between requests: one speech-to-text model in the stt worker, one voice
model in the tts worker. Asking for another one replaces it.
"""
import gc
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

# The protocol owns the real stdout; everything printed by a library goes to stderr.
PROTOCOL = os.fdopen(os.dup(1), 'w', encoding='utf-8', buffering=1)
os.dup2(2, 1)
sys.stdout = sys.stderr

for name, value in (('HF_HUB_OFFLINE', '1'), ('TRANSFORMERS_OFFLINE', '1'),
                    ('HF_HUB_DISABLE_TELEMETRY', '1'), ('TOKENIZERS_PARALLELISM', 'false')):
    os.environ.setdefault(name, value)

HERE = Path(__file__).resolve().parent
STT_RATE = 16000


class Failure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def reply(value):
    PROTOCOL.write(json.dumps(value, ensure_ascii=False) + '\n')
    PROTOCOL.flush()


def read_audio(path, rate):
    import numpy as np
    import soundfile as sf
    try:
        audio, source_rate = sf.read(str(path), dtype='float32', always_2d=True)
    except Exception as exc:                                  # noqa: BLE001 - reported
        raise Failure('InvalidInput', 'This audio file cannot be read: %s' % exc) from exc
    audio = audio.mean(axis=1)
    if source_rate != rate:
        import librosa
        audio = librosa.resample(audio, orig_sr=source_rate, target_sr=rate)
    return np.ascontiguousarray(audio, dtype=np.float32)


def pick_device(requested):
    import torch
    requested = (requested or 'auto').lower()
    if requested == 'auto':
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    if requested == 'cuda' and not torch.cuda.is_available():
        raise Failure('MissingGPU', 'This speech environment has no CUDA device. Choose the CPU.')
    return requested


def release_memory():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prepared_clip(path, scratch):
    """A 16-bit PCM mono WAV of a voice clip, made once per source file.

    F5-TTS reads its reference through pydub, which handles a plain PCM WAV by itself but hands
    anything else (a float WAV such as the XTTS-v2 samples, FLAC, MP3) to ffmpeg, which this
    Tool does not ship. Converting here with libsndfile keeps both voice models on one format.
    """
    import soundfile as sf
    source = Path(path)
    if not source.is_file():
        raise Failure('NotFound', 'The voice clip is missing: %s' % source)
    info = sf.info(str(source))
    if info.format == 'WAV' and info.subtype == 'PCM_16' and info.channels == 1:
        return str(source)
    stat = source.stat()
    key = hashlib.sha256(('%s|%d|%d' % (source.resolve(), stat.st_size, stat.st_mtime_ns))
                         .encode('utf-8')).hexdigest()[:20]
    target = Path(scratch) / ('%s.wav' % key)
    if not target.is_file():
        audio, rate = sf.read(str(source), dtype='float32', always_2d=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.%d.tmp.wav' % os.getpid())
        sf.write(str(temporary), audio.mean(axis=1), rate, subtype='PCM_16')
        os.replace(temporary, target)
    return str(target)


# ---------------------------------------------------------------------- Phonon-2 container

def unpack_phonon(directory, archive_name, folder, expected):
    """Unpack the .tar.zst archive once, check the container digest, and return its path."""
    target = directory / folder
    container = target / 'model.fermion'
    if container.is_file():
        return container
    archive = directory / archive_name
    if not archive.is_file():
        raise Failure('MissingModel', 'The Phonon-2 archive is missing: %s' % archive)
    import tarfile
    import zstandard
    staging = directory / ('%s.%d.tmp' % (folder, os.getpid()))
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with archive.open('rb') as raw, zstandard.ZstdDecompressor().stream_reader(raw) as stream:
        with tarfile.open(fileobj=stream, mode='r|') as bundle:
            bundle.extractall(staging, filter='data')
    found = list(staging.rglob('model.fermion'))
    if len(found) != 1:
        shutil.rmtree(staging, ignore_errors=True)
        raise Failure('InvalidModel', 'The Phonon-2 archive does not hold exactly one container.')
    if expected and sha256(found[0]) != expected:
        shutil.rmtree(staging, ignore_errors=True)
        raise Failure('IntegrityFailure', 'The unpacked Phonon-2 container does not match its '
                                          'published digest.')
    os.replace(found[0].parent, target)
    shutil.rmtree(staging, ignore_errors=True)
    return container


def phonon_state_dict(container):
    """Expand the container to an fp32 ParakeetForTDT state dict.

    Follows `reference_transformers.py` of FermionResearch/Phonon-2 (Apache-2.0): every
    record is expanded exactly, the BatchNorm counter stored as fp16 becomes an int64, and the
    pointwise convolutions squeezed to [O, I] get back their kernel dimension.
    """
    import numpy as np
    import torch
    spec = importlib.util.spec_from_file_location('fermion_container',
                                                  HERE / 'vendor' / 'fermion_container.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tensors, _ = module.read_container(str(container))
    state = {}
    for key, value in tensors.items():
        if key.endswith('num_batches_tracked'):
            number = float(np.asarray(value, dtype=np.float32).reshape(-1)[0])
            state[key] = torch.tensor(int(number) if np.isfinite(number) else 0, dtype=torch.int64)
            continue
        array = np.ascontiguousarray(value.astype(np.float32))
        if array.ndim == 2 and re.search(r'\.conv\.pointwise_conv[12]\.weight$', key):
            array = array[:, :, None]
        state[key] = torch.from_numpy(array)
    return state


# ---------------------------------------------------------------------- the worker

class Speech:
    def __init__(self):
        self.stt = None     # (key, model, processor, device)
        self.tts = None     # (key, family, model, device)

    # ------------------------------------------------------------------ basics

    def do_hello(self, request):
        import torch
        report = {'python': sys.version.split()[0], 'torch': torch.__version__,
                  'cuda': torch.cuda.is_available(),
                  'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}
        # f5_tts installs without an __init__ file, so it is located through its import spec.
        found = importlib.util.find_spec('f5_tts')
        if found is not None and found.submodule_search_locations:
            example = (Path(list(found.submodule_search_locations)[0]) / 'infer' / 'examples'
                       / 'basic' / 'basic_ref_en.wav')
            report['f5Example'] = str(example) if example.is_file() else ''
        return report

    def do_status(self, request):
        return {'stt': list(self.stt[0]) if self.stt else None,
                'tts': list(self.tts[0]) if self.tts else None}

    def do_unload(self, request):
        what = request.get('what', 'all')
        if what in ('stt', 'all'):
            self.stt = None
        if what in ('tts', 'all'):
            self.tts = None
        release_memory()
        return self.do_status(request)

    # ------------------------------------------------------------------ speech to text

    def load_stt(self, request):
        device = pick_device(request.get('device'))
        key = (request['model'], device)
        if self.stt and self.stt[0] == key:
            return 0.0
        self.stt = None
        release_memory()
        started = time.perf_counter()
        from transformers import (AutoProcessor, GenerationConfig, ParakeetForTDT,
                                  ParakeetTDTConfig)
        directory = Path(request['directory'])
        if request['format'] == 'parakeet':
            model = ParakeetForTDT.from_pretrained(str(directory))
        elif request['format'] == 'phonon':
            container = unpack_phonon(directory, request['archive'], request.get('unpack') or 'container',
                                      request.get('containerSha256', ''))
            model = ParakeetForTDT(ParakeetTDTConfig.from_pretrained(str(directory)))
            missing, unexpected = model.load_state_dict(phonon_state_dict(container), strict=False)
            if missing or unexpected:
                raise Failure('InvalidModel', 'The Phonon-2 weights do not fit the model: %d '
                                              'missing, %d unexpected.'
                              % (len(missing), len(unexpected)))
            model.generation_config = GenerationConfig.from_pretrained(str(directory))
        else:
            raise Failure('InvalidParameters', 'Unknown speech-to-text format: %s' % request['format'])
        model.eval().to(device)
        processor = AutoProcessor.from_pretrained(str(directory))
        self.stt = (key, model, processor, device)
        return time.perf_counter() - started

    def do_load_stt(self, request):
        """Load a speech-to-text model ahead of the first words, for live dictation."""
        load = self.load_stt(request)
        return {'loadSeconds': round(load, 1), 'device': self.stt[3]}

    def do_transcribe(self, request):
        import torch
        load = self.load_stt(request)
        _, model, processor, device = self.stt
        audio = read_audio(request['audio'], STT_RATE)
        seconds = len(audio) / STT_RATE
        if seconds < 0.25:
            return {'text': '', 'audioSeconds': round(seconds, 2), 'seconds': 0.0,
                    'loadSeconds': round(load, 1), 'device': device}
        started = time.perf_counter()
        inputs = processor([audio], sampling_rate=STT_RATE, return_tensors='pt', padding=True)
        features = inputs['input_features'].to(device=device, dtype=model.dtype)
        mask = inputs.get('attention_mask')
        with torch.inference_mode():
            output = model.generate(input_features=features,
                                    attention_mask=mask.to(device) if mask is not None else None)
        sequences = getattr(output, 'sequences', output)
        text = processor.batch_decode(sequences, skip_special_tokens=True)[0].strip()
        return {'text': text, 'audioSeconds': round(seconds, 2),
                'seconds': round(time.perf_counter() - started, 2),
                'loadSeconds': round(load, 1), 'device': device}

    # ------------------------------------------------------------------ text to speech

    def load_tts(self, request):
        device = pick_device(request.get('device'))
        key = (request['model'], device)
        if self.tts and self.tts[0] == key:
            return 0.0
        self.tts = None
        release_memory()
        started = time.perf_counter()
        directory = Path(request['directory'])
        family = request['family']
        if family == 'xtts':
            # The Tool installs XTTS-v2 only after its licence was accepted in the Tool;
            # this tells the library not to ask again on a console nobody can see.
            os.environ['COQUI_TOS_AGREED'] = '1'
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import Xtts
            config = XttsConfig()
            config.load_json(str(directory / 'config.json'))
            model = Xtts.init_from_config(config)
            model.load_checkpoint(config, checkpoint_dir=str(directory),
                                  checkpoint_path=str(directory / 'model.pth'),
                                  vocab_path=str(directory / 'vocab.json'),
                                  speaker_file_path=str(directory / 'speakers_xtts.pth'),
                                  eval=True, use_deepspeed=False)
            model.to(device)
        elif family == 'f5':
            from f5_tts.api import F5TTS
            model = F5TTS(model=request['architecture'],
                          ckpt_file=str(directory / request['checkpoint']),
                          vocab_file=str(directory / 'vocab.txt'),
                          vocoder_local_path=request['vocoder'], device=device)
        else:
            raise Failure('InvalidParameters', 'Unknown voice model family: %s' % family)
        self.tts = (key, family, model, device)
        return time.perf_counter() - started

    def do_speakers(self, request):
        """Names of the studio voices shipped with XTTS-v2, without loading the model."""
        import torch
        table = torch.load(str(Path(request['directory']) / 'speakers_xtts.pth'),
                           map_location='cpu', weights_only=True)
        return {'speakers': sorted(table)}

    def do_speak(self, request):
        import numpy as np
        import soundfile as sf
        import torch
        load = self.load_tts(request)
        _, family, model, device = self.tts
        text = (request.get('text') or '').strip()
        if not text:
            raise Failure('InvalidParameters', 'There is no text to read.')
        voice = dict(request.get('voice') or {})
        if voice.get('clip'):
            voice['clip'] = prepared_clip(voice['clip'], request.get('scratch')
                                          or Path(request['output']).parent / 'clips')
        speed = float(request.get('speed') or 1.0)
        started = time.perf_counter()
        # The Tool cuts the text into pieces below XTTS's length limit (its own splitter,
        # enable_text_splitting, imports spaCy with its Japanese and Chinese extras). Each piece
        # is synthesised in turn; with `pieceDir`, each one is written and announced as soon as
        # it exists, so the window starts playing the first sentence while the rest is made.
        pieces = request.get('pieces') or [text]
        piece_dir = request.get('pieceDir', '')
        cancel_file = request.get('cancelFile', '')
        try:
            if family == 'xtts':
                language = request.get('language') or 'en'
                language = 'zh-cn' if language == 'zh' else language
                if voice.get('speaker'):
                    known = model.speaker_manager.speakers
                    if voice['speaker'] not in known:
                        raise Failure('NotFound', 'XTTS-v2 has no built-in voice named %s.'
                                      % voice['speaker'])
                    latents = known[voice['speaker']]
                    conditioning, embedding = latents['gpt_cond_latent'], latents['speaker_embedding']
                elif voice.get('clip'):
                    conditioning, embedding = model.get_conditioning_latents(audio_path=[voice['clip']])
                else:
                    raise Failure('VoiceRequired', 'Choose a voice for XTTS-v2.')
                rate = int(model.config.audio.output_sample_rate)

                def synthesise(piece):
                    with torch.inference_mode():
                        output = model.inference(piece, language, conditioning, embedding,
                                                 speed=speed, enable_text_splitting=False)
                    return np.asarray(output['wav'], dtype=np.float32), rate
            else:
                if not voice.get('clip') or not voice.get('transcript'):
                    raise Failure('VoiceRequired', 'F5-TTS clones a voice: choose one that has a '
                                                   'clip and the words spoken in it.')

                def synthesise(piece):
                    sound, sound_rate, _ = model.infer(
                        ref_file=voice['clip'], ref_text=voice['transcript'], gen_text=piece,
                        speed=speed, nfe_step=int(request.get('steps') or 32),
                        show_info=lambda *args, **kwargs: None)
                    return np.asarray(sound, dtype=np.float32), int(sound_rate)
            parts = []
            rate = 24000
            for index, piece in enumerate(pieces):
                if cancel_file and os.path.exists(cancel_file):
                    raise Failure('Cancelled', 'Reading stopped.')
                sound, rate = synthesise(piece)
                if piece_dir:
                    piece_path = Path(piece_dir) / ('%s-%03d.wav' % (request.get('piecePrefix', 'piece'),
                                                                    index))
                    piece_path.parent.mkdir(parents=True, exist_ok=True)
                    sf.write(str(piece_path), np.clip(sound, -1.0, 1.0), rate, subtype='PCM_16')
                    reply({'id': request.get('id'), 'event': 'piece', 'index': index,
                           'count': len(pieces), 'path': str(piece_path), 'sampleRate': rate,
                           'durationSeconds': round(len(sound) / rate, 2)})
                parts += [sound, np.zeros(int(0.12 * rate), dtype=np.float32)]
            wave = np.concatenate(parts[:-1]) if parts else np.zeros(0, dtype=np.float32)
        except torch.cuda.OutOfMemoryError as exc:
            release_memory()
            raise Failure('InsufficientResources', 'The GPU ran out of memory while speaking. '
                                                   'Unload the chat model or use the CPU.') from exc
        output_path = Path(request['output'])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(output_path.name + '.%d.tmp.wav' % os.getpid())
        sf.write(str(temporary), np.clip(wave, -1.0, 1.0), rate, subtype='PCM_16')
        os.replace(temporary, output_path)
        return {'output': str(output_path), 'sampleRate': rate,
                'durationSeconds': round(len(wave) / rate, 2),
                'seconds': round(time.perf_counter() - started, 2),
                'loadSeconds': round(load, 1), 'device': device}


def main():
    speech = Speech()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        identifier = None
        try:
            request = json.loads(line)
            identifier = request.get('id')
            command = request.get('command', '')
            if command == 'quit':
                reply({'id': identifier, 'ok': True, 'result': {}})
                return 0
            handler = getattr(speech, 'do_' + command, None)
            if handler is None:
                raise Failure('InvalidParameters', 'Unknown command: %s' % command)
            reply({'id': identifier, 'ok': True, 'result': handler(request)})
        except Failure as failure:
            reply({'id': identifier, 'ok': False,
                   'error': {'code': failure.code, 'message': failure.message}})
        except Exception as exc:                              # noqa: BLE001 - reported
            traceback.print_exc()
            reply({'id': identifier, 'ok': False,
                   'error': {'code': 'WorkerError', 'message': '%s: %s' % (type(exc).__name__, exc)}})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
