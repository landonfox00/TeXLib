# texlib_gallery.py
# ============================================================================
# TeXLib -- open (and rebuild) the accessibility feature gallery.
#
#   TeXLib: Open Accessibility Gallery      open a11y_gallery.html in the
#                                           browser (builds it first if missing)
#   TeXLib: Rebuild Accessibility Gallery   regenerate a11y_gallery.html, then
#                                           open it when the build finishes
#
# The gallery (a11y_gallery.py) builds every examples/scenarios feature BOTH ways
# -- normal and accessible (tagged PDF/UA) -- and assembles one self-contained,
# searchable HTML page: per feature it shows the normal render, the accessible
# render, the accessible PDF tag tree + veraPDF badge, and a per-page pixel diff.
#
# Unlike TeXam (an instant local server), the gallery is EXPENSIVE to build
# (it compiles ~15 scenarios two-to-three ways and runs veraPDF), so the two
# commands are split: "Open" is instant -- it just launches the already-built
# HTML in the default browser, the TeXam-style popup -- while "Rebuild" runs the
# generator windowless (like the TeXam launcher), logs to a file, and opens the
# page once it is done. The generated HTML is gitignored, so the first Open
# offers to build it.
#
# a11y_gallery.py + a11y_gallery.html live at the repo root, so they resolve
# with zero config from class_source / the repo root (like texam.py); an
# explicit `a11y_gallery_path` setting overrides for unusual layouts.
#
# Own top-level file (hot-reloads alone).
# ============================================================================

import os
import shutil
import subprocess
import tempfile
import threading
import webbrowser

import sublime
import sublime_plugin

# Windowless generation: no console popup, no taskbar window (CREATE_NO_WINDOW on
# Windows). The flag must be paired with a CONSOLE python (see _python) -- it is
# what gives the generator an invisible console for its many TeX/veraPDF children
# to inherit. The full build takes several minutes; output goes to a log
# (python -u) so a failure is recoverable.
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_BUILD_LOG = os.path.join(tempfile.gettempdir(), "a11y-gallery-build.log")

# Guard against a second Rebuild while one is already running.
_building = threading.Lock()


def _repo_root(settings):
    """Repo root holding a11y_gallery.py / .html: class_source, else two dirs
    above this package (matching texlib_texam / texlib_utils)."""
    root = settings.get("class_source") if settings else None
    if not root:
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        root = os.path.dirname(os.path.dirname(plugin_dir))
    return root


def resolve_paths(settings, stem="a11y_gallery"):
    """Return (generator_script, output_html) for a gallery generator.

    `stem` selects which one: "a11y_gallery" (normal vs tagged, with pixel
    diffs, tag trees and veraPDF) or "class_gallery" (what every class actually
    produces). Both generators write <stem>.html beside themselves, so a single
    resolver serves both.

    An explicit `<stem>_path` setting -- the .py file or its containing
    directory -- wins; otherwise it resolves next to the repo scripts."""
    override = settings.get(stem + "_path") if settings else None
    if override:
        script = override if override.lower().endswith(".py") \
            else os.path.join(override, stem + ".py")
    else:
        script = os.path.join(_repo_root(settings), stem + ".py")
    html = os.path.join(os.path.dirname(script), stem + ".html")
    return script, html


def _open_html(html):
    """Open the generated page in the default browser (a local file URL)."""
    webbrowser.open("file:///" + html.replace("\\", "/"))


def _python():
    """Console python to run the generator with. Returns None if none is found.

    Deliberately NOT pythonw.exe. A GUI-subsystem parent owns no console, so
    every console tool the generator shells out to -- lualatex, veraPDF,
    pdftoppm, magick, dozens per run and several concurrently -- has to allocate
    its OWN console, and each one flashes a window. Console python launched under
    CREATE_NO_WINDOW (below) instead gets a single *invisible* console that the
    whole descendant tree inherits, so nothing ever appears on screen. The
    generator's own subprocess calls therefore need no creationflags of their
    own, and stay clean for CLI/CI use."""
    return shutil.which("python") or shutil.which("python3") or shutil.which("py")


def _run_build(script, html, on_done):
    """Run the generator to completion in a worker thread, then invoke on_done
    (bool ok) back on the main thread. Serialised by _building so two Rebuilds
    can't clobber the same output."""
    def worker():
        ok = False
        try:
            with open(_BUILD_LOG, "ab") as log:
                proc = subprocess.run(
                    [_python(), "-u", script, "-o", html],
                    cwd=os.path.dirname(script), creationflags=_CREATE_NO_WINDOW,
                    stdout=log, stderr=subprocess.STDOUT)
            ok = proc.returncode == 0 and os.path.isfile(html)
        except OSError:
            ok = False
        finally:
            _building.release()
            sublime.set_timeout(lambda: on_done(ok), 0)
    _building.acquire()
    threading.Thread(target=worker, daemon=True).start()


