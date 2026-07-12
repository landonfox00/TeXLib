#!/usr/bin/env python3
r"""collate_keys.py -- merge per-version answer keys into one PDF.

A normal autoexam build slices a multi-version exam into <base>_A.pdf,
<base>_A_solutions.pdf, <base>_B_solutions.pdf, ... (one answer key per version).
When proctoring several versions it is handy to have ALL the keys in a single
bookmarked PDF. This standalone CLI (no Sublime, no TeX) finds the per-version
key slices next to a base PDF and concatenates them, with one outline bookmark
per version.

Usage:
    python collate_keys.py Exams/exam-01.pdf         # -> exam-01_AllKeys.pdf
    python collate_keys.py Exams/exam-01.pdf -o keys.pdf
    python collate_keys.py Exams/exam-01.pdf --versions   # collate <base>_<V>.pdf too
"""
import argparse
import os
import re
import sys


def discover(names, base, versions_too=False):
    """From a list of file names, return (label, name) pairs for the per-version
    answer-key slices of `base`, sorted by label. Matches <base>_<label>_solutions
    .pdf (and, with versions_too, <base>_<label>.pdf that has no _solutions twin).
    Pure -- takes names, returns a plan; no disk access."""
    key_re = re.compile(r"^%s_(.+)_solutions\.pdf$" % re.escape(base))
    keys = {}
    for n in names:
        m = key_re.match(n)
        if m:
            keys[m.group(1)] = n
    if versions_too:
        ver_re = re.compile(r"^%s_([^_]+)\.pdf$" % re.escape(base))
        for n in names:
            m = ver_re.match(n)
            # only a plain version with no dedicated _solutions slice
            if m and m.group(1) not in keys and not n.endswith("_solutions.pdf"):
                keys.setdefault(m.group(1), n)
    return sorted(keys.items())


def collate(paths_with_labels, out_path):
    """Concatenate the given (label, path) PDFs into out_path, one bookmark per
    label. Returns the number of source PDFs merged. Needs pypdf."""
    try:
        from pypdf import PdfWriter
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit("collate_keys: pypdf is required (pip install pypdf): %s"
                         % exc)
    writer = PdfWriter()
    for label, path in paths_with_labels:
        start = len(writer.pages)
        writer.append(path)
        writer.add_outline_item("Version %s" % label, start)
    with open(out_path, "wb") as fh:
        writer.write(fh)
    writer.close()
    return len(paths_with_labels)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge per-version answer keys into one PDF.")
    ap.add_argument("base_pdf", help="the combined <base>.pdf (the key slices sit next to it)")
    ap.add_argument("-o", "--output", help="output path (default <base>_AllKeys.pdf)")
    ap.add_argument("--versions", action="store_true",
                    help="also include <base>_<V>.pdf versions lacking a _solutions slice")
    args = ap.parse_args(argv)

    d = os.path.dirname(os.path.abspath(args.base_pdf))
    base = os.path.splitext(os.path.basename(args.base_pdf))[0]
    names = os.listdir(d) if os.path.isdir(d) else []
    plan = discover(names, base, versions_too=args.versions)
    if not plan:
        print("collate_keys: no per-version key slices (%s_*_solutions.pdf) next to %s"
              % (base, args.base_pdf), file=sys.stderr)
        return 1
    out = args.output or os.path.join(d, base + "_AllKeys.pdf")
    n = collate([(lbl, os.path.join(d, name)) for lbl, name in plan], out)
    print("collate_keys: merged %d key(s) [%s] -> %s"
          % (n, ", ".join(lbl for lbl, _ in plan), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
