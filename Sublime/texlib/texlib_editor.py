# texlib_editor.py
# ============================================================================
# TeXLib -- editor conveniences that COMPLEMENT LaTeXTools (Tier C).
#
#   TeXLib: Word Count            -> latextools_texcount
#   TeXLib: Table of Contents     -> latextools_toc_quickpanel
#   TeXLib: Jump to \ref / \cite  -> latextools_jumpto_anywhere
#   TeXLib: Edit Settings         open the split default|user TeXLib settings
#
# The delegations are the "complement, not replace" half of the plugin: we own
# the build + domain commands and call LaTeXTools by stable command name for the
# editor smarts we deliberately don't rebuild. If LaTeXTools isn't installed the
# delegation is a silent no-op (Sublime ignores an unknown command_name) -- the
# plugin still builds; only these extras rest on the companion package.
#
# Own top-level file (hot-reloads alone). DELEGATIONS is exported so the headless
# test can assert each command maps to the intended LaTeXTools command.
# ============================================================================

import sublime
import sublime_plugin

# Our command name -> the LaTeXTools command it delegates to. Verified against
# the installed LaTeXTools.sublime-package (see PLUGIN-DESIGN.md §8).
DELEGATIONS = {
    "texlib_word_count": "latextools_texcount",
    "texlib_toc": "latextools_toc_quickpanel",
    "texlib_jump_to_ref": "latextools_jumpto_anywhere",
}

# The split-settings default template Sublime opens when the user file is new.
SETTINGS_TEMPLATE = "{\n\t$0\n}\n"


def _is_tex(view):
    if view is None:
        return False
    if view.match_selector(0, "text.tex.latex"):
        return True
    name = view.file_name() or ""
    return name.lower().endswith((".tex", ".cls", ".sty"))


class _DelegateBase(sublime_plugin.WindowCommand):
    """Fire the mapped LaTeXTools command; no-op if it isn't installed."""

    latextools_command = None  # set by subclasses

    def run(self):
        self.window.run_command(self.latextools_command)

    def is_enabled(self):
        return _is_tex(self.window.active_view())


class TexlibWordCountCommand(_DelegateBase):
    """Word count for the active document (delegates to LaTeXTools)."""
    latextools_command = "latextools_texcount"


class TexlibTocCommand(_DelegateBase):
    """Section table-of-contents navigation (delegates to LaTeXTools)."""
    latextools_command = "latextools_toc_quickpanel"


class TexlibJumpToRefCommand(_DelegateBase):
    r"""Jump to the \ref / \cite / \input target under the cursor (LaTeXTools)."""
    latextools_command = "latextools_jumpto_anywhere"


class TexlibEditSettingsCommand(sublime_plugin.WindowCommand):
    """Open the split default | user TeXLib settings (onboarding; matters for
    distribution -- coworkers get a documented starting point they can edit)."""

    def run(self):
        self.window.run_command("edit_settings", {
            "base_file": "${packages}/TeXLib/TeXLib.sublime-settings",
            "user_file": "${packages}/User/TeXLib.sublime-settings",
            "default": SETTINGS_TEMPLATE,
        })


def plugin_loaded():
    print("TeXLib editor conveniences loaded.")
