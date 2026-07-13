#!/usr/bin/env python
"""Fake-Popen coverage for the native async runner (texlib/texlib.py).

The parity test (test_texlib_build.py) drives the brain's coroutine directly and
never touches the runner. This one imports texlib.py with sublime/sublime_plugin
stubbed and a fake subprocess.Popen, so it exercises the ACTUAL driver surface --
the new, riskiest code (PLUGIN-DESIGN Risk #2): feeding each command's output
back to the brain (so a rerun signal actually re-runs THROUGH the runner), the
cancel->kill path, the PER-DOCUMENT build registry that lets distinct documents
build in parallel, and the per-build aux-env injection that keeps those parallel
builds from racing a shared TEXLIB_AUX_DIR. No Sublime, no TeX.

Run:  python Sublime/test_texlib_runner.py
"""
import hashlib
import os
import sys
import tempfile
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))  # texlib.py + texlib_build.py

from _testkit import check  # noqa: E402

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
    """Returns one scripted FakePopen per call; records the argv AND env of each
    call (env is how we prove each build's aux dir reaches ITS own subprocess)."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []
        self.envs = []
        self.last = None

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        self.envs.append(kw.get("env"))
        lines = self.scripts.pop(0) if self.scripts else []
        self.last = FakePopen(lines)
        return self.last


ok = True

# 1. _run_argv streams output, injects THIS build's aux dir into its subprocess
#    env, parks proc on the build's entry, and on cancel kills mid-stream.
factory = PopenFactory([["a\n", "b\n", "c\n"]])
texlib.subprocess.Popen = factory
cancel = threading.Event()
emitted = []
entry = {"thread": None, "cancel": cancel, "proc": None}


def _emit_then_cancel(text):
    emitted.append(text)
    cancel.set()  # cancel right after the first line


out = texlib._run_argv(
    ["lualatex", "doc.tex"], HERE, _emit_then_cancel, cancel, "",
    r"C:\aux\buildA", entry)
ok &= check(out == "a\n", "cancel: only the pre-cancel line was captured")
ok &= check(factory.last.killed, "cancel: process was killed")
ok &= check(len(emitted) == 1, "cancel: streaming stopped after the cancel")
ok &= check(entry["proc"] is None, "cancel: this build's proc slot cleared")
ok &= check(factory.envs[0].get("TEXLIB_AUX_DIR") == r"C:\aux\buildA",
            "aux env: the build's own aux dir is injected into ITS subprocess env")

# 2. _drive feeds output back so a rerun signal re-runs THROUGH the runner, and
#    clears the build's registry entry when it finishes.
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
    ev = threading.Event()
    entry = {"thread": None, "cancel": ev, "proc": None}
    texlib._builds[root] = entry  # simulate run()'s registration
    inst = texlib.TexlibBuildCommand()
    inst._drive(host, tmp, msgs.append, ev, "", root, entry)
ok &= check(len(factory.calls) == 2, "rerun: driver ran 2 passes via _run_argv")
ok &= check(all("-file-line-error" in c for c in factory.calls),
            "rerun: every real engine invocation carried -file-line-error")
ok &= check(host.out == "", "rerun: last pass output fed back (settled)")
ok &= check(root not in texlib._builds, "rerun: registry entry removed on finish")

# 3. Per-document guard: the SAME document is seen as building (a second build is
#    refused); a DIFFERENT document is free to build in parallel (the point).
class _AliveThread:
    def is_alive(self):
        return True


rootA = os.path.join(HERE, "docA.tex")
rootB = os.path.join(HERE, "docB.tex")
texlib._builds[rootA] = {"thread": _AliveThread(), "cancel": None, "proc": None}
ok &= check(texlib._build_active(rootA), "guard: same document is seen as building")
ok &= check(not texlib._build_active(rootB),
            "guard: a DIFFERENT document is free to build in parallel")
ok &= check(texlib._panel_name(rootA) != texlib._panel_name(rootB),
            "panel: concurrent builds get distinct output panels")
texlib._builds.pop(rootA, None)  # reset


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
        entry = {"thread": None, "cancel": ev, "proc": None}
        texlib.TexlibBuildCommand()._drive(
            host, tmp, emit, ev, "", root, entry,
            on_success=lambda: fired.__setitem__("v", True))
    return fired["v"]


ok &= check(_drive_delegation(pdf_exists=True, cancel_on_pass1=False) is True,
            "delegation: on_success fires after a completed build with a PDF")
ok &= check(_drive_delegation(pdf_exists=False, cancel_on_pass1=False) is False,
            "delegation: on_success skipped when no PDF was produced")
ok &= check(_drive_delegation(pdf_exists=True, cancel_on_pass1=True) is False,
            "delegation: on_success skipped when the build was cancelled")

# 5. Outcome classification + error collection (drives on_finish).
def _drive_finish(script_lines):
    captured = {}
    texlib.subprocess.Popen = PopenFactory([script_lines])
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "doc.tex")
        with open(root, "w", encoding="utf-8") as fh:
            fh.write("\\documentclass{pset}\n\\begin{document}\nx\n\\end{document}\n")
        host = texlib_build.TexlibBuild(
            tex_root=root, engine="pdflatex",
            options=["--texlib-mode=default"], display=lambda t: None,
            aux_directory="<<root>>")

        def on_finish(state, errs, warns):
            captured["state"] = state
            captured["errs"] = errs
            captured["warns"] = warns

        ev = threading.Event()
        entry = {"thread": None, "cancel": ev, "proc": None}
        texlib.TexlibBuildCommand()._drive(
            host, tmp, lambda t: None, ev, "", root, entry,
            on_success=None, on_finish=on_finish)
    return captured


r = _drive_finish(["./doc.tex:14: Undefined control sequence.\n", "done\n"])
ok &= check(r["state"] == "error", "classify: a file:line error -> state 'error'")
ok &= check(r["errs"] == ["./doc.tex:14: Undefined control sequence."],
            "classify: the source error line is collected for the summary")

r = _drive_finish(["This is pdfTeX\n", "Output written on doc.pdf (1 page)\n"])
ok &= check(r["state"] == "ok" and r["errs"] == [],
            "classify: clean output -> state 'ok', no errors")

r = _drive_finish(["/tmp/aux/doc.aux:12: Undefined control sequence.\n"])
ok &= check(r["state"] == "error", "classify: an .aux error still marks failure")
ok &= check(r["errs"] == [], "classify: .aux errors excluded from the summary")

r = _drive_finish(["LaTeX Warning: Reference `x' undefined on input line 5.\n",
                   "Output written on doc.pdf\n"])
ok &= check(r["state"] == "ok", "classify: warnings alone do NOT fail the build")
ok &= check(len(r["warns"]) == 1, "classify: the warning is collected")

# 6. _aux_log_path reproduces the build's md5[:12] key; _build_report formats a
#    clickable full-log link and keeps error lines unprefixed.
log_path = texlib._aux_log_path("/some/doc.tex", "doc")
expect_tail = os.path.join(
    "texlib-aux", hashlib.md5(b"/some/doc.tex").hexdigest()[:12], "doc.log")
ok &= check(log_path.endswith(expect_tail),
            "aux log path: <tempdir>/texlib-aux/<md5[:12]>/doc.log")
report = texlib._build_report(
    "doc", ["./doc.tex:14: Undefined control sequence."],
    ["LaTeX Warning: Reference `x' undefined on input line 5."], log_path)
ok &= check("1 error(s), 1 warning(s)" in report, "report: header counts")
ok &= check("\n./doc.tex:14: Undefined control sequence.\n" in report,
            "report: error line kept unprefixed (stays clickable)")
ok &= check(("%s:1: [full build log" % log_path) in report,
            "report: full-log link is a clickable path:1: line")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
