#!/usr/bin/env python3
"""End-to-end integration test for TeXLib's autoexam shuffle guarantees at the
RENDERED-PDF level.

test_shuffle.lua exercises only the pure permute() core (a list -> a permuted
list); it can never see the typeset pipeline that wraps it -- collect at
\\problem time, permute per version, emit through pbank_problem_item, dual
student/solutions emission, per-version seeding. This test drives a REAL
lualatex build of a self-contained 3-version exam (student + solutions copies
of A/B/C in one combined PDF) and reads the PDF back with poppler's pdftotext
to assert the shuffle INVARIANTS hold on the actual page -- the only place a
regression in the emit path (as opposed to permute()) can be caught.

The headline case is the just-fixed "student copy order == solutions copy
order" regression: the two copies of a version must present identical question
order (or the answer key doesn't line up with the exam). That bug lived
entirely in the emit-time seeding (pbank_emit_partno reset per copy), which
test_shuffle.lua's pure-function scope structurally cannot reach. Scenario (e)
locks it forever.

Shuffle makes exam pages non-deterministic, which is why they are excluded from
visual regression (VISUAL_MODULES in smoke_test.py). But the shuffle
GUARANTEES are deterministic even though the order is random: same problem set
every version, points travel with their stem, extra credit pinned last,
sections never bleed into each other, student == solutions per version. Those
are what this asserts -- properties, never a byte match to one drawn order.

A second block asserts three rendering GEOMETRY properties (solution-box right
margin, extra-credit chrome, workbox suppression). Two of them encode the
CORRECTED behavior of a separately-tracked fix (task_c3867d2b) that is not on
this base branch yet, so they are marked known_issue: honest (they start
passing, loudly, the moment that fix lands) without failing CI for a gap that
is deliberately not fixed here. Do NOT weaken them to the current buggy state.

Soft-skips (exit 0) if lualatex or a poppler-flavored pdftotext (-bbox support)
is missing; the pixel-scan geometry checks additionally soft-skip if poppler's
pdftoppm is missing -- matching test_synctex_integration.py's
degrade-don't-fail convention.

Run:  python Sublime/test_shuffle_integration.py     (exit 0 ok/skipped, 1 fail)
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

# TeXLib repo root (this file lives in Sublime/); the shared .cls/.sty/.lua that
# the fixture pulls in resolve from here via TEXINPUTS.
TEXLIB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DPI = 150   # pdftoppm rasterization DPI for the geometry pixel scans


# ============================================================================
# Toolchain discovery + TEXINPUTS
# ============================================================================
def _texinputs_env():
    """Env with TEXINPUTS extended so the repo-root shared files resolve while
    building in a scratch dir OUTSIDE the repo.

    kpathsea cannot search an absolute TEXINPUTS entry containing a comma, and
    the live OneDrive checkout path has one ("University of Nevada, Reno").
    Precedence:
      1. TEXLIB_IT_ROOT (explicit, comma-free) -- lets a worktree that itself
         lives under the comma path point the build at its OWN files (a plain
         C:\\_texlibjunc fallback would compile against the shared checkout
         instead, silently the wrong tree).
      2. C:\\_texlibjunc (the machine's comma-free junction to the live
         checkout) when TEXLIB_ROOT is itself comma-containing.
      3. TEXLIB_ROOT directly (CI/Linux, or any comma-free checkout).
    """
    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    root = os.environ.get("TEXLIB_IT_ROOT") or TEXLIB_ROOT
    if (not os.environ.get("TEXLIB_IT_ROOT") and os.name == "nt"
            and "," in root and os.path.isdir(r"C:\_texlibjunc")):
        root = r"C:\_texlibjunc"
    root = root.replace(os.sep, "/")
    env["TEXINPUTS"] = sep.join([".", root + "//", env.get("TEXINPUTS", "")])
    return env


def _find_poppler(tool):
    """A poppler-flavored `tool` (pdftotext/pdftoppm). Git for Windows ships an
    xpdf-flavored pdftotext that shadows poppler's on PATH and silently lacks
    -bbox (prints its usage instead of erroring), so probe the version banner
    and take the first candidate whose banner says poppler."""
    candidates = []
    which = shutil.which(tool)
    if which:
        candidates.append(which)
    candidates.append(rf"C:\texlive\2025\bin\windows\{tool}.exe")
    for cand in candidates:
        try:
            proc = subprocess.run([cand, "-v"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if "poppler" in ((proc.stdout or "") + (proc.stderr or "")).lower():
            return cand
    return None


LUALATEX = shutil.which("lualatex")
PDFTOTEXT = _find_poppler("pdftotext")
PDFTOPPM = _find_poppler("pdftoppm")


# ============================================================================
# Pass/fail bookkeeping (mirrors test_synctex_integration.py)
# ============================================================================
_PASS = 0
_FAIL = 0
_KNOWN_FAIL = 0
_SKIP = 0


def check(label, cond, detail="", known_issue=None):
    """known_issue: a tracker reference for an assertion that encodes the
    CORRECT/intended behavior but is not expected to pass yet, pending
    separately-tracked follow-up. Keeps the assertion honest (it flips to PASS
    the moment the real fix lands) without failing CI for a known, deliberately
    out-of-scope gap."""
    global _PASS, _FAIL, _KNOWN_FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    elif known_issue:
        _KNOWN_FAIL += 1
        print(f"  KNOWN {label}  (tracked: {known_issue})")
        if detail:
            print(f"        {detail}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def skip(label):
    global _SKIP
    _SKIP += 1
    print(f"  SKIP  {label}")


# ============================================================================
# Fixture: a self-contained 3-version exam
# ============================================================================
# Metadata mirrors examples/Math181-Fall2026/ (coursemeta + course-preamble) so
# the cover renders a real course header. Each problem carries a DISTINCT
# ALL-CAPS needle (never a real word, so pdftotext can't match it by accident)
# AND a distinct point value, so a problem is identifiable across shuffled
# versions by either. Points are surfaced in the PDF text via a PTS<N>PTS marker
# in \questionlabel: the exam class prints no per-question points by default,
# and this exposes the engine's own \question[N] value (from \@points) as a
# parseable token co-located with the stem -- so "points travel" is read from
# what the ENGINE bound to each problem, not from the fixture's own authoring.
COURSEMETA_TEX = r"""\metasetup{
	institution     = {University of Nevada, Reno},
	instructor      = {Landon Fox},
	season          = Fall,
	year            = 2026,
	course-subject  = Math,
	course-number   = 181,
	course-title    = {Calculus I},
	course-section  = 1001,
	exam1-date      = {Sep 19, 2026},
	preamble-file   = {course-preamble},
}
"""

PREAMBLE_TEX = r"""\newcommand{\ivt}{Intermediate Value Theorem}
"""

# Six free-response problems + three multiple-choice, each with a solution and a
# distinct point value. \ivt exercises the auto-loaded course preamble.
BANK_TEX = r"""% Self-contained bank for the shuffle integration test.
\begin{problem}{p-limes}[topic=limes]
	NEEDLELIMES Evaluate $\lim_{x\to3}\frac{x^2-9}{x-3}$.
	\begin{solution}
	SOLLIMES The limit is $6$.
	\end{solution}
