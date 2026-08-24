#!/usr/bin/env python
r"""Parity coverage for the places a build mode has to be declared.

A mode reaches the user through three independent surfaces, each with its own
declaration site, and nothing tied them together:

  MODES              texlib/texlib.py         -> the Ctrl+Shift+B quick panel
  variants[]         TeXLib.sublime-build     -> Tools > Build With...
  args.variant       Default.sublime-commands -> the command palette

`accessible` shipped in the build file alone: the brain implemented it and
Build With... could reach it, but it was missing from MODES, so Ctrl+Shift+B
never listed it -- and because MODE_TOKENS is derived from MODES, dispatching
`texlib_build {"mode": "accessible"}` by hand was rejected as an unknown mode
too. In the other direction the palette went on offering "Solutions" and
"Rubric" after the build file had renamed the first and dropped the second, so
both entries pointed at variants that no longer existed.

Reads all four files as data -- ast for the Python tables, comment-stripped
JSON for the Sublime ones -- rather than importing texlib.py behind stubs, so
what is checked is the files exactly as deploy.ps1 ships them.

Run:  python Sublime/test_texlib_modes.py
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _testkit import check, report  # noqa: E402

BUILD_FILE = os.path.join(HERE, "TeXLib.sublime-build")
PALETTE = os.path.join(HERE, "Default.sublime-commands")
PLUGIN = os.path.join(HERE, "texlib", "texlib.py")
BRAIN = os.path.join(HERE, "texlib", "texlib_build.py")


def module_literal(path, name):
    """Value of a module-level `name = <literal>` assignment, read without
    importing -- texlib.py needs the Sublime API to import, and the point here
    is to read what ships, not what a stubbed import produces."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError("%s: no module-level %s" % (path, name))


def strip_jsonc(text):
    """Drop // line comments outside of strings. Sublime's .sublime-build and
    .sublime-commands are JSON-with-comments, which json.loads will not take;
    the regex form of this eats the // in any URL or escaped path, so track
    string state instead."""
    out = []
    in_string = escaped = in_comment = False
    for ch, nxt in zip(text, text[1:] + "\n"):
        if in_comment:
            if ch == "\n":
                in_comment = False
                out.append(ch)
            continue
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
        elif ch == "/" and nxt == "/":
            in_comment = True
        else:
            out.append(ch)
    return "".join(out)


def load_jsonc(path):
    with open(path, encoding="utf-8") as fh:
        return json.loads(strip_jsonc(fh.read()))


ok = True

# --- the four declaration sites ---------------------------------------------
picker = [tok for (tok, _cap, _blurb) in module_literal(PLUGIN, "MODES")]
macros = module_literal(BRAIN, "MODE_MACROS")
quick = module_literal(BRAIN, "MODE_QUICK")
# _extract_mode accepts MODE_MACROS plus the separately-dispatched quick mode.
accepted = set(macros) | {quick}

build = load_jsonc(BUILD_FILE)
variants = {v["name"]: v for v in build.get("variants", [])}
variant_modes = {}
for name, spec in variants.items():
    for opt in spec.get("options", []):
        if str(opt).startswith("--texlib-mode="):
            variant_modes[name] = str(opt).split("=", 1)[1]

palette_variants = [
    entry["args"]["variant"]
    for entry in load_jsonc(PALETTE)
    if isinstance(entry, dict) and entry.get("args", {}).get("variant")
]

# --- every declared mode is one the brain actually accepts ------------------
for tok in picker:
    ok &= check(tok in accepted,
                "picker mode %r is accepted by the brain" % tok)
for name, tok in sorted(variant_modes.items()):
    ok &= check(tok in accepted,
                "build variant %r passes an accepted mode (%r)" % (name, tok))

# --- the regression: a build variant the picker cannot reach ----------------
# One-directional on purpose. The picker is allowed extras that are not build
# variants -- "default" is what Ctrl+B runs, and "full" exists so the picker
# can force a settling build when default_build_mode is quick -- but a mode
# offered by Build With... and missing from the picker is the defect.
for name, tok in sorted(variant_modes.items()):
    ok &= check(tok in picker,
                "build variant %r (%r) is also in the Ctrl+Shift+B picker"
                % (name, tok))

ok &= check("accessible" in picker,
            "accessible is in the picker (it shipped build-file-only)")

# --- the palette can only name variants that exist --------------------------
for name in palette_variants:
    ok &= check(name in variants,
                "palette entry %r names a real build variant" % name)

# MODE_TOKENS is derived from MODES, so a mode absent from MODES is rejected by
# TexlibBuildCommand.run even when dispatched directly. Pin the derivation.
with open(PLUGIN, encoding="utf-8") as fh:
    ok &= check("MODE_TOKENS = {m[0] for m in MODES}" in fh.read(),
                "MODE_TOKENS is still derived from MODES, not a second literal")

report(ok)
