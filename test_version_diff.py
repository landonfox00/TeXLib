#!/usr/bin/env python3
"""Coverage for version_diff.py (pure comparison logic; no TeX)."""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import version_diff as V


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

ok &= check(V.parse_versions(r"\versions{A, B, C}") == ["A", "B", "C"],
            "parse_versions splits + strips labels")
ok &= check(V.parse_versions("no versions here") == [],
            "parse_versions: none when absent")

n = V.normalize("Problem 1\n  2 of 5  \n42\nAnswer x")
ok &= check("2 of 5" not in n and n.count("42") == 0,
            "normalize drops 'N of M' + bare page-number lines")

# identical versions -> flagged; distinct -> not
rep = V.compare({"A": "solve x squared minus nine", "B": "solve x squared minus nine",
                 "C": "solve the integral of sine"}, threshold=0.98)
byp = {(a, b): r for a, b, r in rep["pairs"]}
ok &= check(abs(byp[("A", "B")] - 1.0) < 1e-9, "identical versions -> ratio 1.0")
ok &= check(byp[("A", "C")] < 0.98, "distinct versions -> below threshold")
ok &= check(("A", "B", byp[("A", "B")]) in rep["too_similar"]
            and len(rep["too_similar"]) == 1, "only the identical pair is flagged")

txt = V.render_report(rep)
ok &= check("TOO SIMILAR" in txt and "VERDICT" in txt, "report renders verdict")

rep2 = V.compare({"A": "alpha problem one", "B": "beta problem two"}, threshold=0.98)
ok &= check(not rep2["too_similar"] and "all versions differ" in V.render_report(rep2),
            "all-distinct -> OK verdict")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
