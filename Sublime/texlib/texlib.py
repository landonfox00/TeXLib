# texlib.py
# ============================================================================
# TeXLib -- native Sublime Text plugin (build + LaTeXTools delegation).
#
# The "complement, not replace" plugin from Sublime/PLUGIN-DESIGN.md. This file
# is the HOST: it resolves the build target, then drives texlib_build.TexlibBuild
# -- the host-agnostic build brain ported from the LaTeXTools builder -- running
# each yielded engine command itself and streaming output to its own panel. It
# replaces LaTeXTools' PdfBuilder host; nothing here needs LaTeXTools to build.
#
# For the editor smarts we DON'T rebuild (Tier C), we delegate to LaTeXTools via
# run_command: a successful build opens/refreshes + forward-syncs the PDF, and
# TexlibViewPdf / TexlibForwardSync expose those on demand. LaTeXTools stays a
# companion we call by stable command name, not a base class we subclass.
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
RESULT_RE = re.compile(RESULT_FILE_REGEX)
# A build failed if it emits a file:line error OR one of these fatal markers
# (which may lack a line number).
FATAL_RE = re.compile(r"^!\s|! LaTeX Error|Emergency stop|Fatal error")
# LaTeX / package warnings, for the condensed report (over/underfull boxes are
# deliberately excluded -- too noisy to be useful).
WARNING_RE = re.compile(r"\bWarning:")
MAX_WARNINGS = 30

# Syntax that colors the panel (errors red, warnings, headers). Resource path;
# best-effort -- a missing/renamed package just leaves the panel uncolored.
BUILD_SYNTAX = "Packages/TeXLib/TeXLib Build Output.sublime-syntax"


def _build_report(base, errors, warnings):
    """The condensed failure report written to the panel: a header with counts,
    the clickable file:line errors, then warnings (capped), then a full-log
    pointer. Kept file:line lines unprefixed so result_file_regex still matches."""
    out = ["", "==== TeXLib: %s -- %d error(s), %d warning(s) ===="
           % (base, len(errors), len(warnings)), ""]
    out.extend(errors)
    shown = warnings[:MAX_WARNINGS]
    if shown:
        out.append("")
        out.extend(shown)
        if len(warnings) > MAX_WARNINGS:
            out.append("... (%d more)" % (len(warnings) - MAX_WARNINGS))
    out += ["", "(full log: run  TeXLib: Reveal Aux Directory)"]
    return "\n".join(out) + "\n"

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
def _panel(window, base_dir):
    """Create (but do NOT show) the build panel. Visibility is decided by the
    show_panel_on_build setting: shown during the build only in 'always' mode,
    and at the end only if the build failed."""
    panel = window.create_output_panel("texlib")
    s = panel.settings()
    s.set("result_file_regex", RESULT_FILE_REGEX)
    # The engine emits relative paths (./exam-01.tex:14:) under -file-line-error;
    # without a base dir Sublime can't resolve them, so clicking wouldn't jump.
    s.set("result_base_dir", base_dir)
    s.set("word_wrap", False)
    s.set("line_numbers", False)
    s.set("scroll_past_end", False)
    try:
        panel.assign_syntax(BUILD_SYNTAX)
    except Exception:  # noqa: BLE001 - coloring is best-effort
        pass
    return panel


def _echo(panel, text):
    panel.run_command(
        "append", {"characters": text, "force": True, "scroll_to_end": True}
    )


def _show_panel(window):
    window.run_command("show_panel", {"panel": "output.texlib"})


def _hide_panel(window):
    """Hide the TeXLib panel, but only if it's the one currently showing."""
    if window.active_panel() == "output.texlib":
        window.run_command("hide_panel")


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


# --- Delegation to LaTeXTools (Tier C: complement, don't rebuild) ------------
def _delegate(window, command, args=None):
    """Invoke a LaTeXTools editor command by name. A silent no-op if LaTeXTools
    isn't installed (Sublime ignores an unknown command_name) -- the graceful
    degradation we want: the plugin still builds; only the editor extras rest on
    the companion package."""
    window.run_command(command, args or {})


