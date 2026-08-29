#!/usr/bin/env python3
"""
End-to-end integration test for TeXLib's SyncTeX inverse search.

Unlike test_schedule_synctex.lua (which fabricates tex.*/tex.inputlineno and
never runs a real engine) and test_texlib_builder.py's schedmap-rewrite tests
(which fabricate a plausible-looking .synctex.gz by hand), this drives the
REAL builder coroutine against a REAL lualatex build, then asks TeX Live's own
`synctex edit -o page:x:y:pdf` CLI to resolve a PDF-space point back to a
source file + line -- exactly what SumatraPDF does internally before invoking
InverseSearchCmdLine. That is what actually catches whether double-clicking a
problem or a calendar cell in the PDF lands where a user expects: neither of
the fabricated-data unit tests can, because both assume the real engine
produces the per-line attribution they hand-construct, which turned out not to
always hold (see the module-level NOTE below).

Fixtures are self-contained (own bank/exam/schedule .tex, not the real
Exams/Schedule templates), so editing the shipped example documents can't
break this test and vice versa. Distinctive ALL-CAPS needle tokens (never
real words) are used so find_word() can't accidentally match something else.

Soft-skips (exit 0) if lualatex, a poppler-flavored pdftotext (-bbox support),
or the synctex CLI are missing -- matching test_biber_integration.py's
degrade-don't-fail convention.

STATUS (2026-07-04): Schedule's default xltabular renderer is a confirmed
fundamental limitation (not fixable by a redirect-timing patch -- see
_rewrite_synctex_for_schedmap's docstring); scenarios 4/5 assert the honest
grid-file fallback that ships today, not per-cell accuracy. A real per-cell
fix (an opt-in box-grid renderer) exists on a separate, unmerged branch. The
"document-attributed problem breaks after a page shipout" theory floated
earlier in this investigation did NOT hold up -- that was a hardcoded-page
bug in manual testing, not a real defect; scenario 3 confirms exact
attribution. One remaining known gap: solution-box content had no working
inverse search at all (a `tcolorbox`-internals issue, unrelated to
Schedule's) -- fixed; scenario 2 asserts it outright now.

Run:  python Sublime/test_synctex_integration.py     (exit 0 ok/skipped, 1 fail)
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

# --- Import the real builder headless. build_versions.py used to do the
# LaTeXTools-stub dance and re-export TexlibBuilder; it was removed, and the
# builder's shared core now lives in the native TeXLib package
# (TeXLib.texlib_build.TexlibBuildCore). Stub LaTeXTools' PdfBuilder and the
# TeXLib package, then import TexlibBuilder directly. -------------------------
TEXLIB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HERE = os.path.dirname(os.path.abspath(__file__))  # Sublime/
sys.path.insert(0, TEXLIB_ROOT)


from _testkit import install_native_builder  # noqa: E402
TexlibBuilder = install_native_builder()


def _build_root():
    """The checkout whose shared TeXLib files the build resolves against; see
    _texinputs_env for the comma/junction rationale."""
    root = TEXLIB_ROOT
    if os.name == "nt" and "," in root and os.path.isdir(r"C:\_texlibjunc"):
        root = r"C:\_texlibjunc"
    return root


def _texinputs_env(tex_dir):
    """Env for the engine, TEXINPUTS extended so the TeXLib-root shared files
    resolve even though tex_dir is a scratch dir OUTSIDE the repo entirely
    (unlike build_versions.py's own _texinputs_env, which assumes tex_dir is
    inside the repo tree and adds the root via a relative '..' path -- that
    relative path would have to cross back through the real OneDrive folder
    name to reach an external scratch dir, defeating the whole point).

    On this machine kpathsea also can't search an ABSOLUTE TEXINPUTS entry
    containing a comma (the real OneDrive path has one, and Python's own
    __file__/getcwd resolution does not preserve "reached via the comma-free
    junction" -- it reports the real underlying path either way). Route
    through the C:\\_texlibjunc junction ONLY when TEXLIB_ROOT itself is the
    comma-containing path -- i.e. this script is running from the live,
    shared OneDrive checkout. A worktree (or any other checkout) elsewhere on
    disk has no comma and must use ITS OWN files directly: the junction
    always points at the live shared checkout, so unconditionally preferring
    it here would silently compile against whatever's currently checked out
    there instead of this worktree's own (possibly different, possibly
    mid-conflict-resolution) content -- exactly the bug that produced a
    confusing, non-reproducible-looking failure when this test was run from
    an isolated worktree while the live checkout was mid-merge on a
    different branch.
    """
    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    root = _build_root().replace(os.sep, "/")
    env["TEXINPUTS"] = sep.join([".", root + "//", env.get("TEXINPUTS", "")])
    # Pin LUAINPUTS too: the problem-bank engine (problem_engine.lua /
    # texlib_synctex.lua) is loaded by LuaTeX via LUAINPUTS, NOT TEXINPUTS. Without
    # this, a TeXLib install under TEXMFHOME silently SHADOWS this checkout's engine
    # (the installed-engine-shadows-checkout hazard), so the staged current classes
    # run against a stale engine -- and the autoexam multi-version emit then renders
    # no problem content, which looks like (but is not) a SyncTeX failure.
    env["LUAINPUTS"] = sep.join([".", root + "//", env.get("LUAINPUTS", "")])
    return env

SYNCTEX = shutil.which("synctex")
LUALATEX = shutil.which("lualatex")

from _testkit import Checker  # noqa: E402
_c = Checker()
check = _c.check


from _testkit import find_poppler  # noqa: E402


PDFTOTEXT = find_poppler()


# --- Real-builder driver, mirroring test_biber_integration.py's run_build ---
def run_build(tex_dir, tex_name, aux_directory="<<temp>>", options=None, engine="pdflatex"):
    """engine defaults to "pdflatex" -- matching a document with no %!TeX
    program directive -- and is force-overridden to lualatex by the builder
    itself for autoexam/quiz/schedule/report-card (see LUALATEX_CLASSES).
    Classes NOT in that set (didactic, pset, syllabus, bingo) but that still
    require lualatex for a specific reason (e.g. didactic's problem-bank
    commands) rely on LaTeXTools resolving a %!TeX program magic comment
    into self.engine BEFORE the builder ever runs -- pass engine="lualatex"
    explicitly here to simulate that resolution; the plain default silently
    fatals under pdflatex for such a document, same as a real misconfigured
    build would."""
    b = TexlibBuilder()
    b.tex_root = os.path.join(tex_dir, tex_name)
    b.tex_name = tex_name
    b.base_name = os.path.splitext(tex_name)[0]
    b.tex_dir = tex_dir
    b.engine = engine
    b.options = options or []
    b.aux_directory = aux_directory
    b.out = ""

    env = _texinputs_env(tex_dir)

    gen = b.commands()
    try:
        item = next(gen)
        while True:
            cmd, msg = item
            proc = subprocess.run(
                cmd, cwd=tex_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180, env=env,
            )
            b.out = (proc.stdout or "") + (proc.stderr or "")
            item = gen.send(proc.returncode)
    except StopIteration:
        pass
    return {"displayed": b._displayed}


# --- pdftotext -bbox word locator ---------------------------------------------
WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"[^>]*>([^<]*)</word>'
)
PAGE_RE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)"')


def find_word(pdf_path, needle, occurrence=1):
    """Return (page, center_x, center_y) of the `occurrence`-th word containing
    `needle` in the PDF, via pdftotext -bbox. page is 1-based; x/y are in PDF
    points from the top-left -- exactly synctex's own coordinate convention."""
    out = subprocess.run(
        [PDFTOTEXT, "-bbox", pdf_path, "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    page = 0
    found = 0
    for line in out.splitlines():
        if PAGE_RE.search(line):
            page += 1
            continue
        wm = WORD_RE.search(line)
        if wm and needle in wm.group(5):
            found += 1
            if found == occurrence:
                x0, y0, x1, y1 = (float(wm.group(i)) for i in range(1, 5))
                return page, (x0 + x1) / 2, (y0 + y1) / 2
    return None


# --- synctex edit wrapper ------------------------------------------------------
def synctex_edit(pdf_path, page, x, y):
    proc = subprocess.run(
        [SYNCTEX, "edit", "-o", f"{page}:{x}:{y}:{pdf_path}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = proc.stdout
    m_in = re.search(r"^Input:(.*)$", out, re.MULTILINE)
    m_line = re.search(r"^Line:(\d+)", out, re.MULTILINE)
    if not m_in or not m_line:
        return {"raw": out, "input": None, "line": None}
    return {"raw": out, "input": m_in.group(1).strip(), "line": int(m_line.group(1))}


def synctex_view(pdf_path, tex_file, line):
    """Forward search: the pages `tex_file:line` resolves to in `pdf_path`.
    Returns [] when the map has no record for that line under the tag the
    lookup resolves the file to."""
    proc = subprocess.run(
        [SYNCTEX, "view", "-i", f"{line}:1:{tex_file}", "-o", pdf_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return [l.split(":", 1)[1].strip()
            for l in (proc.stdout or "").splitlines() if l.startswith("Page:")]


def basename_matches(resolved_input, expected_basename):
    return bool(resolved_input) and (
        os.path.basename(resolved_input).lower() == expected_basename.lower()
    )


def write(tex_dir, name, content):
    with open(os.path.join(tex_dir, name), "w", encoding="utf-8") as fh:
        fh.write(content)


# --- Fixture: bank problems, multi-version, aux-directory-routed -------------
# Line numbers below are load-bearing -- keep the assertions in sync with any
# edit to these fixtures.
BANK_TEX = (
    "% test bank fixture for the SyncTeX integration test.\n"   # 1
    "\\begin{problem}{quad_one}[topic=quad]\n"                  # 2
    "\tSolve SYNCNEEDLESTEM for the unknown.\n"                 # 3
    "\t\\begin{solution}\n"                                     # 4
    "\tSYNCNEEDLESOLUTION goes here.\n"                         # 5
    "\t\\end{solution}\n"                                       # 6
    "\\end{problem}\n"                                          # 7
)
BANK_STEM_LINE = 3
BANK_SOLUTION_LINE = 5

AUTOEXAM_TEX = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\versions{A,B}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{problems}\n"
    "\\problem{quad_one}\n"
    "\\end{problems}\n"
    "\\end{document}\n"
)


def scenario_bank_multiversion():
    print("\n=== Scenario 1: bank problem, multi-version, aux_directory=<<temp>> ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_bank_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "autoexam.tex", AUTOEXAM_TEX)
        run_build(tmp, "autoexam.tex", aux_directory="<<temp>>")

        pdf = os.path.join(tmp, "autoexam.pdf")
        check("PDF was produced", os.path.exists(pdf))
        check("plain .synctex was produced (finalize step ran)",
              os.path.exists(os.path.join(tmp, "autoexam.synctex")))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_STEM_LINE})",
                  r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_bank_solutions_mode():
    """FIXED synctex-solution-staging, then REGRESSED (free-response-solution-inverse-search -- see the two solution
    checks below, now marked known). Historical root-cause notes retained:
    The original theory (tcolorbox defers shipout
    for internal measurement, like xltabular, consuming the redirect before
    real content ships) was WRONG -- disproved by ablation (stripping
    tcolorbox out of {solution} entirely still failed identically). Two
    separate bugs were actually stacked:

      1. problem_engine.lua never staged a SyncTeX redirect for the solution
         region at all -- p.solution was tex.print'd as a raw string with no
         file backing, so its nodes inherited whatever (file,line) the STEM's
         redirect last left active. Fixed by pbank_stage_solution/
         emit_solution_block, which stage+\\@@input the solution's own
         bank-file lines, deferred via a follow-up \\directlua token
         (texlib_synctex.lua allows only one pending redirect at a time,
         consumed by the next matching \\@@input -- same pattern as
         pbank_print_catalog's per-id deferred calls).

      2. Separately: tcolorbox's `enhanced` mode (needed for the old
         `borderline west` accent) does its own internal box handling that
         defeats `synctex edit`'s geometric reverse-search even for
         correctly-tagged content -- confirmed generic, not about solution
         content specifically (the tcolorbox-internal "Solution." header
         text failed identically, untagged or not). Root cause: \\unvbox
         splices nodes with no box-open record of its own, so reverse search
         can't recover correctly-tagged content spliced inside a wrapper
         whose own self-tag is the .sty file, not the bank -- confirmed by
         swapping \\unvbox\\@sol@box for \\box\\@sol@box (a real nested box
         node), which fixed it inside a plain \\colorbox+\\parbox and inside
         tcolorbox's standard (non-enhanced) mode, but not enhanced mode.
         Fixed by dropping tcolorbox for {solution} entirely: plain
         \\colorbox+\\parbox, \\box (not \\unvbox), left accent hand-drawn
         with \\vrule sized from \\ht\\@sol@box/\\dp\\@sol@box (read before
         \\box empties the register). Trade-off accepted: \\box can't split
         across a page the way the old breakable tcolorbox could -- surveyed
         2026-07-04, every shipped solution is a few lines of prose/math,
         none ever needed one."""
    print("\n=== Scenario 2: bank problem, Solutions mode ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_sol_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "autoexam.tex", AUTOEXAM_TEX)
        run_build(tmp, "autoexam.tex", aux_directory="<<temp>>",
                  options=["--texlib-mode=solutions"])

        pdf = os.path.join(tmp, "autoexam.pdf")
        check("PDF was produced (solutions mode)", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESOLUTION")
        check("found the solution needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            # FIXED (free-response-solution-inverse-search): the solution's green fill is now a \smash\rlap'd
            # rule drawn INSIDE the content parbox, not a \colorbox \hbox wrapper.
            # \colorbox orphaned the inner nodes for SyncTeX reverse search (the
            # redirect staged bank.tex fine, but `synctex edit` at the rendered box
            # returned nothing); drawing the fill inside keeps the content reachable.
            check("click on the solution resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_SOLUTION_LINE})",
                  r["line"] == BANK_SOLUTION_LINE, f"got line {r['line']!r}")
            # Full-line clickability (SYNCTEX.md recommendation 2): a click at
            # the box's left edge on the solution's line -- left of every
            # glyph, where only the stamped containers can answer -- must
            # resolve to the solution source. Before container stamping the
            # whole strip left of the text was dead (tag-0 wrappers); measured:
            # x >= 72 (the text margin / box edge) resolves, and this pins it.
            # Residual, documented in SYNCTEX.md: the 6pt visual bleed LEFT of
            # the box edge, the "Solution." header line and the pad bands still
            # answer tag-0 emission-side wrappers (\parbox/\rlap built after
            # the stamp runs) -- cosmetic slivers, deliberately not gated.
            rp = synctex_edit(pdf, pos[0], 74.0, pos[2])
            check("click in the box's left padding resolves to bank.tex",
                  basename_matches(rp["input"], "bank.tex"), rp["raw"][:300])
            check(f"...at the solution's source line ({BANK_SOLUTION_LINE})",
                  rp["line"] == BANK_SOLUTION_LINE, f"got line {rp['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _page_offset_of_last_copy(combined_pdf, last_slice_pdf):
    """How many combined pages precede the LAST sliced copy.

    Derived from the two PDFs rather than from a known copy layout, so a change
    in how many copies a build mode emits cannot silently invalidate a
    hardcoded page arithmetic -- which is exactly what the 0.8.0 rename did.
    Returns None when pypdf is unavailable, so the caller can skip rather than
    fail on a missing optional dependency.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        return len(PdfReader(combined_pdf).pages) - len(
            PdfReader(last_slice_pdf).pages)
    except Exception:  # noqa: BLE001 - a malformed PDF is the test's problem
        return None


def scenario_sliced_copy_inverse_search():
    """The sliced per-version copies are pages carved out of the combined PDF
    with pypdf, so they carry no SyncTeX map of their own and a viewer looks for
    <its own name>.synctex, never the parent's -- double-clicking anywhere in
    one did nothing at all. The builder now cuts a matching map per copy
    (_slice_synctex_for_copies), which is what makes the preferred_pdf setting
    usable: opening <base>_A_solutions.pdf must not cost inverse search.

    Asserted against the real `synctex` CLI, and against the COMBINED map for
    the same physical page -- the slice is only correct if it answers
    identically, which also catches an off-by-one in the page renumbering that
    a "resolves to bank.tex" check alone would sail past."""
    print("\n=== Scenario 11: inverse search inside a sliced per-version copy ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_slice_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "autoexam.tex", AUTOEXAM_TEX)          # \versions{A,B}
        # `solutions' is AutoExamSolMode=only since the 0.8.0 rename (it is the
        # student-facing key), so this emits A-sol, B-sol -- not the four copies
        # A, B, A-sol, B-sol the pre-rename `solutions' produced. Every page
        # number below is derived rather than hardcoded because of exactly that:
        # the copy layout is not this scenario's subject, slice fidelity is.
        run_build(tmp, "autoexam.tex", aux_directory="<<temp>>",
                  options=["--texlib-mode=solutions"])    # -> only: A-sol, B-sol

        combined = os.path.join(tmp, "autoexam.pdf")
        slice_pdf = os.path.join(tmp, "autoexam_A_solutions.pdf")
        slice_map = os.path.join(tmp, "autoexam_A_solutions.synctex")
        check("combined PDF still produced alongside the slices",
              os.path.exists(combined))
        check("the solutions copy was sliced out", os.path.exists(slice_pdf))
        check("a SyncTeX map was cut for it", os.path.exists(slice_map))
        if not (os.path.exists(slice_pdf) and os.path.exists(slice_map)):
            return

        pos = find_word(slice_pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the sliced copy", pos is not None)
        if not pos:
            return
        r = synctex_edit(slice_pdf, *pos)
        check("click inside the SLICE resolves to bank.tex",
              basename_matches(r["input"], "bank.tex"), r["raw"][:300])
        check(f"...at the correct source line ({BANK_STEM_LINE})",
              r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")

        # Same point, same page, through the parent's map: the two must agree.
        # A-sol is the FIRST copy in an `only' build (it was the third when this
        # mode meant dual), so occurrence 1 is the one the slice was cut from.
        cpos = find_word(combined, "SYNCNEEDLESTEM", occurrence=1)
        if cpos:
            rc = synctex_edit(combined, *cpos)
            check("the slice answers exactly as the combined map does",
                  (r["input"], r["line"]) == (rc["input"], rc["line"]),
                  f"slice {r['input']}:{r['line']} vs combined "
                  f"{rc['input']}:{rc['line']}")

        # FORWARD search, the other direction. B-sol is the LAST copy in the
        # combined PDF, so its pages sit at the end and a combined answer must
        # come back shifted by everything before it. That shift is computed --
        # combined page count minus the slice's own -- rather than written down,
        # so the assertion survives a change in how many copies the mode emits.
        # It was hardcoded to 6 (four 2-page copies) and silently became wrong
        # the moment `solutions' stopped meaning dual.
        #
        # Asserted against B-sol rather than A-sol deliberately: forward search
        # into a multi-version exam resolves a bank line to ONE page, because the
        # per-problem SyncTeX redirect gives bank.tex an Input: tag per \@@input
        # and the lookup takes the last -- a pre-existing limitation of the
        # version loop, visible in the COMBINED PDF exactly as much as in a slice
        # (a document-body line resolves to no page at all there, the body being
        # re-emitted through a scratch file). The slice carries whatever the
        # parent had; that faithfulness is what is being checked here, not the
        # upstream lookup.
        bank_tex = os.path.join(tmp, "bank.tex")
        combined_pages = synctex_view(combined, bank_tex, BANK_STEM_LINE)
        bsol = os.path.join(tmp, "autoexam_B_solutions.pdf")
        if combined_pages and os.path.exists(bsol):
            slice_pages = synctex_view(bsol, bank_tex, BANK_STEM_LINE)
            check("forward search resolves through the slice's own map",
                  bool(slice_pages), f"combined gave {combined_pages}")
            offset = _page_offset_of_last_copy(combined, bsol)
            check("...to the page the combined answer maps onto",
                  slice_pages and combined_pages and offset is not None
                  and int(slice_pages[0]) == int(combined_pages[0]) - offset,
                  f"slice {slice_pages} vs combined {combined_pages}, "
                  f"offset {offset}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: document-attributed (non-bank) problem, WITH a page shipout
# before retrieval -- \maketitle in a real document always ships a title
# page first, so this is the realistic case, not an edge case. -------------
DOC_PROBLEM_TEX = (
    "\\documentclass[exam-number=1]{autoexam}\n"           # 1
    "\\begin{document}\n"                                  # 2
    "\\begin{problem}{inlineone}[topic=algebra]\n"         # 3
    "\tSolve SYNCNEEDLEBODYSTEM for x.\n"                  # 4
    "\t\\begin{solution}\n"                                # 5
    "\tSYNCNEEDLEBODYSOLUTION.\n"                           # 6
    "\t\\end{solution}\n"                                  # 7
    "\\end{problem}\n"                                     # 8
    "\\maketitle\n"                                        # 9
    "\\begin{problems}\n"                                  # 10
    "\\problem{inlineone}\n"                               # 11
    "\\end{problems}\n"                                    # 12
    "\\end{document}\n"                                    # 13
)
DOC_PROBLEM_STEM_LINE = 4


def scenario_document_attributed_problem():
    print("\n=== Scenario 3: document-body-defined problem, page shipout "
          "before retrieval ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_doc_")
    try:
        write(tmp, "inline-exam.tex", DOC_PROBLEM_TEX)
        run_build(tmp, "inline-exam.tex", aux_directory="<<temp>>")

        pdf = os.path.join(tmp, "inline-exam.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLEBODYSTEM")
        check("found the stem needle in the PDF (retrieval itself works)",
              pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to the exam file itself",
                  basename_matches(r["input"], "inline-exam.tex"), r["raw"][:300])
            check(f"...at the correct source line ({DOC_PROBLEM_STEM_LINE}), "
                  "not wherever the title page shipped out from",
                  r["line"] == DOC_PROBLEM_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: schedule class, aux-routed (the historically fragile path) ----
SCHEDULE_COURSEMETA_TEX = (
    "\\metasetup{\n"
    "\tinstitution     = {University of Nevada, Reno},\n"
    "\tinstructor      = {Test Instructor},\n"
    "\tseason          = Fall,\n"
    "\tyear            = 2026,\n"
    "\tcourse-subject  = Math,\n"
    "\tcourse-number   = 181,\n"
    "\tcourse-title    = {Calculus I},\n"
    "\tcourse-section  = 1001,\n"
    "\tlecture-days    = MWF,\n"
    "\tlecture-times   = {9:00-9:50am},\n"
    "\tstart-date      = 8-24,\n"
    "\tend-date        = 12-8,\n"
    "\tfinal-date      = 12-15,\n"
    "\tfinal-time      = {9:45-11:45am},\n"
    "}\n"
)
SCHEDULE_TEX = (
    "\\documentclass[landscape=true]{schedule}\n"    # 1
    "\\begin{document}\n"                             # 2
    "\\maketitle\n"                                   # 3
    "\\begin{schedule}\n"                             # 4
    # 8-26 (a Wednesday) falls in the FIRST calendar week given
    # start-date=8-24 below -- close to start-date on purpose, so the
    # holiday needle renders without needing enough \section filler to
    # make the calendar span all the way to some later date.
    "\t\\holiday{8-26}{SYNCNEEDLEHOLIDAY}\n"          # 5
    "\t\\syllabus\n"                                  # 6
    "\t\\section{Test Section One}\n"                 # 7
    "\\end{schedule}\n"                               # 8
    "\\end{document}\n"                               # 9
)
SCHEDULE_HOLIDAY_LINE = 5


def scenario_schedule_aux_routed():
    """xltabular defers real box shipout to end-of-file (confirmed with a
    trivial non-TeXLib xltabular table -- not fixable by a redirect-timing
    patch), so every cell's raw SyncTeX line collapses to one value absent
    from the schedmap. The safe behavior is the HONEST fallback: leave the
    Input record pointing at the auto-generated grid file rather than
    confidently repointing a wrong line at the real source (see
    texlib_builder.py's _rewrite_synctex_for_schedmap for the full writeup).
    This asserts that honest-fallback behavior, not per-cell precision."""
    print("\n=== Scenario 4: schedule class, aux_directory=<<temp>> ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_sched_")
    try:
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_TEX)
        result = run_build(tmp, "schedule.tex", aux_directory="<<temp>>")
        check("builder reports the honest per-cell-unavailable fallback "
              "(not a silent no-op, and not a false 'rewrote' claim)",
              "per-cell SyncTeX could not be applied" in result["displayed"],
              result["displayed"])

        pdf = os.path.join(tmp, "schedule.pdf")
        check("PDF was produced", os.path.exists(pdf))
        check("plain .synctex was produced", os.path.exists(os.path.join(tmp, "schedule.synctex")))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        check("found the holiday needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            # r["input"] is whatever absolute path SyncTeX itself resolved to
            # (e.g. the grid file may live in the aux_directory routing
            # target, not tex_dir) -- check the resolved path directly, not
            # reconstructed relative to tmp, since that's the exact path a
            # real editor would be asked to open.
            resolved_exists = bool(r["input"]) and os.path.exists(r["input"])
            check("click on the holiday cell resolves to a REAL, existing "
                  "file (the grid scratch file is the honest fallback here; "
                  "landing on a wrong line of schedule.tex would be worse)",
                  resolved_exists, r["raw"][:300])
            check("...and does NOT confidently mislabel it as schedule.tex "
                  "(the source) at some unrelated line",
                  not basename_matches(r["input"], "schedule.tex"),
                  f"input={r['input']!r} line={r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_schedule_plain_cli():
    """Plain CLI build (no Sublime builder, no schedmap rewrite): should still
    resolve to SOME real, existing file -- the documented fallback (landing in
    the auto-generated grid file) is acceptable here; a dangling/nonexistent
    reference would not be."""
    print("\n=== Scenario 5: schedule class, plain CLI (no Sublime builder) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_sched_cli_")
    try:
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_TEX)
        env = _texinputs_env(tmp)
        cmd = [LUALATEX, "-interaction=nonstopmode", "-synctex=1",
               "-shell-escape", "schedule.tex"]
        for _ in range(2):
            subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, timeout=180)

        pdf = os.path.join(tmp, "schedule.pdf")
        gz = os.path.join(tmp, "schedule.synctex.gz")
        check("PDF was produced", os.path.exists(pdf))
        check(".synctex.gz was produced (CLI build, no finalize step)", os.path.exists(gz))
        if not (os.path.exists(pdf) and os.path.exists(gz)):
            return

        pos = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        check("found the holiday needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            resolved_exists = bool(r["input"]) and os.path.exists(
                os.path.join(tmp, os.path.basename(r["input"]))
            )
            check("fallback resolves to a REAL, existing file",
                  resolved_exists, r["raw"][:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: a multiple-choice bank problem -- exercises emit_mc_tail's own
# call into emit_solution_block, a DIFFERENT code path than the FR case above
# (Scenario 2), never previously covered. ------------------------------------
MC_BANK_TEX = (
    "\\begin{problem}{mc_one}[topic=mctest]\n"      # 1
    "\tSolve SYNCNEEDLEMCSTEM for x.\n"              # 2
    "\t\\begin{choices}\n"                           # 3
    "\t\t\\cchoice SYNCNEEDLEMCCORRECT\n"             # 4
    "\t\t\\choice SYNCNEEDLEMCWRONG\n"                # 5
    "\t\\end{choices}\n"                              # 6
    "\t\\begin{solution}\n"                          # 7
    "\tSYNCNEEDLEMCSOLUTION explanation.\n"          # 8
    "\t\\end{solution}\n"                            # 9
    "\\end{problem}\n"                                # 10
)
MC_STEM_LINE = 2
MC_SOLUTION_LINE = 8

MC_AUTOEXAM_TEX = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\loadbank{mcbank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{mcproblems}\n"
    "\\problem{mc_one}\n"
    "\\end{mcproblems}\n"
    "\\end{document}\n"
)


def scenario_mc_bank_problem():
    """MC (multiple-choice) bank problem, Solutions mode: emit_mc_tail calls
    emit_solution_block on a DIFFERENT branch than the FR case in Scenario 2
    -- never previously exercised by this suite. Choices themselves are
    engine-selected/shuffled per version and intentionally have no fixed
    source line to redirect to (not asserted here); the stem and solution
    both should.

    HISTORY (mc-key-inverse-search, CLOSED): the solution's raw records always
    carried the correct source line; what failed was resolution -- the parser
    picks a click's answer by a container contest over boxes, and the boxes
    around the solution carried tag 0 / library tags (SYNCTEX.md has the full
    dissection). Container stamping in texlib_synctex.lua fixed both the
    side-by-side and stacked layouts; the checks below are hard now."""
    print("\n=== Scenario 6: MC bank problem, Solutions mode ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_mc_")
    try:
        write(tmp, "mcbank.tex", MC_BANK_TEX)
        write(tmp, "mcautoexam.tex", MC_AUTOEXAM_TEX)
        run_build(tmp, "mcautoexam.tex", aux_directory="<<temp>>",
                  options=["--texlib-mode=solutions"])

        pdf = os.path.join(tmp, "mcautoexam.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLEMCSTEM")
        check("found the MC stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the MC stem resolves to mcbank.tex",
                  basename_matches(r["input"], "mcbank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({MC_STEM_LINE})",
                  r["line"] == MC_STEM_LINE, f"got line {r['line']!r}")

        pos2 = find_word(pdf, "SYNCNEEDLEMCSOLUTION")
        check("found the MC solution needle in the PDF", pos2 is not None)
        if pos2:
            r2 = synctex_edit(pdf, *pos2)
            # FIXED (mc-key-inverse-search, closed by container stamping): the
            # side-by-side minipage layout orphaned the solution because the
            # BOXES around the correctly-attributed glyphs carried tag 0 or a
            # library tag, and the viewer's parser resolves clicks by a
            # container contest over boxes (SYNCTEX.md). texlib_synctex.lua now
            # harvests the solution's own (tag,line) from its body glyphs and
            # stamps every container/rule in the finished box, so BOTH layouts
            # inverse-search. Hard checks: a regression fails loud.
            check("click on the MC solution resolves to mcbank.tex",
                  basename_matches(r2["input"], "mcbank.tex"), r2["raw"][:300])
            check(f"...at the correct source line ({MC_SOLUTION_LINE})",
                  r2["line"] == MC_SOLUTION_LINE, f"got line {r2['line']!r}")

        # FIXED via opt-in: the side-by-side layout above is a deliberate trade-off
        # (the compact "four keys per page" packing) whose minipage box orphans the
        # solution for reverse search. \TeXLibMCKeyStacked renders the MC solution
        # STACKED (full-width below the choices, in the vertical list), so it DOES
        # inverse-search. Prove that here with HARD checks -- a regression fails loud.
        write(tmp, "mcstacked.tex", MC_AUTOEXAM_TEX.replace(
            "\\begin{document}", "\\TeXLibMCKeyStacked\n\\begin{document}", 1))
        run_build(tmp, "mcstacked.tex", aux_directory="<<temp>>",
                  options=["--texlib-mode=solutions"])
        spdf = os.path.join(tmp, "mcstacked.pdf")
        sp = find_word(spdf, "SYNCNEEDLEMCSOLUTION")
        check("[\\TeXLibMCKeyStacked] found the MC solution needle", sp is not None)
        if sp:
            sr = synctex_edit(spdf, *sp)
            check("[\\TeXLibMCKeyStacked] MC solution resolves to mcbank.tex",
                  basename_matches(sr["input"], "mcbank.tex"), sr["raw"][:300])
            check(f"[\\TeXLibMCKeyStacked] ...at line {MC_SOLUTION_LINE}",
                  sr["line"] == MC_SOLUTION_LINE, f"got line {sr['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: the quiz class, a different root class from autoexam, using
# its own \question \getproblem{id} retrieval style (not \problem{filter}
# inside {problems}) -- shares texlib-problembank.sty but never previously
# built through this suite. Reuses BANK_TEX (same needles/lines as Scenario
# 1/2) since the bank format itself doesn't vary by class. --------------------
QUIZ_TEX = (
    "\\documentclass[quiz-number=1]{quiz}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{questions}\n"
    "\\question \\getproblem{quad_one}\n"
    "\\end{questions}\n"
    "\\end{document}\n"
)


def scenario_quiz_bank_problem():
    print("\n=== Scenario 7: quiz class, bank problem via \\getproblem ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_quiz_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "quiz.tex", QUIZ_TEX)
        run_build(tmp, "quiz.tex", aux_directory="<<temp>>")

        pdf = os.path.join(tmp, "quiz.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_STEM_LINE})",
                  r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: a \ppart part carrying a {partsolution} -------------------------
# {partsolution} shipped from 0.7.1 with no call site anywhere in the repo, so
# nothing here ever built one and its inverse search was never measured. Line
# numbers are load-bearing.
PARTSOL_BANK_TEX = (
    "% partsolution fixture\n"                                  # 1
    "\\begin{problem}{ppsol}[topic=fr]\n"                       # 2
    "\tPARTSOLSTEM the stem line.\n"                            # 3
    "\t\\begin{parts}\n"                                        # 4
    "\t\t\\ppart PARTSOLPART the first part.\n"                 # 5
    "\t\t\\begin{partsolution}\n"                               # 6
    "\t\t\tPARTSOLANSWER is the worked part answer.\n"          # 7
    "\t\t\\end{partsolution}\n"                                 # 8
    "\t\\end{parts}\n"                                          # 9
    "\\end{problem}\n"                                          # 10
)
PARTSOL_ANSWER_LINE = 7

PARTSOL_QUIZ_TEX = (
    "\\documentclass[quiz-number=1]{quiz}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{problems}\n"
    "\\problem{ppsol}\n"
    "\\end{problems}\n"
    "\\end{document}\n"
)


def scenario_partsolution_inverse_search():
    """A click on a part solution's answer must land on the ANSWER, not on
    \\end{partsolution}.

    {partsolution} harvested its SyncTeX target from the body box and stamped
    that same body box. Everything built afterwards -- the wrap vtop carrying
    the "Solution." header and rubric, and \\@partsol@frame's parbox, its two
    \\smash\\rlap wrappers and the tint/accent rules -- was created while TeX was
    reading the \\end line, kept that line, and NESTED OUTSIDE the stamped box.
    {solution} survives the same shape (its unstamped chrome is a documented
    cosmetic residual), but a part solution sits one level deeper, inside the
    exam-class {parts} list, and there the outer line-8 containers win the
    parser's smallest-then-deepest contest.

    Measured before the fix, in BOTH the key and key-inline layouts: right file,
    line 8 instead of 7. The left padding band -- answered by the stamped
    container -- was already correct, which is what made this invisible.

    Fix: harvest from the body box, assemble, then stamp the finished frame.
    Both layouts are asserted because key-inline routes the frame through a
    zero-height \\raisebox that the normal layout does not have.
    """
    for mode in ("key", "key-inline"):
        print(f"\n=== Scenario 12: {{partsolution}} inverse search ({mode}) ===")
        tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_partsol_")
        try:
            write(tmp, "bank.tex", PARTSOL_BANK_TEX)
            write(tmp, "quiz.tex", PARTSOL_QUIZ_TEX)
            run_build(tmp, "quiz.tex", aux_directory="<<temp>>",
                      options=[f"--texlib-mode={mode}"])

            pdf = os.path.join(tmp, "quiz.pdf")
            check(f"PDF was produced ({mode})", os.path.exists(pdf))
            if not os.path.exists(pdf):
                continue

            pos = find_word(pdf, "PARTSOLANSWER")
            check(f"the part solution rendered ({mode})", pos is not None)
            if not pos:
                continue
            r = synctex_edit(pdf, *pos)
            check(f"click on the part answer resolves to bank.tex ({mode})",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the answer's line ({PARTSOL_ANSWER_LINE}), not the "
                  f"\\end line ({mode})",
                  r["line"] == PARTSOL_ANSWER_LINE, f"got line {r['line']!r}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: didactic (lecture notes), a non-exam class that also loads
# texlib-problembank so a lecture handout can \getproblem{id} directly in
# running prose -- never previously built through this suite. ---------------
DIDACTIC_TEX = (
    # didactic is NOT in the builder's auto-lualatex class list (only
    # autoexam/quiz/schedule/report-card are) -- it silently defers its
    # LuaLaTeX requirement until a bank command is actually used (see
    # project notes), so a document that calls \getproblem needs this magic
    # comment or a plain pdflatex build fatals. Matches the real, documented
    # gotcha (root chapterN.tex files needed this same fix 2026-06-16).
    "% !TeX program = lualatex\n"
    "\\documentclass{didactic}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\getproblem{quad_one}\n"
    "\\end{document}\n"
)


def scenario_didactic_bank_problem():
    print("\n=== Scenario 8: didactic (lecture notes), bank problem via \\getproblem ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_didactic_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "didactic.tex", DIDACTIC_TEX)
        # engine="lualatex": didactic isn't in the builder's forced-lualatex
        # class list, so this simulates LaTeXTools having already resolved
        # the %!TeX program magic comment in DIDACTIC_TEX before the builder
        # runs -- a plain pdflatex default would silently fatal here (see
        # DIDACTIC_TEX's own comment and the documented gotcha).
        result = run_build(tmp, "didactic.tex", aux_directory="<<temp>>",
                            engine="lualatex")

        pdf = os.path.join(tmp, "didactic.pdf")
        check("PDF was produced", os.path.exists(pdf), result["displayed"][:500])
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_STEM_LINE})",
                  r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: schedule class in BOX-GRID mode (box-grid=true) ---------------
# The box grid draws the calendar as stacked box rows instead of an xltabular,
# so each cell ships eagerly and SyncTeX records it against its OWN grid-file
# line -- which is what makes the .schedmap rewrite land clicks on the real
# source line (the whole point of the mode). These scenarios assert that REAL
# per-cell accuracy, in contrast to scenarios 4/5 which assert the honest
# fallback the DEFAULT (xltabular) renderer is stuck with.
SCHEDULE_BOXGRID_TEX = (
    "\\documentclass[landscape=true, box-grid=true]{schedule}\n"  # 1
    "\\begin{document}\n"                                          # 2
    "\\maketitle\n"                                                # 3
    "\\begin{schedule}\n"                                          # 4
    "\t\\holiday{8-26}{SYNCNEEDLEHOLIDAY}\n"                       # 5
    "\t\\syllabus\n"                                               # 6
    "\t\\section{SYNCNEEDLESECTION}\n"                             # 7
    "\\end{schedule}\n"                                            # 8
    "\\end{document}\n"                                            # 9
)
BOXGRID_HOLIDAY_LINE = 5
BOXGRID_SECTION_LINE = 7


def _stage_schedule_engine(tmp):
    """Copy THIS repo's schedule engine (schedule.cls + the .lua files) plus the
    shared .sty/.lua into the fixture dir so `.` resolves them ahead of anything
    the junction/TEXINPUTS points at. Necessary because box-grid support may be
    an uncommitted/worktree change while the machine's junction still points at
    a box-grid-unaware checkout -- the fixture must exercise the code under test,
    not whatever schedule.cls is on the search path."""
    for pat in ("*.sty", "*.lua"):
        for f in glob.glob(os.path.join(TEXLIB_ROOT, pat)):
            shutil.copy(f, tmp)
    sched = os.path.join(TEXLIB_ROOT, "Schedule")
    for f in glob.glob(os.path.join(sched, "*.lua")):
        shutil.copy(f, tmp)
    shutil.copy(os.path.join(sched, "schedule.cls"), tmp)


def scenario_schedule_boxgrid_builder():
    """Box-grid via the real builder (aux routing + schedmap rewrite): a click
    on a calendar cell must resolve to the SOURCE .tex at the directive's line
    -- real per-cell inverse search, the outcome the xltabular path cannot
    reach. This is the assertion scenarios 4/5 would love to make but can't."""
    print("\n=== Scenario 9: schedule BOX-GRID via builder (real per-cell) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_boxgrid_")
    try:
        _stage_schedule_engine(tmp)
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_BOXGRID_TEX)
        result = run_build(tmp, "schedule.tex", aux_directory="<<temp>>")
        check("builder reports it mapped real cell records to the user source "
              "(box grid, not the honest-fallback message)",
              "cell record(s) to the user source" in result["displayed"],
              result["displayed"])

        pdf = os.path.join(tmp, "schedule.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        # Holiday cell -> its \holiday directive line.
        pos = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        check("found the holiday needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the holiday cell resolves to schedule.tex",
                  basename_matches(r["input"], "schedule.tex"), r["raw"][:300])
            check(f"...at the holiday's own source line ({BOXGRID_HOLIDAY_LINE})",
                  r["line"] == BOXGRID_HOLIDAY_LINE, f"got line {r['line']!r}")

        # Section cell -> its \section directive line: proves DISTINCT cells map
        # to DISTINCT lines (the collapse would put both on one line).
        pos2 = find_word(pdf, "SYNCNEEDLESECTION")
        check("found the section needle in the PDF", pos2 is not None)
        if pos2:
            r2 = synctex_edit(pdf, *pos2)
            check("click on the section cell resolves to schedule.tex",
                  basename_matches(r2["input"], "schedule.tex"), r2["raw"][:300])
            check(f"...at the section's OWN source line ({BOXGRID_SECTION_LINE}), "
                  "distinct from the holiday's -- per-cell, not collapsed",
                  r2["line"] == BOXGRID_SECTION_LINE, f"got line {r2['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_schedule_boxgrid_plain_cli():
    """Box-grid plain CLI (no builder rewrite): each cell's raw attribution
    already lands on its OWN grid-file line (that's what the box grid buys, with
    or without the rewrite), so a click resolves to the grid file at the line
    whose content is that cell -- a genuinely useful fallback, unlike xltabular's
    collapse-to-last-line. We assert the two cells resolve to DIFFERENT grid
    lines (the collapse signature is both landing on the same line)."""
    print("\n=== Scenario 10: schedule BOX-GRID, plain CLI (per-cell grid lines) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_boxgrid_cli_")
    try:
        _stage_schedule_engine(tmp)
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_BOXGRID_TEX)
        env = _texinputs_env(tmp)
        cmd = [LUALATEX, "-interaction=nonstopmode", "-synctex=1",
               "-shell-escape", "schedule.tex"]
        for _ in range(2):
            subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, timeout=180)

        pdf = os.path.join(tmp, "schedule.pdf")
        gz = os.path.join(tmp, "schedule.synctex.gz")
        check("PDF was produced", os.path.exists(pdf))
        check(".synctex.gz was produced", os.path.exists(gz))
        if not (os.path.exists(pdf) and os.path.exists(gz)):
            return

        ph = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        ps = find_word(pdf, "SYNCNEEDLESECTION")
        check("found both needles in the PDF", ph is not None and ps is not None)
        if ph and ps:
            rh = synctex_edit(pdf, *ph)
            rs = synctex_edit(pdf, *ps)
            grid_bn = "schedule_schedule_grid.tex"
            check("holiday cell resolves into the grid file",
                  basename_matches(rh["input"], grid_bn), rh["raw"][:200])
            check("section cell resolves into the grid file",
                  basename_matches(rs["input"], grid_bn), rs["raw"][:200])
            check("the two cells land on DIFFERENT grid lines (per-cell, not "
                  "collapsed to one line as xltabular does)",
                  rh["line"] is not None and rs["line"] is not None
                  and rh["line"] != rs["line"],
                  f"holiday line={rh['line']!r} section line={rs['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("TeXLib SyncTeX inverse-search integration test\n")
    print(f"  build root: {_build_root()}\n")
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext (-bbox support) found.")
        return 0
    if not SYNCTEX:
        print("  SKIP  synctex CLI not found.")
        return 0

    scenario_bank_multiversion()
    scenario_bank_solutions_mode()
    scenario_document_attributed_problem()
    scenario_schedule_aux_routed()
    scenario_schedule_plain_cli()
    scenario_mc_bank_problem()
    scenario_quiz_bank_problem()
    scenario_didactic_bank_problem()
    scenario_schedule_boxgrid_builder()
    scenario_schedule_boxgrid_plain_cli()
    scenario_sliced_copy_inverse_search()
    scenario_partsolution_inverse_search()

    summary = f"\n{_c.passed} passed, {_c.failed} failed"
    if _c.known:
        summary += f", {_c.known} known (tracked, not blocking)"
    print(summary)
    return 1 if _c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
