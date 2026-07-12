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

import hashlib
import os
import re
import subprocess
import tempfile
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


def _aux_log_path(tex_root, base):
    """Absolute path of the build's <base>.log in the <<temp>> aux dir -- the same
    md5(tex_root)[:12] key texlib_build routes aux files to."""
    key = hashlib.md5((tex_root or "").encode("utf-8")).hexdigest()[:12]
    return os.path.join(tempfile.gettempdir(), "texlib-aux", key, base + ".log")


def _build_report(base, errors, warnings, log_path):
    """The condensed failure report: a header with counts, the clickable file:line
    errors, warnings (capped), and a clickable full-log link. Error and log lines
    are unprefixed `path:line: msg` so result_file_regex makes them jump."""
    out = ["", "==== TeXLib: %s -- %d error(s), %d warning(s) ===="
           % (base, len(errors), len(warnings)), ""]
    out.extend(errors)
    shown = warnings[:MAX_WARNINGS]
    if shown:
        out.append("")
        out.extend(shown)
        if len(warnings) > MAX_WARNINGS:
            out.append("... (%d more)" % (len(warnings) - MAX_WARNINGS))
    if log_path:
        out += ["", "%s:1: [full build log -- double-click to open]" % log_path]
    return "\n".join(out) + "\n"

PROGRAM_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+program\s*=\s*(\S+)")
ROOT_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+root\s*=\s*(.+?)\s*$")

# Concurrent builds, one registry entry per tex-root: distinct documents build
# in parallel; a second build of the SAME document is refused. Each entry owns
# its thread/cancel/proc/panel so cancel targeting and the aux env stay per-build
# -- there is NO global TEXLIB_AUX_DIR to race (the runner injects each build's
# own _aux_target into that build's subprocess env instead; see _run_argv).
_builds = {}                    # root_path -> {"thread","cancel","proc","panel"}
_builds_lock = threading.Lock()


def _build_active(root):
    """True if a build for `root` is currently running."""
    with _builds_lock:
        e = _builds.get(root)
        return bool(e and e["thread"] and e["thread"].is_alive())


def _panel_name(root):
    """A per-document output-panel name so concurrent builds don't share one."""
    return "texlib_" + hashlib.md5((root or "").encode("utf-8")).hexdigest()[:8]


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
def _panel(window, root, base_dir):
    """Create (but do NOT show) this build's own output panel (named per tex-root
    so concurrent builds each stream to their own). Visibility is decided by the
    show_panel_on_build setting: shown during the build only in 'always' mode,
    and at the end only if the build failed."""
    panel = window.create_output_panel(_panel_name(root))
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


def _show_panel(window, root):
    window.run_command("show_panel", {"panel": "output." + _panel_name(root)})


def _hide_panel(window, root):
    """Hide this build's panel, but only if it's the one currently showing."""
    if window.active_panel() == "output." + _panel_name(root):
        window.run_command("hide_panel")


# --- Live status-bar progress (spinner + current step) -----------------------
# One main-thread ticker animates a status-bar spinner for EVERY running build.
# Each build's registry entry carries its own view / base / current step, so
# concurrent builds animate independently on the view that launched them (with a
# "(+N more building)" tail); a finished build is popped from _builds, so the
# ticker stops touching its view. The ticker reschedules only while builds run.
SPIN_FRAMES = "⣾⣽⣻⢿⡿⣟⣯⣷"  # braille spinner
_spin_on = [False]


def _status_line(frame, base, step, n_running):
    """Compose one build's status-bar line: spinner frame, base name, current
    step, and a "(+N more building)" tail when several builds run at once.
    Pure (no Sublime) so it's unit-tested headlessly."""
    ch = SPIN_FRAMES[frame % len(SPIN_FRAMES)]
    extra = "   (+%d more building)" % (n_running - 1) if n_running > 1 else ""
    return "%s  TeXLib: %s — %s%s" % (ch, base, (step or "starting…")[:70], extra)


def _spin_tick():
    with _builds_lock:
        entries = [e for e in _builds.values()
                   if e.get("thread") and e["thread"].is_alive()]
    if not entries:
        _spin_on[0] = False
        return
    n = len(entries)
    for e in entries:
        view = e.get("view")
        if view is None:
            continue
        f = e.get("frame", 0)
        e["frame"] = f + 1
        view.set_status("texlib_build",
                        _status_line(f, e.get("base", ""), e.get("step"), n))
    sublime.set_timeout(_spin_tick, 110)


def _spin_ensure():
    """Start the shared status-bar ticker if it isn't already running."""
    if not _spin_on[0]:
        _spin_on[0] = True
        sublime.set_timeout(_spin_tick, 0)


