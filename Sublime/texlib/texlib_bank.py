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

# coursemeta wiring (autoexam/quiz autoload a bank via the coursemeta bank-path,
# and a master bank.tex \loadbank's per-chapter files with a \GetCourseMetaDir
# prefix): resolve both so navigation/completion see the real problem set.
GETMETADIR_RE = re.compile(r"\\GetCourseMetaDir\s*")
BANKPATH_RE = re.compile(
    r"\\meta\s*\{\s*bank-path\s*\}\s*\{([^}]*)\}"      # \meta{bank-path}{...}
    r"|bank-path\s*=\s*(\{[^}]*\}|[^,%\n\r]+)")        # metasetup: bank-path = ...


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


def _strip_comments(text):
    """Drop TeX % comments (respecting \\%) so a commented-out bank-path is not
    read as live."""
    out = []
    for line in text.split("\n"):
        res = []
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if c == "\\" and i + 1 < n:
                res.append(line[i:i + 2])
                i += 2
                continue
            if c == "%":
                break
            res.append(c)
            i += 1
        out.append("".join(res))
    return "\n".join(out)


def find_coursemeta(start_dir):
    """coursemeta.tex at start_dir or up to five parents above it, else None --
    mirrors course-metadata.sty's walk (and texlib_locate.find_coursemeta)."""
    d = os.path.abspath(start_dir)
    for _ in range(6):
        cand = os.path.join(d, "coursemeta.tex")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _expand_metadir(target, coursemeta_dir):
    """Expand a \\GetCourseMetaDir prefix (the macro eats its trailing space) to
    the coursemeta directory; drops to empty when no coursemeta is in scope. A
    function replacement keeps a Windows path's backslashes out of the regex
    replacement."""
    prefix = ""
    if coursemeta_dir:
        prefix = coursemeta_dir.replace("\\", "/").rstrip("/") + "/"
    return GETMETADIR_RE.sub(lambda _m: prefix, target)


def coursemeta_bank_path(coursemeta_path):
    """The coursemeta `bank-path` (autoloaded by autoexam/quiz) resolved to an
    absolute file, or None. Coursemeta-relative; accepts the `bank-path = ...`
    and `\\meta{bank-path}{...}` spellings."""
    text = _read(coursemeta_path)
    if text is None:
        return None
    m = BANKPATH_RE.search(_strip_comments(text))
    if not m:
        return None
    val = (m.group(1) or m.group(2) or "").strip()
    if val.startswith("{") and val.endswith("}"):
        val = val[1:-1].strip()
    base = os.path.dirname(coursemeta_path)
    val = _expand_metadir(val, base)
    if not val:
        return None
    p = val if os.path.isabs(val) else os.path.normpath(os.path.join(base, val))
    return p if os.path.isfile(p) else None


def problem_sources(doc_path, doc_text):
    """Ordered, de-duplicated files that may define bank problems for this doc:
    the doc itself, its \\loadbank / \\importproblem targets followed
    *transitively* (a thin master bank.tex is walked through to the per-chapter
    files that actually define problems), a sibling bank.tex, and the coursemeta
    `bank-path` the classes autoload. \\GetCourseMetaDir in a target is expanded
    to the coursemeta directory, so the scan matches what the real build sees at
    any depth below coursemeta.tex."""
    coursemeta_dir = None
    coursemeta_bank = None
    cm = find_coursemeta(os.path.dirname(doc_path))
    if cm:
        coursemeta_dir = os.path.dirname(cm)
        coursemeta_bank = coursemeta_bank_path(cm)

    files = []
    seen = set()
    queue = []

    def visit(path, text=None):
        key = os.path.normcase(os.path.abspath(path))
        if key in seen or not os.path.isfile(path):
            return
        seen.add(key)
        files.append(path)
        queue.append((path, text))

    def resolve(target, base):
        target = _expand_metadir(target.strip(), coursemeta_dir)
        for cand in (target, target + ".tex"):
            p = cand if os.path.isabs(cand) else os.path.normpath(
                os.path.join(base, cand))
            if os.path.isfile(p):
                return p
        return None

    visit(doc_path, doc_text)
    if coursemeta_bank:
        visit(coursemeta_bank)

    while queue:
        cur_path, cur_text = queue.pop(0)
        if cur_text is None:
            cur_text = _read(cur_path) or ""
        base = os.path.dirname(cur_path)
        for rx in (LOADBANK_RE, IMPORT_RE):
            for m in rx.finditer(cur_text):
                hit = resolve(m.group(1), base)
                if hit:
                    visit(hit)
        visit(os.path.normpath(os.path.join(base, "bank.tex")))
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
