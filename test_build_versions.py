#!/usr/bin/env python3
"""
Tests for build_versions.py (the parallel multi-version exam builder).

Most checks use a FAKE subprocess so the driver's orchestration -- per-version
source copy, coroutine drive, PDF collection, scratch cleanup, parallel fan-out,
and merge -- is exercised deterministically with no TeX toolchain. A final
gated check does a real 2-version autoexam build with lualatex if it (and the
autoexam class) are present, asserting two distinct single-version PDFs come
out (soft-skips otherwise). That real build is what guards the TEXINPUTS /
comma-path resolution that the fake engine cannot exercise.

Run:  python test_build_versions.py     (exit code = number of failures)
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile

# Import build_versions (it stubs LaTeXTools' PdfBuilder itself on import).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_versions as bv  # noqa: E402

_PASS = _FAIL = 0


def check(label, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def _have_pypdf():
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def _write_min_pdf(path):
    """A real 1-page PDF (via pypdf) if available, else minimal bytes."""
    if _have_pypdf():
        from pypdf import PdfWriter
        w = PdfWriter()
        w.add_blank_page(width=72, height=72)
        with open(path, "wb") as fh:
            w.write(fh)
    else:
        with open(path, "wb") as fh:
            fh.write(b"%PDF-1.4\n%%EOF\n")


def _arg(cmd, prefix):
    for a in cmd:
        if str(a).startswith(prefix):
            return str(a)[len(prefix):]
    return None


def fake_run_factory(rerun_first=False):
    """Return a fake subprocess.run that 'builds' by dropping <job>.pdf in the
    -output-directory and returns clean (or one-rerun) output. No biber."""
    state = {"engine_calls": 0}

    def fake_run(cmd, cwd=None, **kw):
        out = ""
        if cmd[0] != "biber":
            state["engine_calls"] += 1
            outdir = _arg(cmd, "-output-directory=") or cwd
            job = _arg(cmd, "--jobname=")
            _write_min_pdf(os.path.join(outdir, job + ".pdf"))
            # leave a jobname-keyed scratch file in CWD to test cleanup
            with open(os.path.join(cwd, job + "_synctex.tex"), "w") as fh:
                fh.write("scratch")
            if rerun_first and state["engine_calls"] == 1:
                out = "Label(s) may have changed. Rerun to get cross-references right."
        return subprocess.CompletedProcess(cmd, 0, out, "")
    return fake_run


def with_fake(fake, fn):
    real = bv.subprocess.run
    bv.subprocess.run = fake
    try:
        return fn()
    finally:
        bv.subprocess.run = real


def make_fixture(versions="A, B", src_extra=""):
    d = tempfile.mkdtemp(prefix="texlib_bv_")
    tex = os.path.join(d, "exam.tex")
    with open(tex, "w", encoding="utf-8") as fh:
        fh.write(r"\documentclass{autoexam}" "\n"
                 r"\versions{" + versions + "}\n" + src_extra +
                 r"\begin{document}q\end{document}" "\n")
    return d, tex


def real_build_check():
    """A genuine 2-version autoexam build via lualatex, asserting two distinct
    single-version PDFs. Soft-skips unless lualatex, the autoexam class, and
    pypdf are all available.

    The fixture is written INSIDE the repo (under Exams/, next to autoexam.cls)
    rather than a system temp dir, deliberately: build_versions resolves the
    shared root .sty/.lua files via a comma-free RELATIVE TEXINPUTS path up from
    the document, which only stays comma-free when the document lives in the
    tree. A /tmp fixture would re-introduce the comma this whole mechanism
    exists to dodge -- so testing from /tmp would not exercise the real path.
    """
    exams = os.path.join(bv.TEXLIB_ROOT, "Exams")
    cls = os.path.join(exams, "autoexam.cls")
    if not shutil.which("lualatex") or not os.path.isfile(cls) or not _have_pypdf():
        why = ("lualatex not on PATH" if not shutil.which("lualatex")
               else "Exams/autoexam.cls not found" if not os.path.isfile(cls)
               else "pypdf not installed")
        print(f"  SKIP  real 2-version autoexam build ({why})")
        return

    from pypdf import PdfReader
    base = "_bv_realtest"
    tex = os.path.join(exams, base + ".tex")
    with open(tex, "w", encoding="utf-8") as fh:
        fh.write(r"\documentclass{autoexam}" "\n"
                 r"\versions{A, B}" "\n"
                 r"\examsetup{number = 1, date = {Jan 1, 2026}}" "\n"
                 r"\begin{document}" "\n"
                 r"This is version \theExamVersion." "\n"
                 r"\end{document}" "\n")
    try:
        rc = bv.main([tex, "--separate"])
        pdfs = {v: os.path.join(exams, f"{base}_{v}.pdf") for v in ("A", "B")}
        check("real build: exit 0", rc == 0, f"rc={rc}")
        check("real build: both per-version PDFs produced",
              all(os.path.exists(p) for p in pdfs.values()),
              [os.path.basename(p) for p in pdfs.values() if not os.path.exists(p)])
        if all(os.path.exists(p) for p in pdfs.values()):
            texts = {v: " ".join(PdfReader(p).pages[0].extract_text().split())
                     for v, p in pdfs.items()}
            check("real build: each PDF is a single version (1 page)",
                  all(len(PdfReader(p).pages) == 1 for p in pdfs.values()))
            check("real build: version A PDF shows version A",
                  "version A" in texts["A"], texts["A"][:70])
            check("real build: version B PDF shows version B",
                  "version B" in texts["B"], texts["B"][:70])
            check("real build: the two versions differ",
                  texts["A"] != texts["B"])
    finally:
        for pat in (base + ".*", base + "_*"):
            for f in glob.glob(os.path.join(exams, pat)):
                bv.TexlibBuilder._force_remove(f)


def main():
    print("build_versions tests\n")

    # --- version detection + engine selection -------------------------------
    probe = bv.TexlibBuilder()
    _, tex = make_fixture("A, B, C")
    with open(tex, encoding="utf-8") as fh:
        src = fh.read()
    check("detect versions A,B,C", probe._parse_versions(src) == ["A", "B", "C"],
          probe._parse_versions(src))
    check("autoexam selects lualatex", probe._select_engine(src) == "lualatex",
          probe._select_engine(src))

    # --- build_one_version: copy + collect PDF + clean scratch (fake) --------
    d, tex = make_fixture("A, B")
    r = with_fake(fake_run_factory(),
                  lambda: bv.build_one_version(tex, "exam", "A", "lualatex", 60, False))
    check("build_one_version: ok", r["ok"], r["log"])
    check("build_one_version: produced exam_A.pdf",
          r["pdf"] and os.path.basename(r["pdf"]) == "exam_A.pdf", r["pdf"])
    check("build_one_version: PDF exists on disk", r["pdf"] and os.path.exists(r["pdf"]))
    check("build_one_version: source copy exam_A.tex cleaned up",
          not os.path.exists(os.path.join(d, "exam_A.tex")))
    check("build_one_version: jobname scratch (exam_A_synctex.tex) cleaned up",
          not os.path.exists(os.path.join(d, "exam_A_synctex.tex")))
    check("build_one_version: single pass (no biber, no rerun)",
          r["passes"] == ["lualatex"], r["passes"])

    # --- rerun signal -> a second pass --------------------------------------
    d2, tex2 = make_fixture("A")
    r2 = with_fake(fake_run_factory(rerun_first=True),
                   lambda: bv.build_one_version(tex2, "exam", "A", "lualatex", 60, False))
    check("build_one_version: rerun signal -> 2 passes",
          r2["passes"] == ["lualatex", "lualatex"], r2["passes"])

    # --- _cleanup_scratch keeps the PDF when asked --------------------------
    d3 = tempfile.mkdtemp(prefix="texlib_bv_clean_")
    for name in ("exam_A.pdf", "exam_A.tex", "exam_A_A.sco", "exam_A.srcmap",
                 "exam_A_autoexam_body_A.tex"):
        with open(os.path.join(d3, name), "w") as fh:
            fh.write("x")
    bv._cleanup_scratch(d3, "exam_A", keep_pdf=True)
    check("_cleanup_scratch: keeps exam_A.pdf",
          os.path.exists(os.path.join(d3, "exam_A.pdf")))
    check("_cleanup_scratch: removes .tex/.sco/.srcmap/body",
          not any(os.path.exists(os.path.join(d3, n)) for n in
                  ("exam_A.tex", "exam_A_A.sco", "exam_A.srcmap",
                   "exam_A_autoexam_body_A.tex")))

    # --- merge_pdfs (needs pypdf) -------------------------------------------
    if _have_pypdf():
        from pypdf import PdfReader
        dm = tempfile.mkdtemp(prefix="texlib_bv_merge_")
        parts = [os.path.join(dm, f"p{i}.pdf") for i in range(3)]
        for p in parts:
            _write_min_pdf(p)
        out = os.path.join(dm, "merged.pdf")
        ok, _ = bv.merge_pdfs(parts, out)
        check("merge_pdfs: ok", ok)
        check("merge_pdfs: page count = sum of parts",
              ok and len(PdfReader(out).pages) == 3,
              len(PdfReader(out).pages) if ok else "n/a")
    else:
        print("  SKIP  merge_pdfs (pypdf not installed)")

    # --- full driver via main(): parallel + combined merge (fake engine) ----
    if _have_pypdf():
        from pypdf import PdfReader
        d4, tex4 = make_fixture("A, B, C")
        rc = with_fake(fake_run_factory(),
                       lambda: bv.main([tex4, "--combined", "-j", "3"]))
        combined = os.path.join(d4, "exam.pdf")
        check("driver --combined: exit 0", rc == 0, f"rc={rc}")
        check("driver --combined: merged exam.pdf has 3 pages",
              os.path.exists(combined) and len(PdfReader(combined).pages) == 3,
              combined)
        check("driver --combined: per-version PDFs dropped (combined-only)",
              not os.path.exists(os.path.join(d4, "exam_A.pdf")))

        d5, tex5 = make_fixture("A, B")
        rc = with_fake(fake_run_factory(),
                       lambda: bv.main([tex5, "--separate"]))
        check("driver --separate: keeps per-version PDFs, no merge",
              rc == 0 and os.path.exists(os.path.join(d5, "exam_A.pdf"))
              and os.path.exists(os.path.join(d5, "exam_B.pdf"))
              and not os.path.exists(os.path.join(d5, "exam.pdf")))
    else:
        print("  SKIP  driver merge tests (pypdf not installed)")

    # --- default output mode is combined ------------------------------------
    if _have_pypdf():
        d6, tex6 = make_fixture("A, B")
        rc = with_fake(fake_run_factory(),
                       lambda: bv.main([tex6]))  # no flag -> combined default
        check("driver default: produces combined exam.pdf (no flag)",
              rc == 0 and os.path.exists(os.path.join(d6, "exam.pdf")), f"rc={rc}")

    # --- solution-build mode detection (\solutions / \justsolutions) --------
    check("solmode: none when neither macro present",
          bv._parse_solmode(r"\documentclass{autoexam}\versions{A,B}") == "none")
    check("solmode: \\solutions -> dual",
          bv._parse_solmode("\\solutions\n\\versions{A,B}") == "dual")
    check("solmode: \\justsolutions -> only (not misread as dual)",
          bv._parse_solmode("\\justsolutions\n\\versions{A,B}") == "only")
    check("solmode: both macros -> dual wins",
          bv._parse_solmode(r"\solutions \justsolutions") == "dual")
    check("solmode: commented macro ignored",
          bv._parse_solmode("% \\solutions\n\\versions{A,B}") == "none")
    check("solmode: word boundary (\\solutionsfoo not a match)",
          bv._parse_solmode(r"\solutionsfoo") == "none")

    # --- real toolchain: genuine 2-version autoexam build (gated) -----------
    real_build_check()

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return _FAIL


if __name__ == "__main__":
    sys.exit(main())
