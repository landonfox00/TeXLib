# texlib.py
# ============================================================================
# TeXLib -- native Sublime Text plugin (Phase 1: real build).
#
# The "complement, not replace" plugin from Sublime/PLUGIN-DESIGN.md. This file
# is the HOST: it resolves the build target, then drives texlib_build.TexlibBuild
# -- the host-agnostic build brain ported from the LaTeXTools builder -- running
# each yielded engine command itself and streaming output to its own panel. It
# replaces LaTeXTools' PdfBuilder host; nothing here needs LaTeXTools to build.
#
# Still coexists with the LaTeXTools "texlib" builder: it binds no default key
# and touches no Packages/User file, so both build paths work until Phase 2.
#
# Deploy: junction to Packages/TeXLib via deploy-plugin.ps1. texlib.py hot-reloads
# on save; editing texlib_build.py (an imported helper) still needs a restart.
# ============================================================================

import os
import re
import subprocess
import threading

import sublime
import sublime_plugin

# The brain. Deployed as Packages/TeXLib, so the intra-package import is by that
# name; fall back to a bare import (tests / a differently-named package dir).
try:
    from TeXLib import texlib_build
except ImportError:
    import texlib_build

# CREATE_NO_WINDOW: we own the engine's Popen, so we suppress the Windows console
# flash directly -- no need for the builder's LaTeXTools-internal monkeypatch.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Build modes: (token, caption, blurb). The token rides the options channel as
# --texlib-mode=<token>, which the brain's _extract_mode maps to the TeXLib flag.
MODES = [
    ("default", "Default", "No \\Show... flag."),
    ("key", "Answer Key", "Injects \\def\\ShowKey{}."),
    ("solutions", "Solutions", "Injects \\def\\ShowSolutions{}."),
    ("student", "Student Copy", "Injects \\def\\StudentMode{}."),
    ("rubric", "Rubric", "Injects \\def\\ShowRubric{}."),
    ("draft", "Draft", "Injects \\def\\ShowDraft{}."),
    ("quick", "Quick (single pass)", "One pass, no biber, no reruns."),
]
MODE_TOKENS = {m[0] for m in MODES}

# file:line:col: message -- matches -file-line-error output (PLUGIN-DESIGN Risk
# #1), identical to the current TeXLib.sublime-build windows file_regex.
RESULT_FILE_REGEX = r"^((?:.:)?[^:\n\r]*):([0-9]+):?([0-9]+)?:? (.*)$"

PROGRAM_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+program\s*=\s*(\S+)")
ROOT_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+root\s*=\s*(.+?)\s*$")

# One build at a time; the cancel command reaches the live thread/process here.
_active = {"thread": None, "cancel": None, "proc": None}


# --- Target resolution -------------------------------------------------------
def _is_tex(view):
    if view is None:
        return False
    if view.match_selector(0, "text.tex.latex"):
        return True
    name = view.file_name() or ""
    return name.lower().endswith((".tex", ".cls", ".sty"))


def _resolve_root(view):
    """(root_path, source_text). Honors a leading `%!TeX root =`; else the file
    is its own root. Reads the live buffer so an unsaved magic comment resolves."""
    fname = view.file_name()
    if not fname:
        return None, ""
    src = view.substr(sublime.Region(0, view.size()))
    m = ROOT_RE.search(src[:1024])
    if m:
        root = os.path.normpath(os.path.join(os.path.dirname(fname), m.group(1)))
        try:
            with open(root, encoding="utf-8", errors="replace") as fh:
                return root, fh.read()
        except OSError:
            return root, src
    return fname, src


def _raw_engine(src):
    """The %!TeX program engine, or pdflatex. NO lua-class force here -- the brain
    owns that (its _select_engine), so forcing stays a single source of truth."""
    m = PROGRAM_RE.search(src)
    return m.group(1).strip().lower() if m else "pdflatex"


# --- Output panel ------------------------------------------------------------
def _panel(window):
    panel = window.create_output_panel("texlib")
    s = panel.settings()
    s.set("result_file_regex", RESULT_FILE_REGEX)
    s.set("word_wrap", False)
    s.set("line_numbers", False)
    s.set("scroll_past_end", False)
    window.run_command("show_panel", {"panel": "output.texlib"})
    return panel


def _echo(panel, text):
    panel.run_command(
        "append", {"characters": text, "force": True, "scroll_to_end": True}
    )


