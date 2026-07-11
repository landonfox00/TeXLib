# texlib_locate.py
# ============================================================================
# TeXLib -- locate build-context files for the active document.
#
#   TeXLib: Open coursemeta.tex   the governing metadata file (walks up to 4
#                                 parents, matching course-metadata.sty).
#   TeXLib: Reveal Aux Directory  the %TEMP%\texlib-aux\<hash> the build routes
#                                 aux files to. The hash and tex_root resolution
#                                 mirror the build brain / runner exactly, so it
#                                 points at the same folder the build used.
#
# Own top-level file (hot-reloads alone). Self-contained by design.
# ============================================================================

import hashlib
import os
import re
import tempfile

import sublime
import sublime_plugin

ROOT_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+root\s*=\s*(.+?)\s*$")


def _is_tex(view):
    if view is None:
        return False
    if view.match_selector(0, "text.tex.latex"):
        return True
    name = view.file_name() or ""
    return name.lower().endswith((".tex", ".cls", ".sty"))


def _tex_root(view):
    """The build's tex_root STRING for the active view -- identical to the
    runner's _resolve_root, so aux_dir_for() hashes the same value: honor a
    leading %!TeX root, else the file itself."""
    fname = view.file_name()
    if not fname:
        return None
    text = view.substr(sublime.Region(0, view.size()))
    m = ROOT_RE.search(text[:1024])
    if m:
        return os.path.normpath(os.path.join(os.path.dirname(fname), m.group(1)))
    return fname


def find_coursemeta(start_dir):
    """coursemeta.tex at start_dir or up to 4 parents above it, else None."""
    d = start_dir
    for _ in range(5):
        cand = os.path.join(d, "coursemeta.tex")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def aux_dir_for(tex_root):
    """The <<temp>> aux dir the build brain routes to for this root:
    <tempdir>/texlib-aux/<md5(tex_root)[:12]>. Mirrors
    texlib_build._resolve_aux_directory so the two agree."""
    key = hashlib.md5((tex_root or "").encode("utf-8")).hexdigest()[:12]
    return os.path.join(tempfile.gettempdir(), "texlib-aux", key)


class TexlibOpenCoursemetaCommand(sublime_plugin.WindowCommand):
    """Open the coursemeta.tex governing the active document."""

    def run(self):
        view = self.window.active_view()
        fname = view.file_name() if view else None
        if not fname:
            sublime.status_message("TeXLib: save the document first.")
            return
        path = find_coursemeta(os.path.dirname(fname))
        if not path:
            sublime.status_message(
                "TeXLib: no coursemeta.tex found above this file.")
            return
        self.window.open_file(path)

    def is_enabled(self):
        return _is_tex(self.window.active_view())


class TexlibRevealAuxCommand(sublime_plugin.WindowCommand):
    """Reveal the aux directory the build routes this document's aux files to."""

    def run(self):
        root = _tex_root(self.window.active_view())
        if not root:
            sublime.status_message("TeXLib: save the document first.")
            return
        auxdir = aux_dir_for(root)
        if not os.path.isdir(auxdir):
            sublime.status_message(
                "TeXLib: no aux directory yet for this document (build it first).")
            return
        self.window.run_command("open_dir", {"dir": auxdir})

    def is_enabled(self):
        return _is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib locators loaded.")
