#!/usr/bin/env python
r"""Coverage for the completion-context classifier (texlib/texlib_complete.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, then checks completion_context
distinguishes 'ids' (inside \getproblem{...}), 'macros' (after a backslash), and
None, so the listener offers the right thing in each spot.

Run:  python Sublime/test_texlib_complete.py
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

sys.modules["sublime"] = types.ModuleType("sublime")
_plugin = types.ModuleType("sublime_plugin")
_plugin.EventListener = object
_plugin.WindowCommand = object  # texlib_bank defines WindowCommands at import
sys.modules["sublime_plugin"] = _plugin

import texlib_complete as tc  # noqa: E402


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


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

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
