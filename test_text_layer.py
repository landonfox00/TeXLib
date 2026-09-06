#!/usr/bin/env python3
"""
Text-layer fidelity gate: what a document SETS must be what the PDF SAYS.

Every other check in this repo looks at the page (visual refs), the structure
(PDF/UA tags, veraPDF) or a handful of expected substrings. None of them looks
at whether a non-ASCII character survives the trip from .tex source to PDF text
layer. That gap hid a live text-corruption bug for the lifetime of the library:

    texlib-corepkg loaded [T1]{fontenc} + lmodern for every engine. Under
    pdfTeX that is correct -- inputenc translates a literal "\u00a7" to
    \\textsection and T1 slot 0x9F is set. Under LuaTeX there IS no UTF-8 ->
    LICR layer (\\DeclareUnicodeCharacter is not even defined), so the literal
    character is handed to the 8-bit font as its codepoint. U+00A7 becomes T1
    slot 0xA7, which is `gbreve', and the document silently typesets "\u011f".
    Characters above U+00FF have no slot at all and were dropped outright.

A 139-character probe scored 79 wrong under lualatex and 0 under pdflatex. None
of it was visible without reading the log or the PDF text layer -- and since the
accessible build FORCES lualatex for every class, the damage landed squarely on
the builds the accessibility program exists to protect.

The two halves of that failure need two different detectors, and this file is
the second one:

  * dropped characters leave a "Missing character" line in the log ->
    smoke_test.check_missing_glyphs, which runs on every build in the suite.
  * MIS-MAPPED characters leave no trace anywhere. The engine cheerfully sets
    the wrong glyph and reports nothing. Only a round trip catches them, which
    is what this file does.

Both engines are tested. pdfTeX is not merely along for the ride: the fix is a
conditional, so the pdfTeX branch is exactly the half a future edit is most
likely to break without noticing.

Usage:
    python test_text_layer.py          # both engines, both documents
    python test_text_layer.py -v       # list every probe result

Soft-skips (exit 0, with a printed reason) when the toolchain is absent, in
line with the rest of the harness: a missing pdftotext must not turn into a red
check on a machine that simply has no poppler.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smoke_test as S  # noqa: E402  (path set above)

# Windows consoles default to a codepage that cannot encode most of the probe
# set; printing a failing character would then raise UnicodeEncodeError and
# report a crash instead of the test result.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


# ---------------------------------------------------------------------------
# The probe set
# ---------------------------------------------------------------------------
# Deliberately curated, not exhaustive. Every entry is either a character that
# actually failed, or a control that must keep passing. Characters whose
# extraction is legitimately ambiguous are NOT here -- a gate that cries wolf
# gets switched off. Specifically excluded:
#
#   \u0132 / \u0133   ligatures; correctly extract as the two letters "IJ"/"ij"
#   \u2026            may extract as three periods
#   \u20ac \u00b5     TS1-only under pdfTeX; extraction varies by build
#
# GROUP A -- codepoint lands in the T1 upper half, so the 8-bit font silently
# set a DIFFERENT letter. These produced no warning of any kind.
GROUP_A = [
    ("\u00a7", "SECTION SIGN",            "set `gbreve' \u011f"),
    ("\u00a1", "INVERTED EXCLAMATION",    "set `aogonek' \u0105"),
    ("\u00bf", "INVERTED QUESTION",       "set `pound' \u00a3"),
    ("\u00a3", "POUND SIGN",              "set `ccaron' \u010d"),
    ("\u00ab", "LEFT GUILLEMET",          "set `nacute' \u0144"),
    ("\u00bb", "RIGHT GUILLEMET",         "set `zdotaccent' \u017c"),
    ("\u00df", "SHARP S",                 "set the digraph \"SS\""),
    ("\u00ff", "Y WITH DIAERESIS",        "set `germandbls' \u00df"),
    ("\u00d7", "MULTIPLICATION SIGN",     "set the OE ligature \u0152"),
    ("\u00f7", "DIVISION SIGN",           "set the oe ligature \u0153"),
]

# GROUP B -- above U+00FF, so the 8-bit font had no slot and the character was
# dropped from the page entirely.
GROUP_B = [
    ("\u0141", "L WITH STROKE",           "dropped"),
    ("\u0142", "l with stroke",           "dropped"),
    ("\u0159", "r with caron",            "dropped"),
    ("\u0161", "s with caron",            "dropped"),
    ("\u017e", "z with caron",            "dropped"),
    ("\u0151", "o with double acute",     "dropped"),
    ("\u0119", "e with ogonek",           "dropped"),
    ("\u0106", "C WITH ACUTE",            "dropped"),
    ("\u0111", "d with stroke",           "dropped"),
    ("\u0131", "DOTLESS I",               "dropped"),
    ("\u2013", "EN DASH",                 "dropped"),
    ("\u2014", "EM DASH",                 "dropped"),
    ("\u201c", "LEFT DOUBLE QUOTE",       "dropped"),
    ("\u201d", "RIGHT DOUBLE QUOTE",      "dropped"),
    ("\u2018", "LEFT SINGLE QUOTE",       "dropped"),
    ("\u2019", "RIGHT SINGLE QUOTE",      "dropped"),
    ("\u201e", "DOUBLE LOW-9 QUOTE",      "dropped"),
]

# GROUP C -- the control group. U+00C0..U+00FF (minus the four T1 reassigns
# above) coincide with their T1 slots, so these passed even while the bundle was
# broken. They are here to prove a future "fix" did not trade one set of
# characters for another.
GROUP_C = [
    ("\u00e9", "e acute",                 "control"),
    ("\u00fc", "u diaeresis",             "control"),
    ("\u00f1", "n tilde",                 "control"),
    ("\u00e5", "a ring",                  "control"),
    ("\u00f8", "o stroke",                "control"),
    ("\u00c6", "AE",                      "control"),
    ("\u00e7", "c cedilla",               "control"),
    ("\u00d1", "N tilde",                 "control"),
]

PROBES = GROUP_A + GROUP_B + GROUP_C


# ---------------------------------------------------------------------------
# Documents under test
# ---------------------------------------------------------------------------
# Two entry points, because they are two different risks. The bundle test pins
# texlib-corepkg itself; the class test proves no class re-breaks it downstream
# (a class loading its own fontenc after the bundle would).
#
# didactic reaches the bundle via basic-utilities -> texlib-utilities; the
# assessment classes (quiz, autoexam, bank) reach the SAME bundle via
# texlib-assessment, so the bundle case covers their font setup too.
DOCS = {
    "corepkg": (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage{texlib-corepkg}\n"
        "\\pagestyle{empty}\n"
    ),
    "didactic": (
        "\\documentclass[unit=Lecture, number=1, title=Text layer probe]"
        "{texlib-didactic}\n"
    ),
}

# "PRB07 <char> ZEND" -- a tag that cannot occur in the surrounding text, and a
# terminator so a dropped character reads as an empty match rather than running
# into the next line. \texttt keeps the tag in a font whose ASCII is never in
# question, and ~ ties stop the probe from starting or ending a line.
_MARK_RE = re.compile(r"PRB(\d{2})\s*(.*?)\s*ZEND", re.S)


def make_document(preamble: str) -> str:
    lines = [preamble, "\\begin{document}", "\\noindent"]
    for i, (ch, _name, _was) in enumerate(PROBES):
        lines.append("\\texttt{PRB%02d}~%s~ZEND\\par" % (i, ch))
    lines.append("\\end{document}")
    return "\n".join(lines) + "\n"


def build_and_extract(doc_key: str, engine: str, tmp_root: str,
                      verbose: bool) -> tuple[list[str], dict[int, str]]:
    """
    Build one probe document with one engine and extract its text layer.
    Returns (problems, {probe index -> extracted string}).
    """
    tmp = tempfile.mkdtemp(prefix=f"texlib_textlayer_{doc_key}_{engine}_",
                           dir=tmp_root)
    # Copy the library in the same way smoke_test does. A TEXINPUTS entry
    # containing a comma is silently unsearchable by kpathsea, and the TeXLib
    # root really can live under one (a OneDrive folder named "...Nevada,
    # Reno..."), so the cwd copy -- not TEXINPUTS -- is what makes this work.
    S._copy_shared_into(tmp)
    coursemeta = os.path.join(tmp, "coursemeta.tex")
    if not os.path.exists(coursemeta):
        with open(coursemeta, "w", encoding="utf-8") as f:
            f.write(S.STUB_COURSEMETA)

    name = "probe"
    src = os.path.join(tmp, name + ".tex")
    with open(src, "w", encoding="utf-8") as f:
        f.write(make_document(DOCS[doc_key]))

    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    env["TEXINPUTS"] = f".{sep}{S.TEXLIB_ROOT}//{sep}{env.get('TEXINPUTS', '')}"

    try:
        r = subprocess.run(
            [engine, "-interaction=nonstopmode", "-halt-on-error", name + ".tex"],
            cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"build failed to run: {exc}"], {}

    log_path = os.path.join(tmp, name + ".log")
    log_text = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log_text = f.read()

    pdf = os.path.join(tmp, name + ".pdf")
    if r.returncode != 0 or not os.path.exists(pdf):
        err = S.extract_tex_errors(log_text or r.stdout) or f"exit={r.returncode}"
        return [f"build failed: {err}"], {}

    # A dropped glyph is the other half of this bug and it IS logged, so assert
    # it here too: this document is the one place we know exactly which
    # characters were requested.
    problems = S.check_missing_glyphs(log_text)

    text = S.extract_pdf_text(pdf)
    if text is None:
        return problems, {}

    got = {int(m.group(1)): m.group(2).strip() for m in _MARK_RE.finditer(text)}
    return problems, got


def describe(s: str) -> str:
    """Render an extracted value as codepoints + names, never as raw glyphs."""
    if s == "":
        return "(nothing -- character dropped from the page)"
    return " ".join("U+%04X %s" % (ord(c), unicodedata.name(c, "?")) for c in s)


def run_case(doc_key: str, engine: str, tmp_root: str, verbose: bool) -> list[str]:
    problems, got = build_and_extract(doc_key, engine, tmp_root, verbose)
    label = f"{doc_key}/{engine}"
    if problems and not got:
        return [f"{label}: {p}" for p in problems]

    out = [f"{label}: {p}" for p in problems]
    if not got:
        return out + [f"{label}: no probes found in the extracted text "
                      "(pdftotext returned nothing usable)"]

    missing_probes = [i for i in range(len(PROBES)) if i not in got]
    if missing_probes:
        out.append(f"{label}: {len(missing_probes)} probe marker(s) not found "
                   f"in the text layer (indices {missing_probes[:8]})")

    for i, (ch, name, was) in enumerate(PROBES):
        if i not in got:
            continue
        val = got[i]
        if val == ch:
            if verbose:
                print(f"    ok   PRB{i:02d} U+{ord(ch):04X} {name}")
            continue
        out.append(
            f"{label}: PRB{i:02d} {name} -- set U+{ord(ch):04X}, "
            f"extracted {describe(val)}  [before the fix: {was}]")
    return out


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    if not S.PDFTOTEXT:
        print("SKIP: pdftotext not found on PATH -- the text layer cannot be read.")
        return 0

    engines = [e for e in ("lualatex", "pdflatex") if shutil.which(e)]
    if not engines:
        print("SKIP: neither lualatex nor pdflatex found on PATH.")
        return 0
    if len(engines) == 1:
        print(f"NOTE: only {engines[0]} available; the other engine's branch of "
              "the corepkg font conditional is NOT covered by this run.")

    print(f"Text-layer round trip: {len(PROBES)} probes x {len(DOCS)} documents "
          f"x {len(engines)} engine(s)")

    failures: list[str] = []
    tmp_root = tempfile.mkdtemp(prefix="texlib_textlayer_")
    try:
        for doc_key in DOCS:
            for engine in engines:
                probs = run_case(doc_key, engine, tmp_root, verbose)
                status = "FAIL" if probs else "pass"
                print(f"  [{status}] {doc_key} / {engine}")
                failures += probs
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        print("\nA mis-mapped character means the PDF's text layer disagrees with "
              "the page: copy-paste, screen readers and PDF/UA extraction all get "
              "the wrong character. See the font block in texlib-corepkg.sty.")
        return 1

    print("\nAll probes round-tripped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
