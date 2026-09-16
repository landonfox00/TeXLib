#!/usr/bin/env python
"""When does a build put a PDF in front of you, and WHICH PDF?

The two suites either side of this one cover the pieces: test_texlib_builder.py
drives the brain's coroutine, test_texlib_runner.py drives the async runner and
checks the post-build viewer TARGET. Neither pins down the decision itself --
the matrix of build outcomes (clean / failed / cancelled / not needed at all)
against what reaches the viewer. That matrix is what this file is.

It was written because three entries in it were wrong, all three invisible from
either neighbouring suite:

  * the fan-out's early preview raised the viewer on a FAILED build (on the
    previous build's PDF, while the panel reported the errors);
  * a skipped build resolved preferred_pdf to the combined PDF, pulling the
    viewer off the slice the author keeps open;
  * a failed build wrote a freshness stamp -- so the NEXT build was skipped as
    "already current" and the error simply vanished. The clean-pass guard
    scanned for a leading "!", which -file-line-error never writes.

The fake engine below therefore writes a .log holding what it printed, exactly
as a real one does: two of the three are invisible to a harness whose engine
leaves no log behind.

No Sublime, no TeX. Run:  python Sublime/test_texlib_viewer.py
"""
import os
import sys
import tempfile
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))  # texlib.py + texlib_build.py

from _testkit import check, report  # noqa: E402

# --- Stub the Sublime API so texlib.py imports outside the editor ------------
_sublime = types.ModuleType("sublime")
_sublime.set_timeout = lambda fn, ms=0: fn()  # run marshaled callbacks inline
_sublime.status_message = lambda *a, **k: None
_sublime.error_message = lambda *a, **k: None
_sublime.Region = lambda a, b: (a, b)
_sublime.platform = lambda: "windows"
_sublime.active_window = lambda: None  # the keep-focus hack no-ops headless


class _Settings:
    """Every TeXLib/LaTeXTools setting at its documented default, which is what
    the open-on-build paths are supposed to do out of the box."""

    def get(self, key, default=None):
        return default


_sublime.load_settings = lambda name: _Settings()
sys.modules["sublime"] = _sublime

_plugin = types.ModuleType("sublime_plugin")
_plugin.WindowCommand = _plugin.TextCommand = _plugin.EventListener = object
sys.modules["sublime_plugin"] = _plugin

import texlib  # noqa: E402  (the runner)
import texlib_build  # noqa: E402  (the brain)
import texlib_freshness  # noqa: E402  (the skip-if-unchanged check)


# --- Fake engine -------------------------------------------------------------
class FakePopen:
    def __init__(self, lines):
        self._lines = iter(lines)
        self.killed = False
        self.stdout = self

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._lines)

    def close(self):
        pass

    def kill(self):
        self.killed = True

    def wait(self):
        return 1 if self.killed else 0


class PopenFactory:
    """One scripted FakePopen per call. `lines` is replayed by EVERY pass, which
    is what a genuinely broken document does -- the same error every time.

    Each pass also WRITES <base>.log holding what it printed, under a banner, as
    a real engine does. Two of the three behaviours this file exists for are
    decided by reading that log, so a harness without one cannot see them."""

    def __init__(self, lines=(), log_dir=None, base="doc"):
        self.lines = list(lines)
        self.log_dir = log_dir
        self.base = base
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if self.log_dir:
            path = os.path.join(self.log_dir, self.base + ".log")
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("This is pdfTeX, Version 3.141592653 (TeX Live "
                             "2026)  15 SEP 2026 09:12\n")
                    fh.writelines(self.lines)
                    fh.write("Output written on %s.pdf (1 page).\n" % self.base)
            except OSError:
                pass
        return FakePopen(list(self.lines))


# A file:line error, the form -file-line-error produces -- in the stream AND in
# the log, where it REPLACES the leading bang.
ERROR_LINE = "./doc.tex:12: Undefined control sequence.\n"
DOC = ("\\" "documentclass{pset}\n"
       "\\" "begin{document}\nx\n"
       "\\" "end{document}\n")


