"""Turning a chat reply into something a voice model can read.

Replies are Markdown. Read as is, a voice spells out backticks, asterisks and URLs, and reads a
code block character by character. `speakable` keeps the words a person would say and drops
the rest; `sentences` cuts the result into pieces short enough for XTTS-v2, whose quality
collapses past a per-language length (273 characters in French) and whose own splitter needs
spaCy with its Japanese and Chinese extras.
"""
import re

# Below XTTS-v2's own limits (TTS/tts/layers/xtts/tokenizer.py, char_limits), with a margin:
# a piece close to the limit already sounds rushed.
LIMITS = {'zh': 70, 'zh-cn': 70, 'ja': 60, 'ko': 85, 'hi': 130, 'ar': 150, 'cs': 170, 'ru': 170,
          'pt': 190, 'it': 195, 'pl': 200, 'tr': 200, 'hu': 200, 'es': 220, 'en': 230, 'de': 230,
          'nl': 230, 'fr': 240}
DEFAULT_LIMIT = 200

_FENCE = re.compile(r'```.*?(```|$)', re.S)
_INLINE = re.compile(r'`([^`\n]+)`')
_IMAGE = re.compile(r'!\[([^\]]*)\]\([^)]*\)')
_LINK = re.compile(r'\[([^\]]+)\]\([^)]*\)')
_URL = re.compile(r'(?:https?://|www\.)\S+')
_TAG = re.compile(r'</?[A-Za-z][^>]*>')
_EMPHASIS = re.compile(r'(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1')
_RULE = re.compile(r'^\s*([-*_]\s*){3,}$')
_TABLE_RULE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$')
_BULLET = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+')
_HEADING = re.compile(r'^\s*#{1,6}\s+')
_QUOTE = re.compile(r'^\s*>+\s?')
_END = re.compile(r'[.!?…:;]["»)\]]*$')


def _inline_code(match):
    # File names and identifiers: read the words, not the punctuation between them.
    return re.sub(r'[_/\\]+', ' ', match.group(1))


def speakable(text):
    """The words of a Markdown reply, one sentence per line of the original."""
    text = _FENCE.sub('\n', text or '')
    text = _IMAGE.sub(r'\1', text)
    text = _LINK.sub(r'\1', text)
    text = _URL.sub('', text)
    text = _TAG.sub('', text)
    text = _INLINE.sub(_inline_code, text)
    lines = []
    for line in text.splitlines():
        if _RULE.match(line) or _TABLE_RULE.match(line):
            continue
        line = _QUOTE.sub('', line)
        line = _HEADING.sub('', line)
        line = _BULLET.sub('', line)
        line = re.sub(r'\s*\|\s*', ', ', line).strip(' ,')
        previous = None
        while previous != line:
            previous, line = line, _EMPHASIS.sub(r'\2', line)
        line = re.sub(r'\s+', ' ', line).strip()
        if not line:
            continue
        # A heading or a list item ends without punctuation; without one, the voice runs it
        # into the next line as if it were the same sentence.
        if not _END.search(line):
            line += '.'
        lines.append(line)
    return ' '.join(lines)


def sentences(text, language='', first=0):
    """Pieces of at most the language's limit, cut at sentence ends, then commas, then spaces.

    With `first`, the opening piece is held to that many characters, so a voice that plays
    pieces as they are made starts speaking sooner; the following pieces are full length.
    """
    limit = LIMITS.get((language or '').lower(), DEFAULT_LIMIT)
    if first:
        opening = sentences(text, language)
        if opening and len(opening[0]) > first:
            short = _cut(opening[0], min(first, limit))
            rest = ' '.join([opening[0][len(short):].strip()] + opening[1:]).strip()
            return [short] + (sentences(rest, language) if rest else [])
        return opening
    pieces = []
    for sentence in re.split(r'(?<=[.!?…])\s+', text.strip()):
        if not sentence:
            continue
        while len(sentence) > limit:
            window = sentence[:limit]
            cut = max(window.rfind(', '), window.rfind('; '), window.rfind(': '))
            if cut < limit // 3:
                cut = window.rfind(' ')
            if cut < limit // 3:
                cut = limit - 1        # no space at all, as in Japanese: a hard cut
            pieces.append(sentence[:cut + 1].strip())
            sentence = sentence[cut + 1:].strip()
        if sentence:
            pieces.append(sentence)
    # Short sentences are read together: one call per sentence would add a pause after each.
    merged = []
    for piece in pieces:
        if merged and len(merged[-1]) + 1 + len(piece) <= limit:
            merged[-1] += ' ' + piece
        else:
            merged.append(piece)
    return merged


def _cut(text, limit):
    """The first stretch of `text` up to `limit` characters, ended at a sentence, comma or space."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    for marks in (('. ', '! ', '? ', '… '), (', ', '; ', ': '), (' ',)):
        cut = max(window.rfind(mark) for mark in marks)
        if cut >= limit // 3:
            return text[:cut + 1].strip()
    return window
