#!/usr/bin/env python3
"""bank_report.py -- coverage dashboard for a TeXLib problem bank.

A standalone CLI (like build_versions.py / package_for_lms.py -- no Sublime, no
TeX). Scans a bank file, a document (plus its \\loadbank targets and a sibling
bank.tex), or a directory, and reports:

  * totals + distinct ids, duplicate ids, dangling \\getproblem references
  * a topic x difficulty MATRIX (the coverage dashboard)
  * unused problems (defined but never \\getproblem'd, when a doc is given)
  * an estimated exam length (per-problem `time=<min>` attrs, else a
    difficulty-based default)

Usage:
    python bank_report.py examples/Math181-Fall2026/bank.tex
    python bank_report.py examples/Math181-Fall2026/exam-01.tex   # + \\getproblem uses
    python bank_report.py examples/Math181-Fall2026/              # all .tex in a dir
    python bank_report.py bank.tex --json
"""
import argparse
import json
import os
import re
import sys

PROBLEM_RE = re.compile(r"\\begin\{problem\}\{([^}]+)\}(?:\s*\[([^\]]*)\])?")
LOADBANK_RE = re.compile(r"\\loadbank\{([^}]+)\}")
IMPORT_RE = re.compile(r"\\importproblem\{([^}]+)\}")
GET_RE = re.compile(r"\\(?:getproblem|useproblem|reqproblem)\{([^}]+)\}")
ATTR_RE = re.compile(r"([A-Za-z][\w-]*)\s*=\s*([^,]+)")

# Difficulty -> default minutes when a problem carries no explicit time=.
DIFFICULTY_MIN = {"easy": 3, "medium": 5, "med": 5, "hard": 8, "challenge": 12}
DEFAULT_MIN = 5


def parse_attrs(attrs):
    return {m.group(1).strip().lower(): m.group(2).strip()
            for m in ATTR_RE.finditer(attrs or "")}


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def bank_sources(path):
    """Files to scan for a single .tex entry point: the file itself, its
    \\loadbank / \\importproblem targets (resolved relative to it, .tex optional),
    and a sibling bank.tex."""
    path = os.path.normpath(path)
    d = os.path.dirname(path)
    files = [path]
    text = read(path)

    def add(rel):
        for cand in (rel, rel + ".tex"):
            p = cand if os.path.isabs(cand) else os.path.normpath(os.path.join(d, cand))
            if os.path.isfile(p) and p not in files:
                files.append(p)
                return

    for m in LOADBANK_RE.finditer(text):
        add(m.group(1).strip())
    for m in IMPORT_RE.finditer(text):
        add(m.group(1).strip())
    sib = os.path.normpath(os.path.join(d, "bank.tex"))
    if os.path.isfile(sib) and sib not in files:
        files.append(sib)
    return files


def resolve_files(target):
    """Files to scan for a path that may be a dir, a bank, or a document."""
    if os.path.isdir(target):
        return sorted(os.path.join(target, f) for f in os.listdir(target)
                      if f.endswith(".tex"))
    return bank_sources(target)


def scan(files):
    """(problems, referenced_ids). problems: list of {id, attrs(dict), file}."""
    problems, referenced = [], set()
    for path in files:
        text = read(path)
        for m in PROBLEM_RE.finditer(text):
            problems.append({"id": m.group(1).strip(),
                             "attrs": parse_attrs(m.group(2) or ""),
                             "file": path})
        for m in GET_RE.finditer(text):
            referenced.add(m.group(1).strip())
    return problems, referenced


def estimate_minutes(problems):
    """Sum explicit time=<min>, else a difficulty-based default per problem."""
    total = 0
    for p in problems:
        t = p["attrs"].get("time")
        if t and t.rstrip("m").strip().isdigit():
            total += int(t.rstrip("m").strip())
        else:
            total += DIFFICULTY_MIN.get(
                p["attrs"].get("difficulty", "").lower(), DEFAULT_MIN)
    return total


def analyze(problems, referenced):
    ids = [p["id"] for p in problems]
    seen, dupes = set(), []
    for i in ids:
        if i in seen and i not in dupes:
            dupes.append(i)
        seen.add(i)
    defined = set(ids)
    topics = sorted({p["attrs"].get("topic", "-") for p in problems})
    diffs = sorted({p["attrs"].get("difficulty", "-") for p in problems})
    matrix = {t: {d: 0 for d in diffs} for t in topics}
    for p in problems:
        matrix[p["attrs"].get("topic", "-")][p["attrs"].get("difficulty", "-")] += 1
    return {
        "total": len(problems),
        "distinct": len(defined),
        "duplicates": sorted(dupes),
        "unused": sorted(defined - referenced),
        "dangling": sorted(referenced - defined),
        "topics": topics,
        "difficulties": diffs,
        "matrix": matrix,
        "minutes": estimate_minutes(problems),
    }


def render(rep):
    L = ["TeXLib Bank Report", "=" * 64, ""]
    L.append("Problems: %d defined (%d distinct)   Est. length: ~%d min"
             % (rep["total"], rep["distinct"], rep["minutes"]))
    L.append("")
    # Topic x difficulty matrix.
    diffs = rep["difficulties"]
    tw = max([len("topic")] + [len(t) for t in rep["topics"]], default=5)
    header = "  %-*s " % (tw, "topic") + " ".join("%7s" % d for d in diffs) + "   total"
    L.append("Coverage (topic x difficulty):")
    L.append(header)
    L.append("  " + "-" * (len(header) - 2))
    for t in rep["topics"]:
        row = rep["matrix"][t]
        cells = " ".join("%7d" % row[d] for d in diffs)
        L.append("  %-*s " % (tw, t) + cells + "   %5d" % sum(row.values()))
    L.append("")
    for title, key in [("Duplicate ids", "duplicates"),
                       ("Unused (defined, never \\getproblem'd)", "unused"),
                       ("Dangling (\\getproblem'd, not defined)", "dangling")]:
        vals = rep[key]
        L.append("%s: %s" % (title, ", ".join(vals) if vals else "(none)"))
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="TeXLib problem-bank coverage report.")
    ap.add_argument("target", help="a bank .tex, a document, or a directory")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)
    if not os.path.exists(args.target):
        print("bank_report: no such path: %s" % args.target, file=sys.stderr)
        return 2
    problems, referenced = scan(resolve_files(args.target))
    if not problems:
        print("bank_report: no \\begin{problem}{...} found under %s" % args.target,
              file=sys.stderr)
        return 1
    rep = analyze(problems, referenced)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
