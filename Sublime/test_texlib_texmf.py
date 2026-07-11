#!/usr/bin/env python
"""Gather-logic coverage for the TEXMF install (texlib/texlib_texmf.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, builds a fake repo tree, and
checks gather_class_files picks the .cls/.sty/.lua payload while excluding Lua
tests, .tex, and infrastructure dirs (.git / Sublime / examples).

Run:  python Sublime/test_texlib_texmf.py
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

sys.modules["sublime"] = types.ModuleType("sublime")
_plugin = types.ModuleType("sublime_plugin")
_plugin.WindowCommand = object
sys.modules["sublime_plugin"] = _plugin

import texlib_texmf  # noqa: E402


def touch(root, rel):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()
    return path


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True
with tempfile.TemporaryDirectory() as root:
    for rel in [
        "texlib-corepkg.sty", "quiver.sty",             # root .sty
        "Exams/autoexam.cls", "Problem Sets/pset.cls",   # .cls (incl. spaced dir)
        "problem_engine.lua", "texlib_synctex.lua",      # engines
        "Schedule/schedule.lua",
        "Schedule/test_schedule_synctex.lua",            # Lua test -> excluded
        "README.md", "notes.tex",                        # wrong ext -> excluded
        "Sublime/texlib/texlib.py",                      # excluded dir
        "examples/Math181/coursemeta.tex",               # excluded dir
        ".git/config",                                   # excluded dir
    ]:
        touch(root, rel)

    got = {os.path.basename(p) for p in texlib_texmf.gather_class_files(root)}

    ok &= check({"autoexam.cls", "pset.cls"} <= got, "gathers .cls from subfolders (incl. spaced dir)")
    ok &= check({"texlib-corepkg.sty", "quiver.sty"} <= got, "gathers root .sty (incl. vendored quiver)")
    ok &= check({"problem_engine.lua", "texlib_synctex.lua", "schedule.lua"} <= got,
                "gathers Lua engines")
    ok &= check("test_schedule_synctex.lua" not in got, "excludes Lua test files")
    ok &= check("notes.tex" not in got and "README.md" not in got, "excludes non-payload extensions")
    ok &= check("texlib.py" not in got, "excludes the Sublime/ plugin dir")
    ok &= check(not any(p.replace("\\", "/").split("/")[-2:][0] == "Math181" for p in
                        texlib_texmf.gather_class_files(root)),
                "excludes examples/")
    ok &= check(len(got) == 7, "gathers exactly the 7 payload files (no .git/config)")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
