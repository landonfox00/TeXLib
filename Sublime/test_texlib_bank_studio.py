#!/usr/bin/env python
r"""Coverage for the Bank Studio launcher (texlib/texlib_bank_studio.py).

No Sublime, no server: stubs sublime/sublime_plugin, then checks
resolve_script's precedence (explicit path > class_source > repo-root fallback).

Run:  python Sublime/test_texlib_bank_studio.py
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

sys.modules["sublime"] = types.ModuleType("sublime")
_plugin = types.ModuleType("sublime_plugin")
_plugin.WindowCommand = object
sys.modules["sublime_plugin"] = _plugin
# texlib_bank_studio imports texlib_locate, which also imports the stubs above.

import texlib_bank_studio  # noqa: E402


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# Explicit path to a .py wins verbatim.
s = {"bank_studio_path": "D:/tools/bank_studio.py", "class_source": "D:/repo"}
ok &= check(texlib_bank_studio.resolve_script(s) == "D:/tools/bank_studio.py",
            "bank_studio_path (.py) used verbatim")

# Explicit path to a directory appends bank_studio.py.
s = {"bank_studio_path": "D:/tools"}
ok &= check(texlib_bank_studio.resolve_script(s)
            == os.path.join("D:/tools", "bank_studio.py"),
            "bank_studio_path (dir) -> dir/bank_studio.py")

# Else class_source root.
s = {"class_source": "D:/repo"}
ok &= check(texlib_bank_studio.resolve_script(s)
            == os.path.join("D:/repo", "bank_studio.py"),
            "class_source -> root/bank_studio.py")

# No settings -> repo-root fallback (two dirs above the package); basename holds.
for s in (None, {}):
    got = texlib_bank_studio.resolve_script(s)
    ok &= check(os.path.basename(got) == "bank_studio.py",
                "fallback resolves to a bank_studio.py path (settings=%r)" % (s,))

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
