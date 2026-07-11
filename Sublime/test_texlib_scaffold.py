#!/usr/bin/env python
r"""Discovery coverage for scaffolding (texlib/texlib_scaffold.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, builds a fake repo tree, and
checks discover_templates finds every <class>-template.tex (class name derived
from the filename, spaced/hyphenated dirs and classes handled) while ignoring
test fixtures and non-template files.

Run:  python Sublime/test_texlib_scaffold.py
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

sys.modules["sublime"] = types.ModuleType("sublime")
_plugin = types.ModuleType("sublime_plugin")
_plugin.WindowCommand = object
sys.modules["sublime_plugin"] = _plugin

import texlib_scaffold  # noqa: E402


def touch(root, rel, body=""):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(body)


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True
with tempfile.TemporaryDirectory() as root:
    touch(root, "Exams/autoexam-template.tex")
    touch(root, "Report Cards/report-card-template.tex")   # spaced dir, hyphen class
    touch(root, "Syllabi/syllabus-template.tex")
    touch(root, "tests/scenarios/quiz/standard/template.tex")  # fixture (no -template)
    touch(root, "Quizzes/quiz-01.tex")                     # a real doc, not a template
    touch(root, "Sublime/texlib/texlib.py")               # excluded dir

    tmpl = texlib_scaffold.discover_templates(root)
    classes = [t["class"] for t in tmpl]

    ok &= check(classes == ["autoexam", "report-card", "syllabus"],
                "discovers exactly the three templates, sorted, class from filename")
    ok &= check(all(t["path"].endswith("-template.tex") for t in tmpl),
                "each entry points at its -template.tex")
    ok &= check("template.tex" not in [os.path.basename(t["path"]) for t in tmpl],
                "ignores tests/ fixture template.tex (no -template suffix)")
    ok &= check(os.path.basename(
                    [t for t in tmpl if t["class"] == "report-card"][0]["path"])
                == "report-card-template.tex",
                "hyphenated class name derived correctly")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