\end{problem}

\begin{problem}{p-contour}[topic=contour]
	NEEDLECONTOUR Is the piecewise function continuous at $x=1$?
	\begin{solution}
	SOLCONTOUR Yes, the one-sided limits agree.
	\end{solution}
\end{problem}

\begin{problem}{p-ivory}[topic=ivory]
	NEEDLEIVORY Use the \ivt{} to show $x^3-x-1=0$ has a root in $(1,2)$.
	\begin{solution}
	SOLIVORY $g(1)<0<g(2)$, apply the theorem.
	\end{solution}
\end{problem}

\begin{problem}{p-derby}[topic=derby]
	NEEDLEDERBY Differentiate $f(x)=x^4-3x$.
	\begin{solution}
	SOLDERBY $f'(x)=4x^3-3$.
	\end{solution}
\end{problem}

\begin{problem}{p-integral}[topic=integral]
	NEEDLEINTGL Compute $\int_0^1 (2x+1)\,dx$.
	\begin{solution}
	SOLINTGL The integral is $2$.
	\end{solution}
\end{problem}

\begin{problem}{p-serum}[topic=serum]
	NEEDLESERUM Does $\sum 1/n^2$ converge?
	\begin{solution}
	SOLSERUM Yes, a convergent $p$-series.
	\end{solution}
