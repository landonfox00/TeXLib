#!/usr/bin/env python3
r"""benchmark.py — where a TeXLib build's time actually goes, per class.

WHY THIS FILE EXISTS

TeXLib had no benchmarks. Not for didactic, not for any of the ten classes --
the only timing code in the repository was in the galleries. That was survivable
while nothing in the library claimed to manage build time, and it stopped being
survivable when the deferral scanner and the format cache landed: those exist
purely to make builds faster, and nothing would notice if a later change put the
cost back.

WHAT IT MEASURES, AND WHY THAT SHAPE

The finding that motivated all of this is that a TeXLib build's cost is package
loading, not typesetting. On a six-page Notes document:

    engine floor (near-empty article)          1.09s
    + the TeXLib class bundle                  3.55s
    + the document's own 25 KB of content      0.25s

The content is smaller than the run-to-run noise. So a benchmark that times
whole builds and stops there measures the class and calls it the document --
which is exactly the mistake that makes such a number useless. This harness
separates the three, per class, by timing three documents rather than one:

    floor    a near-empty \documentclass{article}, same engine
    class    a near-empty document of the class under test
    full     the real example document

and reports  class_load = class - floor  and  content = full - class.

WHY THE GATE IS A RATIO, NOT SECONDS

Absolute seconds are a property of the machine, not the library. A CI runner is
slower than a laptop and varies between runs, so a threshold in seconds either
fails constantly or is set so loose it catches nothing. The regression gate
therefore uses

    class_cost = (class - floor) / floor

which is "how many engine-floors does loading this class cost". That is stable
across machines in a way seconds are not, and it is the number the library
actually controls.

WHAT IT DOES NOT COVER

The committed baseline is measured over `examples/`, because that is what CI can
reach. Be careful reading it as representative: `examples/` contains ONE
tikzpicture and the real teaching corpus contains over a thousand, so anything
whose cost scales with picture count is invisible here. `--corpus DIR` points the
harness at real documents for local runs; those are deliberately not baselined,
since the files are not in the repository.

USAGE

    python benchmark.py                       # measure everything, print a table
    python benchmark.py Notes "Problem Sets"  # only these modules
    python benchmark.py --variants            # also time deferred + cached builds
    python benchmark.py --check               # compare to the committed baseline
    python benchmark.py --update-baseline     # rewrite it (do this deliberately)
    python benchmark.py --json out.json       # machine-readable results
    python benchmark.py --corpus "D:/Teaching"  # add real documents
"""

import argparse
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEXLIB_ROOT = SCRIPT_DIR

# The staging machinery is smoke_test's, not a copy of it. Staging a class into
# a build directory is subtle -- the comma-in-TEXINPUTS problem, the class-home
# fallback, the coursemeta stub -- and a second implementation would drift from
# the one CI actually uses, which would make this harness measure a build no one
# performs. Same reason the buildspec constants live in one file.
sys.path.insert(0, TEXLIB_ROOT)
import smoke_test as _smoke  # noqa: E402

sys.path.insert(0, os.path.join(TEXLIB_ROOT, "Sublime", "texlib"))
import texlib_preamble_scan as _scan        # noqa: E402
import texlib_format_cache as _fmtcache     # noqa: E402

BASELINE_PATH = os.path.join(TEXLIB_ROOT, "tests", "benchmark-baseline.json")


def _manifest_modules(tag):
    """(module, template) pairs carrying `tag`, straight from the manifest."""
    sys.path.insert(0, os.path.join(TEXLIB_ROOT, "examples"))
    import manifest as _manifest      # noqa: E402
    return _manifest.modules(tag)

# How far class_cost may drift above its baseline before --check fails.
# Generous on purpose: this gate exists to catch a package creeping back into
# the bundle (which shows up as tens of percent), not to police noise.
TOLERANCE = 0.25

# The per-picture figure gets its own, much looser tolerance, because it is a
# DIFFERENCE of two timings (full - class) and inherits the noise of both. Two
# consecutive clean runs of the same fixture measured 82 and 54 ms per picture,
# so a 25% gate on it would flake constantly and be turned off within a week,
# which is worse than a loose gate that stays on. What it exists to catch is a
# pathology -- externalisation silently disabled, a pgf regression, a picture
# path that stopped caching -- and those are multiples, not percentages.
PICTURE_TOLERANCE = 1.00