class TexlibOpenA11yGalleryCommand(sublime_plugin.WindowCommand):
    """Open the accessibility feature gallery (build it first if missing)."""

    def run(self):
        settings = sublime.load_settings("TeXLib.sublime-settings")
        script, html = resolve_paths(settings)
        if os.path.isfile(html):
            _open_html(html)
            sublime.status_message("TeXLib: opening the accessibility gallery.")
            return
        # Not built yet -- offer to build it now (a few minutes).
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: a11y_gallery.py not found at\n%s\n\n"
                "Set \"a11y_gallery_path\" in TeXLib.sublime-settings, or point "
                "\"class_source\" at the TeXLib repo root." % script)
            return
        if not sublime.ok_cancel_dialog(
                "The accessibility gallery hasn't been built yet.\n\n"
                "Build it now? It compiles every feature scenario both ways and "
                "takes a few minutes; it will open when it finishes.", "Build"):
            return
        self.window.run_command("texlib_build_a11y_gallery")

    def is_enabled(self):
        return True


class TexlibBuildA11yGalleryCommand(sublime_plugin.WindowCommand):
    """Regenerate a11y_gallery.html, then open it when the build finishes."""

    def run(self):
        settings = sublime.load_settings("TeXLib.sublime-settings")
        script, html = resolve_paths(settings)
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: a11y_gallery.py not found at\n%s\n\n"
                "Set \"a11y_gallery_path\" in TeXLib.sublime-settings, or point "
                "\"class_source\" at the TeXLib repo root." % script)
            return
        if _python() is None:
            sublime.error_message("TeXLib: no python found on PATH to run it.")
            return
        if _building.locked():
            sublime.status_message("TeXLib: the gallery is already building.")
            return
        sublime.status_message(
            "TeXLib: building the accessibility gallery (several minutes) -- "
            "it opens when done; log: %s" % _BUILD_LOG)

        def done(ok):
            if ok:
                _open_html(html)
                sublime.status_message("TeXLib: accessibility gallery ready.")
            else:
                sublime.error_message(
                    "TeXLib: the gallery build failed.\nSee the log:\n%s"
                    % _BUILD_LOG)
        _run_build(script, html, done)

    def is_enabled(self):
        return True


# ---------------------------------------------------------------------------
# Class gallery: what every class actually produces
# ---------------------------------------------------------------------------
# The sibling of the accessibility gallery. That one answers "how does the
# tagged build differ from the normal one"; this one answers "what does a report
# card look like, and what does exam-days = F do to a schedule" -- the question
# that previously meant finding a template, remembering the TEXINPUTS
# incantation and building it by hand.
#
# Same two commands, same resolver, same background-build machinery; only the
# stem differs. It is cheaper to build than the a11y gallery (one build per
# document instead of two or three, no veraPDF, no pixel diffing), but still
# minutes rather than seconds, so it runs through the same non-blocking path.


class TexlibOpenClassGalleryCommand(sublime_plugin.WindowCommand):
    """Open the class gallery (offer to build it if it is not there yet)."""

    def run(self):
        settings = sublime.load_settings("TeXLib.sublime-settings")
        script, html = resolve_paths(settings, "class_gallery")
        if os.path.isfile(html):
            _open_html(html)
            sublime.status_message("TeXLib: opening the class gallery.")
            return
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: class_gallery.py not found at\n%s\n\n"
                "Set \"class_gallery_path\" in TeXLib.sublime-settings, or point "
                "\"class_source\" at the TeXLib repo root." % script)
            return
        if sublime.ok_cancel_dialog(
                "The class gallery has not been built yet.\n\n"
                "Build it now? It renders every declared example and takes a "
                "few minutes.", "Build"):
            self.window.run_command("texlib_build_class_gallery")


class TexlibBuildClassGalleryCommand(sublime_plugin.WindowCommand):
    """Regenerate class_gallery.html, then open it when the build finishes."""

    def run(self):
        settings = sublime.load_settings("TeXLib.sublime-settings")
        script, html = resolve_paths(settings, "class_gallery")
        if not os.path.isfile(script):
            sublime.error_message(
                "TeXLib: class_gallery.py not found at\n%s\n\n"
                "Set \"class_gallery_path\" in TeXLib.sublime-settings, or point "
                "\"class_source\" at the TeXLib repo root." % script)
            return
        if _python() is None:
            sublime.error_message("TeXLib: no python found on PATH to run it.")
            return
        if _building.locked():
            sublime.status_message("TeXLib: a gallery is already building.")
            return
        sublime.status_message(
            "TeXLib: building the class gallery (a few minutes) -- it opens "
            "when done; log: %s" % _BUILD_LOG)

        def done(ok):
            if ok:
                _open_html(html)
                sublime.status_message("TeXLib: class gallery ready.")
            else:
                sublime.error_message(
                    "TeXLib: the class-gallery build failed.\nSee the log:\n%s"
                    % _BUILD_LOG)
        _run_build(script, html, done)


def plugin_loaded():
    print("TeXLib gallery commands loaded (accessibility + class).")
