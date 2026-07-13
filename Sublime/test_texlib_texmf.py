#!/usr/bin/env python
r"""Coverage for the TEXMF UNINSTALL detection (texlib/texlib_texmf.py, M1).

No Sublime, no TeX: stubs sublime/sublime_plugin, builds a fake installed tree
under TEXMFHOME/tex/latex/texlib, and checks installed_files / shadows_checkout.

Run:  python Sublime/test_texlib_texmf.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report, touch  # noqa: E402
stub_sublime("WindowCommand")

import texlib_texmf  # noqa: E402


ok = True
with tempfile.TemporaryDirectory() as root:
    target = os.path.join(root, "tex", "latex", "texlib")

    # Nothing installed yet.
    ok &= check(texlib_texmf.installed_files(target) == [],
                "absent install dir -> empty list (nothing to uninstall)")

    # Populate a fake install: the payload + a stray README (excluded).
    for rel in ["tex/latex/texlib/autoexam.cls",
                "tex/latex/texlib/texlib-corepkg.sty",
                "tex/latex/texlib/problem_engine.lua",
                "tex/latex/texlib/ls-R", "tex/latex/texlib/README.md"]:
        touch(root, rel)

    got = [os.path.basename(p) for p in texlib_texmf.installed_files(target)]
    ok &= check(got == ["autoexam.cls", "problem_engine.lua", "texlib-corepkg.sty"],
                "lists .cls/.sty/.lua payload (sorted), excludes ls-R / README.md")

    # shadows_checkout() reflects whatever installed_texlib_dir() points at.
    texlib_texmf.installed_texlib_dir = lambda t=target: t
    ok &= check(texlib_texmf.shadows_checkout() is True,
                "shadows_checkout: True when a copy is installed")

    import shutil
    shutil.rmtree(target)
    ok &= check(texlib_texmf.shadows_checkout() is False,
                "shadows_checkout: False after the copy is removed")

report(ok)
