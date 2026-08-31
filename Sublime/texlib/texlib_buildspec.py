"""texlib_buildspec.py — the build facts shared by the Sublime builder and the
test harness, declared once.

WHY THIS FILE EXISTS

Three constants have to be identical in two programs that cannot import each
other's natural home:

  * `Sublime/texlib/texlib_build.py` runs inside Sublime's plugin host, which
    has no route to repo-root modules (and importing a test harness into the
    editor would be wrong even if it did).
  * `smoke_test.py` lives at the repo root and drives real builds in CI.

They were duplicated, and they had already drifted: `LUALATEX_CLASSES` listed
`bingo` in the harness and not in the builder. That divergence was survivable
only because `Bingo/bingo-template.tex` happens to carry a `% !TeX program =
lualatex` directive — a bingo document written without one selected pdflatex,
and `bingo.cls` calls `\\directlua` unguarded at class load, so it fatals
immediately. A silent wrong-engine selection is exactly the failure that cost a
debugging session when `thesis` was missing from both copies.

This module is the single source. It sits inside the plugin package rather than
at the repo root because that is the consumer with the hard constraint: the
plugin cannot reach up, but the harness can reach down (`smoke_test.py` adds
this directory to `sys.path`). Sublime does not auto-load `.py` from a package
subfolder, so adding a module here is import-only and cannot become a plugin.
"""

import os
import shutil

# Document classes that MUST be compiled with lualatex.
#
# The mechanism is class-name selection, which works regardless of whether a
# document carries a `% !TeX program` magic comment — the comment is a fallback
# for editors, not the authority.
#
#   autoexam, quiz  — \directlua in the version loop / problem engine
#   schedule, bingo — \directlua unguarded at class load; fatal under pdflatex
#   report-card     — \directlua for the gradebook engine (guarded, but lua)
#   bank            — loads texlib-problembank -> problem_engine.lua
#   thesis          — loads fontspec; pdflatex dies with "requires XeTeX or LuaTeX"
LUALATEX_CLASSES = {
    "autoexam",
    "quiz",
    "schedule",
    "bingo",
    "report-card",
    "bank",
    "thesis",
    # Both spellings of every lua-only class. The texlib-* name is the real
    # class since the CTAN rename; the bare name is its compatibility wrapper,
    # and a document may say either. Selecting pdflatex for one of these is not
    # a soft failure -- bingo and schedule \directlua at class load and fatal
    # immediately, and the error reads like the document is broken.
    "texlib-thesis",
    "texlib-quiz",
    "texlib-autoexam",
    "texlib-schedule",
    "texlib-bingo",
    "texlib-report-card",
    "texlib-bank",
}

# The accessible (tagged PDF/UA-2 + PDF/A-4f) build prefix, injected ahead of
# \documentclass because \DocumentMetadata can only switch tagging on there.
#
# Readers split on which MathML method they understand. AF (associated files)
# is what Firefox's viewer and Foxit read — the in-browser path from an LMS
# link — and SE (structure elements) is what Adobe Acrobat reads, so emitting
# both is what covers a class. We emit AF only, under protest, because SE is
# currently unusable:
#
#   luamml 0.9.2 (TeX Live 2026, 2026-06-20) keeps references to math *noad*
#   nodes — a radical's delimiter and degree — and writes marked-content
#   attributes to them from the structure-element writer after mlist_to_hlist
#   has freed them. Two \sqrt[n]{...} in one formula is enough for a freed
#   slot to be recycled, and LuaTeX aborts the run outright: "(nodes): trying
#   to delete an attribute reference of a non attribute node", no PDF. It
#   reproduces on a bare article + \DocumentMetadata, so it is not ours, and
#   only the SE path reaches the writer — AF alone is unaffected.
#
# That is not an edge case here: 14 documents in the teaching tree carry 57
# such formulas, most of them in the Notes section that teaches radical laws,
# where \sqrt[n]{ab} = \sqrt[n]{a}\sqrt[n]{b} IS the content. Restore
# mathml-SE the moment a fixed luamml ships; nothing else has to change.
ACCESSIBLE_DOCMETA = (
    r"\DocumentMetadata{lang=en,tagging=on,"
    r"tagging-setup={math/setup={mathml-AF},table/header-rows=1},"
    r"pdfstandard={ua-2,a-4f}}"
)

