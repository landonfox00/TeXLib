# texlib_texmf.py
# ============================================================================
# TeXLib -- remove a stale class install from the user's TEXMF tree.
#
# The plugin resolves the TeXLib classes for its OWN builds via TEXINPUTS (the
# `texinputs` setting -> your live checkout), and the classes' Lua loader falls
# back to the .lua sitting beside each .cls. So the plugin needs no installed
# copy of its own.
#
# But that loader tries an installed TEXMF copy FIRST (kpse's "lua" format)
# before the sibling fallback, so a leftover TEXMFHOME/tex/latex/texlib/ -- e.g.
# from an older plugin build that copied the payload there -- silently SHADOWS
# your checkout: edits to the .lua engines appear to do nothing. This command
# removes that install so the checkout (on TEXINPUTS) is authoritative again.
# Installing the classes system-wide for non-plugin tools (CLI, other editors,
# CI) is the standalone TeXLib-Installer's job, not the plugin's.
#
# Own top-level file (hot-reloads alone).
# ============================================================================

import os
import shutil
import subprocess
import threading

import sublime
import sublime_plugin

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# The class payload the install command used to write: document classes (.cls),
# shared packages (.sty), and the Lua engines (.lua).
CLASS_EXTS = (".cls", ".sty", ".lua")


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


def texmf_install_dir(texmfhome):
    """The directory the (now removed) install command wrote to --
    TEXMFHOME/tex/latex/texlib. Removing it un-shadows the live checkout."""
    return os.path.join(texmfhome, "tex", "latex", "texlib")


def installed_files(target):
    """Sorted basenames of the .cls/.sty/.lua payload currently installed under
    `target` (empty list if the dir is absent). The install is flat, so this
    does not recurse and ignores non-payload files (e.g. an ls-R)."""
    if not os.path.isdir(target):
        return []
    return sorted(
        fn for fn in os.listdir(target)
        if os.path.splitext(fn)[1].lower() in CLASS_EXTS)


class TexlibUninstallTexmfCommand(sublime_plugin.WindowCommand):
    """Remove a stale TeXLib class install from TEXMFHOME so builds resolve the
    classes from the live checkout (TEXINPUTS) instead of a shadowing copy."""

    def run(self):
        target = texmf_install_dir(_texmfhome())
        files = installed_files(target)
        if not files:
            sublime.message_dialog(
                "TeXLib: no installed classes to remove.\n\n"
                "Nothing found at\n%s\n\nBuilds already resolve the classes "
                "from your checkout via the \"texinputs\" setting." % target)
            return
        if not sublime.ok_cancel_dialog(
                "Remove %d installed TeXLib class file(s) from:\n%s\n\n"
                "The classes will then resolve from your live checkout (the "
                "\"texinputs\" setting) instead of this copy, which otherwise "
                "shadows it. Your repo is not touched."
                % (len(files), target), "Remove"):
            return
        threading.Thread(
            target=self._uninstall, args=(target, len(files)),
            daemon=True).start()

    def _uninstall(self, target, count):
        try:
            shutil.rmtree(target)
        except Exception as exc:  # noqa: BLE001 - report, never crash the host
            self._dialog("TeXLib: uninstall failed: %s" % exc, error=True)
            return
        # TEXMFHOME is searched live, so the removal takes effect immediately.
        # If autoexam.cls still resolves, it's either another installed copy or
        # a checkout on TEXINPUTS (the latter is exactly what we want).
        stray = _kpsewhich("autoexam.cls")
        note = ("\n\nNote: autoexam.cls still resolves via kpsewhich at\n%s\n"
                "-- another installed copy may exist (or that's your checkout "
                "on TEXINPUTS, which is fine)." % stray) if stray else ""
        self._dialog(
            "TeXLib: removed %d installed class file(s) from\n%s\n\nBuilds now "
            "resolve the classes from your checkout via TEXINPUTS.%s"
            % (count, target, note))

    def _dialog(self, msg, error=False):
        fn = sublime.error_message if error else sublime.message_dialog
        sublime.set_timeout(lambda: fn(msg), 0)


def plugin_loaded():
    print("TeXLib TEXMF uninstall loaded.")
