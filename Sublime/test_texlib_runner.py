#!/usr/bin/env python
"""Fake-Popen coverage for the native async runner (texlib/texlib.py).

The parity test (test_texlib_build.py) drives the brain's coroutine directly and
never touches the runner. This one imports texlib.py with sublime/sublime_plugin
stubbed and a fake subprocess.Popen, so it exercises the ACTUAL driver surface --
the new, riskiest code (PLUGIN-DESIGN Risk #2): feeding each command's output
back to the brain (so a rerun signal actually re-runs THROUGH the runner), the
cancel->kill path, and the single-build overlap guard. No Sublime, no TeX.

Run:  python Sublime/test_texlib_runner.py
"""
import os
import sys
import tempfile
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))  # texlib.py + texlib_build.py

# --- Stub the Sublime API so texlib.py imports outside the editor ------------
_sublime = types.ModuleType("sublime")
_sublime.set_timeout = lambda fn, ms=0: fn()  # run marshaled callbacks inline
_sublime.status_message = lambda *a, **k: None
_sublime.error_message = lambda *a, **k: None
_sublime.Region = lambda a, b: (a, b)


class _Settings:
    def get(self, key, default=None):
        return default


_sublime.load_settings = lambda name: _Settings()
sys.modules["sublime"] = _sublime

_plugin = types.ModuleType("sublime_plugin")
_plugin.WindowCommand = object
_plugin.TextCommand = object
_plugin.EventListener = object
sys.modules["sublime_plugin"] = _plugin

import texlib  # noqa: E402  (the runner)
import texlib_build  # noqa: E402  (the brain)


# --- Fake Popen --------------------------------------------------------------
class FakePopen:
    def __init__(self, lines):
        self._lines = iter(lines)
        self.killed = False
        self.stdout = self  # its own line iterator, with a close()

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._lines)

    def close(self):
        pass

    def kill(self):
        self.killed = True

    def wait(self):
        return 137 if self.killed else 0


class PopenFactory:
    """Returns one scripted FakePopen per call; records the argv of each call."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []
        self.last = None

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        lines = self.scripts.pop(0) if self.scripts else []
        self.last = FakePopen(lines)
        return self.last


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# 1. _run_argv streams output and, on cancel, kills the process mid-stream.
factory = PopenFactory([["a\n", "b\n", "c\n"]])
texlib.subprocess.Popen = factory
cancel = threading.Event()
emitted = []


def _emit_then_cancel(text):
    emitted.append(text)
    cancel.set()  # cancel right after the first line


out = texlib._run_argv(["lualatex", "doc.tex"], HERE, _emit_then_cancel, cancel, "")
ok &= check(out == "a\n", "cancel: only the pre-cancel line was captured")
ok &= check(factory.last.killed, "cancel: process was killed")
ok &= check(len(emitted) == 1, "cancel: streaming stopped after the cancel")
ok &= check(texlib._active["proc"] is None, "cancel: active-proc slot cleared")

# 2. _drive feeds output back so a rerun signal re-runs THROUGH the runner.
factory = PopenFactory([
    ["Rerun to get cross-references right.\n"],  # pass 1 -> ask for a rerun
    [],                                          # pass 2 -> settled
])
texlib.subprocess.Popen = factory
msgs = []
with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, "doc.tex")
    with open(root, "w", encoding="utf-8") as fh:
        fh.write("\\documentclass{pset}\n\\begin{document}\nx\n\\end{document}\n")
    host = texlib_build.TexlibBuild(
        tex_root=root, engine="pdflatex",
        options=["--texlib-mode=default"], display=msgs.append,
        aux_directory="<<root>>",
    )
    inst = texlib.TexlibBuildCommand()
    inst._drive(host, tmp, msgs.append, threading.Event(), "")
ok &= check(len(factory.calls) == 2, "rerun: driver ran 2 passes via _run_argv")
ok &= check(all("-file-line-error" in c for c in factory.calls),
            "rerun: every real engine invocation carried -file-line-error")
ok &= check(host.out == "", "rerun: last pass output fed back (settled)")
ok &= check(texlib._active["thread"] is None, "rerun: active-thread slot cleared")

# 3. Overlap guard: a second build is refused while one is 'running'.
factory = PopenFactory([["x\n"]])
texlib.subprocess.Popen = factory


class _AliveThread:
    def is_alive(self):
        return True


texlib._active["thread"] = _AliveThread()
texlib.TexlibBuildCommand().run(mode="default")  # returns at the guard
ok &= check(len(factory.calls) == 0, "overlap: no engine spawned while a build runs")
texlib._active["thread"] = None  # reset


# 4. Post-build delegation (Tier C) fires only when the build completed AND a PDF
#    exists AND it wasn't cancelled.
def _drive_delegation(pdf_exists, cancel_on_pass1):
    fired = {"v": False}
    texlib.subprocess.Popen = PopenFactory([[]])  # one pass, settles immediately
    ev = threading.Event()
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "doc.tex")
        with open(root, "w", encoding="utf-8") as fh:
            fh.write("\\documentclass{pset}\n\\begin{document}\nx\n\\end{document}\n")
        if pdf_exists:
            open(os.path.join(tmp, "doc.pdf"), "wb").close()

        def emit(text):
            if cancel_on_pass1 and "run 1" in text:
                ev.set()

        host = texlib_build.TexlibBuild(
            tex_root=root, engine="pdflatex",
            options=["--texlib-mode=default"], display=lambda t: None,
            aux_directory="<<root>>",
        )
        texlib.TexlibBuildCommand()._drive(
            host, tmp, emit, ev, "",
            on_success=lambda: fired.__setitem__("v", True))
    return fired["v"]


ok &= check(_drive_delegation(pdf_exists=True, cancel_on_pass1=False) is True,
            "delegation: on_success fires after a completed build with a PDF")
ok &= check(_drive_delegation(pdf_exists=False, cancel_on_pass1=False) is False,
            "delegation: on_success skipped when no PDF was produced")
ok &= check(_drive_delegation(pdf_exists=True, cancel_on_pass1=True) is False,
            "delegation: on_success skipped when the build was cancelled")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
