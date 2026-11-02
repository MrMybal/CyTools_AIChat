# Modular CyUI integration

The standalone application includes unmodified CyUI 1.2.0 Python sources, pinned to
revision 8367401fe45fc22bfed5e227cb3de343177f676b. The source hashes and selected modules
are recorded in app/cyui-source.json. The upstream repository is currently private;
the installed application does not need an upstream checkout or account.

## Modules and ownership

Core, DocumentViews (documents), Code, Audio and Diagnostics.

Stored and streamed messages now use the common Markdown document viewer: headings,
emphasis, links, lists, tables and fenced code. Each conversation/message has independent
cached presentation state. The source icon keeps the original character-selectable text;
full copy and per-message speech actions remain available. Reasoning streams use their own
document state. Dictation level uses Audio. Structured diagnostics replaces the local
log renderer, with selectable raw text and asynchronous full-file copy retained.

Providers, API credentials, sessions, streaming jobs, voice engines, model installation,
conversations and deletion-to-trash policies remain owned by AIChat. No provider or speech
runtime is added or updated. Only the selected Python sources are included.

DocumentViews implements the documented native Markdown subset. It is not a browser or
a Discord implementation. Images, video and 3D attachments are not new capabilities of this
migration. Long Markdown messages have a bounded scrolling document surface; source mode
preserves character selection and exact message contents.

## Build and maintenance

Keep the vendored files unchanged. Application adapters live under gui/ and in
gui_log_view.py. Refresh only from the pinned checkout using
python app/scripts/sync_cyui.py PATH_TO_CYUI. Existing source/release builders include
the selected package and notices. No CMake umbrella, demo, Gallery, browser/CEF or
second Dear ImGui instance is introduced. Existing imgui-bundle remains pinned.

Run the application suite and tests/test_modular_ui.py with runtime/python's Python.
Build the launcher using app/build_launcher.ps1 and validate the actual Windows package.
Tests cover source integrity, cached diagnostics, actual ImGui frames in five themes,
both densities, English/French and simulated DPI scales. This does not certify physical
multi-monitor behavior. Linux/macOS execution remains unverified for this migration.

English remains the default. French, themes, density and text size remain persistent.
Application catalogs are shared with the selected CyUI locale without translating user
messages, model IDs, project data or file paths.

## License

CyUI is MIT: the complete text is included in LICENCES/CyUI-MIT.txt at the product root
and in app/LICENCES. Upstream license: https://github.com/MrMybal/CyUI/blob/main/LICENSE.
The application's own license and all dependency/model licenses remain unchanged.
