"""Microphone and loudspeaker for the window.

The window records and plays; the operations only ever receive or return a WAV file, exactly
as they do from the CLI or MCP. A recording is written to data/inputs/dictation and is never
deleted by the Tool.

Importing this module opens no audio device. Nothing is recorded until `start()` is called
from a button the user pressed, and a recording stops at its limit at the latest.
"""
import threading
import time
import wave
from pathlib import Path

import numpy as np

RATE = 16000                     # what the speech-to-text models work at


def input_devices():
    """[(index, name)] of the devices that can record, the default one first."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default = sd.default.device[0]
        if default is None or int(default) < 0:
            default = sd.query_hostapis(0).get('default_input_device')
        default = int(default)
    except Exception:                                  # noqa: BLE001 - no audio stack
        return []
    # Windows lists each input once per audio API (MME, DirectSound, WASAPI...): keep the API
    # of the default input, so a microphone appears once.
    host = devices[default].get('hostapi') if 0 <= default < len(devices) else None
    found = [(index, device['name']) for index, device in enumerate(devices)
             if device.get('max_input_channels', 0) > 0
             and (host is None or device.get('hostapi') == host)]
    found.sort(key=lambda item: item[0] != default)
    return found


def write_wav(path, audio, rate):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype('<i2')
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(int(rate))
        output.writeframes(pcm.tobytes())
    return path


def read_wav(path):
    """(float32 samples, rate) of a 16-bit PCM WAV, the format the speech engine writes."""
    with wave.open(str(path), 'rb') as source:
        rate = source.getframerate()
        channels = source.getnchannels()
        width = source.getsampwidth()
        frames = source.readframes(source.getnframes())
    if width != 2:
        raise ValueError('Only 16-bit WAV files can be played here.')
    audio = np.frombuffer(frames, dtype='<i2').astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


class Recorder:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.stream = None
        self.blocks = []
        self.lock = threading.Lock()
        self.level = 0.0
        self.limit = 0.0
        self.rate = RATE
        self.purpose = ''
        self.error = ''
        # Live dictation: blocks are also appended to this raw 16-bit PCM file as they arrive,
        # for the transcribe_live job to follow; `<file>.done` tells it the user stopped.
        self.live = None
        self.written = 0

    def flush_live(self):
        """Append the blocks recorded since the last call to the live file (draw loop only)."""
        if self.live is None:
            return
        with self.lock:
            fresh = self.blocks[self.written:]
            self.written = len(self.blocks)
        if fresh:
            pcm = (np.clip(np.concatenate(fresh), -1.0, 1.0) * 32767.0).astype('<i2')
            with self.live.open('ab') as output:
                output.write(pcm.tobytes())

    @property
    def recording(self):
        return self.stream is not None

    @property
    def seconds(self):
        with self.lock:
            return sum(len(block) for block in self.blocks) / float(self.rate)

    def start(self, purpose, limit=120.0, device=None, live=None):
        """Open the microphone. Returns False, with `error` set, when it cannot be opened."""
        import sounddevice as sd
        self.stop(keep=False)
        self.blocks, self.level, self.error = [], 0.0, ''
        self.purpose, self.limit = purpose, float(limit)
        self.written = 0
        self.live = Path(live) if live else None
        if self.live is not None:
            self.live.parent.mkdir(parents=True, exist_ok=True)
            self.live.write_bytes(b'')

        def callback(data, frames, when, status):
            mono = data[:, 0].copy() if data.ndim > 1 else data.copy()
            with self.lock:
                self.blocks.append(mono)
                self.level = float(np.sqrt(np.mean(np.square(mono)))) if len(mono) else 0.0

        self.rate = RATE
        try:
            try:
                self.stream = sd.InputStream(samplerate=self.rate, channels=1, dtype='float32',
                                             device=device, callback=callback)
            except Exception:                          # noqa: BLE001 - the card's own rate
                self.rate = int(sd.query_devices(device, 'input')['default_samplerate'])
                self.stream = sd.InputStream(samplerate=self.rate, channels=1, dtype='float32',
                                             device=device, callback=callback)
            self.stream.start()
        except Exception as exc:                       # noqa: BLE001 - shown to the user
            self.stream = None
            self.error = 'The microphone could not be opened: %s' % exc
            if self.live is not None:
                self.live.unlink(missing_ok=True)
                self.live = None
            return False
        return True

    def reached_limit(self):
        return self.recording and self.seconds >= self.limit

    def stop(self, keep=True):
        """Close the microphone. With keep, write the WAV and return its path ('' if empty)."""
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            finally:
                self.stream = None
        if self.live is not None:
            # Even an empty or discarded recording ends the live job that follows it.
            self.flush_live()
            self.live.with_name(self.live.name + '.done').write_bytes(b'')
            self.live = None
        with self.lock:
            audio = np.concatenate(self.blocks) if self.blocks else np.zeros(0, np.float32)
            self.blocks = []
            self.level = 0.0
        if not keep or len(audio) < self.rate // 4:    # a click, not a recording
            return ''
        name = '%s-%s.wav' % (self.purpose or 'recording', time.strftime('%Y%m%d-%H%M%S'))
        return str(write_wav(self.folder / name, audio, self.rate))


class Player:
    """One output stream fed from a queue, so sentences that arrive one by one play end to end.

    `play` replaces whatever is playing with a whole file; `append` adds a piece to the clip
    being played under the same key, or starts a new one. The stream callback runs on the audio
    thread and only takes samples from the queue; it never reads a file.
    """

    def __init__(self):
        self.current = ''
        self.error = ''
        self.stream = None
        self.rate = 0
        self.queue = []
        self.lock = threading.Lock()

    @property
    def playing(self):
        with self.lock:
            return bool(self.current) and any(len(block) for block in self.queue)

    def _callback(self, output, frames, when, status):
        filled = 0
        with self.lock:
            while filled < frames and self.queue:
                block = self.queue[0]
                take = min(frames - filled, len(block))
                output[filled:filled + take, 0] = block[:take]
                filled += take
                if take == len(block):
                    self.queue.pop(0)
                else:
                    self.queue[0] = block[take:]
        output[filled:, 0] = 0.0

    def _open(self, rate):
        import sounddevice as sd
        if self.stream is not None and self.rate == rate:
            return
        self._close()
        self.stream = sd.OutputStream(samplerate=rate, channels=1, dtype='float32',
                                      callback=self._callback)
        self.stream.start()
        self.rate = rate

    def _close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:                          # noqa: BLE001 - already gone
                pass
            self.stream = None
            self.rate = 0

    def append(self, audio, rate, key):
        """Queue samples after what is already playing under `key`; another key starts over."""
        try:
            if key != self.current:
                self.stop()
            with self.lock:
                if self.rate and self.rate != rate and self.queue:
                    return True              # a piece at another rate never happens mid-reading
            self._open(rate)
            with self.lock:
                self.queue.append(np.ascontiguousarray(audio, dtype=np.float32))
            self.current = key
            self.error = ''
            return True
        except Exception as exc:                       # noqa: BLE001 - shown to the user
            self.error = 'The audio could not be played: %s' % exc
            self.stop()
            return False

    def play(self, path, key=''):
        try:
            audio, rate = read_wav(path)
        except Exception as exc:                       # noqa: BLE001 - shown to the user
            self.error = 'The audio could not be played: %s' % exc
            return False
        self.stop()
        return self.append(audio, rate, key or str(path))

    def stop(self):
        with self.lock:
            self.queue = []
        self.current = ''

    def close(self):
        self.stop()
        self._close()
