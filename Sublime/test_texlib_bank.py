#!/usr/bin/env python
r"""Scan-logic coverage for bank navigation (texlib/texlib_bank.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, then exercises the pure scan
helpers (problem_sources + scan_problems) against a fixture doc that mixes both
patterns — inline \begin{problem} in the doc, an external \loadbank, and the
sibling bank.tex auto-default.

Run:  python Sublime/test_texlib_bank.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("WindowCommand")

import texlib_bank  # noqa: E402


ok = True
with tempfile.TemporaryDirectory() as tmp:
    # Sibling bank.tex (external, \loadbank target AND auto-default).
    with open(os.path.join(tmp, "bank.tex"), "w", encoding="utf-8") as fh:
        fh.write(
            "\\begin{problem}{lim-poly-factor}[topic=limit, section=2.3]\n x \\end{problem}\n"
            "\\begin{problem}{ivt-root}[topic=ivt]\n y \\end{problem}\n")
    # A separate imported problem file.
    with open(os.path.join(tmp, "extra.tex"), "w", encoding="utf-8") as fh:
        fh.write("\\begin{problem}{imported-one}[source=extra]\n z \\end{problem}\n")
    # The document: one inline problem, an explicit \loadbank, an \importproblem.
    doc = os.path.join(tmp, "exam.tex")
    doc_text = (
        "\\documentclass{autoexam}\n"
        "\\loadbank{bank}\n"                 # note: .tex omitted on purpose
        "\\importproblem{extra.tex}{}\n"
        "\\begin{problem}{inline-q}[topic=algebra]\n a \\end{problem}\n"
        "\\begin{document}\\end{document}\n")
    with open(doc, "w", encoding="utf-8") as fh:
        fh.write(doc_text)

    sources = texlib_bank.problem_sources(doc, doc_text)
    base = [os.path.basename(p) for p in sources]
    ok &= check(base[0] == "exam.tex", "sources: the doc itself is first")
    ok &= check("bank.tex" in base, "sources: \\loadbank{bank} resolved (.tex appended)")
    ok &= check("extra.tex" in base, "sources: \\importproblem target included")
    ok &= check(len(sources) == len(set(sources)), "sources: de-duplicated (bank.tex not doubled)")

    problems = texlib_bank.scan_problems(sources)
    ids = [p["id"] for p in problems]
    ok &= check("inline-q" in ids, "scan: inline doc problem found")
    ok &= check("lim-poly-factor" in ids and "ivt-root" in ids, "scan: external bank problems found")
    ok &= check("imported-one" in ids, "scan: imported problem found")

    byid = {p["id"]: p for p in problems}
    ok &= check(byid["lim-poly-factor"]["attrs"] == "topic=limit, section=2.3",
                "scan: attributes captured")
    ok &= check(byid["ivt-root"]["line"] == 2,
                "scan: 0-based line number correct (2nd problem in bank.tex)")

report(ok)