\end{problem}

\begin{problem}{p-mcapple}[topic=mcapple]
	NEEDLEMCAPPLE What is $\frac{d}{dx}\sin x$?
	\begin{choices}
		\cchoice $\cos x$
		\choice $-\cos x$
		\choice $\sin x$
		\choice $-\sin x$
	\end{choices}
	\begin{solution}
	SOLMCAPPLE The derivative is $\cos x$.
	\end{solution}
\end{problem}

\begin{problem}{p-mcpear}[topic=mcpear]
	NEEDLEMCPEAR What is $\int \frac{1}{x}\,dx$?
	\begin{choices}
		\cchoice $\ln|x|+C$
		\choice $-1/x^2+C$
		\choice $x\ln x+C$
		\choice $1/x+C$
	\end{choices}
	\begin{solution}
	SOLMCPEAR The antiderivative is $\ln|x|+C$.
	\end{solution}
\end{problem}

\begin{problem}{p-mcplum}[topic=mcplum]
	NEEDLEMCPLUM What is $\lim_{x\to\infty}\frac{1}{x}$?
	\begin{choices}
		\cchoice $0$
		\choice $1$
		\choice $\infty$
		\choice undefined
	\end{choices}
	\begin{solution}
	SOLMCPLUM The limit is $0$.
	\end{solution}
\end{problem}
"""

# Two {problems} Parts (I, II) + one {mcproblems} Part (III). Part II ends with
# \extracredit[5]{...}. Regular points sum to 70 (matches points={70}); extra
# credit is excluded from that total. \shuffle + \solutions => the combined PDF
# holds A/B/C student copies then A/B/C solutions copies.
EXAM_TEX = r"""\documentclass[exam-number={1}, points={70}]{autoexam}
\loadbank{bank.tex}
\versions{A, B, C}
\shuffle
\solutions

% Surface the engine's \question[N] points as a parseable PTS<N>PTS token in the
% problem label (the exam class shows no per-question points by default). \@points
% is exam.cls's raw value for the question about to be typeset.
\makeatletter
\renewcommand{\questionlabel}{\textbf{Problem \thequestion.} PTS\@points PTS}
\makeatother

\begin{document}
\maketitle

\begin{problems}
	\problem[6]{p-limes}
	\problem[8]{p-contour}
	\problem[9]{p-ivory}
\end{problems}

\begin{problems}
	\problem[11]{p-derby}
	\problem[12]{p-integral}
	\problem[14]{p-serum}
	\extracredit[5]{NEEDLEBONUS Prove that $\lim_{x\to0}\frac{\sin x}{x}=1$.}
\end{problems}

\begin{mcproblems}
	\problem[7]{p-mcapple}
	\problem[2]{p-mcpear}
	\problem[1]{p-mcplum}
\end{mcproblems}

