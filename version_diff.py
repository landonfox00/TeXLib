#!/usr/bin/env python3
r"""version_diff.py -- verify a multi-version exam's versions actually DIFFER.

A `\versions{A,B,...}` autoexam that forgets `\shuffle` (or whose per-version
seeding silently collapses) ships identical copies under different labels -- a
proctoring failure that no build error catches. This standalone CLI (no Sublime)
builds each version on its own (via the class's `\def\Version{<V>}` forced-single
compile), extracts each version's text, and reports the pairwise similarity so
near-identical versions surface loudly.

Usage:
    python version_diff.py Exams/exam.tex
    python version_diff.py Exams/exam.tex --threshold 0.97
    python version_diff.py Exams/exam.tex --engine lualatex
"""
import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys

VERSIONS_RE = re.compile(r"\\versions\{([^}]*)\}")


def parse_versions(tex_text):
    """The version labels from \\versions{A,B,...} (stripped, in order)."""
    m = VERSIONS_RE.search(tex_text)
    if not m:
        return []
    return [v.strip() for v in m.group(1).split(",") if v.strip()]


def normalize(text):
    """Content-focused normalization for comparison: drop the page-number line
    noise ('N of M', bare page numbers) and collapse whitespace, so two versions
    are compared on their problem content, not identical furniture."""
    text = re.sub(r"(?im)^\s*\d+\s+of\s+\d+\s*$", "", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compare(texts_by_version, threshold=0.98):
    """texts_by_version: {label: normalized_text}. Returns a report dict with the
    pairwise similarity ratios and the pairs at/above `threshold` (too similar --
    likely identical versions)."""
    labels = list(texts_by_version)
    pairs = []
    too_similar = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            ratio = difflib.SequenceMatcher(
                None, texts_by_version[a], texts_by_version[b]).ratio()
            pairs.append((a, b, ratio))
            if ratio >= threshold:
                too_similar.append((a, b, ratio))
    return {"pairs": pairs, "too_similar": too_similar, "threshold": threshold}


def render_report(rep):
    L = ["TeXLib version-diff", "=" * 40, ""]
    for a, b, r in rep["pairs"]:
        flag = "  <-- TOO SIMILAR" if r >= rep["threshold"] else ""
        L.append("  %s vs %s : %.3f%s" % (a, b, r, flag))
    L.append("")
    if rep["too_similar"]:
        L.append("VERDICT: %d version pair(s) are >= %.2f similar -- likely "
                 "identical (missing \\shuffle or a seed collapse)."
                 % (len(rep["too_similar"]), rep["threshold"]))
    else:
        L.append("VERDICT: all versions differ. OK.")
    return "\n".join(L)


def build_version(tex_path, version, engine):
    """Build one forced version (\\def\\Version{<v>}) and return its pdftotext, or
    (None, err). Builds in the document's own directory (so coursemeta + banks
    resolve) with the ambient TeX environment. autoexam reads the document body
    from \\jobname.tex, so the jobname must stay the source basename; the output is
    routed to a temp dir with -output-directory so the user's real <base>.pdf is
    never clobbered (each version would otherwise overwrite it)."""
    import tempfile
    tex_dir = os.path.dirname(os.path.abspath(tex_path)) or "."
    name = os.path.basename(tex_path)
    base = os.path.splitext(name)[0]
    pt = _poppler_pdftotext()
    if not pt:
        return None, "no poppler pdftotext"
    outdir = tempfile.mkdtemp(prefix="vdiff_%s_" % version)
    try:
        arg = r"\def\Version{%s}\input{%s}" % (version, name)
        cmd = [engine, "-interaction=nonstopmode", "-halt-on-error",
               "-output-directory=" + outdir, "-jobname=" + base]
        if engine in ("lualatex", "xelatex"):
            cmd.append("-shell-escape")
        cmd.append(arg)
        try:
            for _ in range(2):
                subprocess.run(cmd, cwd=tex_dir, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=240)
        except (OSError, subprocess.SubprocessError) as exc:
            return None, str(exc)
        pdf = os.path.join(outdir, base + ".pdf")
        if not os.path.exists(pdf):
            return None, "no PDF for version %s" % version
        txt = subprocess.run([pt, "-layout", pdf, "-"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout
        return normalize(txt), ""
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


def _poppler_pdftotext():
    for cand in (shutil.which("pdftotext"),
                 r"C:\texlive\2025\bin\windows\pdftotext.exe"):
        if not cand:
            continue
        try:
            p = subprocess.run([cand, "-v"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if "poppler" in ((p.stdout or "") + (p.stderr or "")).lower():
            return cand
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a multi-version exam's versions differ.")
    ap.add_argument("tex", help="the autoexam .tex with \\versions{...}")
    ap.add_argument("--threshold", type=float, default=0.98,
                    help="similarity at/above which a pair is flagged (default 0.98)")
    ap.add_argument("--engine", default="lualatex", help="TeX engine (default lualatex)")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.tex):
        print("version_diff: no such file: %s" % args.tex, file=sys.stderr)
        return 2
    with open(args.tex, encoding="utf-8", errors="replace") as fh:
        versions = parse_versions(fh.read())
    if len(versions) < 2:
        print("version_diff: need >=2 \\versions to compare (found %d)." % len(versions),
              file=sys.stderr)
        return 1
    texts = {}
    for v in versions:
        print("building version %s ..." % v, file=sys.stderr)
        txt, err = build_version(args.tex, v, args.engine)
        if txt is None:
            print("version_diff: build failed for %s: %s" % (v, err), file=sys.stderr)
            return 1
        texts[v] = txt
    rep = compare(texts, args.threshold)
    print(render_report(rep))
    return 1 if rep["too_similar"] else 0


if __name__ == "__main__":
    sys.exit(main())
