import hashlib,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from dataclasses import replace
from imgui_bundle import imgui as i
import cyui
APP=Path(__file__).resolve().parents[1]

class Provenance(unittest.TestCase):
    def test_exact_and_selective_sources(self):
        pin=json.loads((APP/'cyui-source.json').read_text('utf-8'))
        self.assertFalse(pin['modifications'])
        self.assertEqual(len(pin['revision']),40)
        for rel,digest in pin['files'].items():
            actual=(APP/rel).read_text('utf-8').replace('\r\n','\n').encode('utf-8')
            self.assertEqual(hashlib.sha256(actual).hexdigest(),digest,rel)
        self.assertEqual({p.name for p in (APP/'cyui_modules').glob('*.py')},
                         {Path(p).name for p in pin['files'] if p.startswith('cyui_modules/')})
        self.assertEqual((APP/'LICENCES/CyUI-MIT.txt').read_text('utf-8'),
                         (APP.parent/'LICENCES/CyUI-MIT.txt').read_text('utf-8'))

    def test_log_append_preserves_selection_and_source_change_resets_it(self):
        from gui_log_view import LogView
        view=LogView();view.update('INFO First\n','one')
        _,before=view.buffer.snapshot();view.state.selected=before[0].id
        view.update('INFO First\nERROR Second\n','one')
        _,after=view.buffer.snapshot()
        self.assertEqual(view.state.selected,after[0].id)
        self.assertEqual(after[0].id,before[0].id)
        view.update('WARNING Other\n','two')
        _,after=view.buffer.snapshot();self.assertEqual(len(after),1)
        self.assertEqual(after[0].source,'two');self.assertEqual(view.state.selected,0)

class FrameCase(unittest.TestCase):
    def setUp(self):
        i.create_context();io=i.get_io();io.display_size=(1100,850);io.delta_time=1/60
        io.set_ini_filename('');io.backend_flags|=i.BackendFlags_.renderer_has_textures
        io.config_input_trickle_event_queue=False;io.mouse_double_click_time=.001
        cyui.apply()
    def tearDown(self):i.destroy_context()
    def frame(self,draw,position=(-100,-100),button=None,key=None):
        io=i.get_io();io.add_mouse_pos_event(*position)
        if button is not None:io.add_mouse_button_event(*button)
        if key is not None:io.add_key_event(*key)
        i.new_frame();i.set_next_window_pos((0,0));i.set_next_window_size((1100,850))
        i.begin('Adapter',None,i.WindowFlags_.no_title_bar|i.WindowFlags_.no_move|i.WindowFlags_.no_saved_settings)
        i.set_cursor_screen_pos((20,20))
        try:result=draw()
        finally:i.end();i.render()
        return result

class ChatFrames(FrameCase):
    def test_markdown_streams_and_source_in_all_themes(self):
        from gui.document_view import message_view,prune
        from cyui_modules.locale import set_locale
        tab=SimpleNamespace(document={'messages':[{'id':'one'}]})
        view=message_view(tab,'one')
        content='# Header\n**Bold** and *emphasis*, [link](https://example.com)\n~~~python\nvalue=1\n~~~\n\n|Name|Value|\n|---|---|\n|A|B|'
        for theme,*_ in cyui.THEMES:
            for density in ('compact','comfortable'):
                for dpi in (1.,1.5,2.):
                    cyui.apply(theme,density,dpi)
                    for language in ('en','fr'):
                        set_locale(language)
                        self.frame(lambda:view.draw('one',content))
        self.assertEqual(view.document.text,content)
        self.assertIn('table',[b.kind for b in view.document.blocks])
        state=view.state
        self.frame(lambda:view.draw('one',content+'\nStream continues'))
        self.assertIs(view.state,state)
        view.source=True;self.frame(lambda:view.draw('one',content))
        self.assertEqual(view.document.text,content)
        prune(tab);self.assertIn('one',tab._document_views)
        tab.document['messages']=[];prune(tab);self.assertNotIn('one',tab._document_views)
        set_locale('en')

    def test_tabs_never_share_presentation_or_reasoning_state(self):
        from gui.document_view import message_view
        a=SimpleNamespace(document={'messages':[]});b=SimpleNamespace(document={'messages':[]})
        first=message_view(a,'live');second=message_view(b,'live')
        first.document.set_markdown('**First**');first.source=True
        self.assertIsNot(first,second);self.assertFalse(second.source)
        self.assertNotEqual(first.document.text,second.document.text)

    def test_real_message_actions_keep_copy_and_read_aloud(self):
        from gui.chat_panel import draw_message,draw_live
        tab=SimpleNamespace(live_thinking=['Reason'],show_thinking=True,status='Streaming')
        interface=SimpleNamespace(reading=lambda key:False,read_message=lambda *args:None)
        message={'id':'msg','role':'assistant','text':'**Answer**\n~~~json\n{}\n~~~'}
        self.frame(lambda:draw_message(interface,tab,message))
        self.frame(lambda:draw_live(tab,'Live *reply*'))
        self.assertIn('msg',tab._document_views);self.assertIn('live',tab._document_views)
