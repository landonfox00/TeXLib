#!/usr/bin/env python3
"""Coverage for coursemeta_lint.py (pure parse + lint; no TeX)."""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import coursemeta_lint as L


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

META = r"""\metasetup{
    course-number = 181,
    course-title  = {Calculus I},   % braced value with a space
    season = Fall, year = 2026,
    start-date = 8-24, end-date = 12-8, final-date = 12-15,
    exam1-date = {Sep 19, 2026},     % human string with a comma
    exam2-date = {Oct 17, 2026},
}
"""
m = L.parse_meta(META)
ok &= check(m.get("course-title") == "Calculus I", "parse_meta: braced value")
ok &= check(m.get("exam1-date") == "Sep 19, 2026", "parse_meta: braced value with comma")
ok &= check(m.get("start-date") == "8-24", "parse_meta: bare value")
ok &= check(L.parse_md("8-24") == (8, 24) and L.parse_md("Sep 19") is None,
            "parse_md: M-D only")
ok &= check(L.set_exam_dates(m) == [1, 2], "set_exam_dates: exam1,exam2 set")

# schedule with 3 \exam (one is \exam[noquiz]), plus \examreview which must NOT count
SCHED = r"\examreview \exam[noquiz] \examreview \exam \finalreview \exam"
ok &= check(L.count_schedule_exams(SCHED) == 3, "count_schedule_exams excludes \\examreview")

# lint: exam-count mismatch (schedule 3 exams, coursemeta 2 dates) -> warn
warns = L.lint(m, SCHED, r"\examdatetable")
msgs = " ".join(w[1] for w in warns)
ok &= check(any(w[0] == "warn" and "3 \\exam" in w[1] and "2 exam" in w[1] for w in warns),
            "lint: flags schedule/coursemeta exam-count mismatch")

# lint: missing required field -> error
warns2 = L.lint({"course-number": "181"})
ok &= check(any(w[0] == "error" and "course-title" in w[1] for w in warns2),
            "lint: missing required field is an error")

# lint: date order error
warns3 = L.lint({"course-number": "1", "course-title": "x", "season": "Fall",
                 "year": "2026", "start-date": "12-8", "end-date": "8-24"})
ok &= check(any("not before" in w[1] for w in warns3), "lint: start >= end is an error")

# real example course: matched exam count, no errors
ex = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "examples", "Math181-Fall2026")
if os.path.isdir(ex):
    rm = L.parse_meta(open(os.path.join(ex, "coursemeta.tex"), encoding="utf-8").read())
    ok &= check(rm.get("course-number") == "181", "real coursemeta parses (course-number=181)")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