def _seed(tmp, pdf=True, fls=False):
    """A saved document, optionally with the artifacts of an earlier build
    sitting beside it: the PDF a previous run left, and the .fls the freshness
    stamp's dependency list is read from. The .log is written by the engine."""
    root = os.path.join(tmp, "doc.tex")
    with open(root, "w", encoding="utf-8") as fh:
        fh.write(DOC)
    if pdf:
        with open(os.path.join(tmp, "doc.pdf"), "wb") as fh:
            fh.write(b"%PDF-1.7\nthe copy an earlier build left\n")
    if fls:
        with open(os.path.join(tmp, "doc.fls"), "w", encoding="utf-8") as fh:
            fh.write("INPUT doc.tex\n")
    return root


def drive(tmp, root, mode="base", lines=(), cancel_on_first_pass=False):
    """Run one build through the REAL runner and report what the viewer was
    told. Returns (result-dict, host).

      passes    engine invocations that actually ran
      state     the runner's verdict: ok / error / cancelled
      opened    on_success fired -- the post-build open + forward sync
      previews  base names the mid-build early preview offered
    """
    factory = PopenFactory(lines, log_dir=tmp)
    texlib.subprocess.Popen = factory
    cancel = threading.Event()
    result = {"state": None, "opened": False, "previews": [], "messages": []}

    def emit(text):
        result["messages"].append(text)
        if cancel_on_first_pass and "run 1" in text:
            cancel.set()

    host = texlib_build.TexlibBuild(
        tex_root=root, engine="pdflatex",
        options=["--texlib-mode=%s" % mode], display=emit,
        aux_directory="<<root>>",
    )
    host.preview_ready = lambda pdf: result["previews"].append(
        os.path.basename(pdf))
    entry = {"thread": None, "cancel": cancel, "procs": set()}
    texlib.TexlibBuildCommand()._drive(
        host, tmp, emit, cancel, "", root, entry,
        on_success=lambda: result.__setitem__("opened", True),
        on_finish=lambda s, e, w: result.__setitem__("state", s),
    )
    result["passes"] = len(factory.calls)
    return result, host


ok = True

# ---------------------------------------------------------------------------
# 1. Build outcome -> is the viewer touched at all?
#
# The contract Tier C states: a SUCCESSFUL build opens/refreshes the PDF. A
# build that failed must not, because the file beside the source is then either
# the stale copy from the last good build or a half-typeset one -- and putting
# either in front of the user, over the panel that just reported the error, says
# the opposite of what happened.
# ---------------------------------------------------------------------------
print("-- build outcome -> viewer --")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp)
    res, _ = drive(tmp, root, "base")
ok &= check(res["state"] == "ok" and res["opened"],
            "clean single-compile build -> the PDF is opened + forward-synced")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp, pdf=False)
    res, _ = drive(tmp, root, "base")
ok &= check(res["state"] == "ok" and not res["opened"],
            "clean build that produced no PDF -> nothing is opened")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp)
    res, _ = drive(tmp, root, "base", lines=[ERROR_LINE])
ok &= check(res["state"] == "error" and not res["opened"]
            and not res["previews"],
            "FAILED single-compile build -> the stale PDF is NOT opened")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp)
    res, _ = drive(tmp, root, "base", cancel_on_first_pass=True)
ok &= check(res["state"] == "cancelled" and not res["opened"],
            "cancelled build -> nothing is opened")

# The fan-out (`default'/`full' -- i.e. plain Ctrl+B) is the same question asked
# twice, because it is the only mode that offers a mid-build preview. The
# preview fires long before the runner has a verdict, so it reads the log.
with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp)
    res, _ = drive(tmp, root, "default", lines=[ERROR_LINE])
ok &= check(res["state"] == "error" and not res["opened"],
            "FAILED fan-out build -> the post-build open is withheld")
ok &= check(not res["previews"],
            "FAILED fan-out build -> the early preview is withheld too")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp, pdf=False)
    res, _ = drive(tmp, root, "default", lines=[ERROR_LINE])
