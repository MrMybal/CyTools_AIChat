# CyTools_AIChat — developer documentation

Maintenance : **Cyberalien**.

A chat engine built on the CyToolsCore SDK. One runtime serves the desktop window, the CLI,
JSONL, HTTP and MCP, so a conversation is the same object whichever one wrote into it, and a
local model loaded for one of them is the one the others use.

The user guide is `../LISEZ-MOI.md`. The capability matrix, with what was tested and what was
not, is `Docs/CapabilityCoverage.md`.

License: GPL-3.0-only (`../LICENSE`), like the CyToolsCore SDK it is built on. It covers the
code and the window; the vendored connector library, the llama.cpp engine and the model
weights keep their own licences (`licenses.json`, `llm-catalog.json`).

## Layout

```
CyTools_AIChat/
  CyTools_AIChat.exe      Windows launcher (built from app/launcher.cpp)
  CyTools_AIChat.sh       Linux launcher, never executed by this project
  LISEZ-MOI.md            short user guide
  app/                    code, manifest, tests, scripts, documentation
  data/                   conversations, presets, models, jobs, logs, exports, reports
  runtime/                private Python, llama.cpp engines, downloads, updates, backups
```

Inside `app/`:

| Path | What it holds |
|---|---|
| `tool.py` | `create_runtime`: every operation handler, and the CLI entry point |
| `desktop.py` | the Dear ImGui window; frontend only |
| `gui/` | the panels: chat, providers, models, updates |
| `aichat/` | the business code: conversations, presets, credentials, providers, engine, catalogue, updates |
| `aichat/providers/` | one module per provider family |
| `aichat/vendor/cyai_connectors/` | a real copy of the portable connector library; left as upstream wrote it |
| `build_manifest.py` | generates `CyTool.json`; run it after changing a parameter or a provider |
| `tests/` | the pytest suite and the acceptance scripts |

## Install

```powershell
py -3.11 -m venv runtime\python
runtime\python\Scripts\python.exe -m pip install --upgrade pip wheel
runtime\python\Scripts\python.exe -m pip install -r app\requirements.txt
runtime\python\Scripts\python.exe -m pip install -r app\requirements-dev.txt
runtime\python\Scripts\python.exe app\build_manifest.py
powershell -ExecutionPolicy Bypass -File app\build_launcher.ps1
```

`requirements.txt` installs CyToolsCore 0.9.0 (GPL-3.0-only) from its public repository,
https://github.com/MrMybal/CyToolsCore, pinned to commit `442f53740fc6`, the code this Tool was
verified against. **git must be on the PATH**: pip clones that commit.

The virtual environment is created at its final path and is never moved: its scripts hold
absolute paths. Building the launcher needs the Visual Studio C++ build tools; the script
finds them through `vswhere` rather than assuming `cl` is on PATH.

## Run

```powershell
CyTools_AIChat.exe                                     # the window
runtime\python\Scripts\python.exe app\desktop.py       # the window, with a console
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py invoke chat --params-file app\params.json
runtime\python\Scripts\python.exe app\tool.py mcp      # MCP over stdio
runtime\python\Scripts\python.exe app\tool.py serve --port 8765
```

`--data-dir` defaults to `data/jobs`. The Core allows one runtime per data directory, so the
window and a CLI call cannot run against it at the same time.

## Identity and permissions

The operations declare the effects they really have: `network`, `processSpawn`,
`filesystemExternal`, `manageResources`. The Core checks a declared permission against the
calling identity, and the implicit client the transports create holds none, so `tool.py`
mints a local client with exactly the declared permissions and hands its token to the
transport through `CYTOOLS_TOKEN` when no identity is configured. To use a restricted
identity instead:

```powershell
runtime\python\Scripts\python.exe app\tool.py create-client --name readonly
$env:CYTOOLS_TOKEN = '<the token it printed>'
```

That identity is then used as-is, and an operation it lacks the permission for is refused.

## Adding a provider

1. Subclass `Provider` in `aichat/providers/`. Set `kind` to `STATELESS` (the Tool sends the
   transcript every turn) or `SESSION` (the provider keeps the history and is resumed by a
   native identifier). Implement `detect`, `chat`, and `list_models` when it has a catalogue.
2. Register it in `Registry._build`.
3. Add its id to `PROVIDERS` in `build_manifest.py` and to `TRANSPORTS` if it introduces one,
   then regenerate the manifest.
4. Add a row to `Docs/CapabilityCoverage.md` saying whether it was executed or only wired.

`chat` receives a `ChatRequest` and an `on_delta(kind, text)` callback. Call
`request.check()` in the read loop: that is what makes cancellation work.

## Interface strings

Write the English literal in the code, inside `tr(...)` or `label(...)`, then add the French
to `locales/aichat-fr.json` and run:

```powershell
runtime\python\Scripts\python.exe app\scripts\merge_translations.py         # merge
runtime\python\Scripts\python.exe app\scripts\merge_translations.py --check # report only
```

`--check` exits non-zero when an interface literal has no entry. Identifiers, paths, model
names, prompts and anything the user typed are never translated.

## Tests

```powershell
runtime\python\Scripts\python.exe -m pytest app\tests -q
runtime\python\Scripts\python.exe app\tests\acceptance_local.py --engine cuda
runtime\python\Scripts\python.exe app\tests\acceptance_http.py --engine cuda
runtime\python\Scripts\python.exe app\tests\acceptance_mcp.py --provider codex --model ""
runtime\python\Scripts\python.exe app\tests\acceptance_update.py
runtime\python\Scripts\python.exe app\scripts\build_release.py --check
runtime\python\Scripts\python.exe app\desktop.py --smoke-test --smoke-tab Providers
runtime\python\Scripts\python.exe app\desktop.py --smoke-test --smoke-send "Say hello"
```

The pytest suite uses fixtures only: no provider is contacted and no model is loaded. The
acceptance scripts run against the installed providers, engines and weights, and write
their evidence to `data/reports/`.

`--smoke-tab NAME` renders one tab and saves a screenshot of it; hello_imgui can only return
the window as it was when the loop ended, which is why proving four panels render takes four
runs.

## Importing weights another CyTool already has

```powershell
runtime\python\Scripts\python.exe app\scripts\import_models.py --from ..\CyTools_PersonaRP --list
runtime\python\Scripts\python.exe app\scripts\import_models.py --from ..\CyTools_PersonaRP --models hermes-3-3b dolphin3-8b
```

It copies the file, never links it: two Tools sharing one file stop being independent, and
uninstalling a model in one would break the other. Each copy is verified against the SHA-256
this catalogue pins before it is recorded as installed, and is then registered in the model
library so it shares one identifier space with the files you add yourself.

Licence acceptance is carried over only when the source Tool recorded that this user really
accepted it; otherwise `--accept-licenses` is required and means you accept them here.

## Updating the pinned llama.cpp release

`app/engine-assets.json` pins a release tag with the published size and SHA-256 of each
asset. To move to a newer build, read the new assets from the GitHub release API and replace
the entries. The Tool will not download a build whose digest it cannot check beforehand, so
editing the tag alone is not enough.

## Publishing an application release

The expected asset is a `.zip` holding an `app/` directory with `CyTool.json` at its root and
a `release.json` declaring `runtimeAbi`. Bump `RUNTIME_ABI` in `aichat/maintenance.py`
whenever a release stops being loadable by the runtime already installed. Configure the
repository in the Updates tab: the Tool never guesses one.

A checksum published beside a release is not an independent signature. What the Tool verifies
is the size, the digest when the release carries one, the containment of the archive, the
Tool identity, the runtime ABI and that the staged code compiles — never by importing it.