# Below this many seconds a measurement is noise on any machine, and a ratio
# built from it is meaningless. Used to suppress a division that would otherwise
# turn timer jitter into a dramatic-looking regression.
NOISE_FLOOR_SECONDS = 0.05

DEFAULT_REPS = 3

# A near-empty document for each class, used to price the class load with as
# little content as the class will accept. Most classes are happy with nothing;
# the ones listed here need their metadata or a section before they will build.
CLASS_STUB_BODY = {
    "schedule": "",          # the calendar comes from coursemeta
    "report-card": "",
    "bank": "",
}


# Below this many pictures, (full - class) is dominated by measurement noise and
# dividing it by a picture count produces a confident-looking number that means
# nothing. The Perf fixture carries twelve.
MIN_PICTURES_FOR_METRIC = 6

_PICTURE_RE = re.compile(r"\\begin\{tikzpicture\}")


def count_pictures(tex_path):
    r"""Literal \begin{tikzpicture} occurrences in a document and its inputs.

    Deliberately naive. A document that draws through a macro of its own counts
    as one picture per macro BODY rather than per call, and that is accepted
    rather than special-cased: the alternative is teaching this counter about
    each document's private wrappers, which makes a shared metric depend on the
    documents it measures. The Perf fixture is written with twelve literal
    environments for exactly that reason.
    """
    try:
        text, _complete = _scan.gather_source(tex_path)
    except Exception:               # noqa: BLE001 -- a metric, never a build
        return 0
    return len(_PICTURE_RE.findall(text))


def texinputs(existing=""):
    r"""An EXPLICIT, non-recursive search path over the checkout.

    `smoke_test` uses `<root>//`, and a correctness harness is right to: the
    recursive form finds a class wherever it moves, and costs that harness
    nothing it measures. A benchmark cannot use it. kpathsea walks every
    directory the pattern covers, and this repo has 512 of them against 99 real
    ones -- the rest are `.git` and `.claude/worktrees`. Measured on the thesis
    class: `//` adds +1.41s to a 2.17s class load (a 65% overstatement) while
    adding only +0.06s to the engine floor, so it does not even cancel in the
    ratio. The harness would be reporting the search path as if it were the
    class, and CLAUDE.md warns about exactly this pattern for the same reason.

    The explicit list below is what a real build uses. Staging already copies
    the shared files into the build directory, so `.` resolves nearly
    everything; this is the fallback that catches the rest.
    """
    sep = ";" if os.name == "nt" else ":"
    parts = [".", TEXLIB_ROOT]
    for name in sorted(os.listdir(TEXLIB_ROOT)):
        path = os.path.join(TEXLIB_ROOT, name)
        if os.path.isdir(path) and not name.startswith((".", "_", "@")):
            parts.append(path)
    if existing:
        parts.append(existing)
    return sep.join(parts) + sep


def _stub_source(docclass, body=""):
    r"""A minimal document of `docclass`, with no content worth typesetting."""
    return (
        "\\documentclass{%s}\n" % docclass
        + "\\begin{document}\n"
        + (body or "x")
        + "\n\\end{document}\n"
    )


def _empty_article(engine):
    r"""The engine floor document. Same for every class using that engine."""
    return "\\documentclass[11pt,letterpaper]{article}\n\\begin{document}x\\end{document}\n"


