# texlib_texmf.py
# ============================================================================
# TeXLib -- UNINSTALL a stale class copy from the user's TEXMF tree (M1).
#
# The plugin's builds already resolve the TeXLib classes from your live checkout
# via the `texinputs` setting -- so a copy of the classes under TEXMFHOME does
# NOT help the plugin; it *shadows* the checkout (kpathsea / LUAINPUTS can find
# the stale TEXMFHOME copy first), which silently builds teaching docs against
# old packages. This command finds and removes that copy so builds resolve from
# your checkout again. System-wide install for coworkers is the standalone
# TeXLib-Installer's job (a peer distribution channel); the plugin no longer
# copies classes into TEXMF. See PLUGIN-DESIGN.md (installer balance).
#
# installed_texlib_dir() / installed_files() are shared detection helpers that
# TeXLib: Doctor (N2) and the build-time shadow warning (N3) also use.
# ============================================================================

import os
import shutil
import subprocess

import sublime
import sublime_plugin

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# What an install looks like -- the payload the old installer/plugin copied in.
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


def texmfhome():
    """The user-writable TEXMFHOME (searched live), or a ~/texmf fallback."""
    return _kpsewhich("-var-value=TEXMFHOME") or os.path.join(
        os.path.expanduser("~"), "texmf")


def installed_texlib_dir():
    """The TEXMFHOME/tex/latex/texlib directory (whether or not it exists)."""
    return os.path.join(texmfhome(), "tex", "latex", "texlib")


def installed_files(target=None):
    """Sorted .cls/.sty/.lua files currently installed under the texlib dir
    (empty if none). Pure enough to unit-test against a temp tree."""
    target = target or installed_texlib_dir()
    if not os.path.isdir(target):
        return []
    out = []
    for fn in os.listdir(target):
        if os.path.splitext(fn)[1].lower() in CLASS_EXTS:
            out.append(os.path.join(target, fn))
    return sorted(out)


def shadows_checkout():
    """True if a TeXLib class copy is installed under TEXMFHOME -- i.e. it can
    shadow the live checkout that the plugin's builds resolve via texinputs."""
    return bool(installed_files())


class TexlibUninstallTexmfCommand(sublime_plugin.WindowCommand):
    """Remove a stale TeXLib copy from TEXMFHOME so builds resolve from checkout."""

    def run(self):
        target = installed_texlib_dir()
        files = installed_files(target)
        if not files:
            sublime.message_dialog(
                "TeXLib: nothing to uninstall.\n\nNo TeXLib classes are installed "
                "under\n%s\n\nThe plugin already resolves the classes from your "
                "checkout via the \"texinputs\" setting." % target)
            return
        if not sublime.ok_cancel_dialog(
                "Remove %d installed TeXLib class file(s) from:\n%s\n\n"
                "This UN-shadows your live checkout, so builds resolve the classes "
                "from your repo (via \"texinputs\") instead of this stale copy. "
                "System-wide install is the standalone TeXLib-Installer's job."
                % (len(files), target), "Uninstall"):
            return
        try:
            shutil.rmtree(target)
        except OSError as exc:
            sublime.error_message("TeXLib: could not remove %s\n%s" % (target, exc))
            return
        # Refresh the filename database so tools stop finding the removed copy.
        mktexlsr = shutil.which("mktexlsr") or shutil.which("texhash")
        if mktexlsr:
            try:
                subprocess.run([mktexlsr], capture_output=True,
                               creationflags=_NO_WINDOW, timeout=60)
            except Exception:  # noqa: BLE001
                pass
        sublime.message_dialog(
            "TeXLib: removed %d file(s) from\n%s\n\nBuilds now resolve the classes "
            "from your checkout." % (len(files), target))

    def is_enabled(self):
        return shadows_checkout()


def plugin_loaded():
    print("TeXLib TEXMF uninstall loaded.")
