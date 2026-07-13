"""bank_parser.py -- parse a TeXLib problem bank for Bank Studio.

Standalone, stdlib-only, no TeX toolchain required.  Discovers which bank
files back an exam document and parses every ``\\begin{problem}`` block into a
structured record the web app can browse and filter.

Discovery + the header regex are ported from the native Sublime plugin's bank
scanner (Sublime/texlib/texlib_bank.py); that scanner only captures the id, the
raw ``[attrs]`` string, and the source line, so everything below the header --
body/region splitting, MC detection, meta parsing -- is added here.

Region splitting mirrors the Lua engine so a parsed problem matches how the real
build sees it (problem_engine.lua: find_env_block ~642, define_problem_from_env
~1132, parse_meta ~508):
  * strip TeX ``%`` comments first (the engine's \\Collect@Body drops them),
  * excise the ``solution`` block BEFORE the ``choices`` block,
  * a problem is multiple-choice iff a ``choices`` or ``oneparchoices`` block is
    present (a solution block does not make it MC),
  * ``\\begin{parts}`` stays verbatim in the stem (it is a plain list, not a
    region); the engine's scored-part marker is ``\\ppart`` and per-part points
    come from the exam invocation, not the body.

The full verbatim ``\\begin{problem}..\\end{problem}`` block is retained as
``raw`` for the source view.
"""

import os
import re

# --- ported verbatim from the plugin scanner ------------------------------
PROBLEM_RE = re.compile(r"\\begin\{problem\}\{([^}]+)\}(?:\s*\[([^\]]*)\])?")
LOADBANK_RE = re.compile(r"\\loadbank\{([^}]+)\}")
IMPORT_RE = re.compile(r"\\importproblem\{([^}]+)\}")
ROOT_RE = re.compile(r"%\s*!\s*T[eE]X\s+root\s*=\s*(.+)")

# --- added for Bank Studio -------------------------------------------------
PROBLEM_END_RE = re.compile(r"\\end\{problem\}")
CHOICE_RE = re.compile(r"\\(cchoice|choice|fchoice)\b(\s*\[[^\]]*\])?")
PART_PTS_RE = re.compile(r"\\part\s*\[\s*(\d+)\s*\]")