def _post_build_view(window):
    """After a successful build, open/refresh the PDF and forward-sync via
    LaTeXTools' jumpto_pdf (which honors its own forward_sync / keep_focus
    settings, and falls back to the PDF next to the source -- where our copy-back
    puts it). Gated by the TeXLib open_pdf_on_build setting (default on)."""
    settings = sublime.load_settings("TeXLib.sublime-settings")
    if not settings.get("open_pdf_on_build", True):
        return
    _delegate(window, "latextools_jumpto_pdf")


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

        panel = _panel(self.window, tex_dir)
        window = self.window
        base = os.path.basename(root)

        settings = sublime.load_settings("TeXLib.sublime-settings")
        # Panel visibility, LaTeXTools-style: 'errors' (default) surfaces the panel
        # only on failure, as a condensed report; 'always' streams the raw log
        # live; 'never' keeps it hidden (status bar only).
        show_mode = (settings.get("show_panel_on_build") or "errors").lower()
        show_raw = show_mode == "always"

        def emit(text):
            # Only stream to the panel in 'always' mode; 'errors'/'never' collect
            # quietly and write a condensed report at the end (see on_finish).
            if show_raw:
                sublime.set_timeout(lambda t=text: _echo(panel, t), 0)

        if show_raw:
            sublime.set_timeout(lambda: _show_panel(window), 0)
        view.set_status("texlib_build", "TeXLib: building %s..." % base)

        # Optional TEXINPUTS: real cross-package builds need the repo root on the
        # path (comma-free junction). Resolved on the main thread; blank inherits.
        texinputs = settings.get("texinputs") or ""
        if isinstance(texinputs, list):
            texinputs = os.pathsep.join(texinputs)

        host = texlib_build.TexlibBuild(
            tex_root=root, engine=engine,
            options=["--texlib-mode=%s" % mode], display=emit,
        )
        # Publish toggles: the native host has no LaTeXTools builder_settings, so
        # feed the sublime settings in (the brain's _setting_on reads them first,
        # else falls back to the TEXLIB_PUBLISH* env vars).
        toggles = {}
        for _k in ("publish_shareable_copies", "copy_published_path_to_clipboard"):
            _v = settings.get(_k)
            if _v is not None:
                toggles[_k] = _v
        if toggles:
            host.builder_settings = toggles
        emit("TeXLib native build [%s] -- %s\n" % (mode, base))

        def on_success():
            # Post-build PDF open + forward sync (Tier C).
            sublime.set_timeout(lambda: _post_build_view(window), 0)

        def on_finish(state, error_lines, warning_lines):
            # Runs in the worker; marshal all UI changes to the main thread.
            def apply():
                if state == "cancelled":
                    view.set_status("texlib_build", "TeXLib: build cancelled.")
                elif state == "error":
                    view.set_status(
                        "texlib_build", "TeXLib: build failed -- %d error(s)"
                        % (len(error_lines) or 1))
                    if show_mode != "never":
                        # Condensed, colored report. In 'errors' mode the panel
                        # was otherwise empty; in 'always' this appends after the
                        # streamed raw log.
                        _echo(panel, _build_report(base, error_lines, warning_lines))
                        _show_panel(window)
                else:  # ok
                    view.set_status("texlib_build", "TeXLib: built %s" % base)
                    if show_mode != "always":
                        _hide_panel(window)
                sublime.set_timeout(
                    lambda: view.erase_status("texlib_build"),
                    8000 if state == "error" else 4000)
            sublime.set_timeout(apply, 0)

        cancel = threading.Event()
        _active["cancel"] = cancel
        th = threading.Thread(
            target=self._drive,
            args=(host, tex_dir, emit, cancel, texinputs, on_success, on_finish),
        )
        th.daemon = True
        _active["thread"] = th
        th.start()

    def is_enabled(self):
        return _is_tex(self.window.active_view())

    def _drive(self, host, tex_dir, emit, cancel, texinputs,
               on_success=None, on_finish=None):
        """Consume the brain's commands() coroutine: run each yielded argv, feed
        its output back via host.out, resume, collecting file:line errors from the
        stream to classify the outcome (ok / error / cancelled). _postprocess runs
        inside commands(), so reaching StopIteration means the build is done."""
        gen = host.commands()
        error_lines = []
        warning_lines = []
        fatal = [False]

        def collect(line):
            emit(line)
            s = line.rstrip("\r\n")
            m = RESULT_RE.match(s)
            if m:
                fatal[0] = True
                # Source-file errors are the actionable ones; skip generated .aux.
                if not m.group(1).lower().endswith(".aux"):
                    error_lines.append(s)
            elif FATAL_RE.search(s):
                fatal[0] = True
            elif WARNING_RE.search(s) and len(warning_lines) < 500:
                warning_lines.append(s)

        state = "error"
        try:
            item = next(gen)
            while True:
                cmd, msg = item
                emit(msg + "\n")
                host.out = _run_argv(cmd, tex_dir, collect, cancel, texinputs)
                if cancel.is_set():
                    emit("TeXLib: build cancelled.\n")
                    state = "cancelled"
                    break
                item = next(gen)
        except StopIteration:
            state = "error" if fatal[0] else "ok"
        except Exception as exc:  # noqa: BLE001 - never let the worker die silently
            emit("TeXLib: build driver error: %s\n" % exc)
            state = "error"
        finally:
            _active["thread"] = None
            _active["cancel"] = None
        if state == "ok" and on_success:
            if os.path.exists(os.path.join(tex_dir, host.base_name + ".pdf")):
                on_success()
        if on_finish:
            on_finish(state, error_lines, warning_lines)


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


class TexlibViewPdfCommand(sublime_plugin.WindowCommand):
    """Open/refresh the built PDF in the configured viewer (delegates to LaTeXTools)."""

    def run(self):
        _delegate(self.window, "latextools_view_pdf")

    def is_enabled(self):
        return _is_tex(self.window.active_view())


class TexlibForwardSyncCommand(sublime_plugin.WindowCommand):
    """Jump from the cursor to the matching place in the PDF (delegates to
    LaTeXTools' jumpto_pdf; from_keybinding forces the forward sync)."""

    def run(self):
        _delegate(self.window, "latextools_jumpto_pdf", {"from_keybinding": True})

    def is_enabled(self):
        return _is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib native plugin loaded (build + LaTeXTools delegation).")
