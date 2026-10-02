#!/usr/bin/env python3
r"""
End-to-end test of how the tagged half of an accessible build settles.

test_texlib_builder.py scripts the engine's output. This drives the REAL builder
coroutine against REAL pdflatex/lualatex, twice in a row from an empty
directory, on a document with the two properties that used to keep a tagged
build from ever settling:

  * it trips the luamml mathml-SE abort (two \sqrt[n]{...} in one formula), so
    every build runs a probe that dies after reopening the lane's .aux and .toc
    for writing;
  * it gains a page when its table of contents is first read, so a pass that
    starts without a .toc records one page fewer than the next pass ships.

What it asserts:

  * build 1, cold lane: the pass that gains the page is reported by the kernel,
    the builder runs one more, and the PDF it keeps has no duplicated
    parent-tree key and a table of contents that names the right pages;
  * build 2, straight after: the retry that follows the abort finds the .toc and
    the page count build 1 left, ships the settled page count on its first
    pass, and two passes are enough.

The document is a bare `article`. Neither property depends on a TeXLib class,
and an article needs no TEXINPUTS. The unfixed builder kept a 5-page PDF of it
with 29 failed checks of ISO 14289-2:2024 clause 8.2.2, all on page 5, on every
build. The `didactic` form of the same shape is
examples/fixtures/MathML/nth-root-toc.tex, which the smoke and accessible gates
build through their own harness.

Soft-skips with exit 0 when pdflatex or lualatex is absent. pypdf, poppler's
pdftotext and veraPDF are each optional: the checks that need one are skipped
without it, and the kernel-message and pass-count checks need none of them.

Run:  python test_accessible_settle_integration.py   (exit code: 0 ok/skipped)
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

# --- Refuse to run inside Sublime (same guard as test_texlib_builder.py) -----
if "sublime" in sys.modules:
    print("test_accessible_settle_integration.py is a standalone test, "
          "not a plugin.")
    raise SystemExit


# --- Stub LaTeXTools' PdfBuilder and import the real builder -----------------
from _testkit import Checker, find_poppler, install_native_builder  # noqa: E402
TexlibBuilder = install_native_builder()
import texlib_buildspec as _spec  # noqa: E402  (on sys.path via _testkit)

_c = Checker()
check = _c.check


# --- Fixture -----------------------------------------------------------------
# Thirty \section entries make a table of contents longer than one article
# page, which is what guarantees the page gain whatever the last page's fill.
# hyperref turns each entry into a link: the links are the annotations whose
# parent-tree keys collide with the surplus page's.
DOC_TEX = r"""\documentclass{article}
\usepackage{hyperref}
\title{Settle}
\author{TeXLib}
\date{}
\newcommand{\topic}[1]{\section{Topic #1}TOPICMARK#1: one line of body text.\par}
\begin{document}
\maketitle
\tableofcontents
\ExplSyntaxOn
\int_step_inline:nn { 30 } { \topic{#1} }
\ExplSyntaxOff
RADMARK: $\sqrt[n]{ab} = \sqrt[n]{a} \sqrt[n]{b}$
\end{document}
"""
LAST_TOPIC = 30

PAGES_RE = re.compile(r"Output written on .*?\((\d+) pages?", re.S)


def pages_of(out):
    """The page count a pass reported, or None when it wrote no PDF."""
    found = PAGES_RE.findall(out or "")
    return int(found[-1]) if found else None


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def lane_dir(tex_dir):
    """Where the tagged half of an accessible build of doc.tex writes."""
    return os.path.join(tex_dir, "aux", "a11y")


def run_engine(cmd, cwd):
    """One pass, spent again past a luaotfload cache-path abort.

    That abort is a startup race between concurrent engines (see
    texlib_buildspec.luaotfload_cache_aborted); the real hosts retry it once,
    and a test run beside another TeX build needs the same.
    """
    for _attempt in (1, 2):
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        out = (proc.stdout or "") + (proc.stderr or "")
        if not _spec.luaotfload_cache_aborted(out):
            break
    return proc.returncode, out


def run_build(tex_dir):
    """Drive the real builder coroutine, executing each yielded command.

    Returns (passes, display). Each pass is a dict: msg, tagged, out, pages,
    and `toc` and `aux`, the tagged lane's files as that pass found them.

    The aux directory is routed, as every real host routes it. Built in place,
    a tagged pass that finds no .aux or .toc in its lane reads the NORMAL
    half's from the source directory, and a cold lane is then not cold: the
    first complete pass already has a table of contents and the page gain this
    test depends on never happens.
    """
    lane = lane_dir(tex_dir)
    b = TexlibBuilder()
    b.tex_root = os.path.join(tex_dir, "doc.tex")
    b.tex_name = "doc.tex"
    b.base_name = "doc"
    b.tex_dir = tex_dir
    b.engine = "pdflatex"
    b.options = ["--texlib-mode=accessible"]
    b.aux_directory = os.path.join(tex_dir, "aux")
    b.out = ""

    passes = []
    gen = b.commands()
    try:
        item = next(gen)
        while True:
            cmd, msg = item
            tagged = "\\DocumentMetadata" in str(cmd[-1])
            found = {"toc": read_bytes(os.path.join(lane, "doc.toc")),
                     "aux": read_bytes(os.path.join(lane, "doc.aux"))}
            code, out = run_engine(cmd, tex_dir)
            passes.append(dict(found, msg=msg, tagged=tagged, out=out,
                               pages=pages_of(out)))
            b.out = out
            item = gen.send(code)
    except StopIteration:
        pass
    return passes, getattr(b, "_displayed", "")


def split_tagged(passes):
    """(probe aborted?, the tagged passes that completed)."""
    tagged = [p for p in passes if p["tagged"]]
    if tagged and _spec.luamml_se_aborted(tagged[0]["out"]):
        return True, tagged[1:]
    return False, tagged


def duplicate_parent_keys(pdf):
    """Parent-tree keys held more than once, or None when they cannot be read.

    A page's marked content and an annotation's structure element under ONE key
    is what a pass that outgrew its recorded page count writes, and what
    veraPDF reports as clause 8.2.2 on that page.
    """
    try:
        from pypdf import PdfReader  # noqa: PLC0415 - optional dependency
    except ImportError:
        return None
    try:
        root = PdfReader(pdf).trailer["/Root"]
        nums = root["/StructTreeRoot"]["/ParentTree"]["/Nums"]
        keys = [int(nums[i]) for i in range(0, len(nums), 2)]
    except Exception:  # noqa: BLE001 - an unreadable tree is "cannot check"
        return None
    return sorted({k for k in keys if keys.count(k) > 1})


def toc_page_and_real_page(pdf, pdftotext):
    """(the page the contents list for the last topic, the page it is on)."""
    def text(first, last):
        proc = subprocess.run(
            [pdftotext, "-enc", "UTF-8", "-layout", "-f", str(first),
             "-l", str(last), pdf, "-"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60)
        return proc.stdout or ""

    # A contents line ends in its page number; the section heading of the same
    # name ends in the name, so it cannot match.
    listed = re.search(r"Topic %d\b[ .]*?(\d+)\s*$" % LAST_TOPIC, text(1, 3),
                       re.M)
    real = None
    for page in range(1, 51):
        body = text(page, page)
        if not body.strip():
            break
        if "TOPICMARK%d:" % LAST_TOPIC in body:
            real = page
            break
    return (int(listed.group(1)) if listed else None), real


def check_pdf(label, pdf, display, pdftotext):
    """The checks on the tagged PDF a build kept."""
    dupes = duplicate_parent_keys(pdf)
    if dupes is None:
        _c.skip(f"{label}: parent-tree keys (pypdf absent or tree unreadable)")
    else:
        check(f"{label}: no parent-tree key is held twice", dupes == [],
              f"duplicated keys: {dupes}")

    listed, real = (None, None) if pdftotext is None \
        else toc_page_and_real_page(pdf, pdftotext)
    if listed is None or real is None:
        # Not finding the two numbers is a statement about the text layer or
        # the extractor, not about the build, so it does not fail the test.
        _c.skip(f"{label}: contents page numbers (pdftotext "
                + ("absent)" if pdftotext is None
                   else f"gave contents={listed}, body={real})"))
    else:
        check(f"{label}: the contents list the last topic on its real page",
              listed == real,
              f"contents say page {listed}, it is on page {real}")

    # The builder runs veraPDF itself when it is installed and prints the
    # verdict; that line is the claim a user sees, so it is the one asserted.
    if "PDF/UA-2" not in display:
        _c.skip(f"{label}: veraPDF verdict (veraPDF absent)")
    else:
        check(f"{label}: veraPDF passes the tagged PDF",
              "PDF/UA-2 PASSED" in display,
              [ln for ln in display.splitlines() if "PDF/UA-2" in ln])


def main():
    print("TeXLib accessible settle integration test\n")

    if not shutil.which("pdflatex") or not shutil.which("lualatex"):
        print("  SKIP  pdflatex or lualatex not found -- integration test "
              "soft-skipped (this is fine on a bare environment).")
        return 0
    pdftotext = find_poppler("pdftotext")

    tex_dir = tempfile.mkdtemp(prefix="texlib_settle_it_")
    try:
        with open(os.path.join(tex_dir, "doc.tex"), "w", encoding="utf-8") as fh:
            fh.write(DOC_TEX)
        pdf = os.path.join(tex_dir, "doc_accessible.pdf")
        lane_toc = os.path.join(lane_dir(tex_dir), "doc.toc")

        # --- Build 1: cold lane ------------------------------------------------
        p1, d1 = run_build(tex_dir)
        aborted1, done1 = split_tagged(p1)
        print("  build 1: " + "; ".join(
            "%s -> %s" % (p["msg"].split("] ", 1)[-1].rstrip("."), p["pages"])
            for p in p1 if p["tagged"]))
        check("build 1: the tagged half produced a PDF", os.path.exists(pdf))
        check("build 1: at least two tagged passes completed",
              len(done1) >= 2, [p["msg"] for p in done1])
        if len(done1) < 2:
            print(f"\n{_c.passed} passed, {_c.failed} failed")
            return _c.failed or 1

        # The fixture's precondition. If this fails the document no longer
        # gains a page and every check below is vacuous: repair the fixture.
        check("build 1: the document gains a page once its contents are read",
              (done1[0]["pages"] or 0) < (done1[-1]["pages"] or 0),
              [p["pages"] for p in done1])
        check("build 1: the kernel reports the pass that gained the page",
              _spec.lastpage_unsettled(done1[1]["out"]),
              [ln for ln in done1[1]["out"].splitlines() if "lastpage" in ln])
        check("build 1: the builder runs a further pass for it",
              len(done1) == 3 and "run 3 (settle)" in done1[2]["msg"],
              [p["msg"] for p in done1])
        check("build 1: the last tagged pass is settled",
              not _spec.lastpage_unsettled(done1[-1]["out"]),
              [ln for ln in done1[-1]["out"].splitlines() if "Rerun" in ln])
        check_pdf("build 1", pdf, d1, pdftotext)

        settled_pages = done1[-1]["pages"]
        settled_toc = read_bytes(lane_toc)

        # --- Build 2: straight after -------------------------------------------
        p2, d2 = run_build(tex_dir)
        aborted2, done2 = split_tagged(p2)
        print("  build 2: " + "; ".join(
            "%s -> %s" % (p["msg"].split("] ", 1)[-1].rstrip("."), p["pages"])
            for p in p2 if p["tagged"]))
        check("build 2: at least one tagged pass completed", bool(done2),
              [p["msg"] for p in p2])
        if not done2:
            print(f"\n{_c.passed} passed, {_c.failed} failed")
            return _c.failed or 1

        if not (aborted1 and aborted2):
            # A luamml that no longer aborts makes the fallback, and these
            # checks, unnecessary: see ACCESSIBLE_DOCMETA in texlib_buildspec.
            _c.skip("build 2: lane state across the abort (the mathml-SE probe "
                    "did not abort with this luamml)")
        else:
            retry = done2[0]
            check("build 2: the retry finds the .toc build 1 left",
                  settled_toc and retry["toc"] == settled_toc,
                  "%s bytes, build 1 left %s"
                  % (len(retry["toc"] or b""), len(settled_toc or b"")))
            record = ("\\@abspage@last{%s}" % settled_pages).encode("ascii")
            check("build 2: and an .aux that still records the page count",
                  record in (retry["aux"] or b""),
                  (retry["aux"] or b"")[-80:])
            check("build 2: its first pass ships the settled page count",
                  retry["pages"] == settled_pages,
                  f"{retry['pages']} pages, settled at {settled_pages}")
        check("build 2: two tagged passes are enough on a settled lane",
              len(done2) == 2, [p["msg"] for p in done2])
        check("build 2: the last tagged pass is settled",
              not _spec.lastpage_unsettled(done2[-1]["out"]),
              [ln for ln in done2[-1]["out"].splitlines() if "Rerun" in ln])
        check_pdf("build 2", pdf, d2, pdftotext)
    finally:
        shutil.rmtree(tex_dir, ignore_errors=True)

    print(f"\n{_c.passed} passed, {_c.failed} failed, {_c.skipped} skipped")
    return _c.failed


if __name__ == "__main__":
    sys.exit(main())