# --- Engine runner (the new surface: async, streamed, cancellable) -----------
def _run_argv(cmd, cwd, emit, cancel, texinputs):
    """Run one engine/biber command; stream combined output via `emit`; return
    the full captured text (fed back to the brain as self.out for rerun/biber
    detection). Reads os.environ fresh so the brain's TEXLIB_AUX_DIR (set inside
    commands() before the first yield) is inherited by the child."""
    env = dict(os.environ)
    if texinputs:
        env["TEXINPUTS"] = texinputs
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=_NO_WINDOW,
        )
    except Exception as exc:  # noqa: BLE001 - surface launch failures to the panel
        emit("TeXLib: failed to launch %s: %s\n" % (cmd[0], exc))
        return ""
    _active["proc"] = proc
    chunks = []
    try:
        for line in proc.stdout:
            chunks.append(line)
            emit(line)
            if cancel.is_set():
                proc.kill()
                break
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:  # noqa: BLE001
            pass
        proc.wait()
        _active["proc"] = None
    return "".join(chunks)


class TexlibBuildCommand(sublime_plugin.WindowCommand):
    """Native TeXLib build. Palette: "TeXLib: Build ..."; arg {"mode": "<token>"}."""

    def run(self, mode="default"):
        t = _active.get("thread")
        if t and t.is_alive():
            sublime.status_message("TeXLib: a build is already running.")
            return
        view = self.window.active_view()
        if not _is_tex(view):
            sublime.status_message("TeXLib: not a LaTeX document.")
            return
        if mode not in MODE_TOKENS:
            sublime.error_message("TeXLib: unknown build mode %r." % mode)
            return
        if view.is_dirty():
            view.run_command("save")  # the engine reads the file from disk
        root, src = _resolve_root(view)
        if not root:
            sublime.error_message("TeXLib: save the document before building.")
            return
        engine = _raw_engine(src)
        tex_dir = os.path.dirname(root)

        panel = _panel(self.window)

        def emit(text):
            sublime.set_timeout(lambda t=text: _echo(panel, t), 0)

        # Optional TEXINPUTS: real cross-package builds need the repo root on the
        # path (comma-free junction). Resolved on the main thread; blank inherits.
        settings = sublime.load_settings("TeXLib.sublime-settings")
        texinputs = settings.get("texinputs") or ""
        if isinstance(texinputs, list):
            texinputs = os.pathsep.join(texinputs)

        host = texlib_build.TexlibBuild(
            tex_root=root, engine=engine,
            options=["--texlib-mode=%s" % mode], display=emit,
        )
        # Publish toggles: the native host has no LaTeXTools builder_settings, so
        # feed the sublime settings in (the brain's _setting_on reads them first,
        # else falls back to the TEXLIB_PUBLISH* env vars). Lets a tester set
        # "publish_shareable_copies": false to stop the desktop-shortcut clutter.
        toggles = {}
        for _k in ("publish_shareable_copies", "copy_published_path_to_clipboard"):
            _v = settings.get(_k)
            if _v is not None:
                toggles[_k] = _v
        if toggles:
            host.builder_settings = toggles
        emit("TeXLib native build [%s] -- %s\n" % (mode, os.path.basename(root)))
        cancel = threading.Event()
        _active["cancel"] = cancel
        th = threading.Thread(
            target=self._drive, args=(host, tex_dir, emit, cancel, texinputs)
        )
        th.daemon = True
        _active["thread"] = th
        th.start()

    def is_enabled(self):
        return _is_tex(self.window.active_view())

    def _drive(self, host, tex_dir, emit, cancel, texinputs):
        """Consume the brain's commands() coroutine: run each yielded argv, feed
        its output back via host.out, resume. _postprocess runs inside commands()
        at the end, so reaching StopIteration means the build is fully done."""
        gen = host.commands()
        try:
            item = next(gen)
            while True:
                cmd, msg = item
                emit(msg + "\n")
                host.out = _run_argv(cmd, tex_dir, emit, cancel, texinputs)
                if cancel.is_set():
                    emit("TeXLib: build cancelled.\n")
                    return
                item = next(gen)
        except StopIteration:
            pass
        except Exception as exc:  # noqa: BLE001 - never let the worker die silently
            emit("TeXLib: build driver error: %s\n" % exc)
        finally:
            _active["thread"] = None
            _active["cancel"] = None


class TexlibCancelBuildCommand(sublime_plugin.WindowCommand):
    """Cancel the running native build (signals the loop and kills the process)."""

    def run(self):
        cancel = _active.get("cancel")
        if cancel:
            cancel.set()
        proc = _active.get("proc")
        if proc:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        sublime.status_message("TeXLib: cancelling build...")

    def is_enabled(self):
        t = _active.get("thread")
        return bool(t and t.is_alive())


class TexlibBuildPickCommand(sublime_plugin.WindowCommand):
    """Quick-panel mode picker -> dispatches to texlib_build."""

    def run(self):
        items = [[cap, blurb] for (_tok, cap, blurb) in MODES]

        def on_done(i):
            if i >= 0:
                self.window.run_command("texlib_build", {"mode": MODES[i][0]})

        self.window.show_quick_panel(items, on_done)

    def is_enabled(self):
        return _is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib native plugin loaded (Phase 1: build runner).")
