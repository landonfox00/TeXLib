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
}

# The accessible (tagged PDF/UA-2 + PDF/A-4f) build prefix, injected ahead of
# \documentclass because \DocumentMetadata can only switch tagging on there.
#
# Both MathML methods are emitted deliberately: readers split on which they
# understand. AF (associated files) is what Firefox's viewer and Foxit read —
# the in-browser path from an LMS link — and SE (structure elements) is what
# Adobe Acrobat reads. Dropping either silently halves screen-reader coverage.
ACCESSIBLE_DOCMETA = (
    r"\DocumentMetadata{lang=en,tagging=on,"
    r"tagging-setup={math/setup={mathml-AF,mathml-SE},table/header-rows=1},"
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