ok &= check(not res["previews"],
            "FAILED fan-out build with no PDF at all -> still nothing to open")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp)
    res, _ = drive(tmp, root, "default")
ok &= check(res["previews"] == ["doc.pdf"] and res["opened"],
            "clean fan-out build -> one early preview, then the post-build open")

# ---------------------------------------------------------------------------
# 2. Reading the log: what counts as a failed compile
#
# Both of the questions below -- preview or not, stamp or not -- are answered
# from the log, and the answer used to be "scan for a leading bang". Every
# TeXLib pass carries -file-line-error, which writes the origin INSTEAD of the
# bang, so that scan matched nothing at all on a broken document.
# ---------------------------------------------------------------------------
print("\n-- reading the log --")


def _log(text):
    tmp = tempfile.mkdtemp(prefix="texlib_log_")
    path = os.path.join(tmp, "doc.log")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


BANNER = ("This is pdfTeX, Version 3.141592653-2.6-1.40.28 (TeX Live 2026) "
          "(preloaded format=pdflatex 2026.9.15)  15 SEP 2026 09:12\n"
          "entering extended mode\n"
          "(c:/texlive/2026/texmf-dist/tex/latex/base/article.cls\n"
          "Document Class: article 2025/01/01 v1.4n Standard LaTeX class\n"
          "Package: hyperref 2026-01-05 v7.01l\n"
          "LaTeX Font Info:    Trying to load font information on input line 5.\n"
          "LaTeX Warning: Reference `sec:x' on page 1 undefined on input line 9.\n")

ok &= check(not texlib_build.log_reports_error(_log(BANNER)),
            "log: banners, package lines and a warning are not errors")
ok &= check(texlib_build.log_reports_error(
                _log(BANNER + "./doc.tex:12: Undefined control sequence.\n")),
            "log: the -file-line-error form IS an error (the form TeXLib gets)")
ok &= check(texlib_build.log_reports_error(
                _log(BANNER + "./sub/chapter one.tex:4: LaTeX Error: x.\n")),
            "log: a path with a space still reads as an error")
ok &= check(texlib_build.log_reports_error(
                _log(BANNER + "! Undefined control sequence.\n")),
            "log: the classic bang form still reads as an error")
ok &= check(texlib_build.log_reports_error(_log(BANNER + "Emergency stop.\n")),
            "log: a fatal marker with no line number reads as an error")
ok &= check(not texlib_build.log_reports_error(
                os.path.join(HERE, "no-such-file.log")),
            "log: an absent log answers 'no error seen', not 'error'")

# ---------------------------------------------------------------------------
# 3. "Nothing changed" -> the build is skipped, the viewer is NOT
#
# The skip is documented to leave the viewer behavior alone: "the host
# opens/forward-syncs the viewer afterwards exactly as it would have". So a
# no-op build must still reach on_success -- what makes it a no-op is that no
# engine ran, not that the user is left looking at nothing.
# ---------------------------------------------------------------------------
print("\n-- nothing changed -> skip --")


def _build_then_rebuild(mode="base", env=None, lines=()):
    """Two builds of an untouched document. The first writes the freshness
    stamp; the second is the one under test."""
    old = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update(env or {})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = _seed(tmp, fls=True)
            first, _ = drive(tmp, root, mode, lines=lines)
            second, _ = drive(tmp, root, mode, lines=lines)
            return first, second
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


first, second = _build_then_rebuild()
ok &= check(first["passes"] == 1 and second["passes"] == 0,
            "unchanged rebuild -> not one engine pass runs")
ok &= check(second["state"] == "ok",
            "unchanged rebuild -> the verdict is ok, not an error")
ok &= check(second["opened"],
            "unchanged rebuild -> the PDF is STILL opened + forward-synced")
ok &= check(any("already current" in m for m in second["messages"]),
            "unchanged rebuild -> the panel says why nothing was rebuilt")
ok &= check(second["previews"] == [],
            "unchanged rebuild -> no early preview (there was no compile)")

