#!/usr/bin/env python3
"""Shared scaffolding for the TeXLib Sublime test suite: stub modules, tiny
result helpers, and toolchain probes copy-pasted across test_*.py. Dev-only --
deploy.ps1 excludes it. Because Python puts a script's own directory on sys.path,
`import _testkit` resolves from any Sublime/test_*.py with no extra path setup."""
import os
import re
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


# A document argument carries a deferral prefix whenever the preamble scanner
# found something this document never uses -- which, for the synthetic one-line
# documents the suites build, is everything. That prefix is not a MODE macro,
# and the assertions about mode macros compare against the argument with any
# prefix stripped.
_DEFER_PREFIX_RE = re.compile(r"^(?:\\def\\TeXLibNo[A-Za-z]+\{\})+")


def without_defer(arg):
    r"""`arg` minus its \def\TeXLibNo... prefix, unwrapped from \input{...}.

    "doc.tex" -> "doc.tex"
    "\def\TeXLibNoBib{}\input{doc.tex}" -> "doc.tex"
    "\def\ShowKey{}\input{doc.tex}" -> "\def\ShowKey{}\input{doc.tex}"  (a mode
    macro survives, which is exactly what these assertions must still catch.)
    """
    arg = str(arg)
    stripped = _DEFER_PREFIX_RE.sub("", arg)
    if stripped == arg:
        return arg                      # nothing was stripped; leave it alone
    match = re.fullmatch(r"\\input\{(.*)\}", stripped)
    return match.group(1) if match else stripped


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
    The lookup is texlib_buildspec.find_poppler, shared with the repo-root
    suites and version_diff.py; this is the Sublime suites' route to it."""
    tdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "texlib")
    if tdir not in sys.path:
        sys.path.insert(0, tdir)
    import texlib_buildspec
    return texlib_buildspec.find_poppler(tool)


class _StubPdfBuilder:
    """Minimal stand-in for LaTeXTools' PdfBuilder base class."""
    def __init__(self, *a, **k):
        self._displayed = ""

    def display(self, msg):
        self._displayed += str(msg)


def install_native_builder():
    """Stub LaTeXTools' PdfBuilder and register the native TeXLib package so
    `from texlib_builder import TexlibBuilder` imports headless, and return the
    TexlibBuilder class. The shared build core lives in TeXLib.texlib_build
    (a package name that only exists inside Sublime), so register the native
    module under it. Idempotent."""
    here = os.path.dirname(os.path.abspath(__file__))  # Sublime/
    for name in ("LaTeXTools", "LaTeXTools.plugins",
                 "LaTeXTools.plugins.builder",
                 "LaTeXTools.plugins.builder.pdf_builder"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["LaTeXTools.plugins.builder.pdf_builder"].PdfBuilder = _StubPdfBuilder
    tdir = os.path.join(here, "texlib")
    for pth in (here, tdir):
        if pth not in sys.path:
            sys.path.insert(0, pth)
    import texlib_build as _native
    pkg = types.ModuleType("TeXLib")
    pkg.__path__ = [tdir]
    sys.modules.setdefault("TeXLib", pkg)
    sys.modules.setdefault("TeXLib.texlib_build", _native)
    from texlib_builder import TexlibBuilder
    return TexlibBuilder


class Checker:
    """Family-B result tracker. Assign `check = _c.check` so call sites keep
    the bare check(label, cond, detail='', known_issue=None) form; counts live
    on the instance (self.passed / self.failed / self.known)."""
    def __init__(self):
        self.passed = self.failed = self.known = self.skipped = 0

    def check(self, label, cond, detail="", known_issue=None):
        if cond:
            self.passed += 1
            print(f"  PASS  {label}")
        elif known_issue:
            self.known += 1
            print(f"  KNOWN {label}  (tracked: {known_issue})")
            if detail:
                print(f"        {detail}")
        else:
            self.failed += 1
            print(f"  FAIL  {label}")
            if detail:
                print(f"        {detail}")

    def skip(self, label):
        self.skipped += 1
        print(f"  SKIP  {label}")
