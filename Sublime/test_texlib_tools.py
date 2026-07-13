#!/usr/bin/env python
"""Headless coverage for the course-tool wrappers (texlib/texlib_tools.py)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("WindowCommand")

import texlib_tools as TT  # noqa: E402


ok = True
tex = os.path.join("course", "exam-01.tex")

ok &= check(TT.tool_target("bank_report.py", tex) == tex,
            "bank_report -> the .tex itself")
ok &= check(TT.tool_target("version_diff.py", tex) == tex,
            "version_diff -> the .tex itself")
ok &= check(TT.tool_target("collate_keys.py", tex)
            == os.path.join("course", "exam-01.pdf"),
            "collate_keys -> the sibling .pdf")
ok &= check(TT.tool_target("coursemeta_lint.py", tex) == "course",
            "coursemeta_lint -> the document's directory")

# every registered command class maps to a real repo-root script name
for cls in (TT.TexlibBankMatrixCommand, TT.TexlibCollateKeysCommand,
            TT.TexlibVersionDiffCommand, TT.TexlibCoursemetaLintCommand):
    ok &= check(cls.script in TT.TOOL_ARG, "%s.script is a known tool" % cls.__name__)

report(ok)
