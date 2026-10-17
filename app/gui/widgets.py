"""Small widgets and a background helper shared by the panels.

Detecting a provider or asking it for its models means spawning a process or making a
network call. Doing that inside a frame would freeze the window, so anything of that kind
goes through `Async`: the frame starts it, keeps drawing, and picks up the result on a later
frame. The window therefore never blocks on a provider that is slow or unreachable.
"""
import threading
from contextlib import contextmanager

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


def selectable_text(identity, text):
    """Wrapped text the mouse can select and Ctrl+C copies: a frameless read-only text box.

    Plain text in Dear ImGui cannot be selected. A read-only multiline input can, and with
    word wrap and no frame it looks like the text it replaces. Its height is measured so the
    whole message shows without an inner scrollbar.
    """
    from imgui_bundle import ImVec2
    style = imgui.get_style()
    width = imgui.get_content_region_avail().x
    # Measured slightly narrower than the box wraps, so the estimate never comes up short.
    measured = imgui.calc_text_size(text, wrap_width=max(40.0, width - style.scrollbar_size))
    height = measured.y + style.frame_padding.y * 2 + 2
    imgui.push_style_color(imgui.Col_.frame_bg, (0.0, 0.0, 0.0, 0.0))
    imgui.push_style_var(imgui.StyleVar_.frame_border_size, 0.0)
    # No inner margin: the text lines up with the heading above it, like plain text would.
    imgui.push_style_var(imgui.StyleVar_.frame_padding, (0.0, style.frame_padding.y))
    flags = (imgui.InputTextFlags_.read_only | imgui.InputTextFlags_.word_wrap
             | imgui.InputTextFlags_.no_horizontal_scroll)
    imgui.input_text_multiline('##select-' + identity, text, ImVec2(-1, height), flags)
    imgui.pop_style_var(2)
    imgui.pop_style_color()


def bytes_label(value):
    value = float(value or 0)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return '%.1f %s' % (value, unit) if unit != 'B' else '%d B' % value
        value /= 1024
    return str(value)


def status_dot(available, unknown=False):
    """A colour is a hint, never the only signal: the status word is always printed next.

    Drawn by CyUI as a circle on the draw list, so it needs no glyph from the font.
    """
    import cyui
    p = cyui.palette()
    cyui.status_dot(p.textFaint if unknown else (p.success if available else p.error))
    imgui.same_line()


@contextmanager
def card(identity, title='', height=0.0, tone='neutral'):
    """`with card(...)`: a CyUI card whose end_card() is never forgotten."""
    import cyui
    shown = cyui.begin_card(identity, title, height, tone)
    try:
        yield shown
    finally:
        cyui.end_card()
