"""Read the metadata header of a GGUF file without loading a single tensor.

Registering a local model or a LoRA adapter has to answer two questions before anything is
loaded into memory: is this really a GGUF, and is it a base model or an adapter? Both are
answered by the key/value block at the start of the file, so this parser reads only that
block. It allocates nothing tensor sized, executes nothing from the file and stops as soon
as the metadata ends, which is what makes it safe to run on a file the user just picked.

Format reference: the GGUF specification in the ggml repository
(https://github.com/ggml-org/ggml/blob/master/docs/gguf.md).
"""
import struct
from pathlib import Path

MAGIC = b'GGUF'
MAX_KEYS = 16384
MAX_STRING = 1 << 20
MAX_ARRAY = 1 << 24

# Type ids of the GGUF metadata value union.
UINT8, INT8, UINT16, INT16, UINT32, INT32, FLOAT32, BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64 = range(13)
FIXED = {UINT8: ('<B', 1), INT8: ('<b', 1), UINT16: ('<H', 2), INT16: ('<h', 2),
         UINT32: ('<I', 4), INT32: ('<i', 4), FLOAT32: ('<f', 4), BOOL: ('<?', 1),
         UINT64: ('<Q', 8), INT64: ('<q', 8), FLOAT64: ('<d', 8)}


class GGUFError(ValueError):
    pass


class _Reader:
    def __init__(self, stream):
        self.stream = stream

    def take(self, size):
        data = self.stream.read(size)
        if len(data) != size:
            raise GGUFError('Truncated GGUF header')
        return data

    def scalar(self, kind):
        fmt, size = FIXED[kind]
        return struct.unpack(fmt, self.take(size))[0]

    def string(self):
        length = struct.unpack('<Q', self.take(8))[0]
        if length > MAX_STRING:
            raise GGUFError('Unreasonable string length in GGUF header')
        return self.take(length).decode('utf-8', 'replace')

    def value(self, kind, depth=0):
        if kind in FIXED:
            return self.scalar(kind)
        if kind == STRING:
            return self.string()
        if kind == ARRAY:
            if depth:
                raise GGUFError('Nested arrays are not read')
            item_kind = struct.unpack('<I', self.take(4))[0]
            count = struct.unpack('<Q', self.take(8))[0]
            if count > MAX_ARRAY:
                raise GGUFError('Unreasonable array length in GGUF header')
            if item_kind in FIXED:
                _, size = FIXED[item_kind]
                # Arrays hold vocabularies and token scores; skip rather than materialise.
                self.stream.seek(count * size, 1)
                return ['<%d values>' % count]
            if item_kind == STRING:
                # A tokenizer vocabulary is an array of 100k+ strings. Each one is skipped by
                # its length prefix instead of being decoded: the position must stay exact,
                # so stopping early here would desynchronise every later key.
                if count > MAX_ARRAY:
                    raise GGUFError('Unreasonable array length in GGUF header')
                for _ in range(count):
                    length = struct.unpack('<Q', self.take(8))[0]
                    if length > MAX_STRING:
                        raise GGUFError('Unreasonable string length in GGUF header')
                    self.stream.seek(length, 1)
                return ['<%d strings>' % count]
            raise GGUFError('Unsupported array element type in GGUF header')
        raise GGUFError('Unsupported GGUF metadata type: %d' % kind)


def metadata(path, keys=None):
    """Return the metadata key/value pairs, optionally limited to the keys asked for."""
    path = Path(path)
    with path.open('rb') as stream:
        if stream.read(4) != MAGIC:
            raise GGUFError('Not a GGUF file (bad magic)')
        reader = _Reader(stream)
        version = reader.scalar(UINT32)
        if version not in (2, 3):
            raise GGUFError('Unsupported GGUF version: %d' % version)
        reader.scalar(UINT64)  # tensor count, not needed here
        count = reader.scalar(UINT64)
        if count > MAX_KEYS:
            raise GGUFError('Unreasonable metadata key count in GGUF header')
        values = {'gguf.version': version}
        for _ in range(count):
            key = reader.string()
            kind = reader.scalar(UINT32)
            value = reader.value(kind)
            if keys is None or key in keys:
                values[key] = value
        return values


def adapter_kind(path):
    """'lora' for a llama.cpp LoRA adapter, '' for a base model, raising on a bad file."""
    values = metadata(path, keys={'adapter.type', 'general.architecture', 'general.type'})
    return str(values.get('adapter.type') or '')


def describe(path):
    values = metadata(path, keys={'adapter.type', 'general.architecture', 'general.name',
                                  'general.size_label', 'general.file_type', 'adapter.lora.alpha'})
    return {'architecture': str(values.get('general.architecture') or ''),
            'name': str(values.get('general.name') or ''),
            'sizeLabel': str(values.get('general.size_label') or ''),
            'adapterType': str(values.get('adapter.type') or ''),
            'loraAlpha': values.get('adapter.lora.alpha'),
            'ggufVersion': values.get('gguf.version')}
