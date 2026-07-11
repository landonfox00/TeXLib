# texlib_texmf.py
# ============================================================================
# TeXLib -- install the class payload into the user's TEXMF tree.
#
# The plugin bundles/points at the TeXLib classes and injects TEXINPUTS so its
# OWN builds resolve them. This command does the OTHER half -- the job the
# TeXLib-Installer does for coworkers -- for THIS machine: copy every .cls/.sty/
# .lua into TEXMFHOME/tex/latex/texlib/ so *every* TeX tool (CLI, other editors,
# CI) finds them, not just this plugin. See PLUGIN-DESIGN.md (installer balance).
#
# It's a copy (a snapshot), not a symlink -- re-run after changing the classes
# to refresh what non-plugin tools see. Own top-level file (hot-reloads alone).
# ============================================================================

import os
import shutil
import subprocess
import threading

import sublime
import sublime_plugin

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# The class payload: document classes (.cls), shared packages (.sty), and the
# Lua engines (.lua). Skips infrastructure dirs and Lua test files.
CLASS_EXTS = (".cls", ".sty", ".lua")
EXCLUDE_DIRS = {".git", ".claude", "Sublime", "tests", "examples", "__pycache__"}


def gather_class_files(root):
    """Sorted absolute paths of the .cls/.sty/.lua payload under `root`,
    excluding infrastructure dirs and Lua test files (test_*.lua / *_test*.lua).
    Basenames are unique across the library, so the result copies flat."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in CLASS_EXTS:
                continue
            if ext == ".lua" and (fn.startswith("test_") or "_test" in fn):
                continue
            out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _class_source(settings, plugin_dir):
    """Where the class payload lives. Order: explicit class_source setting; a
    bundled latex/ inside the package (the future distributed layout); else the
    repo root two dirs above the package (the dev/junction layout,
    Sublime/texlib -> Sublime -> repo)."""
    override = settings.get("class_source")
    if override:
        return override
    bundled = os.path.join(plugin_dir, "latex")
    if os.path.isdir(bundled):
        return bundled
    return os.path.dirname(os.path.dirname(plugin_dir))


def _kpsewhich(*args):
    exe = shutil.which("kpsewhich")
    if not exe:
        return ""
    try:
        out = subprocess.run(
            [exe, *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=_NO_WINDOW, timeout=15)
        return (out.stdout or "").strip()
    except Exception:  # noqa: BLE001 - kpsewhich absent / erroring is non-fatal
        return ""


def _texmfhome():
    """The user-writable TEXMFHOME (searched live, no ls-R needed), or a
    ~/texmf fallback if kpsewhich isn't on PATH."""
    return _kpsewhich("-var-value=TEXMFHOME") or os.path.join(
        os.path.expanduser("~"), "texmf")


class TexlibInstallTexmfCommand(sublime_plugin.WindowCommand):
    """Copy the TeXLib class payload into TEXMFHOME so all TeX tools find it."""

    def run(self):
        settings = sublime.load_settings("TeXLib.sublime-settings")
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        src = _class_source(settings, plugin_dir)
        files = gather_class_files(src)
        if not files:
            sublime.error_message(
                "TeXLib: no .cls/.sty/.lua found under\n%s\n\n"
                "Set \"class_source\" in TeXLib.sublime-settings to your TeXLib "
                "repo (or its bundled latex/ dir)." % src)
            return
        target = os.path.join(_texmfhome(), "tex", "latex", "texlib")
        if not sublime.ok_cancel_dialog(
                "Install %d TeXLib class file(s) to:\n%s\n\n"
                "Makes them available to ALL TeX tools (CLI, other editors, CI) "
                "-- not just this plugin. Existing files there are overwritten."
                % (len(files), target), "Install"):
            return
        threading.Thread(
            target=self._install, args=(files, target), daemon=True).start()

    def _install(self, files, target):
        try:
            os.makedirs(target, exist_ok=True)
            for f in files:
                shutil.copy2(f, os.path.join(target, os.path.basename(f)))
        except Exception as exc:  # noqa: BLE001 - report, never crash the host
            self._dialog("TeXLib: install failed: %s" % exc, error=True)
            return
        # TEXMFHOME is searched live, so files resolve immediately; confirm it.
        resolved = _kpsewhich("autoexam.cls")
        ok = bool(resolved)
        self._dialog(
            "TeXLib: installed %d file(s) to\n%s\n\n%s"
            % (len(files), target,
               "Verified: autoexam.cls now resolves via kpsewhich."
               if ok else
               "Copied. kpsewhich could not confirm resolution yet -- if a CLI "
               "build can't find the classes, run 'mktexlsr'."))

    def _dialog(self, msg, error=False):
        fn = sublime.error_message if error else sublime.message_dialog
        sublime.set_timeout(lambda: fn(msg), 0)


def plugin_loaded():
    print("TeXLib TEXMF install loaded.")
