#!/usr/bin/env python3
"""End-to-end correctness tests for TeXLib's problem-bank ENGINE.

This targets the "renders the wrong number / wrong answer key" class of silent
failure -- a substituted variable value, a \\calcvar result, or a multiple-choice
answer letter coming out WRONG -- which had essentially no rendered coverage.
tests/fixtures/Exams/fix-test.tex proves the \\problem{id}[a=1,...] override
SYNTAX parses, but never that the substituted VALUES reach the page, and
\\calcvar had no buildable fixture at all.

Unlike test_shuffle.lua / test_exam_seed.lua (pure-Lua unit tests of the seeding
and permutation math) this drives a REAL lualatex build of the committed
fixtures and reads the produced PDF back with poppler's pdftotext, so a
regression anywhere along the engine -> LaTeX -> PDF path is caught:

  * Part 1 (subst-test): every variable is FIXED via the override and authored
    with a differing bank-side value, so a rendered value can only be right if
    the fixed[] guards in set_var/set_rng/calc_var actually blocked the bank's
    own randomisation.  Asserts the exact substituted expression and the exact
    \\calcvar constants.
  * Part 2 (mckey-*): the \\cchoice-marked option carries a distinctive needle;
    the test finds the slot it rendered in and asserts the key's "Answer: X"
    letter equals that slot -- i.e. the KEY is actually CORRECT, not just
    present (emit_mc_tail's letter computation).  Also checks [fixed] order
    preservation, \\fchoice[i] slot pinning, and [choose=m] selection.
  * Stretch (ppart-test): a shuffled exam of multi-part problems, checking each
    problem's \\ppart parts stay contiguous, correctly sub-lettered, and never
    leak to a neighbour (pbank_inject_part atomicity under \\shuffle).
  * Stretch (import-test): \\importproblem renders a standalone file inline with
    its overrides locking the file's own \\setvar/\\setrng, and push_scope/
    pop_scope keeps the import's variables from leaking out.
  * Stretch (vmap-test): parses the engine-emitted .vmap version markers and
    pdftotext-slices each copy's page range (the marker EMISSION in
    autoexam_run_versions was never exercised -- only the builder's slicer was).

Soft-skips (exit 0) if lualatex or a poppler-flavored pdftotext (-bbox / real
poppler banner, NOT Git-for-Windows' bundled xpdf build) is missing -- matching
test_synctex_integration.py's degrade-don't-fail convention.

Run:  python test_engine_correctness.py    (exit 0 ok/skipped, 1 fail)
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(TEXLIB_ROOT, "tests", "fixtures", "Exams")


# --- Toolchain routing / detection (mirrors test_synctex_integration.py) ------
def _build_root():
    r"""The checkout whose shared TeXLib files (.cls/.sty/.lua) the builds resolve
    against.  Defaults to this repo; TEXLIB_TEST_ROOT overrides it to a SPECIFIC
    checkout/worktree.  On Windows kpathsea cannot search an absolute TEXINPUTS
    entry containing a comma (the real OneDrive path has one), so the default is
    routed through the C:\_texlibjunc junction when present -- which resolves to
    the MAIN working tree, NOT necessarily this checkout.  On CI (Linux) the repo
    root is used directly."""
    root = os.environ.get("TEXLIB_TEST_ROOT") or TEXLIB_ROOT
    if root is TEXLIB_ROOT and os.name == "nt" and os.path.isdir(r"C:\_texlibjunc"):
        root = r"C:\_texlibjunc"
    return root


def _texinputs_env(tex_dir):
    """Env for the engine, TEXINPUTS extended so the TeXLib-root shared files
    (classes, .sty, the Lua engine) resolve even though tex_dir is a scratch dir
    OUTSIDE the repo.  On this machine kpathsea cannot search an absolute
    TEXINPUTS entry containing a comma (the real OneDrive path has one), so route
    through the C:\\_texlibjunc junction when present -- harmless no-op on any host
    without it (e.g. CI on Linux, where there is no comma and the repo root is
    used directly).  Same helper as Sublime/test_synctex_integration.py."""
    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    root = _build_root().replace(os.sep, "/")
    env["TEXINPUTS"] = sep.join([".", root + "//", env.get("TEXINPUTS", "")])
    return env


def _find_poppler_pdftotext():
    """A poppler-flavored pdftotext.  On some Windows dev setups Git for Windows
    ships its own xpdfreader pdftotext earlier on PATH; that build renders
    differently and lacks -bbox, so probe candidates and pick the first whose
    version banner mentions poppler (same guard as test_synctex_integration.py)."""
    candidates = []
    which = shutil.which("pdftotext")
    if which:
        candidates.append(which)
    candidates.append(r"C:\texlive\2025\bin\windows\pdftotext.exe")
    for cand in candidates:
        try:
            proc = subprocess.run([cand, "-v"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        banner = (proc.stdout or "") + (proc.stderr or "")
        if "poppler" in banner.lower():
            return cand
    return None


LUALATEX = shutil.which("lualatex")
PDFTOTEXT = _find_poppler_pdftotext()

_PASS = 0
_FAIL = 0


def check(label, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


# --- Real-build driver: copy the committed fixture(s) into a scratch dir, route
# ALL build output (aux, .pdf, .vmap, .sco, engine scratch) to a temp aux subdir,
# and build twice (settles "page X of Y" / point totals).  Returns (pdf, aux). --
def build(tmp, tex_name, *bank_names):
    for name in (tex_name,) + bank_names:
        shutil.copy(os.path.join(FIXTURES, name), os.path.join(tmp, name))
    aux = os.path.join(tmp, "aux")
    os.makedirs(aux, exist_ok=True)
    env = _texinputs_env(tmp)
    cmd = [LUALATEX, "-interaction=nonstopmode",
           "-output-directory=" + aux, "-shell-escape", tex_name]
    out = ""
    for _ in range(2):
        proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=180)
        out = (proc.stdout or "") + (proc.stderr or "")
    base = os.path.splitext(tex_name)[0]
    return os.path.join(aux, base + ".pdf"), aux, out


def pdftext(pdf, first=None, last=None):
    cmd = [PDFTOTEXT]
    if first is not None:
        cmd += ["-f", str(first)]
    if last is not None:
        cmd += ["-l", str(last)]
    cmd += [pdf, "-"]
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def flat(s):
    """Collapse every whitespace run to a single space -- robust substring search
    that is immune to pdftotext line-wrapping / column layout."""
    return re.sub(r"\s+", " ", s).strip()


# =============================================================================
# Part 1: fixed-variable substitution + \calcvar values
# =============================================================================
def scenario_fixed_substitution():
    print("\n=== Part 1: fixed-variable substitution + \\calcvar (subst-test) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_engine_subst_")
    try:
        pdf, _aux, log = build(tmp, "subst-test.tex", "subst-bank.tex")
        check("PDF was produced", os.path.exists(pdf), log[-600:])
        if not os.path.exists(pdf):
            return
        text = flat(pdftext(pdf))

        # The math stem with a=1,b=2,c=3 substituted (pdftotext flattens the ^2
        # superscript to a bare 2).  Proves \get prints the fixed values in order.
        check("fixed a,b,c render into the math stem as '1x2 + 2x + 3'",
              "1x2 + 2x + 3" in text, text[:200])
        # Unambiguous plain readout: only a=1,b=2,c=3 EXACTLY can produce this, so
        # it simultaneously proves the fixed override beat \setvar{a}{7} and both
        # out-of-range \setrng calls (b in [20,29], c in [30,39]).
        check("plain readout is exactly 'A1B2C3D' (fixed beats \\setvar and \\setrng)",
              "A1B2C3D" in text, text[:200])
        check("no leaked \\setvar value (a stayed 1, never 7 -> 'A7B' absent)",
              "A7B" not in text)

        # \calcvar over the fixed inputs: integer a*b+c = 17 (a=3 beat \setvar{a}{99})
        # and the sqrt-style float (a^2+b^2)^0.5 = 5.0.
        check("\\calcvar integer path renders 'CALCINT 17 ENDPROD'",
              "CALCINT 17 ENDPROD" in text, text[:300])
        check("\\calcvar float path renders 'CALCFLOAT 5.0 ENDHYP'",
              "CALCFLOAT 5.0 ENDHYP" in text, text[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# Part 2: multiple-choice answer-key correctness + option pinning
# =============================================================================
# Parse pdftotext output into per-problem blocks: the exam class renders each MC
# option as "X. <needle>" on its own line and the key as an "Answer: X" line
# (blank on student copies).  A block's answer is None for a student copy.
_PROBLEM_RE = re.compile(r"^\s*Problem\s+\d+\.\s*(.*)$")
_CHOICE_RE = re.compile(r"^\s*([A-Z])\.\s+(\S.*)$")
_ANSWER_RE = re.compile(r"^\s*Answer:\s*([A-Z])\b")


def parse_blocks(text):
    blocks, cur = [], None
    for line in text.splitlines():
        m = _PROBLEM_RE.match(line)
        if m:
            cur = {"stem": m.group(1), "choices": [], "answer": None}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        mc = _CHOICE_RE.match(line)
        if mc:
            cur["choices"].append((mc.group(1), mc.group(2).strip()))
            continue
        ma = _ANSWER_RE.match(line)
        if ma:
            cur["answer"] = ma.group(1)
    return blocks


def slot_of(block, needle):
    """The choice letter whose text contains `needle`, or None."""
    for letter, txt in block["choices"]:
        if needle in txt:
            return letter
    return None


def key_block(blocks, stem_needle):
    """The KEY copy (answer letter present) of the problem whose stem matches."""
    for b in blocks:
        if stem_needle in b["stem"] and b["answer"] is not None:
            return b
    return None


def student_block(blocks, stem_needle):
    for b in blocks:
        if stem_needle in b["stem"] and b["answer"] is None:
            return b
    return None


def scenario_mc_answer_key_basic():
    print("\n=== Part 2a: MC answer key, deterministic authored order (mckey-basic) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_engine_mcbasic_")
    try:
        pdf, _aux, log = build(tmp, "mckey-basic.tex", "mckey-bank.tex")
        check("PDF was produced", os.path.exists(pdf), log[-600:])
        if not os.path.exists(pdf):
            return
        blocks = parse_blocks(pdftext(pdf))
        kb = key_block(blocks, "BASICSTEM")
        check("found the key copy of the basic MC problem", kb is not None)
        if not kb:
            return
        # No \shuffle -> authored order preserved; the \cchoice authored 2nd lands
        # at B and the key must read exactly B.
        check("correct option BCORRECT rendered at slot B (authored 2nd)",
              slot_of(kb, "BCORRECT") == "B",
              f"choices={kb['choices']}")
        check("answer key letter is 'B'", kb["answer"] == "B",
              f"answer={kb['answer']!r}")
        check("the key letter matches the \\cchoice option's slot",
              kb["answer"] == slot_of(kb, "BCORRECT"),
              f"answer={kb['answer']!r} correct-slot={slot_of(kb, 'BCORRECT')!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_mc_answer_key_shuffle():
    print("\n=== Part 2b: MC key + option pinning under \\shuffle (mckey-shuffle) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_engine_mcshuf_")
    try:
        pdf, _aux, log = build(tmp, "mckey-shuffle.tex", "mckey-bank.tex")
        check("PDF was produced", os.path.exists(pdf), log[-600:])
        if not os.path.exists(pdf):
            return
        blocks = parse_blocks(pdftext(pdf))

        # (1) Shuffled: the key must name whatever slot the shuffle put the
        # correct option in.  Assertion is seed-invariant -- reads the rendered
        # slot rather than hard-coding it.
        b = key_block(blocks, "SHUFSTEM")
        check("found the shuffled MC key copy", b is not None)
        if b:
            cs = slot_of(b, "SCORRECT")
            check("correct option SCORRECT is present in the shuffled choices",
                  cs is not None, f"choices={b['choices']}")
            check("key letter matches the correct option's shuffled slot",
                  b["answer"] is not None and b["answer"] == cs,
                  f"answer={b['answer']!r} correct-slot={cs!r}")

        # (2) [fixed]: authored order survives \shuffle.
        b = key_block(blocks, "FIXEDSTEM")
        check("found the [fixed] MC key copy", b is not None)
        if b:
            order = [needle for _l, needle in
                     [(l, t.split()[0] if t.split() else "") for l, t in b["choices"]]]
            check("[fixed] block keeps authored order FX1,FCORRECT,FX3,FX4 under \\shuffle",
                  order[:4] == ["FX1", "FCORRECT", "FX3", "FX4"],
                  f"order={order}")
            check("[fixed] correct option still keyed correctly (slot B)",
                  b["answer"] == "B" and slot_of(b, "FCORRECT") == "B",
                  f"answer={b['answer']!r} choices={b['choices']}")

        # (3) \fchoice[3] pins its option to slot 3 (C), regardless of the shuffle.
        b = key_block(blocks, "FORCESTEM")
        check("found the \\fchoice MC key copy", b is not None)
        if b:
            check("\\fchoice[3] lands GFORCED in slot 3 (C)",
                  slot_of(b, "GFORCED") == "C", f"choices={b['choices']}")
            check("key letter matches the correct option's slot (GCORRECT)",
                  b["answer"] is not None and b["answer"] == slot_of(b, "GCORRECT"),
                  f"answer={b['answer']!r} correct-slot={slot_of(b, 'GCORRECT')!r}")

        # (4) [choose=3] presents exactly 3 options and always includes the correct.
        b = key_block(blocks, "CHOOSESTEM")
        check("found the [choose=3] MC key copy", b is not None)
        if b:
            check("[choose=3] presents exactly 3 options",
                  len(b["choices"]) == 3, f"choices={b['choices']}")
            check("[choose=3] always includes the correct option HCORRECT",
                  slot_of(b, "HCORRECT") is not None, f"choices={b['choices']}")
            check("key letter matches the correct option's slot",
                  b["answer"] is not None and b["answer"] == slot_of(b, "HCORRECT"),
                  f"answer={b['answer']!r} correct-slot={slot_of(b, 'HCORRECT')!r}")

        # (5) Student and key copies of a version share ONE shuffled order (the
        # per-version-seed fix: the answer key must match the student's options).
        for stem in ("SHUFSTEM", "FORCESTEM", "CHOOSESTEM"):
            sb, kb = student_block(blocks, stem), key_block(blocks, stem)
            if sb and kb:
                check(f"{stem}: student and key copies share the same option order",
                      sb["choices"] == kb["choices"],
                      f"student={sb['choices']} key={kb['choices']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# Stretch: \ppart atomicity + sub-numbering under \shuffle
# =============================================================================
# A part line renders as "<qno><letter>. <needle>" (e.g. "2a. PONEPARTA ...").
_PART_RE = re.compile(r"^\s*(\d+)([a-z])\.\s+(\S+)")


def parse_fr_blocks(text):
    """Per-problem blocks capturing free-response \\ppart lines as (qno, letter,
    needle) in rendered order."""
    blocks, cur = [], None
    for line in text.splitlines():
        m = _PROBLEM_RE.match(line)
        if m:
            cur = {"stem": m.group(1), "parts": []}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        mp = _PART_RE.match(line)
        if mp:
            cur["parts"].append((mp.group(1), mp.group(2), mp.group(3)))
    return blocks


def scenario_ppart_atomicity():
    print("\n=== Stretch: \\ppart atomicity + sub-numbering under \\shuffle (ppart-test) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_engine_ppart_")
    try:
        pdf, _aux, log = build(tmp, "ppart-test.tex", "ppart-bank.tex")
        check("PDF was produced", os.path.exists(pdf), log[-600:])
        if not os.path.exists(pdf):
            return
        blocks = parse_fr_blocks(pdftext(pdf))

        # Each problem's parts must render contiguously beneath its OWN stem, in
        # authored order, correctly sub-lettered a/b/c... -- regardless of which
        # order the shuffle emitted the two problems in.
        expected = {
            "PONESTEM": (["a", "b", "c"], ["PONEPARTA", "PONEPARTB", "PONEPARTC"]),
            "PTWOSTEM": (["a", "b"], ["PTWOPARTA", "PTWOPARTB"]),
        }
        for stem, (want_letters, want_needles) in expected.items():
            b = next((x for x in blocks if stem in x["stem"]), None)
            check(f"found the {stem} problem block", b is not None)
            if not b:
                continue
            letters = [p[1] for p in b["parts"]]
            needles = [p[2] for p in b["parts"]]
            qnos = {p[0] for p in b["parts"]}
            check(f"{stem}: its parts stay contiguous, in authored order",
                  needles == want_needles, f"got {needles}")
            check(f"{stem}: parts are sub-lettered {want_letters}",
                  letters == want_letters, f"got {letters}")
            check(f"{stem}: all parts share one question number (atomic block)",
                  len(qnos) == 1, f"qnos={qnos}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# Stretch: \importproblem -- standalone file render + override lock + isolation
# =============================================================================
def scenario_importproblem():
    print("\n=== Stretch: \\importproblem render + override lock + scope isolation (import-test) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_engine_import_")
    try:
        pdf, _aux, log = build(tmp, "import-test.tex", "import-problem.tex")
        check("PDF was produced", os.path.exists(pdf), log[-600:])
        if not os.path.exists(pdf):
            return
        text = flat(pdftext(pdf))

        # The standalone file renders inline, and the {a=3,b=4,c=5} overrides lock
        # its own \setvar{a}{77} / out-of-range \setrng{b} (c comes straight from
        # the override) -- same fixed[] semantics as \problem{id}[a=1,...].
        check("\\importproblem renders the file with overrides locked "
              "('IMPSTART 3 and 4 and 5 IMPEND')",
              "IMPSTART 3 and 4 and 5 IMPEND" in text, text[:200])
        # push_scope/pop_scope isolation: a variable the imported file set
        # internally (leak=42, not overridden) must not survive the import, so the
        # following \get{leak} reads undefined and prints "??".
        check("a variable set inside the import does not leak past pop_scope "
              "('AFTERIMP ?? ENDAFTER')",
              "AFTERIMP ?? ENDAFTER" in text, text[:200])
        check("...and the leaked value 42 specifically does not escape",
              "AFTERIMP 42" not in text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# Stretch: engine-emitted .vmap version markers
# =============================================================================
def scenario_vmap_emission():
    print("\n=== Stretch: .vmap version-marker emission (vmap-test) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_engine_vmap_")
    try:
        pdf, aux, log = build(tmp, "vmap-test.tex", "vmap-bank.tex")
        check("PDF was produced", os.path.exists(pdf), log[-600:])
        vmap = os.path.join(aux, "vmap-test.vmap")
        check(".vmap file was emitted by the engine", os.path.exists(vmap))
        if not (os.path.exists(pdf) and os.path.exists(vmap)):
            return

        entries = []
        with open(vmap, encoding="utf-8") as fh:
            for line in fh:
                parts = line.strip().split("|")
                if len(parts) == 3:
                    entries.append((parts[0], parts[1], int(parts[2])))

        # \versions{A,B} x \solutions (dual) => student copies first, then key
        # copies: A|stu, B|stu, A|sol, B|sol.
        labels = [(v, c) for (v, c, _p) in entries]
        check("markers are A|stu, B|stu, A|sol, B|sol in order",
              labels == [("A", "stu"), ("B", "stu"), ("A", "sol"), ("B", "sol")],
              f"labels={labels}")
        pages = [p for (_v, _c, p) in entries]
        check("marker start pages are strictly increasing, first page = 1",
              len(pages) >= 1 and pages[0] == 1 and
              all(pages[i] < pages[i + 1] for i in range(len(pages) - 1)),
              f"pages={pages}")

        # Each marker must point at a page slice whose content matches its copy
        # type: VSTEM everywhere, VSOLUTION only in the sol (key) slices.
        for i, (ver, copy, start) in enumerate(entries):
            end = entries[i + 1][2] - 1 if i + 1 < len(entries) else None
            sliced = flat(pdftext(pdf, first=start, last=end))
            check(f"{ver}|{copy} slice (page {start}) contains the problem stem",
                  "VSTEM" in sliced, sliced[:160])
            if copy == "sol":
                check(f"{ver}|{copy} slice shows the solution needle",
                      "VSOLUTION" in sliced, sliced[:160])
            else:
                check(f"{ver}|{copy} student slice hides the solution needle",
                      "VSOLUTION" not in sliced, sliced[:160])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("TeXLib problem-bank engine correctness tests\n")
    _root = _build_root()
    print(f"  build root: {_root}")
    if (os.name == "nt" and not os.environ.get("TEXLIB_TEST_ROOT")
            and os.path.normcase(_root) == os.path.normcase(r"C:\_texlibjunc")):
        print(f"    NOTE: builds resolve against {_root} (your MAIN working tree),")
        print("    NOT necessarily this checkout. Set TEXLIB_TEST_ROOT to a")
        print("    comma-free path to test a specific worktree.")
    print()
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext found.")
        return 0

    scenario_fixed_substitution()
    scenario_mc_answer_key_basic()
    scenario_mc_answer_key_shuffle()
    scenario_ppart_atomicity()
    scenario_importproblem()
    scenario_vmap_emission()

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
