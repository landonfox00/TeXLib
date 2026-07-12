#!/usr/bin/env python3
r"""coursemeta_lint.py -- sanity + cross-document consistency for a course.

The syllabus (\examdatetable) and the schedule (\exam directives) both draw on
the same coursemeta.tex, but nothing checks they agree. This standalone linter
(no TeX) parses coursemeta.tex plus the sibling syllabus.tex / schedule.tex and
flags:

  * missing required fields (course-number, course-title, season, year,
    start-date, end-date);
  * M-D dates that don't parse, or are out of order (start < end; final-date
    after end-date);
  * a mismatch between the number of \exam directives in the schedule and the
    number of exam<N>-date keys set in coursemeta -- i.e. an exam that will
    render on the schedule but have no date in the syllabus table (or vice
    versa), the classic "added an exam, forgot its date" bug.

Usage:
    python coursemeta_lint.py examples/Math181-Fall2026
    python coursemeta_lint.py examples/Math181-Fall2026/coursemeta.tex
"""
import argparse
import os
import re
import sys

REQUIRED = ["course-number", "course-title", "season", "year",
            "start-date", "end-date"]
# \exam but NOT \examreview / \examseries: \exam followed by a non-letter.
EXAM_RE = re.compile(r"\\exam(?![a-zA-Z])")
EXAMDATETABLE_RE = re.compile(r"\\examdatetable\b")


def parse_meta(text):
    """Parse \\metasetup{ key = value, ... } into {key: value}, honoring {braced}
    values (which may contain commas). Returns a dict."""
    out = {}
    m = re.search(r"\\metasetup\s*\{", text)
    if not m:
        return out
    # brace-match the \metasetup argument
    i = m.end() - 1
    depth, start = 0, None
    for j in range(i, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
            if depth == 1:
                start = j + 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                body = text[start:j]
                break
    else:
        return out
    # scan key = value pairs, respecting {braces}
    n, k = len(body), 0
    while k < n:
        eq = body.find("=", k)
        if eq == -1:
            break
        key = body[k:eq].strip().strip(",").strip()
        v, p, d = k, eq + 1, 0
        # value runs to a top-level comma
        vstart = eq + 1
        p = vstart
        while p < n:
            c = body[p]
            if c == "{":
                d += 1
            elif c == "}":
                d -= 1
            elif c == "," and d == 0:
                break
            p += 1
        val = body[vstart:p].strip()
        if val.startswith("{") and val.endswith("}"):
            val = val[1:-1].strip()
        # strip trailing % comments on the key
        key = re.sub(r"%.*", "", key).strip()
        if key and not key.startswith("%"):
            out[key] = val
        k = p + 1
    return out


def parse_md(value):
    """A M-D date like '8-24' -> (8, 24); None if it isn't M-D."""
    m = re.fullmatch(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", value or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def set_exam_dates(meta):
    """Which exam<N>-date keys are set (non-empty) in coursemeta, sorted by N."""
    out = []
    for n in range(1, 6):
        v = meta.get("exam%d-date" % n, "").strip()
        if v:
            out.append(n)
    return out


def count_schedule_exams(schedule_text):
    return len(EXAM_RE.findall(schedule_text or ""))


def lint(meta, schedule_text=None, syllabus_text=None):
    """Return a list of (level, message). level in {'error','warn','info'}."""
    W = []
    for key in REQUIRED:
        if not meta.get(key, "").strip():
            W.append(("error", "coursemeta: required field '%s' is unset" % key))

    start = parse_md(meta.get("start-date", ""))
    end = parse_md(meta.get("end-date", ""))
    final = parse_md(meta.get("final-date", ""))
    if meta.get("start-date") and not start:
        W.append(("error", "start-date '%s' is not M-D" % meta["start-date"]))
    if meta.get("end-date") and not end:
        W.append(("error", "end-date '%s' is not M-D" % meta["end-date"]))
    if start and end and start >= end:
        W.append(("error", "start-date %s is not before end-date %s"
                  % (meta["start-date"], meta["end-date"])))
    if end and final and final <= end:
        W.append(("warn", "final-date %s is not after end-date %s (finals week?)"
                  % (meta["final-date"], meta["end-date"])))

    # Cross-document: schedule \exam count vs coursemeta exam dates.
    if schedule_text is not None:
        n_sched = count_schedule_exams(schedule_text)
        exam_dates = set_exam_dates(meta)
        n_dates = len(exam_dates)
        if n_sched != n_dates:
            W.append(("warn",
                      "schedule has %d \\exam directive(s) but coursemeta sets %d "
                      "exam<N>-date key(s) %s -- an exam may render with no date in "
                      "the syllabus \\examdatetable (or a date shows with no exam)."
                      % (n_sched, n_dates, exam_dates)))
        else:
            W.append(("info", "schedule \\exam count (%d) matches coursemeta exam "
                      "dates %s." % (n_sched, exam_dates)))
    if syllabus_text is not None and not EXAMDATETABLE_RE.search(syllabus_text):
        W.append(("info", "syllabus does not use \\examdatetable "
                  "(exam-date consistency not surfaced to students)."))
    return W


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint a course's coursemeta + docs.")
    ap.add_argument("target", help="a course directory or its coursemeta.tex")
    args = ap.parse_args(argv)
    if os.path.isdir(args.target):
        course_dir = args.target
    else:
        course_dir = os.path.dirname(os.path.abspath(args.target))
    cm = os.path.join(course_dir, "coursemeta.tex")
    if not os.path.isfile(cm):
        print("coursemeta_lint: no coursemeta.tex in %s" % course_dir, file=sys.stderr)
        return 2
    meta = parse_meta(_read(cm) or "")
    sched = _read(os.path.join(course_dir, "schedule.tex"))
    syl = _read(os.path.join(course_dir, "syllabus.tex"))
    warnings = lint(meta, sched, syl)
    errors = [w for w in warnings if w[0] == "error"]
    print("coursemeta lint — %s" % course_dir)
    print("=" * 48)
    for level, msg in warnings:
        print("  [%-5s] %s" % (level.upper(), msg))
    if not warnings:
        print("  (clean)")
    print()
    print("%d error(s), %d warning(s)."
          % (len(errors), sum(1 for w in warnings if w[0] == "warn")))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
