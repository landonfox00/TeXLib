# texlib_bank_studio.py
# ============================================================================
# TeXLib -- launch the Bank Studio web app on the active exam.
#
#   TeXLib: Open Bank Studio   start bank_studio.py pointed at the active exam
#                              and open it in the browser: peruse the bank
#                              (problems rendered from LaTeX) and drop problems
#                              into the exam as \problem{...} lines written back
#                              into the .tex.
#
# Mirrors the Package-for-LMS shell-out (texlib_utils), but Bank Studio is a
# long-running local server, so we Popen it in its own console (Ctrl+C / close
# the window to stop) rather than run-and-report.
#
# bank_studio.py lives at the repo root, so it resolves with zero config from
# the class_source / repo root (like package_for_lms.py); an explicit
# `bank_studio_path` setting overrides for unusual layouts.
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
_NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0


def resolve_script(settings):
    """Locate bank_studio.py.

    An explicit `bank_studio_path` (a .py file or its containing directory) wins;
    otherwise fall back next to the other repo scripts (class_source, else two
    dirs above the package), matching texlib_utils._repo_root.
    """
    override = settings.get("bank_studio_path") if settings else None
    if override:
        if override.lower().endswith(".py"):
            return override
        return os.path.join(override, "bank_studio.py")
    root = settings.get("class_source") if settings else None
    if not root:
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        root = os.path.dirname(os.path.dirname(plugin_dir))
    return os.path.join(root, "bank_studio.py")


class TexlibOpenBankStudioCommand(sublime_plugin.WindowCommand):
    """Open Bank Studio pointed at the active exam document."""

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
                "TeXLib: bank_studio.py not found at\n%s\n\n"
                "Set \"bank_studio_path\" in TeXLib.sublime-settings to your "
                "bank_studio.py (or its folder), or point \"class_source\" at "
                "the TeXLib repo root." % script)
            return
        py = shutil.which("python") or shutil.which("python3") or shutil.which("py")
        if not py:
            sublime.error_message("TeXLib: no python found on PATH to run it.")
            return
        try:
            subprocess.Popen([py, script, exam], cwd=os.path.dirname(script),
                             creationflags=_NEW_CONSOLE)
        except OSError as exc:
            sublime.error_message("TeXLib: could not launch Bank Studio: %s" % exc)
            return
        sublime.status_message(
            "TeXLib: Bank Studio launching -- it opens in your browser "
            "(close its console window to stop).")

    def is_enabled(self):
        return texlib_locate._is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib Bank Studio launcher loaded.")
