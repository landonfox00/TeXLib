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

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_locate
except ImportError:
    import texlib_locate

# CREATE_NEW_CONSOLE: the server gets its own window showing "serving http://...
# (Ctrl+C to stop)", so it is visible and killable rather than an invisible orphan.
# The window starts MINIMIZED (STARTUPINFO SW_MINIMIZE) so it does not pop up over
# the editor or steal focus -- it just sits in the taskbar, still there to close.
_NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0
_SW_MINIMIZE = 6


def _minimized_console():
    """STARTUPINFO that opens the new console minimized (Windows), else None."""
    if os.name != "nt":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = _SW_MINIMIZE
    return si


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
        try:
            subprocess.Popen([py, script, exam], cwd=os.path.dirname(script),
                             creationflags=_NEW_CONSOLE,
                             startupinfo=_minimized_console())
        except OSError as exc:
            sublime.error_message("TeXLib: could not launch TeXam: %s" % exc)
            return
        sublime.status_message(
            "TeXLib: TeXam launching -- it opens in your browser "
            "(close its console window to stop).")

    def is_enabled(self):
        return texlib_locate._is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib TeXam launcher loaded.")
