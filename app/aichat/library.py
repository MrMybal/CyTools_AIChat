"""Bridge between the download catalogue and the local model library.

The Tool has two ways of getting local weights: downloading a pinned catalogue entry, or
pointing at a file already on the machine. They would otherwise live in two identifier
spaces, and a turn would have to say which one it meant. Instead, a catalogue entry is
registered in the model library as soon as it is installed, so every model and every
adapter is referred to the same way — by its library id — whichever way it arrived.

Registration records a reference, never a copy: the file stays where the download put it,
under `data/models`, and nothing about it is duplicated into a settings file.
"""
from cytools_core import CyToolError

from . import catalog

FORMATS = {'model': 'gguf-model', 'lora': 'gguf-lora'}


def _model_options():
    import model_options
    return model_options


def entries():
    try:
        return _model_options().catalog()['models']
    except Exception:
        return []


def find_by_path(path):
    target = str(path)
    return next((item for item in entries() if item['path'] == target), None)


def register_catalogue_entry(identifier):
    """Register a freshly installed catalogue entry, or return the existing reference."""
    info = catalog.entry(identifier)
    path = catalog.file_path(identifier)
    existing = find_by_path(path)
    if existing is not None:
        return existing
    if not catalog.installed(identifier):
        raise CyToolError('MissingModel', 'Install %s before registering it.' % identifier)
    try:
        return _model_options().add_asset(
            info['name'], str(path), FORMATS[info['kind']], '',
            info.get('license', 'Not declared'), info.get('page', ''))
    except (ValueError, OSError) as exc:
        raise CyToolError('InvalidModel', str(exc)) from exc


def unregister_path(path):
    """Drop a library reference whose file no longer exists, after an uninstall."""
    module = _model_options()
    library = module.catalog()
    before = len(library['models'])
    library['models'] = [item for item in library['models'] if item['path'] != str(path)]
    if len(library['models']) != before:
        module.save_catalog(library)
    return before - len(library['models'])


def adapters():
    """Every LoRA the Tool can apply, with the identifier a turn should use."""
    rows = []
    for item in entries():
        if item.get('kind') != 'lora':
            continue
        rows.append({'id': item['id'], 'name': item['name'], 'path': item['path'],
                     'format': item['format'], 'license': item.get('license', ''),
                     'source': item.get('source', '')})
    return rows


def describe(path):
    """What the GGUF header says about a file, for the interface to show before loading it."""
    from .gguf_header import describe as read_header
    try:
        return read_header(path)
    except Exception as exc:
        return {'error': str(exc)}
