#!/usr/bin/env python
"""Logic coverage for the TEXMF uninstall (texlib/texlib_texmf.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, builds a fake
TEXMFHOME/tex/latex/texlib install, and checks the target-dir resolution and
installed-file listing the uninstall command relies on.

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


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# target-dir resolution: always <TEXMFHOME>/tex/latex/texlib
home = os.path.join("X", "texmf")
ok &= check(
    texlib_texmf.texmf_install_dir(home)
    == os.path.join(home, "tex", "latex", "texlib"),
    "install dir is <TEXMFHOME>/tex/latex/texlib")

# absent install dir -> nothing to remove
with tempfile.TemporaryDirectory() as root:
    ok &= check(
        texlib_texmf.installed_files(os.path.join(root, "texlib")) == [],
        "absent install dir -> empty list (nothing to uninstall)")

# populated install -> lists the .cls/.sty/.lua payload, ignores other files
with tempfile.TemporaryDirectory() as root:
    inst = texlib_texmf.texmf_install_dir(root)
    for fn in ("autoexam.cls", "texlib-corepkg.sty", "schedule.lua",
               "ls-R", "README.md"):
        touch(os.path.join(inst, fn))
    got = texlib_texmf.installed_files(inst)
    ok &= check(
        got == ["autoexam.cls", "schedule.lua", "texlib-corepkg.sty"],
        "lists .cls/.sty/.lua payload (sorted), excludes ls-R / README.md")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