\end{document}
"""

# Authored problem membership per Part (roman -> needle set). The shuffle must
# never move a problem across a Part boundary.
AUTHORED = {
    "I":   {"NEEDLELIMES", "NEEDLECONTOUR", "NEEDLEIVORY"},
    "II":  {"NEEDLEDERBY", "NEEDLEINTGL", "NEEDLESERUM", "NEEDLEBONUS"},
    "III": {"NEEDLEMCAPPLE", "NEEDLEMCPEAR", "NEEDLEMCPLUM"},
}
EC_NEEDLE = "NEEDLEBONUS"
# Authored (needle -> points) for the graded problems; the extra credit is
# excluded (its label carries the previous problem's stale \@points, and its own
# "5" shows via the "(Extra Credit, 5 points)" text, not \question[N]).
AUTHORED_POINTS = {
    "NEEDLELIMES": 6, "NEEDLECONTOUR": 8, "NEEDLEIVORY": 9,
    "NEEDLEDERBY": 11, "NEEDLEINTGL": 12, "NEEDLESERUM": 14,
    "NEEDLEMCAPPLE": 7, "NEEDLEMCPEAR": 2, "NEEDLEMCPLUM": 1,
}


def _write(d, name, content):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        fh.write(content)


def build_exam():
    """Write the fixture to a scratch source dir and run lualatex TWICE with
    -output-directory to a temp build dir (natural jobname 'exam'). Two passes
    settle the per-copy "page X of Y" footer and the label/pageref cross-refs.
    Returns the combined PDF path (or None on failure), plus the temp root so
    the caller can clean it up."""
    root = tempfile.mkdtemp(prefix="texlib_shuffle_it_")
    src = os.path.join(root, "src")
    out = os.path.join(root, "build")
    os.makedirs(src)
    os.makedirs(out)
    _write(src, "coursemeta.tex", COURSEMETA_TEX)
    _write(src, "course-preamble.tex", PREAMBLE_TEX)
    _write(src, "bank.tex", BANK_TEX)
    _write(src, "exam.tex", EXAM_TEX)

    env = _texinputs_env()
    cmd = [LUALATEX, "-interaction=nonstopmode", "-shell-escape", "-synctex=1",
           "-output-directory=" + out, "exam.tex"]
    for _ in range(2):
        subprocess.run(cmd, cwd=src, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300, env=env)
    pdf = os.path.join(out, "exam.pdf")
    return (pdf if os.path.exists(pdf) else None), root


# ============================================================================
# PDF text extraction (pdftotext)
# ============================================================================
_WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"[^>]*>([^<]*)</word>')
_PAGE_RE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)"')
_VERSION_RE = re.compile(r'Version\s+([ABC])')
_PART_RE = re.compile(r'Part\s+([IVX]+)')
_PTS_NEEDLE_RE = re.compile(r'PTS(\d+)PTS.*?(NEEDLE\w+)', re.S)


def page_texts(pdf):
    out = subprocess.run([PDFTOTEXT, pdf, "-"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    pages = out.split("\f")
    while pages and pages[-1].strip() == "":   # pdftotext appends a trailing \f
        pages.pop()
    return pages


def word_pages(pdf):
    """Per-page word boxes: [{'w','h','words':[(x0,y0,x1,y1,text), ...]}]. y is
    PDF points from the top -- pdftotext -bbox's own convention."""
    xml = subprocess.run([PDFTOTEXT, "-bbox", pdf, "-"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    pages = []
    cur = None
    for line in xml.splitlines():
        pm = _PAGE_RE.search(line)
        if pm:
            cur = {"w": float(pm.group(1)), "h": float(pm.group(2)), "words": []}
            pages.append(cur)
            continue
        wm = _WORD_RE.search(line)
        if wm and cur is not None:
            cur["words"].append((float(wm.group(1)), float(wm.group(2)),
                                 float(wm.group(3)), float(wm.group(4)), wm.group(5)))
    return pages


def needles_visual(word_page):
    """Needles on a page in true top-to-bottom VISUAL order (sorted by yMin),
    not pdftotext's stream order."""
    ns = [(y0, t) for (x0, y0, x1, y1, t) in word_page["words"] if t.startswith("NEEDLE")]
    ns.sort()
    return [t for _, t in ns]


def find_copies(texts):
    """Locate every copy by its cover page (the only page carrying "Version").
    Each copy spans [cover_page, next_cover_page). Solutions copies are the ones
    whose cover bears the red "Solutions" banner. Page numbers are NOT
    hardcoded -- pagination depends on answer-space and shifts."""
    covers = []
    for i, pg in enumerate(texts):
        if "Version" in pg:
            m = _VERSION_RE.search(pg)
            covers.append((i, m.group(1) if m else "?",
                           bool(re.search(r"\bSolutions\b", pg))))
    copies = []
    for k, (pi, ver, sol) in enumerate(covers):
        end = covers[k + 1][0] if k + 1 < len(covers) else len(texts)
        copies.append({"ver": ver, "sol": sol, "start": pi, "end": end})
    return copies


def copy_parts(copy, texts, wpages):
    """{roman -> ordered needle list} for one copy. A Part heading ("Part N")
    opens a Part; every page until the next heading belongs to it (so a Part
    spanning multiple pages after a pagination shift still collects correctly)."""
    parts = {}
    cur = None
    for pi in range(copy["start"], copy["end"]):
        m = _PART_RE.search(texts[pi])
        if m:
            cur = m.group(1)
        if cur is None or pi >= len(wpages):
            continue
        parts.setdefault(cur, []).extend(needles_visual(wpages[pi]))
    return parts


def copy_points(copy, texts):
    """{needle -> engine points} for the graded problems of one copy. Each
    PTS<N>PTS marker pairs with the stem needle that immediately follows it; the
    extra credit is excluded (its marker carries a stale value by design)."""
    pts = {}
    for pi in range(copy["start"], copy["end"]):
        for val, needle in _PTS_NEEDLE_RE.findall(texts[pi]):
            if needle != EC_NEEDLE:
                pts[needle] = int(val)
    return pts


# ============================================================================
# PDF pixel scan (pdftoppm) -- for the geometry checks a rule/box has no text
# ============================================================================
def _read_ppm(path):
    """Parse a binary P6 PPM into (w, h, pixels-as-bytes). Pure stdlib, so the
    test needs no imaging library."""
    with open(path, "rb") as f:
        data = f.read()
    assert data[:2] == b"P6", data[:2]
    idx = 2
    vals = []
    while len(vals) < 3:
        while data[idx:idx + 1].isspace():
            idx += 1
        if data[idx:idx + 1] == b"#":                # comment line
            while data[idx:idx + 1] not in (b"\n", b""):
                idx += 1
            continue
        s = idx
        while not data[idx:idx + 1].isspace():
            idx += 1
        vals.append(int(data[s:idx]))
    w, h, _maxv = vals
    idx += 1                                          # single whitespace after maxval
    return w, h, data[idx:idx + w * h * 3]


def render_page(pdf, page, prefix):
    """Rasterize one page to a PPM (vector anti-aliasing OFF so thin rules stay
    crisp for edge detection). Returns the PPM path or None."""
    subprocess.run([PDFTOPPM, "-r", str(DPI), "-aaVector", "no",
                    "-f", str(page), "-l", str(page), pdf, prefix, "-q"],
                   capture_output=True)
    got = sorted(glob.glob(prefix + "*.ppm"))
    return got[0] if got else None


def _horizontal_rules(w, h, pix, min_frac=0.5, dark=110):
    """Detect near-horizontal dark rules (each a long run of dark pixels on one
    row). Adjacent rows are merged. Returns [(y_center, left_x, right_x)]."""
    rows = []
    for y in range(h):
        base = y * w * 3
        run = best = bl = br = cl = 0
        for x in range(w):
            o = base + x * 3
            if pix[o] < dark and pix[o + 1] < dark and pix[o + 2] < dark:
                if run == 0:
                    cl = x
                run += 1
                if run > best:
                    best, bl, br = run, cl, x
            else:
                run = 0
        if best >= int(w * min_frac):
            rows.append((y, bl, br))
    out = []
    group = []
    for r in rows:
        if group and r[0] - group[-1][0] > 3:
            out.append((sum(a[0] for a in group) / len(group),
                        group[0][1], max(a[2] for a in group)))
            group = []
        group.append(r)
    if group:
        out.append((sum(a[0] for a in group) / len(group),
                    group[0][1], max(a[2] for a in group)))
    return out


def _separator_rules(w, h, pix):
    """The inter-problem separator rules only. The header rule (~7% down the
    page) and footer rule (~95% down) both bleed WIDER into the margins than the
    text-block separators, so excluding their y-zones isolates the separators
    (whose right edge is exactly the right text margin)."""
    return [r for r in _horizontal_rules(w, h, pix)
            if 0.15 * h < r[0] < 0.90 * h]


def _green_box_right(w, h, pix):
    """Rightmost pale-green pixel (the green!3!white {solution} box background,
    ~RGB(247,255,247): G a few counts above R==B). Excludes the dark green left
    accent and black text. None if no box is on the page."""
    maxx = -1
    for y in range(h):
        base = y * w * 3
        for x in range(w - 1, maxx, -1):
            o = base + x * 3
            r, g, b = pix[o], pix[o + 1], pix[o + 2]
            if g >= r + 4 and g >= b + 4 and g >= 235:
                if x > maxx:
                    maxx = x
                break
    return maxx if maxx >= 0 else None


def _px_to_pt(px):
    return px * 72.0 / DPI


# ============================================================================
# Shuffle-invariant scenarios
# ============================================================================
def scenario_shuffle_invariants(copies, parts_by, points_by):
    print("\n=== Shuffle invariants (rendered PDF) ===")
    romans = ["I", "II", "III"]
    versions = "ABC"

    # (a) Same problem SET in every version; order not identical across all three.
    for rm in romans:
        sets = {frozenset(parts_by[k].get(rm, [])) for k in parts_by}
        check(f"(a) Part {rm}: identical problem set across all copies",
              len(sets) == 1, f"sets={sets}")
    shuffled_sections = 0
    for rm in romans:
        orders = {v: tuple(parts_by[(v, False)].get(rm, [])) for v in versions}
        if len({o for o in orders.values()}) > 1:
            shuffled_sections += 1
    # Allow a small-n coincidence in ONE section (3 items -> orders can collide),
    # but the exam as a whole must show the shuffle: assert "not all three equal"
    # holds in all but at most one section.
    check("(a) versions are shuffled (not-all-three-equal in >= 2 of 3 sections)",
          shuffled_sections >= len(romans) - 1,
          f"{shuffled_sections}/{len(romans)} sections show distinct version orders")

    # (b) Points travel: each point value stays attached to the same stem.
    base_pts = points_by[("A", False)]
    check("(b) engine points map recovered for every graded problem",
          set(base_pts) == set(AUTHORED_POINTS) and base_pts == AUTHORED_POINTS,
          f"got={base_pts}")
    check("(b) point values are distinct (a swap would be detectable)",
          len(set(base_pts.values())) == len(base_pts))
    travels = all(points_by[k] == base_pts for k in points_by)
    check("(b) every copy binds the same points to the same stem",
          travels, f"maps={points_by}")

    # (c) Extra credit LAST in every copy (student and solutions, every version).
    ec_last = True
    for k, parts in parts_by.items():
        pii = parts.get("II", [])
        if not pii or pii[-1] != EC_NEEDLE:
            ec_last = False
            print(f"        EC not last in {k}: {pii}")
    check("(c) extra credit is last in Part II of every copy", ec_last)

    # (d) Section boundaries: no problem crosses between Parts.
    boundaries_ok = True
    for k, parts in parts_by.items():
        for rm, ns in parts.items():
            if not set(ns) <= AUTHORED[rm]:
                boundaries_ok = False
                print(f"        boundary violation {k} Part {rm}: {ns}")
    check("(d) every Part's problems stay within that Part's authored set",
          boundaries_ok)

    # (e) THE KEY ONE: student copy order == that version's solutions copy order.
    for v in versions:
        mism = []
        for rm in romans:
            s = tuple(parts_by[(v, False)].get(rm, []))
            k = tuple(parts_by[(v, True)].get(rm, []))
            if s != k:
                mism.append((rm, s, k))
        check(f"(e) version {v}: student order == solutions order (all Parts)",
              not mism, f"mismatches={mism}")

    # MC section specifically (the real exam uses MC): differs across versions
    # and student == solutions per version. Part III is the {mcproblems} block;
    # (a)/(e) already cover it, but assert it explicitly since it is a distinct
    # emit path (emit_mc_tail / resolve_mc_order).
    mc_orders = {v: tuple(parts_by[(v, False)].get("III", [])) for v in versions}
    check("(MC) multiple-choice order differs across versions",
          len({o for o in mc_orders.values()}) > 1, f"orders={mc_orders}")
    mc_e = all(parts_by[(v, False)].get("III") == parts_by[(v, True)].get("III")
               for v in versions)
    check("(MC) student MC order == solutions MC order per version", mc_e)


# ============================================================================
# Geometry scenarios
# ============================================================================
def _first_multiproblem_part_page(copy, texts, wpages, want_parts=("I", "II")):
    """First page of `copy` that belongs to a wanted FR Part and holds >= 2
    problems (>= 1 inter-problem separator). Returns (page_index, roman)."""
    cur = None
    for pi in range(copy["start"], copy["end"]):
        m = _PART_RE.search(texts[pi])
        if m:
            cur = m.group(1)
        if cur in want_parts and pi < len(wpages):
            if sum(1 for w in wpages[pi]["words"] if w[4].startswith("NEEDLE")) >= 2:
                return pi, cur
    return None, None


def _part_page_with(copy, texts, wpages, roman, needle):
    """The page of `copy` in Part `roman` that contains `needle`."""
    cur = None
    for pi in range(copy["start"], copy["end"]):
        m = _PART_RE.search(texts[pi])
        if m:
            cur = m.group(1)
        if cur == roman and pi < len(wpages):
            if any(w[4] == needle for w in wpages[pi]["words"]):
                return pi
    return None


def scenario_geometry(pdf, copies, texts, wpages, tmp):
    print("\n=== Rendering geometry ===")
    by = {(c["ver"], c["sol"]): c for c in copies}

    # --- geom (c): student is taller/spread, solutions is compact (workbox
    # suppressed). Deterministic and true on the base branch already, so this is
    # a hard assertion. Measure the vertical span of a Part's problems. --------
    def part_span(copy, roman):
        cur = None
        ys = []
        for pi in range(copy["start"], copy["end"]):
            m = _PART_RE.search(texts[pi])
            if m:
                cur = m.group(1)
            if cur == roman and pi < len(wpages):
                ys += [w[1] for w in wpages[pi]["words"] if w[4].startswith("NEEDLE")]
        return (max(ys) - min(ys)) if len(ys) >= 2 else 0
    for rm in ("I", "II"):
        sstu = part_span(by[("A", False)], rm)
        ssol = part_span(by[("A", True)], rm)
        check(f"geom(c) Part {rm}: student copy spans more than solutions copy",
              sstu > ssol + 20,
              f"student span={sstu:.0f}pt solutions span={ssol:.0f}pt")

    if not PDFTOPPM:
        skip("geom(a)/geom(b) pixel scans (poppler pdftoppm not found)")
        return

    # --- geom (a): the green {solution} box right edge aligns with the
    # inter-problem separator-rule right edge (both at the right text margin).
    # CORRECTED behavior of task_c3867d2b: on this base branch the full-textwidth
    # box renders inside the {questions} list indent that \noindent does not
    # remove, so it overhangs the right margin (box right > separator right).
    solA = by[("A", True)]
    pi, _rm = _first_multiproblem_part_page(solA, texts, wpages)
    if pi is None:
        skip("geom(a) no solutions FR page with >=2 problems found")
    else:
        ppm = render_page(pdf, pi + 1, os.path.join(tmp, "geomA"))
        if not ppm:
            skip("geom(a) pdftoppm produced no image")
        else:
            w, h, pix = _read_ppm(ppm)
            seps = _separator_rules(w, h, pix)
            sep_right = max((r[2] for r in seps), default=None)
            box_right = _green_box_right(w, h, pix)
            if sep_right is None or box_right is None:
                skip("geom(a) could not locate separator rule or solution box")
            else:
                tol = int(DPI * 0.15)   # ~15px @150dpi; base overhang is ~40px
                check("geom(a) solution-box right edge aligns with separator rule",
                      abs(sep_right - box_right) <= tol,
                      f"box_right={box_right}px sep_right={sep_right}px "
                      f"diff={abs(sep_right - box_right)}px (tol {tol}px)",
                      known_issue="task_c3867d2b")

    # --- geom (b): on a STUDENT build the extra-credit item gets the same chrome
    # as a graded problem -- a separator rule ABOVE it and answer space BELOW it.
    # CORRECTED behavior of task_c3867d2b: the base branch replays the deferred
    # bonus with neither. -------------------------------------------------------
    stuA = by[("A", False)]
    pb = _part_page_with(stuA, texts, wpages, "II", EC_NEEDLE)
    if pb is None:
        skip("geom(b) student Part II page with extra credit not found")
        return
    wp = wpages[pb]
    h_pt = wp["h"]
    ns = sorted([(y0, y1, t) for (x0, y0, x1, y1, t) in wp["words"]
                 if t.startswith("NEEDLE")])
    bonus = next((n for n in ns if n[2] == EC_NEEDLE), None)
    regs = [n for n in ns if n[2] != EC_NEEDLE]
    if bonus is None or not regs:
        skip("geom(b) extra credit shares no page with a graded problem")
        return
    last_reg = regs[-1]

    # answer space below EC (bbox): comparable to a graded problem's answer gap.
    gap_below = h_pt - bonus[1]
    reg_gaps = [ns[i][0] - ns[i - 1][1] for i in range(1, len(ns)) if ns[i][2] != EC_NEEDLE]
    med_gap = sorted(reg_gaps)[len(reg_gaps) // 2] if reg_gaps else 0
    check("geom(b) extra credit reserves answer space below it (like a problem)",
          med_gap > 0 and gap_below >= 0.6 * med_gap,
          f"gap below EC={gap_below:.0f}pt median graded gap={med_gap:.0f}pt",
          known_issue="task_c3867d2b")

    # separator rule above EC (pixels): a text-block rule between the last graded
    # problem's stem and the EC stem.
    ppm = render_page(pdf, pb + 1, os.path.join(tmp, "geomB"))
    if not ppm:
        skip("geom(b) pdftoppm produced no image for the separator check")
        return
    w, h, pix = _read_ppm(ppm)
    rule_ys_pt = [_px_to_pt(r[0]) for r in _separator_rules(w, h, pix)]
    sep_above = any(last_reg[1] < ry < bonus[0] for ry in rule_ys_pt)
    check("geom(b) extra credit has a separator rule above it (like a problem)",
          sep_above,
          f"EC stem yTop={bonus[0]:.0f}pt, last graded yBot={last_reg[1]:.0f}pt, "
          f"separator rule ys={[round(y) for y in rule_ys_pt]}",
          known_issue="task_c3867d2b")


# ============================================================================
def main():
    print("TeXLib autoexam shuffle rendered-PDF integration test\n")
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext (-bbox support) found.")
        return 0

    pdf, root = build_exam()
    try:
        check("combined A/B/C student+solutions PDF was produced", pdf is not None)
        if pdf is None:
            return 1 if _FAIL else 0

        texts = page_texts(pdf)
        wpages = word_pages(pdf)
        copies = find_copies(texts)

        # Dual mode: 3 student copies (A/B/C) then 3 solutions copies (A/B/C).
        expected = [("A", False), ("B", False), ("C", False),
                    ("A", True), ("B", True), ("C", True)]
        got = [(c["ver"], c["sol"]) for c in copies]
        check("six copies emitted: A/B/C student, then A/B/C solutions",
              got == expected, f"got={got}")
        if got != expected:
            return 1 if _FAIL else 0

        parts_by = {(c["ver"], c["sol"]): copy_parts(c, texts, wpages) for c in copies}
        points_by = {(c["ver"], c["sol"]): copy_points(c, texts) for c in copies}

        scenario_shuffle_invariants(copies, parts_by, points_by)
        scenario_geometry(pdf, copies, texts, wpages, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    summary = f"\n{_PASS} passed, {_FAIL} failed"
    if _KNOWN_FAIL:
        summary += f", {_KNOWN_FAIL} known (tracked, not blocking)"
    if _SKIP:
        summary += f", {_SKIP} skipped"
    print(summary)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
