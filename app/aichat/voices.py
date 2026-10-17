"""Voices, and the speech preferences of this installation.

A voice is what a text-to-speech model imitates. There are three kinds:

* the studio voices shipped inside XTTS-v2 (`xtts:<name>`): no recording needed, XTTS only;
* sample clips that come with installed models (`sample:<id>`): the two XTTS-v2 samples and
  the F5-TTS example, whose words are known or transcribed once;
* voices you record or import (`voice-<hex>`), kept in data/voices/<id>/ with the clip and
  the words spoken in it. Deleting one moves it to data/voices/deleted/, like a conversation.

F5-TTS always clones: it needs a clip and its exact words. XTTS-v2 takes either a studio voice
or a clip. Words are filled in by speech to text when the user does not type them.
"""
import re
import shutil
import time
import uuid
from pathlib import Path

from cytools_core import CyToolError

from . import catalog, paths
from .paths import read_json, write_json

AUDIO_SUFFIXES = ('.wav', '.flac', '.ogg', '.mp3')

# The F5-TTS example clip says these words (f5_tts/infer/examples/basic/basic.toml).
F5_EXAMPLE_TEXT = 'Some call me nature, others call me mother nature.'

DEFAULT_SETTINGS = {
    'sttModel': '',            # empty: the best installed model for the language
    'ttsModel': '',            # empty: the first installed voice model
    'voice': '',               # empty: a sensible default for the chosen model
    'language': 'auto',        # 'auto' guesses French or English from the text
    'speed': 1.0,
    'ttsDevice': 'auto',       # auto: CUDA when the voice environment has it
    'autoRead': False,         # read every new reply aloud in the window
    'liveDictation': True,     # show the words in the message box while speaking
}


# ---------------------------------------------------------------------- settings

def settings_file():
    return paths.SETTINGS / 'speech.json'


def settings():
    stored = read_json(settings_file(), {})
    return {**DEFAULT_SETTINGS, **{key: value for key, value in stored.items()
                                   if key in DEFAULT_SETTINGS}}


def configure(**changes):
    current = settings()
    for key, value in changes.items():
        if key in DEFAULT_SETTINGS and value is not None:
            current[key] = value
    current['speed'] = min(2.0, max(0.5, float(current['speed'] or 1.0)))
    if current['language'] not in ('auto', '') and not re.fullmatch(r'[a-z]{2}(-[a-z]{2})?',
                                                                     current['language']):
        raise CyToolError('InvalidParameters', 'A language is a code such as fr or en.')
    write_json(settings_file(), current)
    return current


# ---------------------------------------------------------------------- language

FRENCH_WORDS = set('le la les un une des du de et est sont pas que qui je tu il elle nous vous '
                   'ils elles ce cette pour dans sur avec mais ou donc car ne au aux mon ma mes '
                   'ton ta tes son sa ses leur oui non bien tres tout plus'.split())
ENGLISH_WORDS = set('the a an and is are not that which who i you he she we they this these for '
                    'in on with but or so because no to of my your his her their yes very all '
                    'more it be was were have has'.split())


def guess_language(text, fallback='en'):
    """French or English, from accents and common words. Anything else uses the fallback."""
    lowered = (text or '').lower()
    words = re.findall(r"[a-zà-ÿœæ']+", lowered)
    french = sum(word in FRENCH_WORDS for word in words) + 2 * len(re.findall(r'[éèêàçùûôîœ]', lowered))
    english = sum(word in ENGLISH_WORDS for word in words)
    if french == english == 0:
        return fallback
    return 'fr' if french > english else 'en'


def language_for(text, requested=''):
    chosen = (requested or settings()['language'] or 'auto').lower()
    return guess_language(text) if chosen == 'auto' else chosen


# ---------------------------------------------------------------------- the library

def _voice_dir(identifier):
    if not re.fullmatch(r'voice-[0-9a-f]{12}', identifier or ''):
        raise CyToolError('NotFound', 'Unknown voice: %s' % identifier)
    return paths.VOICES / identifier


def _clip(directory):
    found = sorted(path for path in Path(directory).glob('reference.*')
                   if path.suffix.lower() in AUDIO_SUFFIXES)
    return found[0] if found else None


def recorded():
    voices = []
    if not paths.VOICES.is_dir():
        return voices
    for directory in sorted(paths.VOICES.iterdir()):
        document = read_json(directory / 'voice.json') if directory.is_dir() else {}
        clip = _clip(directory) if document else None
        if not document or clip is None:
            continue
        voices.append({'id': directory.name, 'name': document.get('name', directory.name),
                       'kind': 'recorded', 'language': document.get('language', ''),
                       'transcript': document.get('transcript', ''), 'clip': str(clip),
                       'families': ['xtts', 'f5'], 'created': document.get('created', '')})
    return voices


def samples(f5_example=''):
    found = []
    if catalog.installed('xtts-v2'):
        folder = catalog.directory('xtts-v2')
        cache = read_json(paths.VOICES / 'samples.json', {})
        for language in ('fr', 'en'):
            identifier = 'sample:xtts-%s' % language
            found.append({'id': identifier, 'name': 'XTTS-v2 sample (%s)' % language,
                          'kind': 'sample', 'language': language,
                          'transcript': cache.get(identifier, ''),
                          'clip': str(folder / ('%s_sample.wav' % language)),
                          'families': ['xtts', 'f5'], 'created': ''})
    if f5_example and Path(f5_example).is_file():
        found.append({'id': 'sample:f5-en', 'name': 'F5-TTS example (en)', 'kind': 'sample',
                      'language': 'en', 'transcript': F5_EXAMPLE_TEXT, 'clip': f5_example,
                      'families': ['xtts', 'f5'], 'created': ''})
    return found


def studio(speakers):
    return [{'id': 'xtts:' + name, 'name': name, 'kind': 'studio', 'language': '',
             'transcript': '', 'clip': '', 'families': ['xtts'], 'created': ''}
            for name in speakers]


def remember_transcript(identifier, transcript):
    """Keep the words found for a voice so they are transcribed only once."""
    if identifier.startswith('sample:'):
        cache = read_json(paths.VOICES / 'samples.json', {})
        cache[identifier] = transcript
        write_json(paths.VOICES / 'samples.json', cache)
        return
    directory = _voice_dir(identifier)
    document = read_json(directory / 'voice.json')
    document['transcript'] = transcript
    write_json(directory / 'voice.json', document)


def add(source, name, language='', transcript=''):
    source = Path(source)
    if source.suffix.lower() not in AUDIO_SUFFIXES:
        raise CyToolError('InvalidInput', 'A voice clip is a WAV, FLAC, OGG or MP3 file.')
    identifier = 'voice-' + uuid.uuid4().hex[:12]
    directory = paths.VOICES / identifier
    directory.mkdir(parents=True)
    shutil.copy2(source, directory / ('reference' + source.suffix.lower()))
    write_json(directory / 'voice.json',
               {'name': (name or '').strip() or identifier, 'language': language or '',
                'transcript': (transcript or '').strip(),
                'created': time.strftime('%Y-%m-%dT%H:%M:%S'), 'source': source.name})
    return identifier


def delete(identifier):
    directory = _voice_dir(identifier)
    if not directory.is_dir():
        raise CyToolError('NotFound', 'Unknown voice: %s' % identifier)
    destination = paths.VOICES / 'deleted' / ('%s-%d' % (identifier, time.time_ns()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(directory), str(destination))
    return {'voice': identifier, 'deleted': True, 'keptIn': str(destination)}
