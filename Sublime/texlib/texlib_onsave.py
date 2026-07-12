# texlib_onsave.py
# ============================================================================
# TeXLib -- opt-in build-on-save (D6).
#
#   TeXLib: Toggle Build on Save   flip the build_on_save user setting.
#   (listener)                     when it's on, a save of a LaTeX document
#                                  triggers a default TeXLib build.
#
# Off by default. The listener is a thin trigger; it defers to texlib_build,
# which already refuses a second concurrent build of the same document, so a
# rapid save-storm can't stack builds.
#
# Own top-level file (hot-reloads alone).
# ============================================================================

import sublime
import sublime_plugin

SETTINGS = "TeXLib.sublime-settings"


def _is_tex(view):
    if view is None:
        return False
    if view.match_selector(0, "text.tex.latex"):
        return True
    name = view.file_name() or ""
    return name.lower().endswith((".tex",))


class TexlibToggleBuildOnSaveCommand(sublime_plugin.WindowCommand):
    """Turn build-on-save on or off (persists to the user settings)."""

    def run(self):
        s = sublime.load_settings(SETTINGS)
        new = not bool(s.get("build_on_save", False))
        s.set("build_on_save", new)
        sublime.save_settings(SETTINGS)
        sublime.status_message(
            "TeXLib: build on save %s." % ("ON" if new else "OFF"))


class TexlibBuildOnSave(sublime_plugin.EventListener):
    """Trigger a default build after saving a LaTeX document, if enabled."""

    def on_post_save_async(self, view):
        if not _is_tex(view):
            return
        if not sublime.load_settings(SETTINGS).get("build_on_save", False):
            return
        window = view.window()
        if window is None:
            return
        # texlib_build reads the active view; a save keeps it active. It also
        # guards against a duplicate concurrent build of the same document.
        window.run_command("texlib_build", {"mode": "default"})


def plugin_loaded():
    print("TeXLib build-on-save loaded.")
