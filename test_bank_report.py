#!/usr/bin/env python3
"""Coverage for bank_report.py (N6) -- pure analysis + scan, no TeX."""
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import bank_report as br


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# --- analyze: matrix, dupes, unused, dangling -------------------------------
problems = [
    {"id": "a", "attrs": {"topic": "limit", "difficulty": "easy", "time": "3"}},
    {"id": "b", "attrs": {"topic": "limit", "difficulty": "hard", "time": "10"}},
    {"id": "c", "attrs": {"topic": "ivt", "difficulty": "easy"}},
    {"id": "a", "attrs": {"topic": "limit", "difficulty": "easy"}},  # dup id
]
rep = br.analyze(problems, referenced={"a", "ghost"})
ok &= check(rep["total"] == 4 and rep["distinct"] == 3, "totals + distinct")
ok &= check(rep["duplicates"] == ["a"], "duplicate id detected")
ok &= check(rep["unused"] == ["b", "c"], "unused = defined − referenced")
ok &= check(rep["dangling"] == ["ghost"], "dangling = referenced − defined")
ok &= check(rep["matrix"]["limit"]["easy"] == 2
            and rep["matrix"]["limit"]["hard"] == 1, "topic×difficulty matrix")

# time: a=3, b=10 explicit; c easy default 3; dup-a easy default 3 -> 19
ok &= check(rep["minutes"] == 19, "estimate: explicit time= + difficulty default")

# --- scan + bank_sources on a temp bank -------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    bank = os.path.join(tmp, "bank.tex")
    with open(bank, "w", encoding="utf-8") as fh:
        fh.write("\\begin{problem}{p1}[topic=limit] x \\end{problem}\n"
                 "\\begin{problem}{p2}[topic=ivt] y \\end{problem}\n")
    problems2, refs = br.scan(br.bank_sources(bank))
    ids = sorted(p["id"] for p in problems2)
    ok &= check(ids == ["p1", "p2"], "scan: bank not double-counted (path normalized)")

    doc = os.path.join(tmp, "exam.tex")
    with open(doc, "w", encoding="utf-8") as fh:
        fh.write("\\loadbank{bank}\n\\getproblem{p1}\n")
    p3, refs3 = br.scan(br.bank_sources(doc))
    ok &= check("p1" in refs3 and len(p3) == 2,
                "scan: doc resolves \\loadbank + records \\getproblem uses")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
