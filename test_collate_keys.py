#!/usr/bin/env python3
"""Coverage for collate_keys.py (N7): discover plan + a real pypdf merge."""
import os
import sys
import tempfile

import collate_keys as ck


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# --- discover: only per-version key slices, sorted -------------------------
names = ["exam-01.pdf", "exam-01_A.pdf", "exam-01_A_solutions.pdf",
         "exam-01_B_solutions.pdf", "exam-01_C.pdf", "other.pdf"]
plan = ck.discover(names, "exam-01")
ok &= check(plan == [("A", "exam-01_A_solutions.pdf"),
                     ("B", "exam-01_B_solutions.pdf")],
            "discover: picks _solutions slices, sorted, ignores versions/combined")

plan2 = ck.discover(names, "exam-01", versions_too=True)
labels = [lbl for lbl, _ in plan2]
ok &= check("C" in labels and "A" in labels,
            "discover: --versions adds a version lacking a _solutions twin (C)")
ok &= check(dict(plan2)["A"] == "exam-01_A_solutions.pdf",
            "discover: A still prefers its _solutions slice over exam-01_A.pdf")

# --- collate: a real pypdf merge with bookmarks ----------------------------
try:
    from pypdf import PdfWriter, PdfReader
    have_pypdf = True
except ImportError:
    have_pypdf = False

if have_pypdf:
    with tempfile.TemporaryDirectory() as tmp:
        def make(name, pages):
            w = PdfWriter()
            for _ in range(pages):
                w.add_blank_page(width=200, height=200)
            with open(os.path.join(tmp, name), "wb") as fh:
                w.write(fh)

        make("exam_A_solutions.pdf", 2)
        make("exam_B_solutions.pdf", 3)
        plan = [("A", os.path.join(tmp, "exam_A_solutions.pdf")),
                ("B", os.path.join(tmp, "exam_B_solutions.pdf"))]
        out = os.path.join(tmp, "exam_AllKeys.pdf")
        n = ck.collate(plan, out)
        r = PdfReader(out)
        ok &= check(n == 2 and len(r.pages) == 5, "collate: merged pages (2+3=5)")
        ok &= check(len(r.outline) == 2, "collate: one bookmark per version")
else:
    print("  [skip] pypdf not installed -- collate merge check skipped")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