# A FAILED build must never license the next one to be skipped. This is the
# expensive direction of the freshness check: a stamp written from a broken run
# hides the error entirely -- the rebuild does nothing, says "already current",
# and opens the stale PDF.
failed_first, after_failure = _build_then_rebuild(lines=[ERROR_LINE])
ok &= check(failed_first["state"] == "error",
            "failed build -> reported as an error, as ever")
ok &= check(after_failure["passes"] > 0,
            "rebuild after a FAILED build -> it really rebuilds, error and all")
ok &= check(after_failure["state"] == "error"
            and not any("already current" in m for m in after_failure["messages"]),
            "rebuild after a FAILED build -> the error comes back, not 'current'")

# The narrow cases the skip deliberately refuses, so the viewer question never
# even arises for them.
_, fan = _build_then_rebuild(mode="default")
ok &= check(fan["passes"] > 0,
            "the fan-out mode is never skipped, however fresh (Ctrl+B always builds)")
_, off = _build_then_rebuild(env={"TEXLIB_NO_FRESHNESS": "1"})
ok &= check(off["passes"] == 1, "TEXLIB_NO_FRESHNESS=1 disables the skip")

# ---------------------------------------------------------------------------
# 4. ...and WHICH PDF does a skipped build open?
#
# preferred_pdf decides. "combined" (the default) is a path and always resolved.
# "solutions"/"student" are resolved by SEARCHING what the build produced, so a
# skipped build -- which produces nothing -- has to recover that list from its
# stamp; otherwise it silently answers with the combined PDF, pulls the viewer
# off the slice, and _remember_preferred sends "TeXLib: View PDF" after it.
# ---------------------------------------------------------------------------
print("\n-- which PDF does a skipped build open? --")


def _pref(host, value):
    return os.path.basename(host.preferred_pdf_path(value))


def _host(root, mode="solutions"):
    return texlib_build.TexlibBuild(
        tex_root=root, engine="pdflatex",
        options=["--texlib-mode=%s" % mode], display=lambda t: None)


with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp, fls=True)
    with open(os.path.join(tmp, "doc.log"), "w", encoding="utf-8") as fh:
        fh.write("a clean pass\n")
    for name in ("doc_A_solutions.pdf", "doc_A.pdf"):
        with open(os.path.join(tmp, name), "wb") as fh:
            fh.write(b"%PDF-1.7\n")

    built = _host(root)
    built.produced_pdfs = ["doc_A_solutions.pdf", "doc_A.pdf"]
    ok &= check(_pref(built, "solutions") == "doc_A_solutions.pdf",
                "real build: preferred_pdf 'solutions' -> the solutions slice")
    ok &= check(_pref(built, "student") == "doc_A.pdf",
                "real build: preferred_pdf 'student' -> the student slice")

    built._stamp_freshness("pdflatex", "solutions", tmp)
    skipped = _host(root)
    ok &= check(skipped._skip_if_fresh("pdflatex", "solutions", tmp),
                "skip: the stamped document is judged current")
    ok &= check(_pref(skipped, "combined") == "doc.pdf",
                "skip: preferred_pdf 'combined' -> <base>.pdf, unchanged")
    ok &= check(_pref(skipped, "_A_solutions") == "doc_A_solutions.pdf",
                "skip: a LITERAL suffix preference resolves to its slice")
    ok &= check(_pref(skipped, "solutions") == "doc_A_solutions.pdf",
                "skip: preferred_pdf 'solutions' -> the slice, as when built")
    ok &= check(_pref(skipped, "student") == "doc_A.pdf",
                "skip: preferred_pdf 'student' -> the slice, as when built")

    # A slice deleted since the stamp was written is not conjured back.
    os.remove(os.path.join(tmp, "doc_A_solutions.pdf"))
    gone = _host(root)
    gone._skip_if_fresh("pdflatex", "solutions", tmp)
    ok &= check(_pref(gone, "solutions") == "doc.pdf",
                "skip: a slice deleted since the stamp falls back to <base>.pdf")

    # A stamp written before this field existed simply restores nothing -- the
    # stamp format is shared with the running installed copy of the plugin.
    texlib_freshness.write_stamp(os.path.join(tmp, "doc.pdf"),
                                 skipped._freshness_key("pdflatex", "solutions"))
    old_stamp = _host(root)
    ok &= check(old_stamp._skip_if_fresh("pdflatex", "solutions", tmp)
                and old_stamp.produced_pdfs == [],
                "skip: a stamp from an older version still skips, restoring nothing")

