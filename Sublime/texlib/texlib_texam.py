# texlib_texam.py
# ============================================================================
# TeXLib -- launch the TeXam web app on the active exam.
#
#   TeXLib: Open TeXam   start texam.py pointed at the active exam
#                              and open it in the browser: peruse the bank
#                              (problems rendered from LaTeX) and drop problems
#                              into the exam as \problem{...} lines written back
#                              into the .tex.
#
# Mirrors the Package-for-LMS shell-out (texlib_utils), but TeXam is a
# long-running local server, so we Popen it in its own console (Ctrl+C / close
# the window to stop) rather than run-and-report.
#
# texam.py lives at the repo root, so it resolves with zero config from
# the class_source / repo root (like package_for_lms.py); an explicit
# `texam_path` setting overrides for unusual layouts.
#
# Own top-level file (hot-reloads alone).
# ============================================================================

import os
import shutil
import subprocess
import tempfile

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_locate
except ImportError:
    import texlib_locate

# No console at all: launch via pythonw.exe (windowless Python) when available,
# with CREATE_NO_WINDOW as a backstop -- no popup, no taskbar window, no focus
# steal. It cleans itself up rather than orphaning: the page pings to keep it
# alive and auto-quits ~5 min after the tab closes, plus a Quit button stops it
# immediately. Output goes to a log (python -u) so a startup error is recoverable.
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_LAUNCH_LOG = os.path.join(tempfile.gettempdir(), "texam-launch.log")


def resolve_script(settings):
    """Locate texam.py.

    An explicit `texam_path` (a .py file or its containing directory) wins;
    otherwise fall back next to the other repo scripts (class_source, else two
    dirs above the package), matching texlib_utils._repo_root.
    """
    override = settings.get("texam_path") if settings else None
    if override:
        if override.lower().endswith(".py"):
            return override
        return os.path.join(override, "texam.py")
    root = settings.get("class_source") if settings else None
    if not root:
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        root = os.path.dirname(os.path.dirname(plugin_dir))
    return os.path.join(root, "texam.py")


class TexlibOpenTexamCommand(sublime_plugin.WindowCommand):
    """Open TeXam pointed at the active exam document."""

    def run(self):
        view = self.window.active_view()
        exam = texlib_locate._tex_root(view) if view else None
        if not exam:
            sublime.status_message("TeXLib: save the exam document first.")
            return
        # Save first (like Ctrl+B) so TeXaM opens on the CURRENT text, not a stale
        # on-disk copy: the active buffer, plus the resolved %!TeX root view if it
        # is a different open file. A titled+dirty view saves silently; the second
        # pass is a no-op once the first has cleared the dirty flag.
        for v in (view, self.window.find_open_file(exam)):
            if v is not None and v.file_name() and v.is_dirty():
                v.run_command("save")
        settings = sublime.load_settings("TeXLib.sublime-settings")
        script = resolve_script(settings)
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: texam.py not found at\n%s\n\n"
                "Set \"texam_path\" in TeXLib.sublime-settings to your "
                "texam.py (or its folder), or point \"class_source\" at "
                "the TeXLib repo root." % script)
            return
        py = shutil.which("python") or shutil.which("python3") or shutil.which("py")
        if not py:
            sublime.error_message("TeXLib: no python found on PATH to run it.")
            return
        # Prefer pythonw.exe (the windowless Python) so there is genuinely NO
        # console -- the definitive fix on Windows; CREATE_NO_WINDOW stays as a
        # belt-and-suspenders. Fall back to python.exe if pythonw isn't beside it.
        if os.name == "nt":
            pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
            if os.path.isfile(pyw):
                py = pyw
        try:
            log = open(_LAUNCH_LOG, "ab")            # child dups the fd; safe to close after
            subprocess.Popen([py, "-u", script, exam], cwd=os.path.dirname(script),
                             creationflags=_CREATE_NO_WINDOW,
                             stdout=log, stderr=subprocess.STDOUT)   # -u: live log
            log.close()
        except OSError as exc:
            sublime.error_message("TeXLib: could not launch TeXam: %s" % exc)
            return
        sublime.status_message(
            "TeXLib: TeXam launching -- it opens in your browser "
            "(use the Quit button there to stop it).")

    def is_enabled(self):
        return texlib_locate._is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib TeXam launcher loaded.")