# --- Engine runner (the new surface: async, streamed, cancellable) -----------
def _run_argv(cmd, cwd, emit, cancel, texinputs, aux_dir, entry):
    """Run one engine/biber command; stream combined output via `emit`; return
    the full captured text (fed back to the brain as self.out for rerun/biber
    detection). The aux dir is injected into THIS subprocess's own env (never a
    global os.environ), so concurrent builds of different documents can't race a
    shared TEXLIB_AUX_DIR -- each engine gets its own build's aux dir. proc is
    parked on this build's registry `entry` so cancel reaches the right process."""
    env = dict(os.environ)
    if texinputs:
        env["TEXINPUTS"] = texinputs
    env["TEXLIB_AUX_DIR"] = aux_dir or ""
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
    entry["proc"] = proc
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
        entry["proc"] = None
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
        if _build_active(root):
            sublime.status_message(
                "TeXLib: a build for %s is already running." % os.path.basename(root))
            return
        engine = _raw_engine(src)
        tex_dir = os.path.dirname(root)

        panel = _panel(self.window, root, tex_dir)
        window = self.window
        base = os.path.basename(root)
        log_path = _aux_log_path(root, base)

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
            sublime.set_timeout(lambda: _show_panel(window, root), 0)
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
                        _echo(panel, _build_report(
                            base, error_lines, warning_lines, log_path))
                        _show_panel(window, root)
                else:  # ok
                    nwarn = len(warning_lines)
                    if nwarn:
                        # Success-with-warnings: report the count, and DON'T
                        # silently swallow them -- populate this build's panel
                        # with a warnings-only report so "Show Build Output" has
                        # something useful (we don't steal focus by popping it on
                        # a successful build).
                        view.set_status(
                            "texlib_build",
                            "TeXLib: built %s — %d warning(s)" % (base, nwarn))
                        if show_mode == "errors":
                            _echo(panel, _build_report(
                                base, [], warning_lines, log_path))
                    else:
                        view.set_status("texlib_build", "TeXLib: built %s" % base)
                        if show_mode != "always":
                            _hide_panel(window, root)
                sublime.set_timeout(
                    lambda: view.erase_status("texlib_build"),
                    8000 if state == "error" else 4000)
            sublime.set_timeout(apply, 0)

        cancel = threading.Event()
        entry = {"thread": None, "cancel": cancel, "proc": None,
                 "panel": _panel_name(root), "view": view, "base": base,
                 "step": None, "frame": 0}
        th = threading.Thread(
            target=self._drive,
            args=(host, tex_dir, emit, cancel, texinputs, root, entry,
                  on_success, on_finish),
        )
        th.daemon = True
        entry["thread"] = th
        # Register atomically, replacing any finished entry for this root. The
        # _build_active guard above already refused a still-running same-doc build.
        with _builds_lock:
            _builds[root] = entry
        th.start()
        _spin_ensure()  # animate the status bar until this (and any peer) build ends

    def is_enabled(self):
        return _is_tex(self.window.active_view())

    def _drive(self, host, tex_dir, emit, cancel, texinputs, root, entry,
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
                entry["step"] = msg.rstrip(". …")  # current step for the spinner
                emit(msg + "\n")
                host.out = _run_argv(cmd, tex_dir, collect, cancel, texinputs,
                                     getattr(host, "_aux_target", None), entry)
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
            with _builds_lock:
                _builds.pop(root, None)
        if state == "ok" and on_success:
            if os.path.exists(os.path.join(tex_dir, host.base_name + ".pdf")):
                on_success()
        if on_finish:
            on_finish(state, error_lines, warning_lines)


def _kill_entry(entry):
    if entry.get("cancel"):
        entry["cancel"].set()
    proc = entry.get("proc")
    if proc:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


class TexlibCancelBuildCommand(sublime_plugin.WindowCommand):
    """Cancel the build for the ACTIVE document. Different documents build
    concurrently, so this targets only the active view's build; use "Cancel All
    Builds" to stop every running build at once."""

    def _root(self):
        view = self.window.active_view()
        root, _ = _resolve_root(view) if view else (None, "")
        return root

    def run(self):
        root = self._root()
        with _builds_lock:
            entry = _builds.get(root)
        if not entry:
            sublime.status_message("TeXLib: no build running for this document.")
            return
        _kill_entry(entry)
        sublime.status_message("TeXLib: cancelling build...")

    def is_enabled(self):
        return _build_active(self._root())


class TexlibCancelAllBuildsCommand(sublime_plugin.WindowCommand):
    """Cancel every running native build."""

    def run(self):
        with _builds_lock:
            entries = list(_builds.values())
        for entry in entries:
            _kill_entry(entry)
        sublime.status_message("TeXLib: cancelling all builds...")

    def is_enabled(self):
        with _builds_lock:
            return any(e["thread"] and e["thread"].is_alive()
                       for e in _builds.values())


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


class TexlibBuildStatusCommand(sublime_plugin.WindowCommand):
    """List every running native build and its current step (parallel builds)."""

    def run(self):
        with _builds_lock:
            rows = [(e.get("base", os.path.basename(r)), e.get("step") or "starting…")
                    for r, e in _builds.items()
                    if e.get("thread") and e["thread"].is_alive()]
        if not rows:
            sublime.status_message("TeXLib: no builds running.")
            return
        items = [[b, "current step: %s" % s] for (b, s) in rows]
        self.window.show_quick_panel(items, lambda i: None)


class TexlibShowOutputCommand(sublime_plugin.WindowCommand):
    """Show the output panel for the active document's build (running or last).
    Makes the success-with-warnings report reachable without stealing focus."""

    def run(self):
        view = self.window.active_view()
        root, _ = _resolve_root(view) if view else (None, "")
        if not root:
            sublime.status_message("TeXLib: no document.")
            return
        self.window.run_command(
            "show_panel", {"panel": "output." + _panel_name(root)})

    def is_enabled(self):
        return _is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib native plugin loaded (build + LaTeXTools delegation).")
