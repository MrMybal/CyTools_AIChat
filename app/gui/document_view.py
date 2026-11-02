# Per-conversation Markdown presentation. Speech, messages and persistence stay host-owned.
from dataclasses import dataclass, field
import webbrowser
from cyui_modules.documents import Document, DocumentState, document_view
import cyui
from ui_common import imgui

@dataclass
class MessageView:
    document: Document = field(default_factory=Document)
    state: DocumentState = field(default_factory=DocumentState)
    source: bool = False
    _height_key: object = None
    _height: float = 0.

    def height(self, width):
        # The common document owns layout; cap large messages to a scrollable surface.
        key=(self.document.text,round(width),cyui.dpi(),cyui.density(),imgui.get_font_size())
        if key!=self._height_key:
            line=imgui.get_text_line_height_with_spacing();spacing=imgui.get_style().item_spacing.y
            h=imgui.get_style().window_padding.y*2+spacing
            for block in self.document.blocks:
                if block.kind=='code':h+=line+cyui.dp(max(90,min(320,len(block.code.lines)*20+48)))+spacing*2
                elif block.kind=='table':
                    columns=max(1,max(map(len,block.rows)))
                    cell=max(cyui.dp(30),(width-imgui.get_style().cell_padding.x*2*columns)/columns)
                    h+=sum(max([imgui.calc_text_size(x,wrap_width=cell).y for x in row] or [line])+imgui.get_style().cell_padding.y*2 for row in block.rows)+spacing*2
                elif block.kind=='rule':h+=cyui.dp(24)
                else:
                    h+=max(line,imgui.calc_text_size(block.text,wrap_width=max(cyui.dp(40),width-cyui.dp(24))).y)+spacing
                    if block.kind=='heading':h+=line*.6
                    elif block.kind=='quote':h+=cyui.dp(20)
            self._height_key=key;self._height=max(line+cyui.dp(20),min(cyui.dp(640),h))
        return self._height

    def draw(self,identity,text):
        self.document.set_markdown(str(text))
        if self.source:
            from .widgets import selectable_text
            selectable_text(identity,str(text))
            return
        result=document_view('markdown-'+identity,self.state,self.document,
                             (0,self.height(imgui.get_content_region_avail().x)))
        url=result.get('link','')
        if url.startswith(('https://','http://')):webbrowser.open(url)


def message_view(tab,identity):
    views=getattr(tab,'_document_views',None)
    if views is None:views=tab._document_views={}
    return views.setdefault(str(identity),MessageView())


def prune(tab):
    present={str(m['id']) for m in tab.document.get('messages',[])}|{'live','thinking'}
    views=getattr(tab,'_document_views',{})
    for key in set(views)-present:del views[key]
