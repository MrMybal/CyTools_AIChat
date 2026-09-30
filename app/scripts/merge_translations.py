"""Fold app/locales/aichat-fr.json into the shared catalogue, and report what is missing.

The catalogue the scaffold ships already covers the facade (Options, log, advanced access).
This script adds the strings this Tool introduces, and then walks the interface source to
list any `tr(...)` or `label(...)` literal that still has no French entry, so a new label
cannot quietly ship untranslated.

    runtime/python/Scripts/python.exe app/scripts/merge_translations.py [--check]

`--check` reports without writing, and exits non-zero when something is missing.
"""
import ast
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
CATALOGUE = APP / 'locales/ui.json'
SOURCE = APP / 'locales/aichat-fr.json'
UI_FILES = sorted(APP.glob('gui/*.py')) + [APP / 'desktop.py']


def visible(text):
    """`label()` translates only the part before ###; '##' hides a label entirely."""
    if text.startswith('##'):
        return ''
    return text.partition('###')[0]


def literals():
    found = []
    for path in UI_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in ('tr', 'label') or not node.args:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.append(argument.value)
            elif isinstance(argument, ast.BinOp):
                parts = [n.value for n in ast.walk(argument)
                         if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                if parts:
                    found.append(''.join(parts))
    return sorted({visible(item) for item in found if visible(item)})


def main():
    check = '--check' in sys.argv
    catalogue = json.loads(CATALOGUE.read_text(encoding='utf-8-sig'))
    additions = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    added = 0
    for english, french in additions.items():
        if english.startswith('_'):
            continue
        entry = {'en': english, 'fr': french}
        if catalogue.get(english) != entry:
            catalogue[english] = entry
            added += 1
    missing = [item for item in literals() if item not in catalogue]
    if not check and added:
        CATALOGUE.write_text(json.dumps(dict(sorted(catalogue.items())), indent=2,
                                        ensure_ascii=False) + '\n', encoding='utf-8',
                             newline='\n')
    print(json.dumps({'catalogueEntries': len(catalogue), 'added': added,
                      'interfaceLiterals': len(literals()), 'missing': missing}, indent=2,
                     ensure_ascii=False))
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
