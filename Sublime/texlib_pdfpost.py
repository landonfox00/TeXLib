#!/usr/bin/env python3
"""
pypdf-dependent PDF post-processing for the TeXLib builder, in one place.

Two build steps need pypdf: slicing one combined multi-copy exam PDF into a PDF
per version/solutions copy (from a <base>.vmap sidecar), and splitting a
combined exam+solutions PDF in two (from a <base>.spl 'split_page=N' signal).

Why a standalone module: Sublime Text's embedded Python (plugin_host, 3.8) has
no site-packages, so `import pypdf` fails there -- under a real Ctrl+B build the
post-processing silently did nothing, even though it worked from the CLI test
harness (which runs under the system Python, where pypdf is installed).
texlib_builder imports these functions in-process when pypdf is importable and
otherwise runs this file as a script under an external Python that has it. One
implementation, invoked two ways -- no logic drift.

CLI (used by the external-Python fallback):
    python texlib_pdfpost.py slice <vmap> <pdf> <out_dir> <base_name>
    python texlib_pdfpost.py split <spl>  <pdf> <out_dir> <base_name>
On success it writes one JSON object to stdout: {"produced": [...],
"messages": [...]}.  Exit code 3 means pypdf is unavailable even here, so the
caller can print an actionable "install pypdf" message instead of a generic
failure.
"""

from __future__ import annotations

import json
import os
import sys

# Distinct exit code so the builder can tell "the external Python also lacks
# pypdf" apart from an ordinary crash and give a precise message.
PYPDF_MISSING_EXIT = 3


def _force_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def slice_from_vmap(vmap_path, pdf_path, out_dir, base_name):
    """Slice a combined multi-copy PDF into one PDF per version/solutions copy.

    Each .vmap line is "version|stu-or-sol|start_page" in typeset order (version
    may be empty when the document declares no \\versions). A record's last page
    is one before the next record's start, or the PDF's real last page for the
    final record.  Returns {"produced": [names], "messages": [strings]}; does
    NOT delete the .vmap (the caller removes it on every outcome).  Raises
    ImportError if pypdf is unavailable.
    """
    from pypdf import PdfReader, PdfWriter

    produced, messages = [], []
    records = []
    with open(vmap_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != 3:
                continue
            ver, sol, start = parts
            try:
                records.append((ver, sol == "sol", int(start)))
            except ValueError:
                continue
    if not records:
        return {"produced": produced, "messages": messages}

    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    base_pdf_name = os.path.basename(pdf_path)
    for i, (ver, is_sol, start) in enumerate(records):
        # Clamp to the PDF's real length: a later record's declared start (used
        # as this record's end + 1) is untrusted sidecar data, not a guarantee
        # about this PDF. Clamping lets an earlier, valid record still slice
        # even if a later one is bogus/out of range.
        end = records[i + 1][2] - 1 if i + 1 < len(records) else total
        end = min(end, total)
        if not (1 <= start <= end):
            messages.append(
                "TeXLib: .vmap record {}/{} ({}-{}) out of range for a "
                "{}-page PDF; skipping.".format(
                    ver or "(none)", "sol" if is_sol else "stu",
                    start, end, total))
            continue
        suffix = "_solutions" if is_sol else ""
        ver_part = "_{}".format(ver) if ver else ""
        out_name = "{}{}{}.pdf".format(base_name, ver_part, suffix)
        if out_name == base_pdf_name:
            # No version label AND not the solutions copy (a \solutions document
            # with no \versions): the student record's filename collides with
            # the combined PDF itself. Slicing here would overwrite it with a
            # subset of its own pages -- skip; it already IS this "slice".
            continue
        writer = PdfWriter()
        for p in range(start - 1, end):
            writer.add_page(reader.pages[p])
        out_path = os.path.join(out_dir, out_name)
        _force_remove(out_path)
        with open(out_path, "wb") as fh:
            writer.write(fh)
        produced.append(out_name)
    if produced:
        messages.append(
            "TeXLib: sliced per-version PDF(s) from the combined build: "
            + ", ".join(produced) + ".")
    return {"produced": produced, "messages": messages}


def split_from_spl(spl_path, pdf_path, out_dir, base_name):
    """Split a combined exam+solutions PDF at the .spl's 'split_page=N'.

    Returns {"produced": [names], "messages": [strings]}; does NOT delete the
    .spl (the caller removes it only when produced is non-empty, so an
    out-of-range split leaves the signal in place). Raises ImportError if pypdf
    is unavailable.
    """
    from pypdf import PdfReader, PdfWriter

    produced, messages = [], []
    with open(spl_path, "r", encoding="utf-8") as fh:
        content = fh.read().strip()
    if "split_page=" not in content:
        return {"produced": produced, "messages": messages}
    split_page = int(content.split("=", 1)[1].strip())

    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    if not (0 < split_page < total):
        messages.append(
            "TeXLib: .spl split_page={} out of range (PDF has {} pages); "
            "skipping split.".format(split_page, total))
        return {"produced": produced, "messages": messages}

    exam = PdfWriter()
    for i in range(split_page):
        exam.add_page(reader.pages[i])
    exam_name = base_name + "_Exam.pdf"
    with open(os.path.join(out_dir, exam_name), "wb") as fh:
        exam.write(fh)

    solutions = PdfWriter()
    for i in range(split_page, total):
        solutions.add_page(reader.pages[i])
    sol_name = base_name + "_Solutions.pdf"
    with open(os.path.join(out_dir, sol_name), "wb") as fh:
        solutions.write(fh)

    produced.extend([exam_name, sol_name])
    messages.append(
        "TeXLib: split into {}_Exam.pdf / _Solutions.pdf.".format(base_name))
    return {"produced": produced, "messages": messages}


_OPS = {"slice": slice_from_vmap, "split": split_from_spl}


def main(argv):
    if len(argv) != 5 or argv[0] not in _OPS:
        sys.stderr.write(
            "usage: texlib_pdfpost.py {slice|split} <sidecar> <pdf> "
            "<out_dir> <base_name>\n")
        return 2
    op, sidecar, pdf, out_dir, base = argv
    try:
        result = _OPS[op](sidecar, pdf, out_dir, base)
    except ImportError:
        return PYPDF_MISSING_EXIT
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
