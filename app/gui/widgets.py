"""Small widgets and a background helper shared by the panels.

Detecting a provider or asking it for its models means spawning a process or making a
network call. Doing that inside a frame would freeze the window, so anything of that kind
goes through `Async`: the frame starts it, keeps drawing, and picks up the result on a later
frame. The window therefore never blocks on a provider that is slow or unreachable.
"""
import threading

from ui_common import imgui

MISSING = object()


class Async:
    """One background call whose result is read from the draw loop."""

    def __init__(self):
        self.thread = None
        self.value = MISSING
        self.error = ''
        self.label = ''
        self.lock = threading.Lock()

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    @property
    def ready(self):
        return self.value is not MISSING

    def start(self, function, label=''):
        if self.running:
            return False
        self.label = label
        self.error = ''
        self.value = MISSING

        def run():
            try:
                result = function()
                with self.lock:
                    self.value = result
            except Exception as exc:
                with self.lock:
                    self.error = str(exc) or repr(exc)
                    self.value = MISSING

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return True

    def take(self, default=None):
        with self.lock:
            if self.value is MISSING:
                return default
            return self.value

    def join(self, timeout=3.0):
        if self.thread is not None:
            self.thread.join(timeout=timeout)


def combo(label, values, current, formatter=str, width=0.0):
    """A combo over arbitrary values. Returns (changed, value) keeping the value, not an index."""
    items = list(values)
    if not items:
        imgui.begin_disabled(True)
        imgui.combo(label, 0, ['—'])
        imgui.end_disabled()
        return False, current
    index = items.index(current) if current in items else 0
    if width:
        imgui.set_next_item_width(width)
    changed, chosen = imgui.combo(label, index, [formatter(item) for item in items])
    return changed, items[chosen]


def copy_button(label, text, identity=''):
    if imgui.small_button(label + '###copy-' + (identity or label)):
        imgui.set_clipboard_text(text)
        return True
    return False


def wrapped(text, width=0.0):
    imgui.push_text_wrap_pos(width)
    imgui.text_unformatted(text)
    imgui.pop_text_wrap_pos()


def bytes_label(value):
    value = float(value or 0)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return '%.1f %s' % (value, unit) if unit != 'B' else '%d B' % value
        value /= 1024
    return str(value)


def status_dot(available, unknown=False):
    """A colour is a hint, never the only signal: the status word is always printed next.

    The marker stays plain ASCII. The font the window ships with has no geometric shapes
    block, so a round bullet has no glyph and renders as an empty box.
    """
    colour = (0.55, 0.55, 0.55, 1.0) if unknown else \
        ((0.36, 0.78, 0.45, 1.0) if available else (0.85, 0.45, 0.4, 1.0))
    imgui.text_colored(colour, '[?]' if unknown else ('[+]' if available else '[-]'))
    imgui.same_line()
