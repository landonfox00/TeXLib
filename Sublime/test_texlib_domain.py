#!/usr/bin/env python
r"""Headless coverage for the plugin domain-depth cluster (D1–D5 pure logic).

Stubs sublime/sublime_plugin, then exercises the pure helpers of:
  * texlib_topic     -- attr parsing, topic buckets, filtering (D1)
  * texlib_bankreport-- coverage report + preview wrapper (D2, D3)
  * texlib_meta      -- .metadump parse/render (D4)
  * texlib_complete  -- coursemeta key extraction + \metasetup detection (D5)

Run:  python Sublime/test_texlib_domain.py
"""
import os
import sys
import types

try:  # keep unicode in labels from crashing a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

_s = types.ModuleType("sublime")
_s.INHIBIT_WORD_COMPLETIONS = 8
sys.modules["sublime"] = _s
_p = types.ModuleType("sublime_plugin")
_p.WindowCommand = object
_p.EventListener = object
_p.ViewEventListener = object
sys.modules["sublime_plugin"] = _p

import texlib_topic       # noqa: E402
import texlib_bankreport  # noqa: E402
import texlib_meta        # noqa: E402
import texlib_complete    # noqa: E402


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# --- D1: topic parsing / bucketing / filtering ------------------------------
attrs = texlib_topic.parse_attrs("topic=limit, section=2.3, difficulty=hard")
ok &= check(attrs == {"topic": "limit", "section": "2.3", "difficulty": "hard"},
            "D1: parse_attrs splits key=value pairs")

problems = [
    {"id": "a", "attrs": "topic=limit"},
    {"id": "b", "attrs": "topic=limit"},
    {"id": "c", "attrs": "topic=ivt"},
    {"id": "d", "attrs": ""},
]
topics = texlib_topic.topics_of(problems)
labels = [t[0] for t in topics]
ok &= check(any("limit  (2)" in l for l in labels), "D1: topic bucket counts")
ok &= check(any(l.startswith("(no topic)") for l in labels), "D1: no-topic bucket")
lim = texlib_topic.problems_with(problems, "topic", "limit")
ok &= check([p["id"] for p in lim] == ["a", "b"], "D1: filter problems by topic")

# --- D2: bank report --------------------------------------------------------
probs = [
    {"id": "p1", "attrs": "topic=limit, difficulty=easy"},
    {"id": "p2", "attrs": "topic=limit, difficulty=hard"},
    {"id": "p3", "attrs": "topic=ivt"},
    {"id": "p1", "attrs": "topic=limit"},   # duplicate id
]
rep = texlib_bankreport.bank_report(probs, referenced={"p1", "zzz"})
ok &= check(rep["total"] == 4 and rep["distinct"] == 3, "D2: totals + distinct")
ok &= check(rep["duplicates"] == ["p1"], "D2: duplicate id detected")
ok &= check(rep["unused"] == ["p2", "p3"], "D2: unused = defined − referenced")
ok &= check(rep["dangling"] == ["zzz"], "D2: dangling = referenced − defined")
text = texlib_bankreport.render_report(rep, "exam.tex")
ok &= check("Bank Report" in text and "Unused" in text, "D2: report renders")

# --- D3: preview wrapper ----------------------------------------------------
w = texlib_bankreport.preview_wrapper("/course/bank.tex", "/course")
ok &= check("\\documentclass{bank}" in w, "D3: wrapper uses bank.cls")
ok &= check("\\loadbank{bank}" in w, "D3: relative \\loadbank without .tex")
ok &= check("\\printbankcatalog" in w, "D3: wrapper catalogs the bank")
ok &= check(texlib_bankreport.resolve_bank("/x/bank.tex",
            "\\begin{problem}{a} x \\end{problem}") == "/x/bank.tex",
            "D3: a bare fragment previews itself")

# --- D4: metadump parse/render ----------------------------------------------
rows = texlib_meta.parse_metadump(
    "course-number\t181\ncourse-title\tCalculus I\ncourse-section\t\n")
ok &= check(dict(rows).get("course-number") == "181", "D4: parses key\\tvalue")
ok &= check(("course-section", "") in rows, "D4: keeps unset (empty) fields")
rendered = texlib_meta.render_metadump(rows, "syllabus.tex")
ok &= check("Calculus I" in rendered and "(unset)" in rendered,
            "D4: renders values + marks unset")

# --- D5: coursemeta keys + \metasetup detection -----------------------------
snippet = (r"\meta_create_var:nn { course-number } { CourseNumber }" "\n"
           r"    instructor-email .tl_gset:c = { g__meta_email_tl }," "\n")
keys = texlib_complete.coursemeta_keys(snippet)
ok &= check("course-number" in keys and "instructor-email" in keys,
            "D5: extracts canonical + alias keys")
ok &= check(texlib_complete.in_metasetup("\\metasetup{\n  course-num"),
            "D5: detects open \\metasetup{")
ok &= check(not texlib_complete.in_metasetup("\\metasetup{ x=1 }\n more"),
            "D5: closed \\metasetup{ is not 'inside'")
ok &= check(texlib_complete._key_position("  course-num")
            and not texlib_complete._key_position("  course-number = 18"),
            "D5: key position vs value position")

# D5 integration: the REAL course-metadata.sty exposes the known keys.
real = os.path.join(os.path.dirname(HERE), "course-metadata.sty")
if os.path.isfile(real):
    with open(real, encoding="utf-8", errors="replace") as fh:
        rk = texlib_complete.coursemeta_keys(fh.read())
    ok &= check({"course-number", "lecture-days", "exam1-date"} <= set(rk),
                "D5: real course-metadata.sty keys extracted (%d keys)" % len(rk))

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
