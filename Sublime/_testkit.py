#!/usr/bin/env python3
"""Shared scaffolding for the TeXLib Sublime test suite: stub modules, tiny
result helpers, and toolchain probes copy-pasted across test_*.py. Dev-only --
deploy.ps1 excludes it. Because Python puts a script's own directory on sys.path,
`import _testkit` resolves from any Sublime/test_*.py with no extra path setup."""
import os
import shutil
import subprocess
import sys
import types


def stub_sublime(*plugin_classes, **sublime_attrs):
    """Register minimal `sublime` / `sublime_plugin` stub modules so the plugin
    source imports headless. `plugin_classes` are the sublime_plugin base names
    exposed as `object` (default: WindowCommand); `sublime_attrs` set attributes
    on the `sublime` module (e.g. status_message=lambda *a, **k: None)."""
    s = types.ModuleType("sublime")
    for k, v in sublime_attrs.items():
        setattr(s, k, v)
    sys.modules["sublime"] = s
    p = types.ModuleType("sublime_plugin")
    for name in (plugin_classes or ("WindowCommand",)):
        setattr(p, name, object)
    sys.modules["sublime_plugin"] = p
    return s, p


def check(cond, label):
    """Family-A assertion: print [OK]/[FAIL] and return cond so callers can
    accumulate `ok &= check(...)`."""
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


def report(ok):
    """Family-A footer: print the verdict and exit 0 (pass) / 1 (fail)."""
    print("\nALL PASS" if ok else "\nFAILURES ABOVE")
    sys.exit(0 if ok else 1)


def touch(root, rel, body=""):
    """Create root/<rel> (slash-separated) with parent dirs and optional
    contents; return the absolute path."""
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def find_poppler(tool="pdftotext"):
    """Absolute path to a poppler-flavored `tool` (pdftotext/pdftoppm), or None.
    Git for Windows ships an xpdf-flavored pdftotext that shadows poppler's on
    PATH and silently lacks -bbox (prints usage instead of erroring), so probe
    the -v banner and take the first candidate whose banner says poppler."""
    candidates = []
    which = shutil.which(tool)
    if which:
        candidates.append(which)
    candidates.append(rf"C:\texlive\2025\bin\windows\{tool}.exe")
    for cand in candidates:
        try:
            proc = subprocess.run([cand, "-v"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if "poppler" in ((proc.stdout or "") + (proc.stderr or "")).lower():
            return cand
    return None
