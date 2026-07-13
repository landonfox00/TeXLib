#!/usr/bin/env python3
"""
Real-build coverage for three TeXLib engine-emission edges that the existing
suites only test against HAND-WRITTEN sidecars or not at all. Every scenario
drives a real lualatex build and reads the rendered PDF back with poppler
`pdftotext`, so a disagreement between what the engine emits and what actually
lands on the page fails here (a fabricated-sidecar unit test cannot).

  1. `.vmap` version-split markers -- the EMITTER, not just the slicer.
     test_texlib_builder.py's vmap tests feed `_slice_versions_from_vmap`
     HAND-WRITTEN `<ver>|stu|<page>` sidecars, so the emitter (autoexam.cls's
     \\AutoExamVmapRecord, driven by autoexam_run_versions in
     problem_engine.lua) and the slicer could disagree and both "pass". Here a
     real `\\versions{A,B}` + \\ShowSolutions exam is built, the ENGINE-emitted
     .vmap is read from the aux dir, and each marker's page is cross-checked
     against the real PDF: the referenced page must BE that version/copy's
     cover ("Version <letter>", plus the red "Solutions" banner iff a sol
     marker) and no other page may. The builder's real slice step is then run
     over the emitted sidecar to prove emitter and slicer agree end-to-end.

  2. "Page X of Y" footer resolving across the two-pass build. The exam's
     center footer is "\\thepage of <page-count reference>" that only reaches
     the .aux at end of run (autoexam.cls: \\pageref*{@lastqpage} with a
     `lastpage` fallback); the shared analog is texlib-footer.sty:38's
     `\\thepage\\ of \\pageref{LastPage}` (didactic/pset). Both need the
     `lastpage` package (texlib-assessment.sty:14) and a second pass, and a
     one-pass or aux-misrouted build leaves "of ??". Nothing asserted that
     today. Here a one-pass build is shown to contain "of ??" (the regression
     IS observable) and a two-pass build to have resolved it to "<n> of <N>".

  3. `\\ppart` atomicity under \\shuffle + a standalone `\\importproblem`.
     Neither had a buildable fixture. A multi-part problem (\\ppart x3) inside
     a \\shuffle+\\versions exam is built; pdftotext confirms its parts stay
     CONTIGUOUS (no other problem interleaves between them) and sub-number
     correctly ("<q>a." "<q>b." "<q>c.") in every version, even the one where
     \\shuffle sandwiches it between two other problems. A minimal
     \\importproblem fixture confirms an imported standalone problem's stem
     renders.

Why raw lualatex instead of TexlibBuilder.commands(): the real builder deletes
the .vmap in _postprocess right after slicing, so a full builder run leaves
nothing to inspect for edge 1. Each scenario therefore drives the engine
directly (two passes, aux routed to a temp dir) to keep the emitted sidecar,
then feeds THAT real sidecar through the builder's real slicer.

Shared library files are copied into each (comma-free) temp build dir rather
than reached via TEXINPUTS: this worktree lives under a path containing a comma
("...Nevada, Reno..."), which kpathsea silently cannot search, and the
C:\\_texlibjunc junction points at the LIVE checkout, not this worktree -- so
the copy is the only way to guarantee the build tests THIS tree's files.

Soft-skips (exit 0) if lualatex or a poppler-flavored pdftotext (-layout, not
Git's xpdf build) is missing, matching test_synctex_integration.py's
degrade-don't-fail convention. The builder-slicer sub-check additionally
soft-skips if TexlibBuilder / pypdf can't be imported.

Run:  python Sublime/test_engine_emit_edges.py     (exit 0 ok/skipped, 1 fail)
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

# Refuse to run inside Sublime: the LaTeXTools stub installed for the slicer
# sub-check would clobber the real PdfBuilder (same guard as test_texlib_builder).
if "sublime" in sys.modules:
    raise SystemExit

TEXLIB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBLIME_DIR = os.path.dirname(os.path.abspath(__file__))

LUALATEX = shutil.which("lualatex")

from _testkit import Checker  # noqa: E402
_c = Checker()
check = _c.check


from _testkit import find_poppler  # noqa: E402


PDFTOTEXT = find_poppler()


# --- Build-dir assembly ------------------------------------------------------
def _copy_shared_into(tmp, class_home=None):
    """Copy the TeXLib-root shared files (.sty/.lua/.cls) and every module's
    .cls into a build dir, then the class's home-module files (instructions /
    title .tex the class \\inputs). Never overwrites. Mirrors smoke_test.py's
    cwd-copy strategy that dodges the comma-in-TEXINPUTS kpathsea limit."""
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            shutil.copy2(src, tmp)
    for entry in os.listdir(TEXLIB_ROOT):
        sub = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isdir(sub):
            for f in os.listdir(sub):
                if f.lower().endswith(".cls"):
                    dest = os.path.join(tmp, f)
                    if not os.path.exists(dest):
                        shutil.copy2(os.path.join(sub, f), dest)
    if class_home:
        home = os.path.join(TEXLIB_ROOT, class_home)
        for f in os.listdir(home):
            src = os.path.join(home, f)
            if os.path.isfile(src) and not os.path.exists(os.path.join(tmp, f)):
                shutil.copy2(src, tmp)


def _write(tmp, name, content):
    with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
        fh.write(content)


def _build(tmp, tex_name, aux_dir, passes=2, mode_def=""):
    """Run lualatex `passes` times, aux routed to aux_dir (-output-directory +
    TEXLIB_AUX_DIR so the Lua engine's own scratch routes there too). Returns
    the last CompletedProcess. mode_def is an optional \\def injected before
    \\input (e.g. r'\\def\\ShowSolutions{}')."""
    os.makedirs(aux_dir, exist_ok=True)
    env = os.environ.copy()
    env["TEXLIB_AUX_DIR"] = aux_dir
    arg = (mode_def + "\\input{" + tex_name + "}") if mode_def else tex_name
    cmd = [LUALATEX, "-interaction=nonstopmode", "-synctex=1", "-shell-escape",
           f"-output-directory={aux_dir}", arg]
    last = None
    for _ in range(passes):
        last = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env,
                              timeout=180)
    return last


def _page_texts(pdf_path):
    """Per-page text of the PDF (poppler -layout), split on the form feed
    between pages. Index i-1 is 1-based page i; a trailing empty split from the
    final page's form feed is harmless."""
    out = subprocess.run(
        [PDFTOTEXT, "-layout", pdf_path, "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    return out.split("\f")


def _flat(text):
    return " ".join(text.split())


# --- Shared fixtures ---------------------------------------------------------
# Trimmed from examples/Math181-Fall2026/coursemeta.tex: the keys an autoexam
# cover / assessment footer actually reads (exam1-date feeds the cover date).
COURSEMETA = (
    "\\metasetup{\n"
    "  institution     = {University of Nevada, Reno},\n"
    "  instructor      = {Landon Fox},\n"
    "  season          = Fall,\n"
    "  year            = 2026,\n"
    "  course-subject  = Math,\n"
    "  course-number   = 181,\n"
    "  course-title    = {Calculus I},\n"
    "  course-section  = 1001,\n"
    "  start-date      = 8-24,\n"
    "  end-date        = 12-8,\n"
    "  final-date      = 12-15,\n"
    "  final-time      = {9:45-11:45am},\n"
    "  exam1-date      = {Sep 19, 2026},\n"
    "}\n"
)


def is_cover_for(page_text, ver, sol):
    """True iff `page_text` is version `ver`'s cover of the right copy kind.
    Binds a vmap marker to a specific page: the cover carries "Version <ver>"
    and no other version, and the red "Solutions" banner appears iff this is a
    solutions (`sol == "sol"`) copy. Problem/blank pages carry no "Version ..."
    marker, so they are rejected -- which is what makes a wrong-page marker
    fail."""
    low = page_text.lower()
    has_ver = f"version {ver}".lower() in low
    has_other = any(
        o != ver and f"version {o}".lower() in low for o in ("A", "B")
    )
    has_sol = "solutions" in low
    return has_ver and not has_other and (has_sol == (sol == "sol"))


# ============================================================================ #
# Edge 1: .vmap version-split markers -- the EMITTER, cross-checked vs the PDF
# ============================================================================ #
VMAP_BANK = (
    "\\begin{problem}{p-alpha}[topic=alpha]\n"
    "\tCompute VMAPALPHA: $1+1$.\n"
    "\t\\begin{solution} VMAPALPHASOL: it equals 2. \\end{solution}\n"
    "\\end{problem}\n"
    "\n"
    "\\begin{problem}{p-beta}[topic=beta]\n"
    "\tCompute VMAPBETA: $2+2$.\n"
    "\t\\begin{solution} VMAPBETASOL: it equals 4. \\end{solution}\n"
    "\\end{problem}\n"
)

VMAP_EXAM = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\versions{A, B}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{problems}\n"
    "\t\\problem{topic=alpha}\n"
    "\t\\problem{topic=beta}\n"
    "\\end{problems}\n"
    "\\end{document}\n"
)


def _parse_vmap(path):
    """Parse `<ver>|<sol>|<page>` lines into a list of (ver, sol, page)."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) == 3 and parts[2].isdigit():
                rows.append((parts[0], parts[1], int(parts[2])))
    return rows


def _load_builder():
    """Install the LaTeXTools stub and import TexlibBuilder for the slicer
    sub-check. Returns the class, or None if unavailable."""
    try:
        import types
        for name in ("LaTeXTools", "LaTeXTools.plugins",
                     "LaTeXTools.plugins.builder",
                     "LaTeXTools.plugins.builder.pdf_builder"):
            sys.modules.setdefault(name, types.ModuleType(name))

        class _StubPdfBuilder:
            def __init__(self, *a, **k):
                self._displayed = ""

            def display(self, msg):
                self._displayed += str(msg)

        sys.modules["LaTeXTools.plugins.builder.pdf_builder"].PdfBuilder = _StubPdfBuilder
        if SUBLIME_DIR not in sys.path:
            sys.path.insert(0, SUBLIME_DIR)
        import pypdf  # noqa: F401  (slicer runs in-process only when present)
        from texlib_builder import TexlibBuilder
        return TexlibBuilder
    except Exception:
        return None


def _slice_check(combined_pdf, vmap_path, records):
    """Feed the ENGINE-emitted sidecar through the builder's real slicer and
    assert each produced per-copy PDF is exactly its version's cover + content.
    Proves emitter and slicer agree end-to-end (not just that each passes its
    own fabricated fixture)."""
    Builder = _load_builder()
    if Builder is None:
        print("  SKIP  slicer sub-check (TexlibBuilder / pypdf unavailable)")
        return
    slice_dir = tempfile.mkdtemp(prefix="texlib_emit_slice_")
    try:
        base = os.path.join(slice_dir, "exam")
        shutil.copy2(combined_pdf, base + ".pdf")
        shutil.copy2(vmap_path, base + ".vmap")
        vb = Builder()
        vb.tex_dir = slice_dir
        vb.base_name = "exam"
        vb._aux_target = None
        vb._slice_versions_from_vmap(slice_dir, base)

        # Content each version's copy must / must not contain.
        stu_needles = {"A": "VMAPALPHA", "B": "VMAPBETA"}
        sol_needles = {"A": "VMAPALPHASOL", "B": "VMAPBETASOL"}
        for ver, sol, _page in records:
            suffix = f"_{ver}" + ("_solutions" if sol == "sol" else "")
            slice_pdf = base + suffix + ".pdf"
            check(f"slicer produced exam{suffix}.pdf ({ver}/{sol})",
                  os.path.exists(slice_pdf))
            if not os.path.exists(slice_pdf):
                continue
            pages = _page_texts(slice_pdf)
            check(f"  ...its first page is version {ver}'s {sol} cover",
                  is_cover_for(pages[0], ver, sol),
                  _flat(pages[0])[:160])
            whole = _flat("\n".join(pages)).lower()
            check(f"  ...contains only version {ver} (no other version label)",
                  f"version {ver}".lower() in whole
                  and all(f"version {o}".lower() not in whole
                          for o in ("A", "B") if o != ver))
            check(f"  ...carries this copy's own content needle",
                  (sol_needles[ver] if sol == "sol" else stu_needles[ver]).lower()
                  in whole)
            if sol != "sol":
                check("  ...a student copy shows no solution needle / banner",
                      sol_needles[ver].lower() not in whole
                      and "solutions" not in whole)
    finally:
        shutil.rmtree(slice_dir, ignore_errors=True)


def scenario_vmap_version_split():
    print("\n=== Edge 1: .vmap version-split markers (emitter vs real PDF) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_emit_vmap_")
    aux = tempfile.mkdtemp(prefix="texlib_emit_vmap_aux_")
    try:
        _copy_shared_into(tmp, class_home="Exams")
        _write(tmp, "coursemeta.tex", COURSEMETA)
        _write(tmp, "bank.tex", VMAP_BANK)
        _write(tmp, "exam.tex", VMAP_EXAM)
        # \ShowSolutions => dual mode: student copies of every version, then
        # instructor copies -> A|stu, B|stu, A|sol, B|sol.
        _build(tmp, "exam.tex", aux, passes=2, mode_def=r"\def\ShowSolutions{}")

        pdf = os.path.join(aux, "exam.pdf")
        vmap = os.path.join(aux, "exam.vmap")
        check("combined PDF was produced", os.path.exists(pdf))
        check("engine emitted a .vmap in the aux dir", os.path.exists(vmap))
        if not (os.path.exists(pdf) and os.path.exists(vmap)):
            return

        records = _parse_vmap(vmap)
        check("vmap records are exactly {A,B} x {stu,sol}",
              {(v, s) for v, s, _ in records}
              == {("A", "stu"), ("B", "stu"), ("A", "sol"), ("B", "sol")},
              repr(records))
        pages = _page_texts(pdf)
        n = len([p for p in pages if p.strip()])

        prev = 0
        for ver, sol, page in records:
            check(f"{ver}|{sol}: page {page} in range and after the previous",
                  prev < page <= n, f"prev={prev} page={page} n={n}")
            prev = page
            # The marker's page must be THIS copy's cover and no other page may
            # be -- so a marker pointing at the wrong page fails here.
            matches = [i + 1 for i, t in enumerate(pages)
                       if is_cover_for(t, ver, sol)]
            check(f"{ver}|{sol}: page {page} is the unique {ver}/{sol} cover",
                  matches == [page],
                  f"pages matching ({ver},{sol}) = {matches}, marker said {page}")

        # Discrimination: the predicate rejects the page AFTER each cover (the
        # problem page), proving these assertions aren't vacuously true.
        first = records[0]
        prob_idx = first[2]  # 0-based index of the page after the cover
        if prob_idx < len(pages):
            check("cover predicate rejects the following (problem) page",
                  not is_cover_for(pages[prob_idx], first[0], first[1]))

        _slice_check(pdf, vmap, records)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(aux, ignore_errors=True)


# ============================================================================ #
# Edge 2: "Page X of Y" footer resolves across the two-pass build
# ============================================================================ #
FOOTER_BANK = (
    "\\begin{problem}{p-alpha}[topic=alpha]\n"
    "\tCompute FOOTERALPHA: $1+1$.\n"
    "\t\\begin{solution} s. \\end{solution}\n"
    "\\end{problem}\n"
    "\\begin{problem}{p-beta}[topic=beta]\n"
    "\tCompute FOOTERBETA: $2+2$.\n"
    "\t\\begin{solution} s. \\end{solution}\n"
    "\\end{problem}\n"
)

FOOTER_EXAM = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{problems}\n"
    "\t\\problem{topic=alpha}\n"
    "\t\\problem{topic=beta}\n"
    "\\end{problems}\n"
    "\\end{document}\n"
)

OF_UNRESOLVED = "of ??"
# "<page> of <count>" -- a leading page number distinguishes the footer from a
# stray "... of 2026" in the cover date / institution line.
OF_RESOLVED_RE = re.compile(r"\b\d+\s+of\s+\d+\b")


def _build_footer(passes):
    tmp = tempfile.mkdtemp(prefix=f"texlib_emit_foot{passes}_")
    aux = tempfile.mkdtemp(prefix=f"texlib_emit_foot{passes}_aux_")
    _copy_shared_into(tmp, class_home="Exams")
    _write(tmp, "coursemeta.tex", COURSEMETA)
    _write(tmp, "bank.tex", FOOTER_BANK)
    _write(tmp, "exam.tex", FOOTER_EXAM)
    _build(tmp, "exam.tex", aux, passes=passes)
    pdf = os.path.join(aux, "exam.pdf")
    text = "\n".join(_page_texts(pdf)) if os.path.exists(pdf) else None
    return pdf, text, tmp, aux


def scenario_footer_page_of_n():
    print("\n=== Edge 2: 'Page X of Y' footer across the two-pass build ===")
    # One pass: LastPage isn't in the .aux yet, so the footer shows "of ??".
    # Asserting this makes the two-pass assertion meaningful (the regression it
    # guards is observable output, not a silent internal state).
    pdf1, text1, tmp1, aux1 = _build_footer(1)
    try:
        check("one-pass build produced a PDF", os.path.exists(pdf1))
        if text1 is not None:
            check("one pass leaves the footer unresolved ('of ??' present)",
                  OF_UNRESOLVED in text1,
                  "expected an unresolved \\pageref{LastPage} on a single pass")
    finally:
        shutil.rmtree(tmp1, ignore_errors=True)
        shutil.rmtree(aux1, ignore_errors=True)

    # Two passes: LastPage resolves -> "of <N>", no "of ??".
    pdf2, text2, tmp2, aux2 = _build_footer(2)
    try:
        check("two-pass build produced a PDF", os.path.exists(pdf2))
        if text2 is not None:
            check("two passes leave no unresolved 'of ??' footer",
                  OF_UNRESOLVED not in text2)
            check("two passes resolve the footer to 'of <N>'",
                  bool(OF_RESOLVED_RE.search(text2)),
                  _flat(text2)[-160:])
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)
        shutil.rmtree(aux2, ignore_errors=True)


# ============================================================================ #
# Edge 3a: \ppart atomicity under \shuffle + \versions
# ============================================================================ #
PPART_BANK = (
    "\\begin{problem}{p-multi}[topic=multi]\n"
    "\tStem PARTSTEMNEEDLE with several parts.\n"
    "\t\\begin{parts}\n"
    "\t\t\\ppart Evaluate PARTNEEDA here.\n"
    "\t\t\\ppart Evaluate PARTNEEDB here.\n"
    "\t\t\\ppart Evaluate PARTNEEDC here.\n"
    "\t\\end{parts}\n"
    "\t\\begin{solution} PARTSOLNEEDLE done. \\end{solution}\n"
    "\\end{problem}\n"
    "\n"
    "\\begin{problem}{p-fill1}[topic=fillone]\n"
    "\tSingle problem FILLONESTEM: $1+1$.\n"
    "\t\\begin{solution} s. \\end{solution}\n"
    "\\end{problem}\n"
    "\n"
    "\\begin{problem}{p-fill2}[topic=filltwo]\n"
    "\tSingle problem FILLTWOSTEM: $2+2$.\n"
    "\t\\begin{solution} s. \\end{solution}\n"
    "\\end{problem}\n"
)

# \problem[2,3,4]{...} distributes per-part points to the three \ppart calls;
# \shuffle reorders the three problems independently per version (seeded by the
# version letter), so the multi-part problem lands at a different position in A
# vs B -- the case where a non-atomic \ppart could let a filler slip between
# parts.
PPART_EXAM = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\versions{A, B}\n"
    "\\shuffle\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{problems}\n"
    "\t\\problem[2,3,4]{topic=multi}\n"
    "\t\\problem{topic=fillone}\n"
    "\t\\problem{topic=filltwo}\n"
    "\\end{problems}\n"
    "\\end{document}\n"
)

FILLER_STEMS = ("FILLONESTEM", "FILLTWOSTEM")


def _version_spans(records, num_pages):
    """From student-copy vmap records, map each version to its (start,end) page
    range [start, end) covering that copy's cover + problem pages."""
    stu = sorted(((v, p) for v, s, p in records if s == "stu"),
                 key=lambda x: x[1])
    spans = {}
    for i, (ver, start) in enumerate(stu):
        end = stu[i + 1][1] if i + 1 < len(stu) else num_pages + 1
        spans[ver] = (start, end)
    return spans


def _check_ppart_contiguous(ver, text):
    a = text.find("PARTNEEDA")
    b = text.find("PARTNEEDB")
    c = text.find("PARTNEEDC")
    stem = text.find("PARTSTEMNEEDLE")
    check(f"[{ver}] all three \\ppart parts render", min(a, b, c, stem) >= 0,
          f"stem={stem} a={a} b={b} c={c}")
    if min(a, b, c, stem) < 0:
        return
    check(f"[{ver}] parts appear in order a<b<c after the stem",
          stem < a < b < c, f"stem={stem} a={a} b={b} c={c}")
    lo, hi = stem, c
    for f in FILLER_STEMS:
        pos = text.find(f)
        check(f"[{ver}] no '{f}' interleaves between the parts (atomic)",
              pos < 0 or not (lo < pos < hi),
              f"{f} at {pos}, parts span [{lo},{hi}]")
    # Sub-numbering: the parts carry the multi-part problem's own question
    # number, "<q>a." "<q>b." "<q>c." in order.
    heading = None
    for m in re.finditer(r"Problem\s+(\d+)\.", text[:stem]):
        heading = m.group(1)
    check(f"[{ver}] the multi-part problem has a 'Problem <n>.' heading",
          heading is not None)
    if heading is None:
        return
    la = text.find(f"{heading}a.", stem)
    lb = text.find(f"{heading}b.", stem)
    lc = text.find(f"{heading}c.", stem)
    check(f"[{ver}] parts sub-number correctly as {heading}a./{heading}b./{heading}c.",
          0 <= la < lb < lc, f"a={la} b={lb} c={lc}")


def scenario_ppart_atomicity():
    print("\n=== Edge 3a: \\ppart atomicity under \\shuffle + \\versions ===")
    tmp = tempfile.mkdtemp(prefix="texlib_emit_ppart_")
    aux = tempfile.mkdtemp(prefix="texlib_emit_ppart_aux_")
    try:
        _copy_shared_into(tmp, class_home="Exams")
        _write(tmp, "coursemeta.tex", COURSEMETA)
        _write(tmp, "bank.tex", PPART_BANK)
        _write(tmp, "exam.tex", PPART_EXAM)
        _build(tmp, "exam.tex", aux, passes=2)

        pdf = os.path.join(aux, "exam.pdf")
        vmap = os.path.join(aux, "exam.vmap")
        check("combined PDF was produced", os.path.exists(pdf))
        check("engine emitted a .vmap (two student copies)",
              os.path.exists(vmap))
        if not (os.path.exists(pdf) and os.path.exists(vmap)):
            return

        records = _parse_vmap(vmap)
        pages = _page_texts(pdf)
        num_pages = len([p for p in pages if p.strip()])
        spans = _version_spans(records, num_pages)
        check("both versions A and B are present in the vmap",
              set(spans) == {"A", "B"}, repr(records))

        version_orders = {}
        for ver in ("A", "B"):
            if ver not in spans:
                continue
            start, end = spans[ver]
            joined = _flat("\n".join(pages[start - 1:end - 1]))
            _check_ppart_contiguous(ver, joined)
            order = [s for _, s in sorted(
                (joined.find(s), s) for s in
                ("PARTSTEMNEEDLE",) + FILLER_STEMS if joined.find(s) >= 0)]
            version_orders[ver] = order

        # Informational: \shuffle should give the two versions different
        # orders (it does with these seeds), which is what makes atomicity a
        # non-trivial property to hold. Not a hard failure if a future seed
        # change collapses them -- contiguity above is the real assertion.
        if len(version_orders) == 2 and version_orders["A"] == version_orders["B"]:
            print("  NOTE  both versions shuffled to the same order this build; "
                  "atomicity still asserted, but the case is less adversarial.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(aux, ignore_errors=True)


# ============================================================================ #
# Edge 3b: \importproblem renders a standalone problem's stem
# ============================================================================ #
STANDALONE_PROBLEM = (
    "% A standalone problem file, \\input either directly or via \\importproblem.\n"
    "Compute IMPORTSTEMNEEDLE: the derivative of $x^2$ is $2x$.\n"
)

IMPORT_DOC = (
    "% !TeX program = lualatex\n"
    "\\documentclass{didactic}\n"
    "\\begin{document}\n"
    "\\section{Imported}\n"
    "\\importproblem{standalone-problem.tex}{}\n"
    "\\end{document}\n"
)


def scenario_importproblem_stem():
    print("\n=== Edge 3b: \\importproblem renders a standalone problem's stem ===")
    tmp = tempfile.mkdtemp(prefix="texlib_emit_import_")
    aux = tempfile.mkdtemp(prefix="texlib_emit_import_aux_")
    try:
        _copy_shared_into(tmp, class_home="Notes")
        _write(tmp, "coursemeta.tex", COURSEMETA)
        _write(tmp, "standalone-problem.tex", STANDALONE_PROBLEM)
        _write(tmp, "doc.tex", IMPORT_DOC)
        _build(tmp, "doc.tex", aux, passes=2)

        pdf = os.path.join(aux, "doc.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return
        text = _flat("\n".join(_page_texts(pdf)))
        check("the imported problem's stem renders",
              "IMPORTSTEMNEEDLE" in text, text[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(aux, ignore_errors=True)


def main():
    print("TeXLib engine-emission edge tests\n")
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext (-layout) found.")
        return 0

    scenario_vmap_version_split()
    scenario_footer_page_of_n()
    scenario_ppart_atomicity()
    scenario_importproblem_stem()

    print(f"\n{_c.passed} passed, {_c.failed} failed")
    return 1 if _c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