class Staged:
    """One example document, copied into a temp dir and ready to compile.

    Staging is the expensive part (it copies the whole shared library in), so it
    happens once per document and every timed variant runs against the result.
    """

    def __init__(self, module, template):
        self.module = module
        self.template = template
        self.module_dir = os.path.join(TEXLIB_ROOT, module)
        self.tex_src = os.path.join(self.module_dir, template)
        self.jobname = os.path.splitext(template)[0]
        self.dir = None
        self.engine = None
        self.docclass = None

    def __enter__(self):
        safe = re.sub(r"[^\w.-]+", "_", self.module)
        self.dir = tempfile.mkdtemp(prefix="texlib_bench_%s_" % safe)
        self.engine = _smoke.detect_engine(self.tex_src)
        self.docclass = _smoke.detect_class(self.tex_src) or ""

        for entry in os.listdir(self.module_dir):
            src = os.path.join(self.module_dir, entry)
            if os.path.isfile(src):
                shutil.copy2(src, self.dir)

        home = _smoke.CLASS_HOME_MODULE.get(self.docclass)
        if home and home != self.module:
            home_dir = os.path.join(TEXLIB_ROOT, home)
            for entry in os.listdir(home_dir):
                src = os.path.join(home_dir, entry)
                if os.path.isfile(src) and not os.path.exists(
                        os.path.join(self.dir, entry)):
                    shutil.copy2(src, self.dir)

        _smoke._copy_shared_into(self.dir)

        coursemeta = os.path.join(self.dir, "coursemeta.tex")
        if not os.path.exists(coursemeta):
            with io.open(coursemeta, "w", encoding="utf-8") as fh:
                fh.write(_smoke.STUB_COURSEMETA)

        self.env = os.environ.copy()
        self.env["TEXINPUTS"] = texinputs(self.env.get("TEXINPUTS", ""))
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)
        return False

    def write(self, name, source):
        path = os.path.join(self.dir, name)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        return path

    def run(self, argv, timeout=180):
        return subprocess.run(
            argv, cwd=self.dir, env=self.env, timeout=timeout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def engine_cmd(self, extra=()):
        cmd = [self.engine, "-interaction=nonstopmode"]
        if self.engine == "lualatex":
            cmd.append("-shell-escape")
        return cmd + list(extra)


def log_is_clean(staged, jobname):
    """True when <jobname>.log carries no TeX error lines.

    The return code is not enough. Under -interaction=nonstopmode the engine
    recovers from most errors and exits 0, so a document that is quietly failing
    still produces a timing -- and a failing build is FASTER, which is the worst
    possible direction for a benchmark to be wrong in. A missing log is treated
    as unclean for the same reason.
    """
    path = os.path.join(staged.dir, jobname + ".log")
    try:
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            return not any(line.startswith("!") for line in fh)
    except OSError:
        return False


def timed(staged, argv, reps):
    """Best-of-`reps` wall time for one command, after a discarded warm-up.

    Best-of, not mean: the quantity of interest is how long the work takes, and
    every source of noise on a desktop machine adds time rather than removing
    it. A mean measures the machine's background load as much as the build.
    Returns (seconds, ok) -- ok is False if the command ever failed, in which
    case the timing is reported but must not be baselined.
    """
    ok = True
    try:
        staged.run(argv)                       # warm-up, discarded
    except subprocess.TimeoutExpired:
        return float("nan"), False
    best = None
    for _ in range(reps):
        start = time.perf_counter()
        try:
            result = staged.run(argv)
        except subprocess.TimeoutExpired:
            return float("nan"), False
        elapsed = time.perf_counter() - start
        ok = ok and result.returncode == 0
        best = elapsed if best is None else min(best, elapsed)
    return best, ok


def measure(module, template, reps, variants, floors, bench_doc=False,
            noisy=None):
    """Every measurement for one document. Returns a dict, or None if unusable.

    `bench_doc` marks a document present for its content rather than its class
    (see the Perf fixture): it contributes the per-picture figure and is kept out
    of the per-class baseline.
    """
    if noisy is None:
        noisy = []
    with Staged(module, template) as st:
        if not os.path.exists(st.tex_src):
            return None

        # 1. Engine floor, re-measured for EVERY document, next to the class
        #    measurement it will be divided into.
        #
        #    It was measured once per engine and cached, on the reasoning that
        #    the floor is a property of the toolchain and re-measuring it would
        #    only cost runtime. That was wrong, and the harness caught it: in one
        #    run the SAME class priced 3.42s under the Notes staging and 6.54s
        #    under Perf, because the machine had drifted between the first
        #    document and the last and every later class was being divided by a
        #    floor from a faster moment.
        #
        #    The whole point of reporting a ratio is that machine speed cancels,
        #    and it only cancels if numerator and denominator are measured under
        #    the same conditions. A cached floor quietly destroys that property
        #    on exactly the long runs the baseline is generated from.
        st.write("_bench_floor.tex", _empty_article(st.engine))
        floor, _ = timed(st, st.engine_cmd(["_bench_floor.tex"]), reps)
        floors.setdefault(st.engine, floor)   # kept only for reporting

        # 2. Class load: the same near-empty document, but of this class.
        stub_name = "_bench_stub.tex"
        st.write(stub_name, _stub_source(
            st.docclass, CLASS_STUB_BODY.get(st.docclass, "")))
        class_time, class_ok = timed(st, st.engine_cmd([stub_name]), reps)
        class_ok = class_ok and log_is_clean(st, "_bench_stub")

        # 2b. The same stub with every deferral the scanner can apply. This is
        #     the number a real build actually pays, and it is roughly HALF the
        #     eager one for the heavy classes -- didactic 2.27s -> 1.16s, pset
        #     2.09s -> 1.15s. Reporting only the eager figure told the truth
        #     about the bundle and the wrong thing about the user's experience.
        #
        #     The flags come from the SCANNER, asked about this very stub, not
        #     from a hardcoded full set. That distinction matters: the scanner
        #     refuses to defer tikz for a class it has not audited, so forcing
        #     every flag would advertise a floor those classes cannot actually
        #     reach. A stub has no content, so what comes back is the most the
        #     scanner would ever defer for this class -- its true floor, against
        #     the eager figure as the ceiling, with real documents in between.
        st.write("_bench_min.tex", _stub_source(
            st.docclass, CLASS_STUB_BODY.get(st.docclass, "")))
        deferred_prefix = _scan.defer_prefix_for(
            os.path.join(st.dir, "_bench_min.tex"))
        st.write("_bench_min.tex",
                 deferred_prefix + "\n" + _stub_source(
                     st.docclass, CLASS_STUB_BODY.get(st.docclass, "")))
        min_time, min_ok = timed(st, st.engine_cmd(["_bench_min.tex"]), reps)
        min_ok = min_ok and log_is_clean(st, "_bench_min")
        if not min_ok:
            # A class that cannot build with everything deferred is not a
            # failure of the benchmark -- most cannot, and should not be able
            # to. It simply has no floor to report.
            min_time = None
        elif min_time > class_time + NOISE_FLOOR_SECONDS:
            # Deferring cannot cost MORE than not deferring, so this is not a
            # result: it is the machine telling us it is too noisy to measure on
            # right now. Reporting it as a number would put an impossible figure
            # in a table that people read as fact, and -- worse -- into a
            # committed baseline. Seen for real: a run where autoexam, bingo and
            # syllabus all came back with min > class while the pdflatex floor
            # ranged 1.25-1.81s within the single run.
            min_time = None
            noisy.append(module)

        # 3. The real document, one pass, exactly as it is today.
        full, full_ok = timed(st, st.engine_cmd([template]), reps)
        full_ok = full_ok and log_is_clean(st, os.path.splitext(template)[0])

        # Per-picture cost. Content time is noise on an ordinary document -- it
        # is smaller than the run-to-run spread -- so this is only meaningful
        # where there are enough pictures for them to BE the content, which is
        # what examples/fixtures/Perf exists to provide. Below the threshold the
        # figure is deliberately not reported rather than reported as noise.
        pictures = count_pictures(os.path.join(st.dir, template))
        content = full - class_time
        per_picture = ((content / pictures * 1000.0)
                       if pictures >= MIN_PICTURES_FOR_METRIC and content > 0
                       else None)

        row = {
            "module": module,
            "template": template,
            "class": st.docclass,
            "engine": st.engine,
            "floor_s": floor,
            "class_s": class_time,
            "full_s": full,
            "class_load_s": class_time - floor,
            "class_min_s": (min_time - floor) if min_time else None,
            "reclaimed_s": (class_time - min_time) if min_time else None,
            "content_s": content,
            "class_cost": ((class_time - floor) / floor
                           if floor and floor > NOISE_FLOOR_SECONDS else None),
            "pictures": pictures,
            "ms_per_picture": per_picture,
            "bench": bench_doc,
            "ok": bool(class_ok and full_ok),
        }

        if variants:
            names = _scan.deferrable_for(os.path.join(st.dir, template))
            prefix = _scan.defer_macros(names)
            row["deferred"] = names
            if prefix:
                arg = prefix + "\\input{%s}" % template
                deferred, ok = timed(st, st.engine_cmd([arg]), reps)
            else:
                deferred, ok = full, full_ok
            row["deferred_s"] = deferred
            row["deferred_ok"] = ok

            key = _fmtcache.ensure(os.path.join(st.dir, template), st.engine,
                                   prefix, TEXLIB_ROOT, env=st.env)
            if key:
                st.env = _fmtcache.env_with_cache(st.env)
                cached, ok = timed(
                    st, [st.engine, "-fmt=" + key, "-interaction=nonstopmode",
                         template], reps)
                row["cached_s"] = cached
                row["cached_ok"] = ok
            else:
                row["cached_s"] = None
                row["cached_ok"] = False

        return row


def corpus_documents(corpus_dir, limit):
    """(module, template) pairs for real documents under `corpus_dir`.

    `module` is an absolute path here rather than a repo-relative one; Staged
    only ever joins it to TEXLIB_ROOT, and os.path.join returns an absolute
    second argument unchanged, so both shapes work without a special case.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(corpus_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(filenames):
            if not name.endswith(".tex"):
                continue
            path = os.path.join(dirpath, name)
            if _smoke.detect_class(path) in _smoke.CLASS_HOME_MODULE:
                found.append((dirpath, name))
                if len(found) >= limit:
                    return found
    return found


def fmt(value, width=7):
    if value is None:
        return "-".rjust(width)
    if value != value:                       # NaN
        return "timeout".rjust(width)
    return ("%.2f" % value).rjust(width)


def print_table(rows, variants):
    head = "%-22s %-12s %-9s %7s %7s %7s %7s %7s" % (
        "module", "class", "engine", "floor", "class", "min", "content", "cost")
    if variants:
        head += " %7s %7s" % ("defer", "cached")
    print(head)
    print("-" * len(head))
    for r in rows:
        line = "%-22s %-12s %-9s %s %s %s %s %s" % (
            r["module"].split("/")[-1][:22], r["class"][:12], r["engine"],
            fmt(r["floor_s"]), fmt(r["class_load_s"]), fmt(r.get("class_min_s")),
            fmt(r["content_s"]), fmt(r["class_cost"]))
        if variants:
            line += " %s %s" % (fmt(r.get("deferred_s")), fmt(r.get("cached_s")))
        if not r["ok"]:
            line += "  BUILD FAILED"
        print(line)

    usable = [r for r in rows if r["ok"] and r["class_cost"] is not None]
    if usable:
        costs = [r["class_cost"] for r in usable]
        print("-" * len(head))
        print("class load costs %.1f-%.1f engine floors (median %.1f)"
              % (min(costs), max(costs), statistics.median(costs)))

    reclaimed = [r for r in rows
                 if r["ok"] and r.get("reclaimed_s") and r["class_load_s"] > 0]
    if reclaimed:
        print("deferral reclaims (class -> min):")
        for r in sorted(reclaimed, key=lambda x: -x["reclaimed_s"])[:6]:
            print("  %-13s %.2f -> %.2f s  (-%.0f%%)"
                  % (r["class"][:13], r["class_load_s"], r["class_min_s"],
                     100 * r["reclaimed_s"] / r["class_load_s"]))

    drawn = [r for r in rows if r.get("ms_per_picture")]
    for r in drawn:
        print("%s: %d pictures, %.0f ms each"
              % (r["module"].split("/")[-1], r["pictures"], r["ms_per_picture"]))


def load_baseline():
    try:
        with io.open(BASELINE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def save_baseline(rows):
    os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
    payload = {
        "_comment": [
            "Baseline for benchmark.py --check. The gate is class_cost =",
            "(class - floor) / floor, i.e. how many engine-floors loading this",
            "class costs -- a ratio, because absolute seconds are a property of",
            "the machine and would make the gate either flaky or useless.",
            "Regenerate deliberately with: python benchmark.py --update-baseline",
        ],
        "tolerance": TOLERANCE,
        "picture_tolerance": PICTURE_TOLERANCE,
        # Bench rows are excluded here. They are chosen for their CONTENT, and
        # the Perf fixture happens to be a didactic document -- so keying by
        # class alone let it overwrite the Notes template's didactic figure with
        # its own, arbitrarily, depending on declaration order. The class cost
        # comes from the smoke corpus; bench documents contribute the
        # per-picture figure below and nothing else.
        "classes": {
            r["class"]: round(r["class_cost"], 3)
            for r in rows
            if r["ok"] and r["class_cost"] is not None and not r.get("bench")
        },
        # Per-picture typesetting cost, in milliseconds, from whichever bench
        # documents carry enough pictures to measure it. This is the half of the
        # workload the class-cost figures cannot see: examples/ has one picture,
        # a real teaching tree has over a thousand. Keyed by module so adding a
        # second bench document does not overwrite the first.
        "ms_per_picture": {
            r["module"]: round(r["ms_per_picture"], 1)
            for r in rows if r["ok"] and r.get("ms_per_picture")
        },
    }
    with io.open(BASELINE_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


def check_against_baseline(rows):
    """True when nothing regressed. Prints one line per class either way."""
    baseline = load_baseline()
    if not baseline:
        print("\nno baseline at %s -- run --update-baseline first"
              % os.path.relpath(BASELINE_PATH, TEXLIB_ROOT))
        return False

    tolerance = baseline.get("tolerance", TOLERANCE)
    expected = baseline.get("classes", {})
    print("\nregression check (tolerance %+.0f%%)" % (tolerance * 100))
    failures, unmeasured = [], []
    for r in rows:
        name = r["class"]
        # Bench documents are not priced by class -- see save_baseline. Checking
        # them here would report the same class twice, from two documents that
        # were never meant to agree on anything but the class they share.
        if r.get("bench"):
            continue
        if name not in expected:
            unmeasured.append(name)
            continue
        if not r["ok"] or r["class_cost"] is None:
            print("  %-14s SKIP  (build failed or floor too small to divide)"
                  % name)
            continue
        was, now = expected[name], r["class_cost"]
        limit = was * (1 + tolerance)
        drift = (now - was) / was if was else 0.0
        verdict = "ok  " if now <= limit else "FAIL"
        if now > limit:
            failures.append(name)
        print("  %-14s %s  %.2f -> %.2f  (%+.0f%%)"
              % (name, verdict, was, now, drift * 100))

    # Per-picture cost, gated the same way and for the same reason. This is the
    # half of the workload the class figures cannot see, so a regression here --
    # pictures getting more expensive to typeset -- would otherwise be invisible
    # to CI entirely.
    expected_pic = baseline.get("ms_per_picture", {})
    pic_tolerance = baseline.get("picture_tolerance", PICTURE_TOLERANCE)
    for r in rows:
        now = r.get("ms_per_picture")
        was = expected_pic.get(r["module"])
        if not now or was is None:
            continue
        limit = was * (1 + pic_tolerance)
        verdict = "ok  " if now <= limit else "FAIL"
        if now > limit:
            failures.append(r["module"] + " (ms/picture)")
        print("  %-14s %s  %.1f -> %.1f ms/picture  (%+.0f%%)"
              % (os.path.basename(r["module"])[:14], verdict, was, now,
                 100 * (now - was) / was if was else 0))

    if unmeasured:
        print("  not in baseline: %s" % ", ".join(sorted(set(unmeasured))))
    if failures:
        print("\n%d class(es) regressed: %s" % (len(failures), ", ".join(failures)))
        return False
    print("\nno regressions")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure where a TeXLib build's time goes, per class.")
    parser.add_argument("modules", nargs="*",
                        help="Substring filter on module path (default: all).")
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS,
                        help="Timed repetitions per measurement (best-of).")
    parser.add_argument("--variants", action="store_true",
                        help="Also time the deferred and format-cached builds.")
    parser.add_argument("--corpus", metavar="DIR",
                        help="Also benchmark real documents found under DIR.")
    parser.add_argument("--corpus-limit", type=int, default=5,
                        help="How many corpus documents to take (default 5).")
    parser.add_argument("--json", metavar="FILE", help="Write results as JSON.")
    parser.add_argument("--check", action="store_true",
                        help="Compare against the committed baseline; exit 1 on a regression.")
    parser.add_argument("--update-baseline", action="store_true",
                        help="Rewrite the committed baseline from this run.")
    args = parser.parse_args(argv)

    # The smoke corpus prices the classes; the `bench' corpus prices what the
    # smoke corpus cannot see. examples/ carries ONE tikzpicture against a real
    # teaching tree's thousand, so without a bench document the per-picture
    # figure has nothing to measure. Nothing else reads the `bench' tag, which is
    # why adding it costs no CI build time.
    documents = list(_smoke.MODULES) + list(_manifest_modules("bench"))
    if args.modules:
        documents = [(m, t) for (m, t) in documents
                     if any(f.lower() in m.lower() for f in args.modules)]
    # One document per class is enough to price the class, and the corpus has
    # several per class. Keep the first of each; --corpus adds real ones.
    #
    # A `bench' document is exempt from that de-duplication. The Perf fixture is
    # a didactic document and didactic is already priced by the Notes template,
    # so the filter would drop precisely the document that exists to measure
    # something the others cannot -- it is here for its CONTENT, not its class.
    bench = set(_manifest_modules("bench"))
    seen, unique = set(), []
    for module, template in documents:
        if (module, template) in bench:
            unique.append((module, template))
            continue
        docclass = _smoke.detect_class(os.path.join(TEXLIB_ROOT, module, template))
        if docclass and docclass not in seen:
            seen.add(docclass)
            unique.append((module, template))
    documents = unique

    if args.corpus:
        documents += corpus_documents(args.corpus, args.corpus_limit)

    if not documents:
        print("no documents matched")
        return 2

    print("TeXLib benchmark")
    print("  root      : %s" % TEXLIB_ROOT)
    print("  documents : %d" % len(documents))
    print("  reps      : %d (best-of, after a discarded warm-up)\n" % args.reps)

    floors, rows, noisy = {}, [], []
    for module, template in documents:
        label = "%s/%s" % (os.path.basename(module), template)
        sys.stdout.write("  measuring %-44s " % label[:44])
        sys.stdout.flush()
        started = time.perf_counter()
        try:
            row = measure(module, template, args.reps, args.variants, floors,
                          bench_doc=((module, template) in bench), noisy=noisy)
        except Exception as exc:              # noqa: BLE001 - report and continue
            print("ERROR %s" % exc)
            continue
        if row is None:
            print("skipped")
            continue
        rows.append(row)
        print("%.1fs" % (time.perf_counter() - started))

    print()
    print_table(rows, args.variants)

    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
            fh.write("\n")
        print("\nwrote %s" % args.json)

    if noisy:
        print("\nTOO NOISY TO MEASURE: %s" % ", ".join(
            os.path.basename(m) for m in sorted(set(noisy))))
        print("  Deferring came out slower than not deferring, which is "
              "impossible.\n  The machine is under load or thermally throttled; "
              "these figures are not results.")

    if args.update_baseline:
        # A baseline is a fact other runs are judged against, and one written
        # from a run this noisy is worse than none: it silently loosens the gate
        # to whatever today's interference happened to be. Refusing costs a
        # re-run; accepting costs a gate that no longer catches anything.
        if noisy:
            print("\nREFUSING to write a baseline from a run flagged noisy.")
            print("  Re-run on a quiet machine, or raise --reps.")
            return 1
        payload = save_baseline(rows)
        print("\nbaseline written: %d classes -> %s"
              % (len(payload["classes"]),
                 os.path.relpath(BASELINE_PATH, TEXLIB_ROOT)))
        return 0

    if args.check:
        return 0 if check_against_baseline(rows) else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