# The marker the classes gate their accessible branches on (\ifdefined
# \TeXLibAccessibleMode). Defined on the command line, never in the source.
ACCESSIBLE_MACRO = ACCESSIBLE_DOCMETA + r"\def\TeXLibAccessibleMode{}"

# The marker alone, for documents that carry their own \DocumentMetadata.
ACCESSIBLE_MARKER_ONLY = r"\def\TeXLibAccessibleMode{}"


def accessible_macro_for(tex_path):
    """The accessible-build prefix appropriate for one document.

    The TeX Live 2026 kernel makes a second \\DocumentMetadata declaration a
    fatal error ("Two \\DocumentMetadata declarations"), where 2025 quietly
    tolerated the duplicate. A document that opens with its OWN declaration --
    the thesis template's documented layout, since the PDF/A + PDF/UA choices
    there are the author's to make -- keeps it, and receives only the
    \\TeXLibAccessibleMode marker. Everything else gets the full injected
    metadata as before. An unreadable file gets the full prefix: the build
    itself will fail loudly on the missing file either way.
    """
    try:
        with open(tex_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except OSError:
        return ACCESSIBLE_MACRO
    for line in source.splitlines():
        head = line.split("%", 1)[0]
        if "\\DocumentMetadata" in head:
            return ACCESSIBLE_MARKER_ONLY
    return ACCESSIBLE_MACRO


# --- veraPDF conformance reporting ------------------------------------------
#
# The accessible build's conformance is checked by veraPDF, and BOTH consumers
# need to find the same binary: `smoke_test.py` validates with it, and the
# builder writes the human-readable report beside `<base>_accessible.pdf`.
# Declared here for the same reason as everything above -- the harness and the
# plugin cannot import each other.

# PDF/UA-2. The accessible build declares `pdfstandard={ua-2,a-4f}`, so ua2 is
# the flavour that actually matches what was asked for; veraPDF's `0`
# (autodetect) would silently fall back to a weaker profile on a file whose XMP
# claim is missing -- which is the very defect the check exists to catch.
VERAPDF_FLAVOUR = "ua2"

# Written beside <base>_accessible.pdf, matching its `_accessible` stem so the
# pair sorts together in a file listing.
VERAPDF_REPORT_SUFFIX = "_accessible-report.html"


def _verapdf_candidates():
    """Well-known install locations, in the order they should win.

    veraPDF ships as an IzPack installer that does NOT put itself on PATH, so
    `shutil.which` alone reports "not installed" on a machine where it plainly
    is -- the local smoke runs were soft-skipping conformance for exactly this
    reason while a full veraPDF sat in the user's home directory. `/opt/verapdf`
    is where `.github/workflows/accessible.yml` installs it.
    """
    home = os.path.expanduser("~")
    roots = [os.path.join(home, "verapdf")]
    if os.name == "nt":
        for env in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.environ.get(env)
            if base:
                roots.append(os.path.join(base, "verapdf"))
        names = ("verapdf.bat", "verapdf")
    else:
        roots.append("/opt/verapdf")
        names = ("verapdf",)
    for root in roots:
        for name in names:
            yield os.path.join(root, name)


def find_verapdf():
    """Absolute path to the veraPDF CLI, or None. PATH wins over the guesses."""
    for name in ("verapdf", "verapdf.bat"):
        found = shutil.which(name)
        if found:
            return found
    for path in _verapdf_candidates():
        if os.path.isfile(path):
            return path
    return None


def verapdf_report_cmd(exe, pdf_path, fmt="html", itemize=False):
    """argv for one veraPDF run over `pdf_path`.

    `itemize` adds --success, which logs every PASSED check rather than only
    the failures. That is the difference between a 20 KB verdict and a ~1 MB
    document evidencing all 841 checks a conforming file satisfies -- the
    latter is what a reviewer asking for proof of conformance wants, and the
    former is what you want on every build. The file argument goes last.
    """
    cmd = [exe, "--flavour", VERAPDF_FLAVOUR, "--format", fmt]
    if itemize:
        cmd.append("--success")
    cmd.append(pdf_path)
    return cmd
