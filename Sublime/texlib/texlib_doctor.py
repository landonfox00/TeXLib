# texlib_doctor.py
# ============================================================================
# TeXLib -- Doctor: one command that checks the build environment (N2).
#
# Reports on the toolchain (lualatex / pdflatex / biber / synctex), the optional
# helpers (pdftotext / pdftoppm / chktex), an external python with pypdf (needed
# for multi-version PDF slicing), the `texinputs` setting, coursemeta resolution
# for the active document, and -- the recurring footgun -- whether a TEXMFHOME
# copy of the classes is SHADOWING your live checkout (see texlib_texmf / M1, N3).
#
# render_doctor is pure and unit-tested; the probing is live.
# ============================================================================

import os
import shutil
import subprocess

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_texmf, texlib_locate
except ImportError:
    import texlib_texmf
    import texlib_locate

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

ENGINES = ["lualatex", "pdflatex", "biber", "synctex"]
OPTIONAL = ["pdftotext", "pdftoppm", "chktex", "mktexlsr"]

OK, WARN, FAIL = "ok", "warn", "fail"
_MARK = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}


def _which(name):
    return shutil.which(name) or ""


def check_engines():
    rows = []
    for e in ENGINES:
        p = _which(e)
        rows.append((e, OK if p else FAIL, p or "not found on PATH"))
    return rows


def check_optional():
    rows = []
    for e in OPTIONAL:
        p = _which(e)
        rows.append((e, OK if p else WARN, p or "(optional) not found"))
    return rows


def check_python_pypdf():
    py = (_which("python") or _which("python3") or _which("py")
          or os.environ.get("TEXLIB_PYTHON", ""))
    if not py:
        return ("python + pypdf", WARN,
                "no python on PATH (multi-version PDF slicing needs it)")
    try:
        r = subprocess.run(
            [py, "-c", "import pypdf; print(pypdf.__version__)"],
            capture_output=True, text=True, creationflags=_NO_WINDOW, timeout=20)
    except Exception as exc:  # noqa: BLE001
        return ("python + pypdf", WARN, str(exc))
    if r.returncode == 0:
        return ("python + pypdf", OK, "%s (pypdf %s)" % (py, r.stdout.strip()))
    return ("python + pypdf", WARN, "%s: pypdf not importable (pip install pypdf)" % py)


def check_shadow():
    d = texlib_texmf.installed_texlib_dir()
    files = texlib_texmf.installed_files(d)
    if files:
        return ("TEXMF shadow", WARN,
                "%d file(s) under %s shadow your checkout — run "
                "'TeXLib: Uninstall Classes from TEXMF'" % (len(files), d))
    return ("TEXMF shadow", OK, "no shadowing install (%s)" % d)


def check_texinputs():
    ti = sublime.load_settings("TeXLib.sublime-settings").get("texinputs")
    if not ti:
        return ("texinputs setting", OK,
                "unset — builds inherit the process TEXINPUTS")
    value = os.pathsep.join(ti) if isinstance(ti, list) else str(ti)
    return ("texinputs setting", OK, value)


def check_coursemeta(view):
    fname = view.file_name() if view else None
    if not fname:
        return ("coursemeta (active doc)", WARN, "no active document")
    cm = texlib_locate.find_coursemeta(os.path.dirname(fname))
    if cm:
        return ("coursemeta (active doc)", OK, cm)
    return ("coursemeta (active doc)", WARN,
            "none found above %s" % os.path.basename(fname))


def render_doctor(sections):
    """Render [(title, [(name, status, detail), ...]), ...] as a report, with an
    overall verdict line. Pure -- no Sublime, no probing."""
    worst = OK
    out = ["TeXLib Doctor — build environment check", "=" * 60, ""]
    for title, rows in sections:
        out.append(title)
        for name, status, detail in rows:
            if status == FAIL:
                worst = FAIL
            elif status == WARN and worst != FAIL:
                worst = WARN
            out.append("  %s  %-22s %s" % (_MARK[status], name, detail))
        out.append("")
    verdict = {OK: "All good.", WARN: "Usable, with warnings above.",
               FAIL: "Missing required tools — see [FAIL] above."}[worst]
    out.append("Verdict: %s" % verdict)
    out.append("")
    return "\n".join(out), worst


class TexlibDoctorCommand(sublime_plugin.WindowCommand):
    """Check the TeXLib build environment and open a report."""

    def run(self):
        view = self.window.active_view()
        sections = [
            ("Engines (required):", check_engines()),
            ("Helpers (optional):", check_optional() + [check_python_pypdf()]),
            ("Configuration:", [check_texinputs(), check_shadow(),
                                check_coursemeta(view)]),
        ]
        text, _worst = render_doctor(sections)
        out = self.window.new_file()
        out.set_name("TeXLib · Doctor")
        out.set_scratch(True)
        out.run_command("append", {"characters": text})
        out.set_read_only(True)


def plugin_loaded():
    print("TeXLib doctor loaded.")
