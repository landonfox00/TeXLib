#!/usr/bin/env python3
"""
package_for_lms.py -- zip a course's shareable PDFs into one LMS-upload bundle.

Companion to the builder's publish step (see \\TeXLibDeclarePublishable in
course-metadata.sty and _publish_shareable_copies in Sublime/texlib_builder.py).
Once you have built the syllabus and schedule, each drops a generically named
copy next to its source -- "Syllabus.pdf" and "Tentative Schedule.pdf". This
script collects those (anywhere under the course root) and zips them into
<Course>_<Term>_LMS.zip, ready to attach to a WebCampus / Canvas page.

The course root is the directory holding coursemeta.tex, discovered by walking
up from the given path (default: the current directory). Course / term for the
zip name are read from coursemeta.tex.

Usage:
    python package_for_lms.py                     # course of the current dir
    python package_for_lms.py examples/Math181-Fall2026
    python package_for_lms.py Syllabi/syllabus.tex        # a file in a course
    python package_for_lms.py -o ~/Desktop/M181.zip .     # custom output path
    python package_for_lms.py --list .                    # show what would go in

Exit code: 0 on success, 1 if no course root or no shareable PDFs were found.
"""

import argparse
import os
import re
import sys
import zipfile

# The generic published copy names the builder emits (the \TeXLibDeclarePublishable
# <generic> for syllabus and schedule). Matched case-insensitively.
SHAREABLE_NAMES = ("Syllabus.pdf", "Tentative Schedule.pdf")

# How far up to walk looking for coursemeta.tex (mirrors course-metadata.sty's
# ., .., ../.., ../../.. search depth, plus a little headroom).
MAX_WALK_UP = 5


def find_course_root(start):
    """Return the nearest ancestor directory (including `start`) that contains a
    coursemeta.tex, or None. `start` may be a file or a directory."""
    d = os.path.abspath(start)
    if os.path.isfile(d):
        d = os.path.dirname(d)
    for _ in range(MAX_WALK_UP + 1):
        if os.path.isfile(os.path.join(d, "coursemeta.tex")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _strip_tex_comments(text):
    """Drop TeX line comments (an unescaped % to end of line)."""
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def _meta_value(body, key):
    """Pull a single metadata value for `key` from a \\metasetup body. Handles
    both braced ({Calculus I}) and bare (181) values; returns '' if unset."""
    m = re.search(
        r"(?<![\w-])" + re.escape(key) + r"\s*=\s*(?:\{([^{}]*)\}|([^,}\n]*))",
        body,
    )
    if not m:
        return ""
    val = m.group(1) if m.group(1) is not None else m.group(2)
    return (val or "").strip()


def parse_coursemeta(path):
    """Read coursemeta.tex into the subset of fields we need for the zip name."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return {}
    body = _strip_tex_comments(raw)
    keys = ("course-subject", "course-number", "course-section",
            "season", "year", "term")
    return {k: _meta_value(body, k) for k in keys}


def course_term_tokens(meta):
    """(<Course>, <Term>) filename tokens with whitespace stripped, mirroring the
    builder's coded-name derivation: Course = subject+number, Term = an explicit
    `term` else season+year. Either may be '' when its inputs are unset."""
    subject = re.sub(r"\s+", "", meta.get("course-subject", ""))
    number = re.sub(r"\s+", "", meta.get("course-number", ""))
    course = subject + number
    term = meta.get("term", "").strip()
    if not term:
        term = meta.get("season", "").strip() + meta.get("year", "").strip()
    term = re.sub(r"\s+", "", term)
    return course, term


def find_shareables(root, names=SHAREABLE_NAMES):
    """Collect files under `root` whose basename matches one of `names`
    (case-insensitive). One path per distinct target name (first match wins, in a
    stable walk order), so a stray copy deeper in the tree can't duplicate it."""
    wanted = {n.lower(): None for n in names}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            key = fn.lower()
            if key in wanted and wanted[key] is None:
                wanted[key] = os.path.join(dirpath, fn)
    return [p for p in wanted.values() if p]


def make_zip(paths, out_path):
    """Zip `paths` (flat, stored by basename) into out_path. Returns the arcnames
    written."""
    written = []
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            arc = os.path.basename(p)
            zf.write(p, arcname=arc)
            written.append(arc)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Zip a course's shareable PDFs for LMS upload.")
    ap.add_argument("path", nargs="?", default=".",
                    help="a course directory or a file in one (default: .)")
    ap.add_argument("-o", "--output", default=None,
                    help="zip path (default: <root>/<Course>_<Term>_LMS.zip)")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="list the shareable PDFs that would be bundled, then exit")
    args = ap.parse_args(argv)

    root = find_course_root(args.path)
    if not root:
        print(f"package_for_lms: no coursemeta.tex found at or above "
              f"{os.path.abspath(args.path)!r} (looked up {MAX_WALK_UP} levels).",
              file=sys.stderr)
        return 1

    shareables = find_shareables(root)
    if not shareables:
        print(f"package_for_lms: no shareable PDFs "
              f"({' / '.join(SHAREABLE_NAMES)}) found under {root!r}.\n"
              f"  Build the syllabus and schedule first -- the builder's publish "
              f"step writes those generic copies.", file=sys.stderr)
        return 1

    if args.list_only:
        print(f"Course root: {root}")
        for p in shareables:
            print(f"  {os.path.relpath(p, root)}")
        return 0

    meta = parse_coursemeta(os.path.join(root, "coursemeta.tex"))
    course, term = course_term_tokens(meta)
    stem = "_".join(t for t in (course, term) if t) or os.path.basename(root)
    out_path = args.output or os.path.join(root, f"{stem}_LMS.zip")

    written = make_zip(shareables, out_path)
    print(f"Wrote {out_path}")
    for arc in written:
        print(f"  + {arc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
