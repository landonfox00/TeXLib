#!/usr/bin/env python3
"""
TeXLib smoke test harness.

Builds every per-module template.tex and reports pass/fail. Intended as the
safety net for refactors that touch shared .sty/.cls files (e.g. consolidating
course-metadata.sty, extracting math utilities, deduping the autoexam engine).

The script self-locates: place it at the TeXLib root and run it from anywhere.
Each build runs in a fresh temp directory with TEXINPUTS prepended so the
canonical TeXLib root is found regardless of the host's kpse configuration.

Usage:
    python smoke_test.py                 # build every module in default mode
    python smoke_test.py Notes Exams     # build a subset
    python smoke_test.py --student       # also build with \\StudentMode
    python smoke_test.py --key           # also build with \\ShowKey
    python smoke_test.py --modes all     # default + student + key + solutions
    python smoke_test.py --timeout 180   # raise per-build timeout (seconds)
    python smoke_test.py -v              # print full TeX log on failure
    python smoke_test.py --no-content    # build-only (skip pdftotext/artifact checks)
    python smoke_test.py --visual        # also diff each page vs tests/visual_refs/
    python smoke_test.py --update-refs   # (re)generate the visual references
    python smoke_test.py --dump-text     # print each module's extracted PDF text
    python smoke_test.py --scenarios            # run core visual scenario packs
    python smoke_test.py --scenarios schedule   # ...limited to one area
    python smoke_test.py --scenarios --full     # the ultimate run (all tiers)
    python smoke_test.py --scenarios --update-refs   # regenerate scenario refs

Visual scenario packs live under tests/scenarios/<area>/<name>/ — each a
self-contained template exercising one configuration (orientation, month-pages,
edge dates, ...). `--scenarios` builds and visually diffs them; tier `core`
runs by default, `full` only with `--full`. This is a local aid (references are
rendering-environment-specific), separate from the per-push module suite.

Content checks (on by default) extract the rendered PDF's text with `pdftotext`
and assert each module's expected substrings are present, plus that key
generated artifacts (e.g. the schedule grid file) are non-empty — catching
"builds green but renders blank" regressions. Visual checks (opt-in) render
each page and pixel-diff it against committed references. All of these degrade
to a soft skip when their external tool (poppler / ImageMagick) is absent, so a
bare TeX install still runs the build-only smoke test.

Exit code is the number of failed builds (0 = all passed).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEXLIB_ROOT = SCRIPT_DIR  # script lives at TeXLib root

# External tools for content/visual checks. All optional: when a tool is
# missing the corresponding check is skipped (with a warning) rather than
# failing, so a bare `lualatex`/`pdflatex` install can still run build-only.
#   pdftotext / pdftoppm  -> poppler-utils
#   magick (or compare)   -> ImageMagick
PDFTOTEXT = shutil.which("pdftotext")
PDFTOPPM = shutil.which("pdftoppm")
MAGICK = shutil.which("magick")
COMPARE = shutil.which("compare")  # ImageMagick 6 standalone

# Committed reference images for visual regression (--visual). Generated with
# --update-refs; environment-specific (font rendering differs across TeX Live
# builds), so regenerate after an intentional layout change or a toolchain bump.
VISUAL_REF_DIR = os.path.join(TEXLIB_ROOT, "tests", "visual_refs")
VISUAL_DPI = 100
# Visual regression only makes sense for modules whose output is DETERMINISTIC.
# autoexam/quiz shuffle versions and pull random bank problems, so their pages
# differ build-to-build — pixel-diffing them is pure noise. Restrict to the
# fixed-layout modules (the schedule grid is the motivating case).
VISUAL_MODULES = {"Schedule", "Report Cards", "Syllabi", "Notes"}
# Max fraction of differing pixels (after a small color fuzz) tolerated per page
# before a page is flagged as a visual regression. Tight, because refs and the
# build under test come from the same machine in the intended local workflow.
VISUAL_MAX_DIFF_FRAC = 0.002

# Visual scenario packs (tier 2/3): tests/scenarios/<area>/<name>/template.tex,
# each a self-contained doc (metadata inline via \metasetup) exercising ONE
# configuration. An optional `tags` file (whitespace-separated, e.g. "full")
# marks the tier; absent => {"core"}. `core` runs by default; `full` only with
# --full. A scenario's <area> maps to the module whose .cls/.lua it builds on.
SCENARIOS_DIR = os.path.join(TEXLIB_ROOT, "tests", "scenarios")
SCENARIO_AREA_MODULE = {
    "schedule": "Schedule",
    "report-cards": "Report Cards",
    "syllabi": "Syllabi",
    "notes": "Notes",
    "quiz": "Quizzes",
}

# Modules and their template files. Engine is auto-detected from \documentclass.
MODULES = [
    ("Bingo",        "template.tex"),
    ("Exams",        "template.tex"),
    ("Notes",        "template.tex"),
    ("Quizzes",      "template.tex"),
    ("Report Cards", "template.tex"),
    ("Schedule",     "template.tex"),
    ("Syllabi",      "template.tex"),
    ("Problem Sets", "template.tex"),
    # Feature-test entries (live under Test/<Module>/). Each is a self-contained
    # .tex that exercises something the canonical template doesn't — e.g. the
    # fix-overrides syntax \problem{id}[a=1,b=2]. Treated like any other module
    # by build_one (it copies siblings + collects root + module .cls files).
    ("Test/Exams",   "fix-test.tex"),
]

# Classes that require lualatex (use \directlua, luaotfload, or sibling .lua files).
LUALATEX_CLASSES = {"autoexam", "quiz", "schedule"}

# Build-flag toggles. Each maps a CLI flag to a TeX macro define.
MODES = {
    "default":   None,
    "student":   r"\def\StudentMode{}",
    "key":       r"\def\ShowKey{}",
    "solutions": r"\def\ShowSolutions{}",
    "rubric":    r"\def\ShowRubric{}",
}

# A stub coursemeta.tex dropped into every build directory. course-metadata.sty
# auto-loads coursemeta.tex from the build dir (or an ancestor); templates that
# require course metadata cannot build in an isolated temp dir without it.
# Schedule is the strict case — it needs lecture-days / start-date / end-date —
# but other modules happily pick up these values too. Real course folders
# always supply their own coursemeta.tex; this stub is only for smoke testing.
STUB_COURSEMETA = r"""% coursemeta.tex - auto-generated stub for TeXLib smoke testing.
\metasetup{
	institution     = {Smoke Test University},
	instructor      = {Test Instructor},
	season          = Fall,
	year            = 2026,
	course-subject  = Math,
	course-number   = 101,
	course-title    = {Smoke Test Course},
	course-section  = 1,
	course-room     = TBD,
	lecture-days    = {MWF, TTh},
	lecture-times   = {9:00-9:50am, 9:00-10:15am},
	start-date      = 8-24,
	end-date        = 12-8,
	final-date      = 12-15,
	final-time      = 9:45-11:45am,
}
"""


# ---------------------------------------------------------------------------
# Content expectations
# ---------------------------------------------------------------------------
#
# After a successful build, the rendered PDF's text (via pdftotext) must
# contain every substring listed for that module (case-insensitive). These
# catch the "compiles green but renders blank/garbled" class that a build-only
# check misses — e.g. the schedule grid that silently rendered zero rows.
# Keep the strings to durable, content-level tokens (column headers, directive
# output, instruction boilerplate), NOT layout/font-sensitive details.
EXPECT_TEXT = {
    # Bingo renders the banner as spaced letters ("B  I  N  G  O"), so match the
    # always-present grid cell coordinates instead.
    "Bingo":        ["B1", "O5"],
    "Exams":        ["Problem 1", "Problem 2"],
    "Notes":        ["Introduction", "Theorem"],
    "Quizzes":      ["Quiz"],
    "Report Cards": ["Report Card"],
    "Schedule":     ["MONDAY", "WEEK", "Quiz 1", "Final Exam"],
    # Syllabi/template.tex carries its own metadata (not the stub), so key on
    # the template's stable section headings.
    "Syllabi":      ["Course Description", "Office Hours"],
    "Problem Sets": ["Problem 1"],
    "Test/Exams":   ["Problem 1"],
}

# Generated sidecar files that must exist AND be non-empty after a build. A
# dependency-free content signal (no pdftotext needed): the schedule's grid
# file is 0 bytes exactly when render_grid produced no rows — the empty-grid
# bug. Patterns are globbed inside the build's temp dir.
EXPECT_ARTIFACT_NONEMPTY = {
    "Schedule": ["*_schedule_grid.tex"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{(\w[\w-]*)\}")


def safe_name(module: str) -> str:
    """Filesystem-safe slug for a module name (e.g. 'Test/Exams' -> 'Test_Exams')."""
    return re.sub(r"[^\w.-]+", "_", module)


def extract_pdf_text(pdf_path: str) -> str | None:
    """Return the PDF's text via pdftotext, or None if the tool is unavailable."""
    if not PDFTOTEXT:
        return None
    try:
        r = subprocess.run(
            [PDFTOTEXT, "-layout", pdf_path, "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def check_content(module: str, tmp: str, pdf_path: str,
                  check_text: bool = True) -> tuple[list[str], bool]:
    """
    Verify rendered content. Returns (problems, text_skipped).
    `text_skipped` is True when substring checks were requested but pdftotext
    is unavailable (a soft skip, not a failure). `check_text=False` runs only
    the dependency-free artifact check — used by scenario builds, where the
    per-page visual diff (not a fixed substring list) is the content check and
    EXPECT_TEXT's module tokens may not apply to every configuration.
    """
    problems: list[str] = []

    # Artifact non-emptiness (dependency-free).
    for pat in EXPECT_ARTIFACT_NONEMPTY.get(module, []):
        hits = glob.glob(os.path.join(tmp, pat))
        if not any(os.path.getsize(h) > 0 for h in hits):
            problems.append(f"artifact {pat} missing or empty")

    # Text substrings (needs pdftotext).
    expects = EXPECT_TEXT.get(module, []) if check_text else []
    text_skipped = False
    if expects:
        text = extract_pdf_text(pdf_path)
        if text is None:
            text_skipped = True
        else:
            low = text.lower()
            missing = [s for s in expects if s.lower() not in low]
            if missing:
                problems.append("missing text: " + ", ".join(repr(s) for s in missing))

    return problems, text_skipped


def _compare_pages(ref_png: str, test_png: str) -> int | None:
    """
    Return the number of differing pixels (ImageMagick AE metric, small fuzz)
    between two PNGs, or None if no comparison tool is available. A huge value
    is returned when dimensions differ (ImageMagick reports that as an error).
    """
    if MAGICK:
        cmd = [MAGICK, "compare", "-metric", "AE", "-fuzz", "3%", ref_png, test_png, "null:"]
    elif COMPARE:
        cmd = [COMPARE, "-metric", "AE", "-fuzz", "3%", ref_png, test_png, "null:"]
    else:
        return None
    try:
        r = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # AE count is printed to stderr (merged into stdout here) as the LAST line,
    # e.g. "1234" or "1234 (0.00188)". Scan from the end for a line that is
    # purely the metric, so a leading ImageMagick warning line that happens to
    # contain a number isn't mistaken for the count. Dimension mismatch ->
    # non-zero exit + no metric line.
    for ln in reversed((r.stdout or "").splitlines()):
        m = re.match(r"^\s*(\d+)(?:\s*\([\d.eE+-]+\))?\s*$", ln)
        if m:
            return int(m.group(1))
    return 10**9 if r.returncode != 0 else 0


def check_visual(module: str, tmp: str, pdf_path: str, update: bool) -> tuple[list[str], bool]:
    """
    Render every PDF page to PNG and compare against committed references.
    With `update`, (re)write the references instead. Returns (problems, skipped).
    """
    if not PDFTOPPM or not (MAGICK or COMPARE):
        return [], True  # soft skip: missing poppler/imagemagick

    slug = safe_name(module)
    prefix = os.path.join(tmp, "vis")
    try:
        subprocess.run(
            [PDFTOPPM, "-png", "-r", str(VISUAL_DPI), pdf_path, prefix],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"pdftoppm failed: {exc}"], False
    pages = sorted(glob.glob(prefix + "*.png"))
    if not pages:
        return ["no pages rendered"], False

    if update:
        os.makedirs(VISUAL_REF_DIR, exist_ok=True)
        for old in glob.glob(os.path.join(VISUAL_REF_DIR, f"{slug}-*.png")):
            os.remove(old)
        for i, pg in enumerate(pages, 1):
            shutil.copy2(pg, os.path.join(VISUAL_REF_DIR, f"{slug}-{i}.png"))
        return [], False

    refs = sorted(glob.glob(os.path.join(VISUAL_REF_DIR, f"{slug}-*.png")))
    if not refs:
        return [f"no reference images for {module} (run --update-refs)"], False
    if len(pages) != len(refs):
        return [f"page count {len(pages)} != reference {len(refs)}"], False

    problems: list[str] = []
    for i, (pg, rf) in enumerate(zip(pages, refs), 1):
        diff = _compare_pages(rf, pg)
        if diff is None:
            return [], True
        # Budget scales with page area so a fixed fraction means the same thing
        # for portrait notes and landscape schedules.
        w, h = _png_size(rf)
        budget = int(w * h * VISUAL_MAX_DIFF_FRAC)
        if diff > budget:
            problems.append(f"page {i} differs ({diff} px > {budget} budget)")
    return problems, False


def _png_size(path: str) -> tuple[int, int]:
    """Read a PNG's (width, height) from its IHDR header. Falls back to a
    landscape-letter guess at VISUAL_DPI if the header can't be read."""
    import struct
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
    except (OSError, struct.error):
        pass
    return (1100, 850)


def detect_engine(tex_path: str) -> str:
    """Pick lualatex if the documentclass needs it, else pdflatex."""
    try:
        with open(tex_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return "pdflatex"
    m = DOCCLASS_RE.search(content)
    if m and m.group(1) in LUALATEX_CLASSES:
        return "lualatex"
    return "pdflatex"


def extract_tex_errors(log_text: str, max_lines: int = 6) -> str:
    """Pull the first handful of TeX-error-looking lines from a log."""
    lines: list[str] = []
    for ln in log_text.splitlines():
        s = ln.rstrip()
        if (
            s.startswith("!")
            or s.startswith("l.")
            or "LaTeX Error" in s
            or "Fatal error" in s
            or "Runaway argument" in s
            or "Emergency stop" in s
        ):
            lines.append(s)
            if len(lines) >= max_lines:
                break
    return " | ".join(lines)


def _decode(s) -> str:
    """Coerce a bytes-or-str value (e.g. from a TimeoutExpired exception) to str."""
    if s is None:
        return ""
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    return s


# Log signals that another compilation pass is needed. A single pass leaves
# \pageref{LastPage} (and other forward refs / TOC entries) unresolved -- the
# "1 of ??" you see in a one-shot build -- because the label only reaches the
# .aux at end of run. Re-running clears it, the way latexmk / the Sublime
# builder do.
# Note: unlike the Sublime builder's RERUN_RE (which deliberately EXCLUDES
# "There were undefined references" to avoid looping on a genuinely-missing
# label), the smoke test includes it on purpose: it wants fully-settled output
# for visual diffing, and the re-run loop is hard-capped at max_passes (3), so
# a never-resolving ref costs at most two extra passes rather than an open loop.
RERUN_RE = re.compile(
    r"(Rerun to get|Rerun LaTeX|There were undefined references"
    r"|Label\(s\) may have changed)", re.I)


def _run_with_reruns(cmd: list[str], tmp: str, env: dict, timeout: int,
                     jobname: str, max_passes: int = 3):
    """
    Run the TeX engine, re-running while its .log asks for it (cross-refs /
    LastPage / TOC), up to `max_passes`. Returns
    (returncode, log_text, stdout, elapsed, passes). Propagates
    subprocess.TimeoutExpired (per pass) like subprocess.run.
    """
    log_path = os.path.join(tmp, jobname + ".log")
    t0 = time.time()
    returncode, stdout, log_text, passes = 0, "", "", 0
    for i in range(max_passes):
        passes = i + 1
        r = subprocess.run(
            cmd, cwd=tmp, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        returncode, stdout = r.returncode, r.stdout
        log_text = ""
        if os.path.exists(log_path):
            try:
                with open(log_path, encoding="utf-8", errors="replace") as f:
                    log_text = f.read()
            except OSError:
                pass
        # Stop on a fatal error (a rerun won't fix it) or once no rerun is asked.
        if returncode != 0 or i + 1 >= max_passes \
                or not RERUN_RE.search(log_text or stdout or ""):
            break
    return returncode, log_text, stdout, time.time() - t0, passes


def build_one(
    module: str,
    template: str,
    mode_macro: str | None,
    timeout: int,
    verbose: bool,
    content: bool = True,
    visual: str | None = None,
    dump_text: bool = False,
) -> tuple[bool, float, str, str, bool]:
    """
    Build a single template.tex in an isolated temp directory.

    `content`: run text/artifact content checks after a successful build.
    `visual`:  None (off), "check" (compare to refs), or "update" (write refs).

    Returns (ok, elapsed_seconds, error_excerpt, log_path_on_failure, skipped),
    where `skipped` is True if a requested content/visual check was soft-skipped
    because its external tool (poppler / ImageMagick) was unavailable.
    """
    module_dir = os.path.join(TEXLIB_ROOT, module)
    tex_src = os.path.join(module_dir, template)
    if not os.path.exists(tex_src):
        return False, 0.0, f"missing template: {tex_src}", "", False

    engine = detect_engine(tex_src)

    # Build in a temp dir so we don't pollute the real module folder with
    # .aux/.log/.synctex.gz etc. Copy the module's local files (.cls/.lua/.tex
    # siblings of template.tex) over so they're discoverable as ./ files.
    safe_module = re.sub(r"[^\w.-]+", "_", module)
    tmp = tempfile.mkdtemp(prefix=f"texlib_smoke_{safe_module}_")
    try:
        for entry in os.listdir(module_dir):
            src = os.path.join(module_dir, entry)
            if os.path.isfile(src):
                shutil.copy2(src, tmp)

        # Copy the TeXLib-root shared files (.sty/.lua/.cls) and every module's
        # .cls into the build dir so they resolve via the cwd. This sidesteps a
        # hard kpathsea limitation: a TEXINPUTS entry containing a COMMA is
        # silently unsearchable, and the TeXLib root can easily live under one
        # (e.g. a OneDrive folder named "...University of Nevada, Reno..."). The
        # module's own files were copied first and win any name clash, since
        # _copy_shared_into never overwrites a file already present.
        _copy_shared_into(tmp)

        # Drop in a stub coursemeta.tex unless the module already ships one.
        # course-metadata.sty auto-loads it from the cwd; without it, any
        # template that reads course metadata (Schedule needs lecture-days /
        # start-date / end-date) aborts.
        coursemeta = os.path.join(tmp, "coursemeta.tex")
        if not os.path.exists(coursemeta):
            with open(coursemeta, "w", encoding="utf-8") as f:
                f.write(STUB_COURSEMETA)

        env = os.environ.copy()
        sep = ";" if os.name == "nt" else ":"
        existing = env.get("TEXINPUTS", "")
        # TEXINPUTS is still set as a belt-and-suspenders fallback for hosts
        # whose TeXLib root has no comma. The cwd copy above is what actually
        # makes the build robust.
        #   `//` = recursive search (LITERAL forward slashes, every platform).
        #   `.`  = the build's working directory.
        #   trailing path separator = "...and the default texmf trees too".
        env["TEXINPUTS"] = f".{sep}{TEXLIB_ROOT}//{sep}{existing}"

        cmd = [engine, "-interaction=nonstopmode", "-halt-on-error"]
        if engine == "lualatex":
            cmd.append("-shell-escape")
        if mode_macro:
            # Compile-time flag injection: \def\StudentMode{}\input{template.tex}
            cmd.append(f"{mode_macro}\\input{{{template}}}")
        else:
            cmd.append(template)

        jobname = os.path.splitext(template)[0]
        pdf = os.path.join(tmp, jobname + ".pdf")
        t0 = time.time()
        try:
            returncode, log_text, stdout_text, elapsed, _passes = _run_with_reruns(
                cmd, tmp, env, timeout, jobname)
        except subprocess.TimeoutExpired as exc:
            return (False, time.time() - t0, f"timeout after {timeout}s",
                    _save_log(tmp, _decode(exc.stdout)), False)

        ok = returncode == 0 and os.path.exists(pdf)
        if ok and dump_text:
            txt = extract_pdf_text(pdf)
            print(f"\n===== {module} :: extracted text =====")
            print(txt if txt is not None else "(pdftotext unavailable)")
            print(f"===== end {module} =====\n")
        if ok:
            skipped = False
            problems: list[str] = []
            if content:
                cp, text_skipped = check_content(module, tmp, pdf)
                problems += cp
                skipped = skipped or text_skipped
            if visual and module in VISUAL_MODULES:
                vp, vis_skipped = check_visual(module, tmp, pdf, update=(visual == "update"))
                problems += vp
                skipped = skipped or vis_skipped
            if problems:
                err = "CONTENT: " + "; ".join(problems)
                saved = _save_log(tmp, log_text or stdout_text, verbose=verbose, jobname=jobname)
                return False, elapsed, err, saved, skipped
            return True, elapsed, "", "", skipped

        err = extract_tex_errors(log_text or stdout_text) or f"exit={returncode}, no pdf"
        saved = _save_log(tmp, log_text or stdout_text, verbose=verbose, jobname=jobname)
        return False, elapsed, err, saved, False
    finally:
        # Don't trash the temp dir if we need the log for diagnosis.
        # The _save_log() helper has already copied the log out if needed.
        shutil.rmtree(tmp, ignore_errors=True)


def _save_log(tmp_dir: str, log_text, verbose: bool = False, jobname: str = "build") -> str:
    """Persist a failure log next to the script. Returns the path."""
    log_text = _decode(log_text)
    log_dir = os.path.join(TEXLIB_ROOT, ".smoke_logs")
    os.makedirs(log_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(log_dir, f"{jobname}_{stamp}.log")
    try:
        with open(dest, "w", encoding="utf-8", errors="replace") as f:
            f.write(log_text)
    except OSError:
        return ""
    if verbose:
        print("    --- full log ---")
        for ln in log_text.splitlines()[-50:]:
            print(f"    {ln}")
    return dest


# ---------------------------------------------------------------------------
# Visual scenario packs
# ---------------------------------------------------------------------------

def discover_scenarios(area_filter: list[str], include_full: bool) -> list[dict]:
    """
    Find scenario dirs under tests/scenarios/<area>/<name>/ (each holding a
    template.tex). Returns dicts {area, name, dir, slug, tags}, filtered by
    `area_filter` (empty = all areas) and tier (core always; full only when
    `include_full`). `slug` is "<area>__<name>" — the visual-ref key.
    """
    out: list[dict] = []
    if not os.path.isdir(SCENARIOS_DIR):
        return out
    for area in sorted(os.listdir(SCENARIOS_DIR)):
        area_dir = os.path.join(SCENARIOS_DIR, area)
        if not os.path.isdir(area_dir) or (area_filter and area not in area_filter):
            continue
        for name in sorted(os.listdir(area_dir)):
            sdir = os.path.join(area_dir, name)
            if not os.path.isfile(os.path.join(sdir, "template.tex")):
                continue
            tags = {"core"}
            tagfile = os.path.join(sdir, "tags")
            if os.path.isfile(tagfile):
                try:
                    with open(tagfile, encoding="utf-8") as f:
                        tags = set(f.read().split()) or {"core"}
                except OSError:
                    pass
            if "core" not in tags and not include_full:
                continue
            out.append({"area": area, "name": name, "dir": sdir,
                        "slug": f"{area}__{name}", "tags": tags})
    return out


def _copy_shared_into(tmp: str) -> None:
    """Copy the TeXLib-root shared files (.sty/.lua/.cls) and every module's
    .cls into a build dir, never overwriting files already there. Mirrors
    build_one's cwd-copy strategy that dodges the comma-in-TEXINPUTS limit."""
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            dest = os.path.join(tmp, entry)
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
    for entry in os.listdir(TEXLIB_ROOT):
        sub = os.path.join(TEXLIB_ROOT, entry)
        if not os.path.isdir(sub):
            continue
        for f in os.listdir(sub):
            if f.lower().endswith(".cls"):
                dest = os.path.join(tmp, f)
                if not os.path.exists(dest):
                    shutil.copy2(os.path.join(sub, f), dest)


def _read_expect_text(sdir: str) -> list[str]:
    """A scenario's optional `expect-text` file: substrings (one per line) that
    must appear in the rendered PDF. Blank lines and '#' comments are ignored."""
    path = os.path.join(sdir, "expect-text")
    if not os.path.isfile(path):
        return []
    out: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                s = ln.strip()
                if s and not s.startswith("#"):
                    out.append(s)
    except OSError:
        return []
    return out


def build_scenario(scen: dict, timeout: int, verbose: bool,
                   content: bool, visual: str) -> tuple[bool, float, str, str, bool]:
    """
    Build one scenario in isolation and run content + visual checks against its
    slug. The scenario ships its own metadata inline (no stub coursemeta).
    Returns (ok, elapsed, err, log_path_on_failure, skipped).
    """
    area, slug, sdir = scen["area"], scen["slug"], scen["dir"]
    module = SCENARIO_AREA_MODULE.get(area)
    if not module:
        return False, 0.0, f"no module mapping for scenario area '{area}'", "", False
    module_dir = os.path.join(TEXLIB_ROOT, module)
    template = "template.tex"
    engine = detect_engine(os.path.join(sdir, template))

    tmp = tempfile.mkdtemp(prefix=f"texlib_scen_{safe_name(slug)}_")
    try:
        # Scenario files first (they win name clashes), then the module's
        # .cls/.lua, then root shared files. No stub coursemeta — scenarios set
        # metadata inline via \metasetup.
        for entry in os.listdir(sdir):
            src = os.path.join(sdir, entry)
            if os.path.isfile(src):
                shutil.copy2(src, tmp)
        for entry in os.listdir(module_dir):
            src = os.path.join(module_dir, entry)
            if os.path.isfile(src) and not os.path.exists(os.path.join(tmp, entry)):
                shutil.copy2(src, tmp)
        _copy_shared_into(tmp)

        env = os.environ.copy()
        sep = ";" if os.name == "nt" else ":"
        env["TEXINPUTS"] = f".{sep}{TEXLIB_ROOT}//{sep}{env.get('TEXINPUTS', '')}"
        cmd = [engine, "-interaction=nonstopmode", "-halt-on-error"]
        if engine == "lualatex":
            cmd.append("-shell-escape")
        cmd.append(template)

        jobname = os.path.splitext(template)[0]
        pdf = os.path.join(tmp, jobname + ".pdf")
        t0 = time.time()
        try:
            returncode, log_text, stdout_text, elapsed, _passes = _run_with_reruns(
                cmd, tmp, env, timeout, jobname)
        except subprocess.TimeoutExpired as exc:
            return (False, time.time() - t0, f"timeout after {timeout}s",
                    _save_log(tmp, _decode(exc.stdout)), False)

        if returncode != 0 or not os.path.exists(pdf):
            err = extract_tex_errors(log_text or stdout_text) or f"exit={returncode}, no pdf"
            return False, elapsed, err, _save_log(tmp, log_text or stdout_text, verbose, jobname), False

        problems: list[str] = []
        skipped = False
        if content:
            # Artifact check only (grid non-empty). The per-page visual diff is
            # the real content check for visual scenarios; the module's
            # EXPECT_TEXT tokens don't apply across every configuration.
            cp, tskip = check_content(module, tmp, pdf, check_text=False)
            problems += cp
            skipped = skipped or tskip

        # Optional per-scenario text assertion: an `expect-text` file lists
        # substrings (one per line; blank lines and '#' comments ignored) that
        # MUST appear in the rendered PDF. Lets a scenario assert content
        # directly (e.g. that the right instructions file was resolved),
        # independent of pixel references.
        text_expects = _read_expect_text(sdir)
        if text_expects:
            text = extract_pdf_text(pdf)
            if text is None:
                skipped = True  # pdftotext unavailable -> soft skip
            else:
                low = text.lower()
                missing = [s for s in text_expects if s.lower() not in low]
                if missing:
                    problems.append(
                        "missing text: " + ", ".join(repr(s) for s in missing))

        # Visual diff: the assertion for visual scenarios. Skipped for a
        # text-only scenario (ships `expect-text`, carries no reference PNGs) so
        # it needn't commit a pixel ref.
        has_refs = bool(glob.glob(
            os.path.join(VISUAL_REF_DIR, f"{safe_name(slug)}-*.png")))
        if has_refs or not text_expects:
            vp, vskip = check_visual(slug, tmp, pdf, update=(visual == "update"))
            problems += vp
            skipped = skipped or vskip

        if problems:
            return (False, elapsed, "CONTENT: " + "; ".join(problems),
                    _save_log(tmp, log_text or stdout_text, verbose, jobname), skipped)
        return True, elapsed, "", "", skipped
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenarios(area_filter: list[str], include_full: bool, update_refs: bool,
                  content_enabled: bool, timeout: int, verbose: bool) -> int:
    """Run the visual scenario packs. Returns the number of failures."""
    scen = discover_scenarios(area_filter, include_full)
    visual_mode = "update" if update_refs else "check"
    have_magick = bool(MAGICK or COMPARE)
    vmiss = [n for n, ok in (("pdftoppm", PDFTOPPM), ("ImageMagick", have_magick)) if not ok]

    print("TeXLib smoke test — visual scenarios")
    print(f"  dir     : {SCENARIOS_DIR}")
    print(f"  filter  : {', '.join(area_filter) if area_filter else 'all areas'}"
          f"; tier: {'core+full' if include_full else 'core'}")
    print(f"  visual  : {'update refs' if update_refs else 'compare'}"
          + (f"  [{', '.join(vmiss)} MISSING -> skipped]" if vmiss else ""))
    print(f"  found   : {len(scen)} scenario(s)")
    print()
    if not scen:
        print("No scenarios matched. Add tests/scenarios/<area>/<name>/template.tex.")
        return 0

    results: list[tuple[str, bool, str]] = []
    any_skipped = False
    t_start = time.time()
    for s in scen:
        sys.stdout.write(f"  [{s['slug']:<26}] ... ")
        sys.stdout.flush()
        ok, elapsed, err, saved, skipped = build_scenario(
            s, timeout, verbose, content_enabled, visual_mode)
        any_skipped = any_skipped or skipped
        tail = "" if ok else f"  ({err})"
        if skipped and ok:
            tail = "  (checks partially skipped)"
        if saved and not ok:
            tail += f"  log: {saved}"
        print(f"{'PASS' if ok else 'FAIL'} {elapsed:5.1f}s{tail}")
        results.append((s["slug"], ok, err))

    total = time.time() - t_start
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(slug, err) for slug, ok, err in results if not ok]
    print()
    print(f"Summary: {passed}/{len(results)} scenarios passed in {total:.1f}s total")
    if update_refs:
        print(f"(reference images written under {VISUAL_REF_DIR})")
    if any_skipped:
        print("Note: some checks were skipped (missing poppler/ImageMagick).")
    if failed:
        print("Failures:")
        for slug, err in failed:
            print(f"  - {slug}: {err}")
    return len(failed)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # PDF text (and TeX logs) can carry glyphs the host console encoding can't
    # represent (e.g. cp1252 on Windows). Make our own output tolerant so a
    # stray character never crashes the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(
        description="Smoke-test every TeXLib module template under one or more build modes."
    )
    p.add_argument("modules", nargs="*", help="Subset of modules to test (default: all)")
    p.add_argument("--student", action="store_true", help=r"Also build with \StudentMode")
    p.add_argument("--key", action="store_true", help=r"Also build with \ShowKey")
    p.add_argument("--solutions", action="store_true", help=r"Also build with \ShowSolutions")
    p.add_argument("--rubric", action="store_true", help=r"Also build with \ShowRubric")
    p.add_argument(
        "--modes",
        choices=["default", "all"],
        default="default",
        help="Shortcut: 'all' = default+student+key+solutions+rubric. Default: just default.",
    )
    p.add_argument("--timeout", type=int, default=120, help="Per-build timeout in seconds.")
    p.add_argument("-v", "--verbose", action="store_true", help="Show last 50 log lines on failure.")
    p.add_argument(
        "--no-content", action="store_true",
        help="Skip content checks (pdftotext substrings + artifact non-emptiness); build-only.",
    )
    p.add_argument(
        "--visual", action="store_true",
        help="Also compare each rendered page against tests/visual_refs/ (needs poppler + ImageMagick).",
    )
    p.add_argument(
        "--update-refs", action="store_true",
        help="Regenerate visual reference images instead of comparing. Implies --visual.",
    )
    p.add_argument(
        "--dump-text", action="store_true",
        help="Print each module's extracted PDF text and exit (aid for writing EXPECT_TEXT).",
    )
    p.add_argument(
        "--scenarios", nargs="*", metavar="AREA", default=None,
        help="Run visual scenario packs (tests/scenarios/) instead of the module suite. "
             "Optionally limit to AREA(s), e.g. --scenarios schedule. Always visual; "
             "combine with --update-refs to regenerate scenario references.",
    )
    p.add_argument(
        "--full", action="store_true",
        help="With --scenarios, include `full`-tier scenarios (default: core only).",
    )
    args = p.parse_args()

    visual_mode: str | None = None
    if args.update_refs:
        visual_mode = "update"
    elif args.visual:
        visual_mode = "check"
    content_enabled = not args.no_content

    # Scenario packs are a separate run path (their own templates + refs).
    if args.scenarios is not None:
        return run_scenarios(args.scenarios, args.full, args.update_refs,
                             content_enabled, args.timeout, args.verbose)

    if args.modules:
        wanted = set(args.modules)
        targets = [(m, t) for (m, t) in MODULES if m in wanted]
        missing = wanted - {m for (m, _) in MODULES}
        if missing:
            print(f"warning: unknown modules ignored: {sorted(missing)}", file=sys.stderr)
    else:
        targets = list(MODULES)

    modes: list[tuple[str, str | None]] = [("default", None)]
    enable_all = args.modes == "all"
    for flag in ("student", "key", "solutions", "rubric"):
        if enable_all or getattr(args, flag):
            modes.append((flag, MODES[flag]))

    # --dump-text: build each target once (default mode) and print its text.
    if args.dump_text:
        for module, template in targets:
            build_one(module, template, None, args.timeout, args.verbose,
                      content=False, visual=None, dump_text=True)
        return 0

    # Surface missing optional tools up front so a green run isn't mistaken for
    # "content verified" when the checker silently no-op'd.
    check_bits = []
    if content_enabled:
        check_bits.append("content" + ("" if PDFTOTEXT else " [pdftotext MISSING -> text checks skipped]"))
    if visual_mode:
        have_magick = bool(MAGICK or COMPARE)
        miss = [n for n, ok in (("pdftoppm", PDFTOPPM), ("ImageMagick", have_magick)) if not ok]
        check_bits.append(
            ("visual:update" if visual_mode == "update" else "visual")
            + (f" [{', '.join(miss)} MISSING -> skipped]" if miss else "")
        )

    print(f"TeXLib smoke test")
    print(f"  root    : {TEXLIB_ROOT}")
    print(f"  modules : {len(targets)} ({', '.join(m for m, _ in targets)})")
    print(f"  modes   : {', '.join(name for name, _ in modes)}")
    print(f"  checks  : build{(' + ' + ', '.join(check_bits)) if check_bits else ' only'}")
    print()

    results: list[tuple[str, str, bool, float, str]] = []
    any_skipped = False
    t_start = time.time()
    for module, template in targets:
        for mode_name, mode_macro in modes:
            label = f"  [{module:<14}] {mode_name:<9} "
            sys.stdout.write(label + "... ")
            sys.stdout.flush()
            ok, elapsed, err, saved, skipped = build_one(
                module, template, mode_macro, args.timeout, args.verbose,
                content=content_enabled, visual=visual_mode,
            )
            any_skipped = any_skipped or skipped
            status = "PASS" if ok else "FAIL"
            tail = "" if ok else f"  ({err})"
            if skipped and ok:
                tail = "  (checks partially skipped)"
            if saved and not ok:
                tail += f"  log: {saved}"
            print(f"{status} {elapsed:5.1f}s{tail}")
            results.append((module, mode_name, ok, elapsed, err))

    total = time.time() - t_start
    passed = sum(1 for _, _, ok, _, _ in results if ok)
    failed = [(m, mode, err) for (m, mode, ok, _, err) in results if not ok]

    print()
    print(f"Summary: {passed}/{len(results)} passed in {total:.1f}s total")
    if any_skipped:
        print("Note: some content/visual checks were skipped (missing poppler/ImageMagick).")
    if failed:
        print("Failures:")
        for m, mode, err in failed:
            print(f"  - {m} [{mode}]: {err}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
# fence
