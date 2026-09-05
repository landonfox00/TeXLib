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

# How far class_cost may drift above its baseline before --check fails.
# Generous on purpose: this gate exists to catch a package creeping back into
# the bundle (which shows up as tens of percent), not to police noise.
TOLERANCE = 0.25

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
        sep = ";" if os.name == "nt" else ":"
        self.env["TEXINPUTS"] = ".%s%s//%s%s" % (
            sep, TEXLIB_ROOT, sep, self.env.get("TEXINPUTS", ""))
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


def measure(module, template, reps, variants, floors):
    """Every measurement for one document. Returns a dict, or None if unusable."""
    with Staged(module, template) as st:
        if not os.path.exists(st.tex_src):
            return None

        # 1. Engine floor. Shared per engine across the whole run: it is a
        #    property of the toolchain, and re-measuring it per document would
        #    triple the harness's runtime to produce the same number.
        if st.engine not in floors:
            st.write("_bench_floor.tex", _empty_article(st.engine))
            floor, _ = timed(st, st.engine_cmd(["_bench_floor.tex"]), reps)
            floors[st.engine] = floor
        floor = floors[st.engine]

        # 2. Class load: the same near-empty document, but of this class.
        stub_name = "_bench_stub.tex"
        st.write(stub_name, _stub_source(
            st.docclass, CLASS_STUB_BODY.get(st.docclass, "")))
        class_time, class_ok = timed(st, st.engine_cmd([stub_name]), reps)

        # 3. The real document, one pass, exactly as it is today.
        full, full_ok = timed(st, st.engine_cmd([template]), reps)

        row = {
            "module": module,
            "template": template,
            "class": st.docclass,
            "engine": st.engine,
            "floor_s": floor,
            "class_s": class_time,
            "full_s": full,
            "class_load_s": class_time - floor,
            "content_s": full - class_time,
            "class_cost": ((class_time - floor) / floor
                           if floor and floor > NOISE_FLOOR_SECONDS else None),
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
    head = "%-22s %-12s %-9s %7s %7s %7s %7s" % (
        "module", "class", "engine", "floor", "class", "content", "cost")
    if variants:
        head += " %7s %7s" % ("defer", "cached")
    print(head)
    print("-" * len(head))
    for r in rows:
        line = "%-22s %-12s %-9s %s %s %s %s" % (
            r["module"].split("/")[-1][:22], r["class"][:12], r["engine"],
            fmt(r["floor_s"]), fmt(r["class_load_s"]), fmt(r["content_s"]),
            fmt(r["class_cost"]))
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
        "classes": {
            r["class"]: round(r["class_cost"], 3)
            for r in rows if r["ok"] and r["class_cost"] is not None
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

    documents = list(_smoke.MODULES)
    if args.modules:
        documents = [(m, t) for (m, t) in documents
                     if any(f.lower() in m.lower() for f in args.modules)]
    # One document per class is enough to price the class, and the corpus has
    # several per class. Keep the first of each; --corpus adds real ones.
    seen, unique = set(), []
    for module, template in documents:
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

    floors, rows = {}, []
    for module, template in documents:
        label = "%s/%s" % (os.path.basename(module), template)
        sys.stdout.write("  measuring %-44s " % label[:44])
        sys.stdout.flush()
        started = time.perf_counter()
        try:
            row = measure(module, template, args.reps, args.variants, floors)
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

    if args.update_baseline:
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
