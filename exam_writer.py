"""exam_writer.py -- add / remove / reorder problems in an exam .tex.

Standalone, stdlib-only, pure string manipulation (no TeX toolchain).  Bank
Studio's "add to exam" writes ``\\problem{id}`` (or ``\\problem{topic=...}``)
lines into the exam source: free-response problems go in ``\\begin{problems}``,
multiple-choice in ``\\begin{mcproblems}`` -- the same split the exam classes
expect (texlib-problembank.sty).  Either environment is created (after
``\\maketitle``, before ``\\end{document}``) when absent.

Entry indices are document-order (as returned by ``parse_exam``); the web app
uses them for remove/reorder.  Reorder swaps two adjacent siblings' ``\\problem``
text in place, preserving the surrounding layout.
"""

import re

ENV_FR = "problems"
ENV_MC = "mcproblems"

# \problem, optional [pts][stretch], {arg}.  arg is a bank id or a key=val filter.
PROBLEM_RE = re.compile(r"\\problem((?:\s*\[[^\]]*\])*)\s*\{([^}]*)\}")


def _env_span(text, env):
    """(begin_start, inner_start, inner_end, end_after) for the first
    ``\\begin{env}[*][opts]..\\end{env}``, or None."""
    bpat = re.compile(r"\\begin\s*\{" + re.escape(env) + r"\}\*?(?:\s*\[[^\]]*\])?")
    epat = re.compile(r"\\end\s*\{" + re.escape(env) + r"\}")
    bm = bpat.search(text)
    if not bm:
        return None
    em = epat.search(text, bm.end())
    if not em:
        return None
    return (bm.start(), bm.end(), em.start(), em.end())


def parse_exam(text):
    """Ordered problem entries across both environments.

    Each entry: {index, env ('fr'|'mc'), arg, is_filter, pts, start, end}
    where start/end bound the whole ``\\problem...{arg}`` match.
    """
    entries = []
    for env, kind in ((ENV_FR, "fr"), (ENV_MC, "mc")):
        span = _env_span(text, env)
        if not span:
            continue
        base = span[1]
        inner = text[span[1]:span[2]]
        for m in PROBLEM_RE.finditer(inner):
            arg = m.group(2).strip()
            entries.append({
                "env": kind,
                "arg": arg,
                "is_filter": "=" in arg,
                "pts": (m.group(1) or "").strip(),
                "start": base + m.start(),
                "end": base + m.end(),
            })
    entries.sort(key=lambda e: e["start"])
    for i, e in enumerate(entries):
        e["index"] = i
    return entries


def public_entries(text):
    """Entries trimmed to what the API returns (no byte offsets)."""
    return [{"index": e["index"], "env": e["env"], "arg": e["arg"],
             "is_filter": e["is_filter"], "pts": e["pts"]}
            for e in parse_exam(text)]


def _detect_indent(text):
    """Indentation used for existing \\problem lines, default one tab."""
    m = re.search(r"\n([ \t]+)\\problem\b", text)
    return m.group(1) if m else "\t"


def _new_env_block(env, line):
    return "\n\\begin{" + env + "}\n" + line + "\n\\end{" + env + "}\n"


def _insert_new_env(text, env, line):
    block = _new_env_block(env, line)
    if env == ENV_MC:
        fr = _env_span(text, ENV_FR)
        if fr:                                   # place MC after the FR block
            return text[:fr[3]] + "\n" + block + text[fr[3]:]
    mt = re.search(r"\\maketitle\b[^\n]*\n", text)
    if mt:
        return text[:mt.end()] + block + text[mt.end():]
    ed = re.search(r"\\end\s*\{document\}", text)
    if ed:
        return text[:ed.start()] + block + text[ed.start():]
    return text + block


def add_problem(text, arg, is_mc):
    """Append ``\\problem{arg}`` to the right environment, creating it if needed."""
    env = ENV_MC if is_mc else ENV_FR
    line = _detect_indent(text) + "\\problem{" + arg + "}"
    span = _env_span(text, env)
    if not span:
        return _insert_new_env(text, env, line)
    inner = text[span[1]:span[2]].rstrip("\n")
    return text[:span[1]] + inner + "\n" + line + "\n" + text[span[2]:]


def remove_problem(text, index):
    """Delete the entry at document-order `index` (whole line)."""
    entries = parse_exam(text)
    if not (0 <= index < len(entries)):
        return text
    e = entries[index]
    ls = text.rfind("\n", 0, e["start"]) + 1
    le = text.find("\n", e["end"])
    le = len(text) if le == -1 else le + 1
    return text[:ls] + text[le:]


def move_problem(text, index, direction):
    """Swap the entry at `index` with its neighbor in the same environment
    (direction -1 = earlier, +1 = later).  No-op at a boundary."""
    entries = parse_exam(text)
    if not (0 <= index < len(entries)):
        return text
    e = entries[index]
    sibs = [x for x in entries if x["env"] == e["env"]]
    pos = sibs.index(e)
    npos = pos + direction
    if not (0 <= npos < len(sibs)):
        return text
    f = sibs[npos]
    lo, hi = (e, f) if e["start"] < f["start"] else (f, e)
    lo_txt = text[lo["start"]:lo["end"]]
    hi_txt = text[hi["start"]:hi["end"]]
    text = text[:hi["start"]] + lo_txt + text[hi["end"]:]
    text = text[:lo["start"]] + hi_txt + text[lo["end"]:]
    return text


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("usage: python exam_writer.py <exam.tex>")
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        src = fh.read()
    for e in public_entries(src):
        tag = "MC" if e["env"] == "mc" else "FR"
        print(f"[{e['index']}] {tag} \\problem{{{e['arg']}}}")
