#!/usr/bin/env python
r"""Coverage for the completion-context classifier (texlib/texlib_complete.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, then checks completion_context
distinguishes 'ids' (inside \getproblem{...}), 'macros' (after a backslash), and
None, so the listener offers the right thing in each spot.

Run:  python Sublime/test_texlib_complete.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("EventListener", "WindowCommand")

import texlib_complete as tc  # noqa: E402


ctx = tc.completion_context
ok = True

ok &= check(ctx("\\getproblem{lim", "m") == "ids", "inside \\getproblem{ -> ids")
ok &= check(ctx("\\getproblem{", "{") == "ids", "empty \\getproblem{ -> ids")
ok &= check(ctx("\\question \\reqproblem{lin", "n") == "ids",
            "mid-line \\reqproblem{ -> ids")
ok &= check(ctx("\\get", "\\") == "macros", "right after a backslash -> macros")
ok &= check(ctx("\\", "\\") == "macros", "bare backslash -> macros")
ok &= check(ctx("\\getproblem{id} done", " ") is None,
            "after a CLOSED \\getproblem{} -> None")
ok &= check(ctx("plain words her", "r") is None, "ordinary prose -> None")
ok &= check(ctx("\\setvar{x}{y}", "}") is None,
            "a non-id macro is not treated as ids")

report(ok)
