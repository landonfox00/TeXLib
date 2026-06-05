#!/usr/bin/env python3
"""
Parallel multi-version exam builder for TeXLib autoexam documents.

Builds every \\versions{...} entry of an autoexam .tex CONCURRENTLY (one OS
process per version), instead of one-at-a-time. Each version reuses the TeXLib
builder's own per-version pipeline -- engine selection, the biber-skip cache,
and the cross-reference rerun loop -- so there is no logic drift from the
Sublime builder.

Output (both available; combined is the default):
    (default / --combined) one merged <base>.pdf containing every version
    --separate             keep the per-version PDFs <base>_A.pdf, <base>_B.pdf
    --both                 do both (merged file + per-version PDFs kept)

Why a separate tool (not the Sublime builder): LaTeXTools runs one command at a
time through a coroutine whose rerun loop inspects each command's output, so it
cannot fan out. This driver runs outside that model, so the interactive builder
is untouched.

How it stays correct under parallelism: autoexam's Lua reads the document body
from `<jobname>.tex`, and every scratch file it writes is `<jobname>`-keyed. So
each version is built under a distinct jobname `<base>_<ver>` against its own
source copy `<base>_<ver>.tex` -- distinct jobnames never collide, and the body
reader (and \\shufflepages) still find their source. CWD stays the real document
directory so \\loadbank and other relative inputs resolve exactly as normal.

Standalone: no Sublime/LaTeXTools install needed. Needs lualatex/pdflatex (+
biber if the exam cites) on PATH, and pypdf for merging (--combined/--both).

Usage:
    python build_versions.py path/to/exam.tex            # combined exam.pdf
    python build_versions.py exam.tex --separate         # exam_A.pdf, ...
    python build_versions.py exam.tex --both -j 4 -v
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types


# --- Import the real TeXLib builder (stub LaTeXTools' PdfBuilder) ------------
class _StubPdfBuilder:
    def __init__(self, *a, **k):
        self._displayed = ""

    def display(self, msg):
        self._displayed += str(msg)


def _import_builder():
    here = os.path.dirname(os.path.abspath(__file__))
    sublime_dir = os.path.join(here, "Sublime")
    for name in (
        "LaTeXTools",
        "LaTeXTools.plugins",
        "LaTeXTools.plugins.builder",
        "LaTeXTools.plugins.builder.pdf_builder",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["LaTeXTools.plugins.builder.pdf_builder"].PdfBuilder = _StubPdfBuilder
    sys.path.insert(0, sublime_dir)
    from texlib_builder import TexlibBuilder  # noqa: E402
    return TexlibBuilder


TexlibBuilder = _import_builder()


# --- One version build ------------------------------------------------------
def _aux_dir_for(tex_root, version):
    """Persistent per-(document, version) aux dir, so the biber cache survives
    across runs (mirrors the Sublime builder's <<temp>> scheme)."""
    key = hashlib.md5(f"{tex_root}\0{version}".encode("utf-8")).hexdigest()[:12]
    d = os.path.join(tempfile.gettempdir(), "texlib-versions", key)
    os.makedirs(d, exist_ok=True)
    return d


def build_one_version(tex_root, base, version, engine, timeout, verbose):
    """Build a single version -> dict(version, ok, pdf, passes, seconds, log)."""
    tex_dir = os.path.dirname(os.path.abspath(tex_root))
    src_name = os.path.basename(tex_root)
    jobname = f"{base}_{version}"
    copy_name = f"{jobname}.tex"          # jobname must match the source basename
    copy_path = os.path.join(tex_dir, copy_name)
    aux = _aux_dir_for(tex_root, version)

    b = TexlibBuilder()
    b.tex_root = tex_root
    b.tex_name = copy_name                # _build_version does \input{tex_name}
    b.base_name = base                    # jobname becomes base_name + "_" + ver
    b.tex_dir = tex_dir
    b.engine = engine
    b.out = ""
    b._aux_target = aux

    base_cmd = [engine, "-interaction=nonstopmode", "-synctex=1"]
    if engine in ("lualatex", "xelatex"):
        base_cmd.append("-shell-escape")
    base_cmd.append(f"-output-directory={aux}")

    t0 = time.monotonic()
    heads, log = [], []
    try:
        shutil.copyfile(tex_root, copy_path)
        gen = b._build_version(base_cmd, engine, version)
        item = next(gen)
        while True:
            cmd, _msg = item
            heads.append(cmd[0])
            proc = subprocess.run(
                cmd, cwd=tex_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            log.append(out)
            b.out = out
            item = gen.send(proc.returncode)
    except StopIteration:
        pass
    except Exception as exc:  # noqa: BLE001
        return {"version": version, "ok": False, "pdf": None, "passes": heads,
                "seconds": time.monotonic() - t0, "log": f"{exc}"}
    finally:
        _cleanup_scratch(tex_dir, jobname, keep_pdf=False)

    # Collect the PDF from the aux dir back next to the source.
    src_pdf = os.path.join(aux, jobname + ".pdf")
    out_pdf = os.path.join(tex_dir, jobname + ".pdf")
    ok = os.path.exists(src_pdf)
    if ok:
        TexlibBuilder._force_remove(out_pdf)
        shutil.copyfile(src_pdf, out_pdf)
    last = log[-1] if log else ""
    undefined = "There were undefined references" in last
    return {
        "version": version,
        "ok": ok and not undefined,
        "pdf": out_pdf if ok else None,
        "passes": heads,
        "seconds": time.monotonic() - t0,
        "log": ("undefined references remained" if undefined else
                ("" if ok else "no PDF produced")) +
               (("\n" + last[-1500:]) if (verbose or not ok) else ""),
    }


def _cleanup_scratch(tex_dir, jobname, keep_pdf):
    """Remove a version's jobname-keyed scratch from the source dir.

    autoexam writes <jobname>.tex (our copy), <jobname>.srcmap,
    <jobname>_<ver>.sco, <jobname>_autoexam_body_*.tex, <jobname>_prob_*.tex,
    <jobname>_synctex.tex, etc. -- all prefixed by the jobname. Sweep them, but
    never touch the final <jobname>.pdf when keep_pdf is True.
    """
    for path in glob.glob(os.path.join(tex_dir, jobname + "*")):
        if keep_pdf and path.endswith(".pdf"):
            continue
        try:
            TexlibBuilder._force_remove(path)
        except Exception:  # noqa: BLE001
            pass


# --- Merge ------------------------------------------------------------------
def merge_pdfs(version_pdfs, out_path):
    """Concatenate per-version PDFs (in version order) into out_path."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return False, ("pypdf not installed -- cannot merge. Install with "
                       "'pip install pypdf', or use --separate.")
    writer = PdfWriter()
    for pdf in version_pdfs:
        reader = PdfReader(pdf)
        for page in reader.pages:
            writer.add_page(page)
    TexlibBuilder._force_remove(out_path)
    with open(out_path, "wb") as fh:
        writer.write(fh)
    return True, out_path


# --- Driver -----------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Parallel multi-version exam builder.")
    ap.add_argument("texfile", help="the autoexam .tex with \\versions{...}")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--combined", action="store_true",
                   help="merge versions into one <base>.pdf (default)")
    g.add_argument("--separate", action="store_true",
                   help="keep per-version PDFs, do not merge")
    g.add_argument("--both", action="store_true",
                   help="merged <base>.pdf AND per-version PDFs")
    ap.add_argument("-j", "--jobs", type=int, default=0,
                    help="max parallel version builds (default: CPU count)")
    ap.add_argument("--timeout", type=int, default=300,
                    help="per-command timeout in seconds (default 300)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print the tail of each version's log")
    args = ap.parse_args(argv)

    tex_root = os.path.abspath(args.texfile)
    if not os.path.isfile(tex_root):
        print(f"error: no such file: {tex_root}")
        return 2
    with open(tex_root, "r", encoding="utf-8", errors="replace") as fh:
        src = fh.read()

    base = os.path.splitext(os.path.basename(tex_root))[0]
    probe = TexlibBuilder()
    versions = probe._parse_versions(src)
    engine = probe._select_engine(src)
    if not versions:
        print("error: no \\versions{...} / \\examversions{...} found.")
        return 2

    # Default output mode: combined (per the standalone default).
    combined = args.combined or args.both or not args.separate
    keep_separate = args.separate or args.both

    jobs = args.jobs if args.jobs > 0 else (os.cpu_count() or 4)
    jobs = max(1, min(jobs, len(versions)))
    print(f"Building {len(versions)} version(s) {versions} of {base!r} with "
          f"{engine}, {jobs} in parallel...")

    t0 = time.monotonic()
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futs = {pool.submit(build_one_version, tex_root, base, v, engine,
                            args.timeout, args.verbose): v for v in versions}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results[r["version"]] = r
            status = "ok" if r["ok"] else "FAILED"
            print(f"  [{r['version']}] {status} in {r['seconds']:.1f}s "
                  f"({'/'.join(r['passes'])})")
            if r["log"] and (args.verbose or not r["ok"]):
                print("      " + r["log"].replace("\n", "\n      "))
    wall = time.monotonic() - t0

    ordered = [results[v] for v in versions]
    failed = [r["version"] for r in ordered if not r["ok"]]
    total_cpu = sum(r["seconds"] for r in ordered)
    print(f"\nWall time {wall:.1f}s (sum of version times {total_cpu:.1f}s -> "
          f"{(total_cpu / wall):.1f}x speedup).")

    if failed:
        print(f"FAILED versions: {failed}. Not merging.")
        return 1

    if combined:
        out = os.path.join(os.path.dirname(tex_root), base + ".pdf")
        ok, msg = merge_pdfs([r["pdf"] for r in ordered], out)
        print(f"Combined -> {msg}" if ok else f"Merge skipped: {msg}")
        if not ok and not keep_separate:
            return 1
        if not keep_separate:
            for r in ordered:  # combined-only: drop the per-version PDFs
                TexlibBuilder._force_remove(r["pdf"])
    if keep_separate:
        print("Per-version PDFs: " +
              ", ".join(os.path.basename(r["pdf"]) for r in ordered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
