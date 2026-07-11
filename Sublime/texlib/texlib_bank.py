# texlib_bank.py
# ============================================================================
# TeXLib bank navigation -- a domain command LaTeXTools has no concept of.
#
# Scans the active document plus its \loadbank / \importproblem targets (and a
# sibling bank.tex, the problembank auto-default) for \begin{problem}{id}[attrs]
# definitions, then offers a quick panel to either jump to a problem's
# definition or insert a \getproblem{id} retrieval at the cursor.
#
# A separate top-level plugin file so it hot-reloads independently of texlib.py.
# Self-contained: no import of the build runner (avoids a reload dependency).
# ============================================================================

import os
import re

import sublime
import sublime_plugin

# \begin{problem}{id}[optional, attrs]  -- id may contain hyphens/underscores.
PROBLEM_RE = re.compile(r"\\begin\{problem\}\{([^}]+)\}(?:\s*\[([^\]]*)\])?")
LOADBANK_RE = re.compile(r"\\loadbank\{([^}]+)\}")
IMPORT_RE = re.compile(r"\\importproblem\{([^}]+)\}")
ROOT_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+root\s*=\s*(.+?)\s*$")


def _is_tex(view):
    if view is None:
        return False
    if view.match_selector(0, "text.tex.latex"):
        return True
    name = view.file_name() or ""
    return name.lower().endswith((".tex", ".cls", ".sty"))


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def problem_sources(doc_path, doc_text):
    """Ordered, de-duplicated files that may define bank problems for this doc:
    the doc itself, its \\loadbank / \\importproblem targets (resolved relative
    to the doc dir; a bank ref may omit .tex), and a sibling bank.tex."""
    doc_dir = os.path.dirname(doc_path)
    files = [doc_path]

    def add(rel):
        for cand in (rel, rel + ".tex"):
            p = cand if os.path.isabs(cand) else os.path.normpath(
                os.path.join(doc_dir, cand))
            if os.path.isfile(p) and p not in files:
                files.append(p)
                return

    for m in LOADBANK_RE.finditer(doc_text):
        add(m.group(1).strip())
    for m in IMPORT_RE.finditer(doc_text):
        add(m.group(1).strip())
    sibling = os.path.normpath(os.path.join(doc_dir, "bank.tex"))
    if os.path.isfile(sibling) and sibling not in files:
        files.append(sibling)
    return files


def scan_problems(files):
    """List of {id, attrs, file, line} across the given files (line 0-based).
    `files` may include the doc's own path; text is read fresh from disk."""
    out = []
    for path in files:
        text = _read(path)
        if text is None:
            continue
        for m in PROBLEM_RE.finditer(text):
            out.append({
                "id": m.group(1).strip(),
                "attrs": (m.group(2) or "").strip(),
                "file": path,
                "line": text.count("\n", 0, m.start()),
            })
    return out


def _resolve_doc(view):
    """(doc_path, doc_text) honoring a leading %!TeX root; the live buffer wins
    for the doc, but a resolved root is read from disk."""
    fname = view.file_name()
    if not fname:
        return None, ""
    text = view.substr(sublime.Region(0, view.size()))
    m = ROOT_RE.search(text[:1024])
    if m:
        root = os.path.normpath(os.path.join(os.path.dirname(fname), m.group(1)))
        rt = _read(root)
        if rt is not None:
            return root, rt
    return fname, text


def _items(problems):
    rows = []
    for p in problems:
        tail = os.path.basename(p["file"])
        sub = (p["attrs"] + "  ·  " + tail) if p["attrs"] else tail
        rows.append([p["id"], sub])
    return rows


class _BankMixin:
    """Shared scan + quick-panel; not a Command itself (so Sublime doesn't
    register a phantom command for the base)."""

    def is_enabled(self):
        return _is_tex(self.window.active_view())

    def _pick(self, on_choose):
        view = self.window.active_view()
        doc_path, doc_text = _resolve_doc(view)
        if not doc_path:
            sublime.status_message("TeXLib: save the document first.")
            return
        problems = scan_problems(problem_sources(doc_path, doc_text))
        if not problems:
            sublime.status_message(
                "TeXLib: no \\begin{problem}{...} in this document or its bank(s).")
            return

        def done(i):
            if i >= 0:
                on_choose(problems[i])

        self.window.show_quick_panel(_items(problems), done)


class TexlibGotoProblemCommand(_BankMixin, sublime_plugin.WindowCommand):
    """Jump to a bank problem's \\begin{problem}{id} definition."""

    def run(self):
        def go(p):
            self.window.open_file(
                "%s:%d" % (p["file"], p["line"] + 1), sublime.ENCODED_POSITION)

        self._pick(go)


class TexlibInsertProblemCommand(_BankMixin, sublime_plugin.WindowCommand):
    """Insert \\getproblem{id} for a chosen bank problem at the cursor."""

    def run(self):
        def ins(p):
            self.window.active_view().run_command(
                "insert", {"characters": "\\getproblem{%s}" % p["id"]})

        self._pick(ins)


def plugin_loaded():
    print("TeXLib bank navigation loaded.")
