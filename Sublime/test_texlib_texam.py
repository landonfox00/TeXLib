#!/usr/bin/env python
r"""Coverage for the TeXam launcher (texlib/texlib_texam.py).

No Sublime, no server: stubs sublime/sublime_plugin, then checks
resolve_script's precedence (explicit path > class_source > repo-root fallback).

Run:  python Sublime/test_texlib_texam.py
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
# texlib_texam imports texlib_locate, which also imports the stubs above.

import texlib_texam  # noqa: E402


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# Explicit path to a .py wins verbatim.
s = {"texam_path": "D:/tools/texam.py", "class_source": "D:/repo"}
ok &= check(texlib_texam.resolve_script(s) == "D:/tools/texam.py",
            "texam_path (.py) used verbatim")

# Explicit path to a directory appends texam.py.
s = {"texam_path": "D:/tools"}
ok &= check(texlib_texam.resolve_script(s)
            == os.path.join("D:/tools", "texam.py"),
            "texam_path (dir) -> dir/texam.py")

# Else class_source root.
s = {"class_source": "D:/repo"}
ok &= check(texlib_texam.resolve_script(s)
            == os.path.join("D:/repo", "texam.py"),
            "class_source -> root/texam.py")

# No settings -> repo-root fallback (two dirs above the package); basename holds.
for s in (None, {}):
    got = texlib_texam.resolve_script(s)
    ok &= check(os.path.basename(got) == "texam.py",
                "fallback resolves to a texam.py path (settings=%r)" % (s,))

# The launcher runs the server with NO console window (CREATE_NO_WINDOW on
# Windows; 0 elsewhere), and logs output to a recoverable file.
if os.name == "nt":
    ok &= check(texlib_texam._CREATE_NO_WINDOW == 0x08000000,
                "hidden launch: CREATE_NO_WINDOW set on Windows")
else:
    ok &= check(texlib_texam._CREATE_NO_WINDOW == 0,
                "hidden launch: no window flag off Windows")
ok &= check(texlib_texam._LAUNCH_LOG.endswith("texam-launch.log"),
            "launch log path defined")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
