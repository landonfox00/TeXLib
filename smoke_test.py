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

Exit code is the number of failed builds (0 = all passed).
"""

from __future__ import annotations

import argparse
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
# Helpers
# ---------------------------------------------------------------------------

DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{(\w[\w-]*)\}")


def detect_engine(tex_path: str) -> str:
    """Pick lualatex if the documentclass needs it, else pdflatex."""
    try:
        with open(tex_path, "r", encoding="utf-8", errors="ignore") as f:
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


def build_one(
    module: str,
    template: str,
    mode_macro: str | None,
    timeout: int,
    verbose: bool,
) -> tuple[bool, float, str, str]:
    """
    Build a single template.tex in an isolated temp directory.
    Returns (ok, elapsed_seconds, error_excerpt, full_log_path_on_failure).
    """
    module_dir = os.path.join(TEXLIB_ROOT, module)
    tex_src = os.path.join(module_dir, template)
    if not os.path.exists(tex_src):
        return False, 0.0, f"missing template: {tex_src}", ""

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

        # Also copy the TeXLib-root shared files (course-metadata.sty,
        # texlib-build.sty, basic-utilities.sty, texlib-mathutils.sty,
        # texlib-theorems.sty, texlib-footer.sty, quiver.sty,
        # problem_engine.lua, ...) into the build dir so they resolve via
        # the cwd. This sidesteps a hard kpathsea limitation: a TEXINPUTS
        # entry containing a COMMA is silently unsearchable, and the TeXLib
        # root can easily live under one (e.g. a OneDrive folder named
        # "...University of Nevada, Reno..."). A space in the path is fine;
        # a comma is not. Module files were copied first and win any name
        # clash, so we never overwrite them.
        for entry in os.listdir(TEXLIB_ROOT):
            src = os.path.join(TEXLIB_ROOT, entry)
            if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
                dest = os.path.join(tmp, entry)
                if not os.path.exists(dest):
                    shutil.copy2(src, dest)

        # Also collect .cls files from each module subdirectory. Without this,
        # tests living under Test/<Module>/ that do \documentclass{<sibling>}
        # cannot find the sibling module's class file (the cwd-copy trick
        # above only covers root-level files). Module .cls files have unique
        # names so name-clash is not a concern.
        for entry in os.listdir(TEXLIB_ROOT):
            sub = os.path.join(TEXLIB_ROOT, entry)
            if not os.path.isdir(sub):
                continue
            for f in os.listdir(sub):
                if f.lower().endswith(".cls"):
                    dest = os.path.join(tmp, f)
                    if not os.path.exists(dest):
                        shutil.copy2(os.path.join(sub, f), dest)

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

        t0 = time.time()
        try:
            r = subprocess.run(
                cmd,
                cwd=tmp,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            elapsed = time.time() - t0
        except subprocess.TimeoutExpired as exc:
            elapsed = time.time() - t0
            partial = _decode(exc.stdout)
            return False, elapsed, f"timeout after {timeout}s", _save_log(tmp, partial)

        jobname = os.path.splitext(template)[0]
        pdf = os.path.join(tmp, jobname + ".pdf")
        log_path = os.path.join(tmp, jobname + ".log")

        log_text = ""
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_text = f.read()
            except OSError:
                pass

        ok = r.returncode == 0 and os.path.exists(pdf)
        if ok:
            return True, elapsed, "", ""

        err = extract_tex_errors(log_text or r.stdout) or f"exit={r.returncode}, no pdf"
        saved = _save_log(tmp, log_text or r.stdout, verbose=verbose, jobname=jobname)
        return False, elapsed, err, saved
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
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
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
    args = p.parse_args()

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

    print(f"TeXLib smoke test")
    print(f"  root    : {TEXLIB_ROOT}")
    print(f"  modules : {len(targets)} ({', '.join(m for m, _ in targets)})")
    print(f"  modes   : {', '.join(name for name, _ in modes)}")
    print()

    results: list[tuple[str, str, bool, float, str]] = []
    t_start = time.time()
    for module, template in targets:
        for mode_name, mode_macro in modes:
            label = f"  [{module:<14}] {mode_name:<9} "
            sys.stdout.write(label + "... ")
            sys.stdout.flush()
            ok, elapsed, err, saved = build_one(
                module, template, mode_macro, args.timeout, args.verbose
            )
            status = "PASS" if ok else "FAIL"
            tail = "" if ok else f"  ({err})"
            if saved and not ok:
                tail += f"  log: {saved}"
            print(f"{status} {elapsed:5.1f}s{tail}")
            results.append((module, mode_name, ok, elapsed, err))

    total = time.time() - t_start
    passed = sum(1 for _, _, ok, _, _ in results if ok)
    failed = [(m, mode, err) for (m, mode, ok, _, err) in results if not ok]

    print()
    print(f"Summary: {passed}/{len(results)} passed in {total:.1f}s total")
    if failed:
        print("Failures:")
        for m, mode, err in failed:
            print(f"  - {m} [{mode}]: {err}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
# fence