# ---------------------------------------------------------------------------
# 5. The early-preview contract itself
# ---------------------------------------------------------------------------
print("\n-- early preview contract --")

with tempfile.TemporaryDirectory() as tmp:
    root = _seed(tmp)
    host = _host(root, mode="default")
    seen = []
    host.preview_ready = seen.append
    host._offer_preview(tmp)
    ok &= check([os.path.basename(p) for p in seen] == ["doc.pdf"],
                "preview: the host hook is handed <base>.pdf by absolute path")

    # A .spl build replaces <base>.pdf with its two halves in _postprocess, so
    # previewing it would put up a file that is about to vanish.
    with open(os.path.join(tmp, "doc.spl"), "w", encoding="utf-8") as fh:
        fh.write("split\n")
    del seen[:]
    host._offer_preview(tmp)
    ok &= check(seen == [], "preview: declined for a .spl (split) build")
    os.remove(os.path.join(tmp, "doc.spl"))

    # No PDF to show -- the compile died before producing one.
    os.remove(os.path.join(tmp, "doc.pdf"))
    del seen[:]
    host._offer_preview(tmp)
    ok &= check(seen == [], "preview: declined when there is no PDF at all")

    # A viewer must never be able to fail a build.
    _seed(tmp)

    def _boom(pdf):
        raise RuntimeError("viewer exploded")

    host.preview_ready = _boom
    try:
        host._offer_preview(tmp)
        survived = True
    except Exception:  # noqa: BLE001
        survived = False
    ok &= check(survived, "preview: a throwing viewer hook does not fail the build")

# ---------------------------------------------------------------------------
# 6. What the viewer is actually told on a skipped build
#
# _post_build_view is reached with the same arguments a real build would use, so
# a no-op build forward-syncs Sumatra (jumpto_pdf) exactly as a real one does --
# the documented intent, and the reason the skip is invisible in normal use.
# ---------------------------------------------------------------------------
print("\n-- the command the viewer receives --")


class _FakeView:
    def __init__(self, path, text=""):
        self._path, self._text = path, text

    def file_name(self):
        return self._path

    def match_selector(self, point, selector):
        return False

    def size(self):
        return len(self._text)

    def substr(self, region):
        return self._text


class _FakeWindow:
    def __init__(self, active):
        self.active, self.commands = active, []

    def active_view(self):
        return self.active

    def run_command(self, name, args=None):
        self.commands.append((name, args or {}))


doc = os.path.join(HERE, "doc.tex")
doc_pdf = os.path.join(HERE, "doc.pdf")
slice_pdf = os.path.join(HERE, "doc_A_solutions.pdf")

win = _FakeWindow(_FakeView(doc))
texlib._post_build_view(win, doc, doc_pdf)
ok &= check(win.commands == [("latextools_jumpto_pdf", {})],
            "skip: the viewer is refreshed AND forward-synced, like a real build")

win = _FakeWindow(_FakeView(doc))
texlib._post_build_view(win, doc, slice_pdf)
ok &= check(win.commands == [("latextools_view_pdf", {"file": slice_pdf})],
            "a preferred slice is opened by path (jumpto_pdf cannot aim at one)")
ok &= check(texlib._recall_preferred(doc) is None,
            "a remembered slice that does not exist on disk is not recalled")

# The knock-on the section-4 restore exists to prevent: once a build has
# remembered the combined PDF, View PDF has no slice left to recall.
texlib._remember_preferred(doc, slice_pdf)
texlib._remember_preferred(doc, doc_pdf)
ok &= check(texlib._recall_preferred(doc) is None,
            "remembering <base>.pdf clears the slice View PDF would have reopened")

report(ok)
