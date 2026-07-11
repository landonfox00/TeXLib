# texlib_builder.py
# ============================================================================
# TexlibBuilder -- LaTeXTools adapter for the native TeXLib build core.
#
# The build LOGIC now lives in ONE place: TexlibBuildCore in the native package
# (TeXLib/texlib_build.py). This file is a thin adapter so the LaTeXTools
# "texlib" builder -- Tools > Build With > TeXLib and the old command-palette
# entries -- keeps working, sharing that one core, with nothing to drift.
#
# The primary Ctrl+B path is the native command (texlib_build) and does NOT use
# this file. This is the fallback/legacy host.
#
# Requires the native TeXLib package installed (it imports the core from it) and
# a LaTeXTools with the PdfBuilder API.
#
# Deploy to Packages/User/ with "builder": "texlib" in LaTeXTools.sublime-settings.
# ============================================================================

import importlib
import os

# Windows: keep short-lived subprocesses (and -- via _suppress_build_console_flash
# below -- LaTeXTools' build spawns) from flashing a console window. 0 elsewhere.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW

try:
    # Modern LaTeXTools layout.
    from LaTeXTools.plugins.builder.pdf_builder import PdfBuilder
except ImportError:
    try:
        # Legacy LaTeXTools layout.
        from LaTeXTools.builders.pdfBuilder import PdfBuilder
    except ImportError as _exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "TexlibBuilder: could not import PdfBuilder from LaTeXTools. "
            "Tried both 'LaTeXTools.plugins.builder.pdf_builder' (modern) and "
            "'LaTeXTools.builders.pdfBuilder' (legacy). Is LaTeXTools installed "
            "and reasonably up to date?"
        ) from _exc

# The shared build core, from the native TeXLib package.
from TeXLib.texlib_build import TexlibBuildCore


# --- Suppress the Windows build console flash --------------------------------
def _suppress_build_console_flash():
    """
    Remove the brief console-window flash on Ctrl+B builds (Windows only).

    LaTeXTools spawns every build process -- lualatex, biber, each rerun --
    through ``latextools.utils.external_command``, which hands Popen a SW_HIDE
    ``startupinfo`` but never sets ``CREATE_NO_WINDOW``. SW_HIDE alone does not
    stop Windows from allocating a console for a console-subsystem exe
    (lualatex) launched by a GUI process, so it flashes for the length of the
    pass. We wrap that module's *own* ``Popen`` name -- it does
    ``from subprocess import Popen``, so a global ``subprocess.Popen`` patch
    (the earlier attempt) never reached it -- and OR ``CREATE_NO_WINDOW`` into
    creationflags.

    Gated on ``startupinfo is not None``: external_command only builds a
    startupinfo on its hide path (``show_window=False``). The Sumatra/sioyek
    PDF viewers call it with ``show_window=True`` (startupinfo stays None), so
    their windows are left untouched.

    Best-effort and idempotent: any failure here just leaves the harmless flash
    in place rather than breaking builds.
    """
    if os.name != "nt":
        return
    ec = None
    for modpath in (
        "LaTeXTools.latextools.utils.external_command",  # modern layout
        "LaTeXTools.latextools_utils.external_command",  # legacy layout
    ):
        try:
            ec = importlib.import_module(modpath)
            break
        except Exception:
            continue
    if ec is None or not hasattr(ec, "Popen"):
        return
    if getattr(ec, "_texlib_nowindow_patched", False):
        return

    _real_popen = ec.Popen

    def _popen_no_window(*args, **kwargs):
        if kwargs.get("startupinfo") is not None:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | _NO_WINDOW
        return _real_popen(*args, **kwargs)

    ec.Popen = _popen_no_window
    ec._texlib_nowindow_patched = True


_suppress_build_console_flash()


class TexlibBuilder(TexlibBuildCore, PdfBuilder):
    """LaTeXTools host for the shared build core.

    Base order matters: TexlibBuildCore FIRST so commands() and the _* helpers
    resolve to the core (not to any PdfBuilder stub); PdfBuilder supplies
    __init__ and the host attributes the core reads -- display / tex_root /
    tex_name / base_name / engine / options / out / aux_directory.

    Class name stays 'TexlibBuilder' on purpose: LaTeXTools derives the builder
    name by stripping 'Builder' and snake-casing, so this maps to 'texlib' (what
    the "builder": "texlib" setting expects). TeXLibBuilder would map to
    'te_xlib' and fail to load.
    """

    name = "TeXLib Builder"
