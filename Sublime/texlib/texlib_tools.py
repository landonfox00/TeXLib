# texlib_tools.py
# ============================================================================
# TeXLib -- plugin wrappers over the standalone course tools (shell-out, like
# Package for LMS).  Each runs a repo-root script on the active document and
# shows its output in a scratch view:
#
#   TeXLib: Bank Report (matrix)   bank_report.py   -- topic x difficulty matrix
#   TeXLib: Collate Answer Keys    collate_keys.py  -- merge per-version keys PDF
#   TeXLib: Version Diff           version_diff.py  -- versions actually differ?
#   TeXLib: Coursemeta Lint        coursemeta_lint.py -- metadata + cross-doc check
#
# Own top-level file (hot-reloads alone). tool_target() (which script arg to pass
# for the active file) is a pure helper, unit-tested headlessly.
# ============================================================================

import os
import shutil
import subprocess
import threading

import sublime
import sublime_plugin

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# script -> how to derive its argument from the active .tex path.
#   "tex"    -> the .tex itself         (bank_report, version_diff)
#   "pdf"    -> the sibling <base>.pdf   (collate_keys)
#   "dir"    -> the document's directory (coursemeta_lint; walks to course root)
TOOL_ARG = {
    "bank_report.py": "tex",
    "version_diff.py": "tex",
    "collate_keys.py": "pdf",
    "coursemeta_lint.py": "dir",
}


def tool_target(script, tex_path):
    """The argument to pass `script` for the active document `tex_path`. Pure."""
    kind = TOOL_ARG.get(script, "tex")
    if kind == "pdf":
        return os.path.splitext(tex_path)[0] + ".pdf"
    if kind == "dir":
        return os.path.dirname(tex_path)
    return tex_path


def _repo_root():
    settings = sublime.load_settings("TeXLib.sublime-settings")
    override = settings.get("class_source")
    if override:
        return override
    plugin_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.dirname(os.path.dirname(plugin_dir))


def _python():
    return (shutil.which("python") or shutil.which("python3")
            or shutil.which("py") or os.environ.get("TEXLIB_PYTHON", ""))


def _is_tex(view):
    if view is None:
        return False
    if view.match_selector(0, "text.tex.latex"):
        return True
    name = view.file_name() or ""
    return name.lower().endswith(".tex")


class _ToolBase(sublime_plugin.WindowCommand):
    """Run a repo-root tool on the active document; stream its output to a view."""

    script = None        # e.g. "bank_report.py"
    title = "TeXLib Tool"

    def run(self):
        view = self.window.active_view()
        fname = view.file_name() if view else None
        if not fname:
            sublime.status_message("TeXLib: save the document first.")
            return
        script = os.path.join(_repo_root(), self.script)
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: %s not found at\n%s\n\nSet \"class_source\" in "
                "TeXLib.sublime-settings to your TeXLib repo." % (self.script, script))
            return
        py = _python()
        if not py:
            sublime.error_message("TeXLib: no python on PATH to run %s." % self.script)
            return
        arg = tool_target(self.script, fname)
        threading.Thread(target=self._run, args=(py, script, arg, fname),
                         daemon=True).start()

    def _run(self, py, script, arg, fname):
        try:
            proc = subprocess.run(
                [py, script, arg], capture_output=True, text=True,
                encoding="utf-8", errors="replace", cwd=os.path.dirname(fname),
                creationflags=_NO_WINDOW, timeout=600)
        except Exception as exc:  # noqa: BLE001
            self._show("TeXLib: %s failed: %s" % (self.script, exc))
            return
        out = ((proc.stdout or "") + (proc.stderr or "")).strip() or "(no output)"
        self._show(out)

    def _show(self, text):
        def apply():
            v = self.window.new_file()
            v.set_name(self.title)
            v.set_scratch(True)
            v.run_command("append", {"characters": text})
            v.set_read_only(True)
        sublime.set_timeout(apply, 0)

    def is_enabled(self):
        return _is_tex(self.window.active_view())


class TexlibBankMatrixCommand(_ToolBase):
    """Coverage matrix (topic x difficulty) for the active document's bank."""
    script = "bank_report.py"
    title = "TeXLib · Bank Coverage"


class TexlibCollateKeysCommand(_ToolBase):
    """Merge per-version answer-key PDFs next to the active document into one."""
    script = "collate_keys.py"
    title = "TeXLib · Collate Keys"


class TexlibVersionDiffCommand(_ToolBase):
    """Check that a multi-version exam's versions actually differ."""
    script = "version_diff.py"
    title = "TeXLib · Version Diff"


class TexlibCoursemetaLintCommand(_ToolBase):
    """Sanity + cross-document consistency for the active document's course."""
    script = "coursemeta_lint.py"
    title = "TeXLib · Coursemeta Lint"


def plugin_loaded():
    print("TeXLib course tools loaded.")