def _read(path):
    """Read a file as UTF-8, tolerating bad bytes; None on OSError."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def strip_comments(text):
    """Remove TeX ``%`` comments (respecting ``\\%``), preserving line count."""
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


def resolve_root(doc_path, doc_text):
    """Honor a leading ``%!TeX root=`` directive (first 1 KB); else the doc."""
    m = ROOT_RE.search(doc_text[:1024])
    if not m:
        return doc_path, doc_text
    rel = m.group(1).strip()
    root = rel if os.path.isabs(rel) else os.path.normpath(
        os.path.join(os.path.dirname(doc_path), rel))
    text = _read(root)
    if text is None:
        return doc_path, doc_text
    return root, text


def problem_sources(doc_path, doc_text):
    """Ordered, de-duplicated bank files: the doc, its \\loadbank /
    \\importproblem targets, then a sibling bank.tex.  Single level (no
    recursion into loaded banks) -- matches the plugin scanner."""
    files = [doc_path]
    base = os.path.dirname(doc_path)

    def add(rel):
        for cand in (rel, rel + ".tex"):
            path = cand if os.path.isabs(cand) else os.path.normpath(
                os.path.join(base, cand))
            if os.path.isfile(path) and path not in files:
                files.append(path)
                return

    for m in LOADBANK_RE.finditer(doc_text):
        add(m.group(1).strip())
    for m in IMPORT_RE.finditer(doc_text):
        add(m.group(1).strip())

    sibling = os.path.normpath(os.path.join(base, "bank.tex"))
    if os.path.isfile(sibling) and sibling not in files:
        files.append(sibling)
    return files


def parse_meta(attrs):
    """Comma-split ``key=val`` list; split on the first ``=``; trim; drop
    tokens without ``=`` (mirrors problem_engine.lua parse_meta)."""
    meta = {}
    for pair in attrs.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            meta[k.strip()] = v.strip()
    return meta


def _find_env(s, env):
    """First ``\\begin{env}[opts]..\\end{env}`` in s.

    Returns (start, inner, end_after, opts) where start indexes ``\\begin``,
    inner is the text between the tags, end_after indexes just past ``\\end{env}``,
    and opts is the bracketed option string (without brackets).  None if absent.
    Real banks do not nest solution/choices in themselves, so first-begin /
    next-matching-end is sufficient (the engine's brace-depth guard covers
    pathological cases we don't expect here).
    """
    bpat = re.compile(r"\\begin\s*\{" + re.escape(env) + r"\}(\s*\[[^\]]*\])?")
    epat = re.compile(r"\\end\s*\{" + re.escape(env) + r"\}")
    bm = bpat.search(s)
    if not bm:
        return None
    em = epat.search(s, bm.end())
    if not em:
        return None
    opts = ""
    if bm.group(1):
        opts = bm.group(1).strip()[1:-1].strip()
    return (bm.start(), s[bm.end():em.start()], em.end(), opts)


def parse_choices(raw):
    """Parse a choices block's inner text into option dicts.

    \\cchoice -> correct, \\choice -> distractor, \\fchoice -> forced.  Each
    item's text runs to the next marker.  An \\fchoice may carry an optional
    ``[i]`` slot index, ignored for display.
    """
    items = []
    if not raw:
        return items
    marks = list(CHOICE_RE.finditer(raw))
    for i, m in enumerate(marks):
        kind = m.group(1)
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
        items.append({
            "kind": kind,
            "correct": kind == "cchoice",
            "text": raw[start:end].strip(),
        })
    return items


def _split_body(body):
    """Split a comment-stripped problem body into
    (stem, choices_items, choices_env, solution, is_mc)."""
    solution = ""
    content = body
    sol = _find_env(body, "solution")
    if sol:
        solution = sol[1].strip()
        content = body[:sol[0]] + body[sol[2]:]

    cenv = None
    ch = _find_env(content, "choices")
    if ch:
        cenv = "choices"
    else:
        ch = _find_env(content, "oneparchoices")
        if ch:
            cenv = "oneparchoices"

    stem = content
    choices = []
    is_mc = False
    if ch:
        is_mc = True
        choices = parse_choices(ch[1])
        stem = content[:ch[0]] + content[ch[2]:]

    return stem.strip(), choices, cenv, solution, is_mc


def _to_plain(tex):
    """Rough plaintext of a stem for search/quick display: drop the common
    math/markup noise so a topic search matches readable words."""
    s = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", tex)
    s = re.sub(r"\\[a-zA-Z@]+\*?", " ", s)      # control sequences
    s = re.sub(r"[\\${}\[\]^_&~]", " ", s)      # stray math/format chars
    return re.sub(r"\s+", " ", s).strip()


class Problem:
    """One parsed bank problem."""

    def __init__(self, pid, attrs, source_file, line, raw, body):
        self.id = pid
        self.attrs = attrs
        self.meta = parse_meta(attrs)
        self.meta.setdefault("id", pid)
        self.source_file = source_file
        self.line = line              # 0-based, like the plugin scanner
        self.raw = raw                # verbatim \begin{problem}..\end{problem}

        stem, choices, cenv, solution, is_mc = _split_body(strip_comments(body))
        self.stem = stem
        self.choices = choices
        self.choices_env = cenv
        self.solution = solution
        self.is_mc = is_mc

        pts = [int(x) for x in PART_PTS_RE.findall(stem)]
        self.points = sum(pts) if pts else None
        self.part_points = pts

    @property
    def topic(self):
        return self.meta.get("topic", "")

    @property
    def section(self):
        return self.meta.get("section", "")

    @property
    def source(self):
        return self.meta.get("source", "")

    def to_dict(self):
        return {
            "id": self.id,
            "type": "mc" if self.is_mc else "fr",
            "meta": self.meta,
            "topic": self.topic,
            "section": self.section,
            "source": self.source,
            "points": self.points,
            "part_points": self.part_points,
            "stem_tex": self.stem,
            "choices": self.choices,
            "solution_tex": self.solution,
            "raw": self.raw,
            "preview": _to_plain(self.stem)[:240],
            "source_file": self.source_file,
            "line": self.line,
        }


def scan_problems(files):
    """Parse every ``\\begin{problem}`` in the given files.  First definition of
    an id wins (later duplicates are recorded on the winner's ``duplicate``
    flag), mirroring how a reader would treat a re-used id as a warning."""
    out = []
    by_id = {}
    for path in files:
        text = _read(path)
        if text is None:
            continue
        for m in PROBLEM_RE.finditer(text):
            end = PROBLEM_END_RE.search(text, m.end())
            if not end:
                continue
            pid = m.group(1).strip()
            attrs = (m.group(2) or "").strip()
            raw = text[m.start():end.end()]
            body = text[m.end():end.start()]
            line = text.count("\n", 0, m.start())
            if pid in by_id:
                by_id[pid].duplicate = True
                continue
            p = Problem(pid, attrs, path, line, raw, body)
            p.duplicate = False
            by_id[pid] = p
            out.append(p)
    return out


def discover(exam_path):
    """Convenience for the server/CLI: resolve the bank behind an exam file and
    return (sources, [Problem, ...])."""
    text = _read(exam_path)
    if text is None:
        raise FileNotFoundError(exam_path)
    root, root_text = resolve_root(os.path.abspath(exam_path), text)
    sources = problem_sources(root, root_text)
    return sources, scan_problems(sources)


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        sys.exit("usage: python bank_parser.py <exam-or-bank.tex>")
    srcs, probs = discover(sys.argv[1])
    print("# sources:", *srcs, sep="\n#   ")
    print(json.dumps([p.to_dict() for p in probs], indent=2))
