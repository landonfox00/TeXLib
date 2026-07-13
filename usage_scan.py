"""usage_scan.py -- where has each bank problem been used before?

Scans the sibling assessment files in a course directory for references to each
problem, so Bank Studio can flag what a student may have already seen (or what
you're intentionally recycling).  A reference is either by **id**
(``\\problem{lim-poly-factor}``, ``\\getproblem{lim-poly-factor}``, ...) or by
**topic filter** (``\\problem{topic=limit}``) matching the problem's own topic.

Definitions (``\\begin{problem}{id}``) are not references -- the ``\\problem``
retrieval token never appears inside ``\\begin{problem}`` -- and the bank
source files and the exam currently open are excluded by the caller.
"""

import glob
import os
import re

from bank_parser import parse_meta, strip_comments

# \problem / \getproblem / \useproblem / \reqproblem {arg}.  \b after the name
# so \problems (the environment) and \importproblem are not matched.
USE_RE = re.compile(
    r"\\(?:problem|getproblem|useproblem|reqproblem)\b\s*(?:\[[^\]]*\])*\s*\{([^}]*)\}")


def uses_in(text):
    """Every problem-retrieval argument (id or filter string) in a document."""
    return [m.group(1).strip() for m in USE_RE.finditer(strip_comments(text))]


def scan(course_dir, problems, exclude_paths):
    """Return {problem_id: [{"file": basename, "by": "id"|"topic"}, ...]}.

    Scans ``*.tex`` in `course_dir` except `exclude_paths` (the bank sources and
    the current exam).  An id reference wins over a topic reference for the same
    file.
    """
    exclude = {os.path.abspath(p) for p in exclude_paths}
    file_uses = {}
    for f in glob.glob(os.path.join(course_dir, "*.tex")):
        if os.path.abspath(f) in exclude:
            continue
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                file_uses[os.path.basename(f)] = uses_in(fh.read())
        except OSError:
            pass

    result = {}
    for p in problems:
        hits = []
        for fname, args in file_uses.items():
            by = None
            for arg in args:
                if arg == p.id:
                    by = "id"
                    break
                if p.topic and "=" in arg and parse_meta(arg).get("topic") == p.topic:
                    by = "topic"
            if by:
                hits.append({"file": fname, "by": by})
        result[p.id] = hits
    return result
