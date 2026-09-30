#!/usr/bin/env sh
# Linux launcher for CyTools_AIChat.
#
# NOT VALIDATED. This project has only ever run the Tool on Windows x64, so this script is
# written from the same layout as the Windows launcher but has never been executed. Treat a
# first run on Linux as an installation to verify, not as a supported path.
#
# A Windows environment is never reusable here: runtime/python holds absolute paths and
# Windows executables, and the llama.cpp engine pinned in app/engine-assets.json is a
# Windows build. Both have to be created again on the target machine:
#
#   python3 -m venv runtime/python
#   runtime/python/bin/python -m pip install -r app/requirements.txt
#   runtime/python/bin/python app/tool.py invoke engine_list --params '{}'
#
# The engine catalogue ships Windows assets only. On Linux, install llama.cpp yourself and
# register the server path, or use a provider that needs no local engine.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$ROOT/runtime/python/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "The private runtime is missing: $PYTHON" >&2
    echo "Create it with: python3 -m venv runtime/python && runtime/python/bin/python -m pip install -r app/requirements.txt" >&2
    exit 1
fi
cd -- "$ROOT"
exec "$PYTHON" "$ROOT/app/desktop.py" "$@"
