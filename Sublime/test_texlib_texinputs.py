#!/usr/bin/env python
r"""Coverage for the DERIVED TEXINPUTS default (texlib._derive_texinputs).

`texinputs` used to ship commented out, documented as "leave unset to inherit
the process environment". Sublime inherits no TEXINPUTS and the classes live in
the checkout rather than a TEXMF tree, so unset meant every document failed at
\documentclass with "File `didactic.cls' not found" -- for anyone who installed
this package without the standalone installer, which was the only thing writing
that setting. The plugin now derives the path from its own location instead.

The derivation is a real filesystem walk keyed off __file__, so these tests copy
texlib.py into <root>/Sublime/texlib/ on disk and import it FROM there. Mocking
__file__ would test the mock rather than the resolution that actually matters.

Run:  python Sublime/test_texlib_texinputs.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("WindowCommand", "EventListener")

SRC = os.path.join(HERE, "texlib", "texlib.py")
CORE = ("texlib-coursemeta.sty", "texlib-build.sty", "texlib-utilities.sty")
_loaded = [0]


def load_plugin_at(root):
    """Copy texlib.py to <root>/Sublime/texlib/ and import it from there, so
    __file__ resolution sees the real layout."""
    pkg = os.path.join(root, "Sublime", "texlib")
    os.makedirs(pkg, exist_ok=True)
    _loaded[0] += 1
    name = "texlib_under_test_%d" % _loaded[0]
    dst = os.path.join(pkg, name + ".py")
    shutil.copyfile(SRC, dst)
    spec = importlib.util.spec_from_file_location(name, dst)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_library(root, modules, core=True):
    os.makedirs(root, exist_ok=True)
    if core:
        for f in CORE:
            open(os.path.join(root, f), "w").write("% stub\n")
    for name, files in modules.items():
        d = os.path.join(root, name)
        os.makedirs(d, exist_ok=True)
        for f in files:
            open(os.path.join(d, f), "w").write("% stub\n")


ok = True
tmp = tempfile.mkdtemp()

# --- a library-shaped tree --------------------------------------------------
lib = os.path.join(tmp, "Library")
make_library(lib, {
    "Notes": ["didactic.cls"],
    "Exams": ["autoexam.cls"],
    "Problem Sets": ["pset.cls"],      # a space in the name must survive
    "Bank": ["bank.lua"],              # .lua counts too
    "examples": ["demo.tex"],          # no .sty/.cls/.lua -> excluded
    "tests": ["conftest.py"],          # ditto
    ".hidden": ["x.sty"],              # dot-dir -> excluded
})
mod = load_plugin_at(lib)
segs = mod._derive_texinputs().split(os.pathsep)
names = {s.rsplit("/", 1)[-1] for s in segs if s not in (".", "")}
names.discard(os.path.basename(lib))

ok &= check(segs[0] == ".", "first segment is the current directory")
ok &= check(segs[1].replace("\\", "/") == lib.replace("\\", "/"),
            "second segment is the library root")
ok &= check(names == {"Notes", "Exams", "Problem Sets", "Bank"},
            "only module dirs holding .cls/.sty/.lua are included")
ok &= check("examples" not in names and "tests" not in names,
            "dirs without TeX sources are excluded")
ok &= check(".hidden" not in names, "dot-directories are excluded")
ok &= check("Sublime" not in names, "Sublime\\ (the package's own home) is excluded")

# The empty segment is added by _resolve_texinputs, which every caller goes
# through. Without it TEXINPUTS REPLACES kpathsea's default path instead of
# extending it, and every build fatals at startup.
resolved = mod._resolve_texinputs(mod._derive_texinputs())
ok &= check(resolved.split(os.pathsep)[-1] == "",
            "resolved value ends in the load-bearing empty segment")

# --- a tree that is NOT a library -------------------------------------------
# Deriving something plausible-but-wrong here would point builds at a foreign
# tree; deriving nothing preserves the old inherit-the-environment behaviour.
notlib = os.path.join(tmp, "NotALibrary")
make_library(notlib, {"Notes": ["didactic.cls"]}, core=False)
ok &= check(load_plugin_at(notlib)._derive_texinputs() == "",
            "a non-library derives nothing rather than guessing")

# --- an explicit setting still wins -----------------------------------------
explicit = mod._resolve_texinputs([".", "C:/custom", ""])
ok &= check("C:/custom" in explicit and os.path.basename(lib) not in explicit,
            "an explicit texinputs passes through unchanged")

report(ok)
