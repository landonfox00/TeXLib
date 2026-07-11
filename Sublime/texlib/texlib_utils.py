# texlib_utils.py
# ============================================================================
# TeXLib -- small build-adjacent utility commands.
#
#   TeXLib: Clean Aux Directory   delete the %TEMP%\texlib-aux\<hash> dir for the
#                                 active document (force a from-scratch rebuild).
#   TeXLib: Package for LMS        run package_for_lms.py on the active document's
#                                 course (bundles the built Syllabus.pdf +
#                                 Tentative Schedule.pdf into a zip).
#
# Own top-level file (hot-reloads alone). Reuses texlib_locate for the aux-dir
# resolution (same hash the build uses).
# ============================================================================

import os
import shutil
import subprocess
import threading

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_locate
except ImportError:
    import texlib_locate

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _repo_root(settings):
    """Where package_for_lms.py lives: the class_source setting (repo root) if
    set, else the repo root two dirs above the package."""
    override = settings.get("class_source")
    if override:
        return override
    plugin_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.dirname(os.path.dirname(plugin_dir))


class TexlibCleanAuxCommand(sublime_plugin.WindowCommand):
    """Delete the aux directory the build routes this document's aux files to."""

    def run(self):
        root = texlib_locate._tex_root(self.window.active_view())
        if not root:
            sublime.status_message("TeXLib: save the document first.")
            return
        auxdir = texlib_locate.aux_dir_for(root)
        if not os.path.isdir(auxdir):
            sublime.status_message(
                "TeXLib: no aux directory to clean for this document.")
            return
        n = sum(len(files) for _, _, files in os.walk(auxdir))
        if not sublime.ok_cancel_dialog(
                "Delete the aux directory (%d file(s)) for this document?\n%s\n\n"
                "Forces a from-scratch rebuild; nothing next to your source is "
                "touched." % (n, auxdir), "Delete"):
            return
        try:
            shutil.rmtree(auxdir)
            sublime.status_message("TeXLib: cleaned aux dir (%d file(s))." % n)
        except OSError as exc:
            sublime.error_message("TeXLib: could not clean aux dir: %s" % exc)

    def is_enabled(self):
        return texlib_locate._is_tex(self.window.active_view())


class TexlibPackageLmsCommand(sublime_plugin.WindowCommand):
    """Run package_for_lms.py on the active document's course."""

    def run(self):
        view = self.window.active_view()
        fname = view.file_name() if view else None
        if not fname:
            sublime.status_message("TeXLib: save the document first.")
            return
        settings = sublime.load_settings("TeXLib.sublime-settings")
        script = os.path.join(_repo_root(settings), "package_for_lms.py")
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: package_for_lms.py not found at\n%s\n\n"
                "Set \"class_source\" in TeXLib.sublime-settings to your TeXLib "
                "repo." % script)
            return
        py = shutil.which("python") or shutil.which("python3") or shutil.which("py")
        if not py:
            sublime.error_message("TeXLib: no python found on PATH to run it.")
            return
        threading.Thread(
            target=self._run, args=(py, script, fname), daemon=True).start()

    def _run(self, py, script, target):
        try:
            proc = subprocess.run(
                [py, script, target], capture_output=True, text=True,
                encoding="utf-8", errors="replace", cwd=os.path.dirname(target),
                creationflags=_NO_WINDOW, timeout=120)
        except Exception as exc:  # noqa: BLE001
            self._dialog("TeXLib: could not run package_for_lms: %s" % exc, True)
            return
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        self._dialog(
            "TeXLib: package_for_lms exited %d.\n\n%s"
            % (proc.returncode, out[:1500] or "(no output)"),
            proc.returncode != 0)

    def _dialog(self, msg, error=False):
        fn = sublime.error_message if error else sublime.message_dialog
        sublime.set_timeout(lambda: fn(msg), 0)

    def is_enabled(self):
        return texlib_locate._is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib utilities loaded.")
