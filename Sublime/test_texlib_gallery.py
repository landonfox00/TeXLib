#!/usr/bin/env python
r"""Coverage for the accessibility-gallery launcher (texlib/texlib_gallery.py).

No Sublime, no build: stubs sublime/sublime_plugin, then checks resolve_paths'
precedence (explicit path > class_source > repo-root fallback) and that the
output HTML always resolves beside the generator script.

Run:  python Sublime/test_texlib_gallery.py
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

import texlib_gallery  # noqa: E402


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# Explicit path to a .py wins verbatim; html sits beside it.
s = {"a11y_gallery_path": "D:/tools/a11y_gallery.py", "class_source": "D:/repo"}
script, html = texlib_gallery.resolve_paths(s)
ok &= check(script == "D:/tools/a11y_gallery.py",
            "a11y_gallery_path (.py) used verbatim")
ok &= check(html == os.path.join("D:/tools", "a11y_gallery.html"),
            "html resolves beside the .py override")

# Explicit path to a directory appends a11y_gallery.py.
s = {"a11y_gallery_path": "D:/tools"}
script, html = texlib_gallery.resolve_paths(s)
ok &= check(script == os.path.join("D:/tools", "a11y_gallery.py"),
            "a11y_gallery_path (dir) -> dir/a11y_gallery.py")
ok &= check(html == os.path.join("D:/tools", "a11y_gallery.html"),
            "html beside the dir-resolved script")

# class_source -> root/a11y_gallery.py (+ .html).
s = {"class_source": "D:/repo"}
script, html = texlib_gallery.resolve_paths(s)
ok &= check(script == os.path.join("D:/repo", "a11y_gallery.py"),
            "class_source -> root/a11y_gallery.py")
ok &= check(html == os.path.join("D:/repo", "a11y_gallery.html"),
            "class_source -> root/a11y_gallery.html")

# No settings at all -> repo-root fallback (basename check, path is env-specific).
for s in ({}, None):
    script, html = texlib_gallery.resolve_paths(s)
    ok &= check(os.path.basename(script) == "a11y_gallery.py"
                and os.path.basename(html) == "a11y_gallery.html",
                "fallback resolves to a11y_gallery.py/.html (settings=%r)" % (s,))

# The windowless flag is the Win32 CREATE_NO_WINDOW on nt, 0 elsewhere.
if os.name == "nt":
    ok &= check(texlib_gallery._CREATE_NO_WINDOW == 0x08000000,
                "CREATE_NO_WINDOW set on Windows")
else:
    ok &= check(texlib_gallery._CREATE_NO_WINDOW == 0,
                "CREATE_NO_WINDOW is 0 off Windows")

ok &= check(texlib_gallery._BUILD_LOG.endswith("a11y-gallery-build.log"),
            "build log path names the gallery build")

# The generator must run under a CONSOLE python, never pythonw.exe. A
# GUI-subsystem parent has no console to hand down, so every lualatex/veraPDF/
# pdftoppm child allocates its own -- which is a screenful of popup windows.
# CREATE_NO_WINDOW + console python gives them one invisible console to inherit.
_py = texlib_gallery._python()
if _py is None:
    print("  [SKIP] no python on PATH to check the launcher flavour")
else:
    ok &= check(os.path.basename(_py).lower() != "pythonw.exe",
                "generator runs under console python, not pythonw.exe")

print("\n%s" % ("ALL PASS" if ok else "FAILURES ABOVE"))
sys.exit(0 if ok else 1)
