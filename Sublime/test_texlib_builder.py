#!/usr/bin/env python3
"""
Standalone logic test for texlib_builder.py -- no Sublime / LaTeXTools needed.

It stubs the LaTeXTools PdfBuilder base class, imports TexlibBuilder, and drives
its commands() coroutine over synthetic documents to verify the decision logic:
engine selection, --texlib-mode extraction, \\versions parsing, and the
assembled command lines.

What this CAN'T check: whether a .sublime-build variant's `options` actually
reaches self.options inside a real LaTeXTools build -- only a live Sublime build
confirms that. This harness covers the builder's "brain"; the README's manual
test steps cover the Sublime wiring.

Run:  python test_texlib_builder.py     (exit code = number of failures)
"""

import hashlib
import json
import os
import sys
import types
import tempfile

# --- 0. Refuse to run inside Sublime Text -----------------------------------
# This file is a standalone test, NOT a Sublime plugin. If Sublime auto-loads
# it from Packages/User/, the stub-install code below would overwrite the real
# LaTeXTools.PdfBuilder with a fake one, and texlib_builder.py would then
# subclass the fake -- breaking builder registration ("Cannot find builder
# texlib"). Detect that we're inside Sublime and exit cleanly.
if "sublime" in sys.modules:  # only true inside Sublime's plugin host
    print(
        "test_texlib_builder.py was loaded by Sublime, but this is a "
        "standalone test, not a plugin. Move it out of Packages/User/ "
        "(e.g. back to TeXLib/Sublime/ where it belongs)."
    )
    # Do NOT define any classes, do NOT call any setup, do NOT raise (raising
    # would clutter the console). Just stop module execution here.
    raise SystemExit  # caught silently by Sublime's plugin loader


# --- 1. Stub the LaTeXTools PdfBuilder base class ---------------------------

class _StubPdfBuilder:
    """Minimal stand-in for LaTeXTools' PdfBuilder."""

    def __init__(self, *args, **kwargs):
        self._displayed = ""

    def display(self, msg):
        self._displayed += str(msg)


def _install_latextools_stub():
    """Make `from LaTeXTools.plugins.builder.pdf_builder import PdfBuilder` work."""
    for name in (
        "LaTeXTools",
        "LaTeXTools.plugins",
        "LaTeXTools.plugins.builder",
        "LaTeXTools.plugins.builder.pdf_builder",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["LaTeXTools.plugins.builder.pdf_builder"].PdfBuilder = _StubPdfBuilder


_install_latextools_stub()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _install_texlib_package_stub():
    """texlib_builder.py pulls its shared build core from the native TeXLib
    Sublime package (`from TeXLib.texlib_build import TexlibBuildCore`). That
    package name only exists inside Sublime (deploy-plugin.ps1 junctions
    Sublime/texlib -> Packages/TeXLib), so register the native texlib_build
    module under the TeXLib package name to make the import resolve headless."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "texlib"))
    import texlib_build as _native  # Sublime/texlib/texlib_build.py (sublime-free)
    pkg = types.ModuleType("TeXLib")
    pkg.__path__ = [os.path.join(here, "texlib")]
    sys.modules.setdefault("TeXLib", pkg)
    sys.modules.setdefault("TeXLib.texlib_build", _native)


_install_texlib_package_stub()

from texlib_builder import TexlibBuilder  # noqa: E402
from texlib_build import GRADEBOOK_SHEETS, TexlibBuildCore  # noqa: E402  (native core)


# --- 2. Harness ------------------------------------------------------------

def run_builder(doc_src, options=None, engine="pdflatex", aux_files=None):
    """Build a TexlibBuilder over a synthetic document; return (commands, display).

    `commands` is the list of (command_list, message) tuples the builder would
    run. We feed exit status 0 back for every command (so no rerun fires, since
    self.out is empty).

    `aux_files` (optional) maps filename -> contents to pre-create in the tex
    dir before building -- used to exercise the biber change-detection path
    (e.g. a doc.bcf / doc.bbl / doc.bcf.texlibhash trio).
    """
    tmp = tempfile.mkdtemp(prefix="texlib_bt_")
    tex_path = os.path.join(tmp, "doc.tex")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(doc_src)
    for name, contents in (aux_files or {}).items():
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
            fh.write(contents)

    b = TexlibBuilder()
    b.tex_root = tex_path
    b.tex_name = "doc.tex"
    b.base_name = "doc"
    b.tex_dir = tmp
    b.engine = engine
    b.options = list(options or [])
    b.out = ""  # empty -> rerun loop never fires

    cmds = []
    gen = b.commands()
    try:
        item = next(gen)
        while True:
            cmds.append(item)
            item = gen.send(0)
    except StopIteration:
        pass
    return cmds, getattr(b, "_displayed", "")


def drive_builder(doc_src, options=None, engine="pdflatex",
                  seed_files=None, steps=None):
    """Drive commands() with a scripted side-effect timeline -> (cmds, disp, tmp).

    run_builder feeds empty output, so the biber/rerun branches never fire. This
    harness instead simulates a real multi-pass build so those branches execute
    and the FULL command sequence can be asserted:

      seed_files : {name: contents} written to the tex dir BEFORE the build,
                   to mimic artifacts a previous build left behind
                   (e.g. a doc.bbl + doc.bcf.texlibhash that lets biber skip).
      steps      : list aligned to the yielded commands. steps[i] is applied
                   AFTER the i-th command is yielded and BEFORE the next send(),
                   so it models what that command "did":
                     {"out":    "<engine output the builder will inspect>",
                      "write":  {name: contents},  # aux files the pass created
                      "remove": [names]}           # aux files it deleted
                   Entries past the end of the list default to clean output
                   (out="") with no file changes.

    The builder reads biber state from the filesystem (.bcf/.bbl/.texlibhash in
    the tex dir, since no aux_directory is set) and rerun state from self.out --
    both of which this harness controls per step.
    """
    tmp = tempfile.mkdtemp(prefix="texlib_sim_")
    tex_path = os.path.join(tmp, "doc.tex")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(doc_src)
    for name, contents in (seed_files or {}).items():
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
            fh.write(contents)

    b = TexlibBuilder()
    b.tex_root = tex_path
    b.tex_name = "doc.tex"
    b.base_name = "doc"
    b.tex_dir = tmp
    b.engine = engine
    b.options = list(options or [])
    b.out = ""

    steps = steps or []

    def apply(i):
        step = steps[i] if i < len(steps) else {}
        for name in step.get("remove", []):
            try:
                os.remove(os.path.join(tmp, name))
            except OSError:
                pass
        for name, contents in step.get("write", {}).items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(contents)
        b.out = step.get("out", "")

    cmds = []
    gen = b.commands()
    try:
        item = next(gen)
        i = 0
        while True:
            cmds.append(item)
            apply(i)
            i += 1
            item = gen.send(0)
    except StopIteration:
        pass
    return cmds, getattr(b, "_displayed", ""), tmp


def heads(cmds):
    """The first token (engine name or 'biber') of each yielded command."""
    return [c[0][0] for c in cmds]


def _md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _fp(bcf_content, datasources=None):
    """Expected biber-inputs fingerprint for a .bcf (with optional .bib
    datasources), mirroring TexlibBuilder._biber_inputs_hash -- including the
    biber-version suffix when biber is on PATH, so cache-skip tests stay valid
    on machines with or without biber installed."""
    parts = [_md5(bcf_content)]
    for name, content in (datasources or {}).items():
        parts.append(name + ":" + _md5(content))
    ver = TexlibBuilder._biber_version()
    if ver:
        parts.append("biber:" + ver)
    return "|".join(parts)


_PASS = 0
_FAIL = 0


def check(label, condition, detail=""):
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


# --- 3. Test cases ---------------------------------------------------------

def main():
    print("TeXLib builder logic tests\n")

    # (a) plain article -> pdflatex, default mode, plain filename arg
    cmds, _ = run_builder(r"\documentclass{article}\begin{document}x\end{document}")
    check("article -> pdflatex", bool(cmds) and cmds[0][0][0] == "pdflatex", cmds)
    check("article -> plain filename arg, no mode macro",
          bool(cmds) and cmds[0][0][-1] == "doc.tex", cmds)
    check("article -> exactly one build", len(cmds) == 1, f"{len(cmds)} builds")

    # (b) autoexam with no magic comment -> forced lualatex + -shell-escape
    cmds, disp = run_builder(r"\documentclass{autoexam}\begin{document}x\end{document}")
    check("autoexam -> forced lualatex", bool(cmds) and cmds[0][0][0] == "lualatex", cmds)
    check("autoexam -> -shell-escape present",
          bool(cmds) and "-shell-escape" in cmds[0][0], cmds)
    check("autoexam -> 'requires lualatex' message shown",
          "requires lualatex" in disp, repr(disp))

    # (c) didactic + --texlib-mode=key -> \def\ShowKey{} injected
    cmds, _ = run_builder(r"\documentclass{didactic}\begin{document}x\end{document}",
                          options=["--texlib-mode=key"])
    arg = cmds[0][0][-1] if cmds else ""
    check("mode=key -> \\def\\ShowKey{} injected", r"\def\ShowKey{}" in arg, arg)
    check("mode=key -> \\input{doc.tex} present", r"\input{doc.tex}" in arg, arg)
    check("mode=key -> --texlib-mode token NOT passed to engine",
          not any("--texlib-mode" in str(x) for x in cmds[0][0]), cmds[0][0])

    # (d) pset + student mode
    cmds, _ = run_builder(r"\documentclass{pset}\begin{document}x\end{document}",
                          options=["--texlib-mode=student"])
    check("mode=student -> \\def\\StudentMode{}",
          r"\def\StudentMode{}" in cmds[0][0][-1], cmds)

    # (e) a real engine option survives alongside the mode token
    cmds, _ = run_builder(r"\documentclass{article}\begin{document}x\end{document}",
                          options=["--texlib-mode=draft", "-halt-on-error"])
    check("real option -halt-on-error preserved",
          "-halt-on-error" in cmds[0][0], cmds[0][0])
    check("mode=draft -> \\def\\ShowDraft{}",
          r"\def\ShowDraft{}" in cmds[0][0][-1], cmds[0][0][-1] if cmds else "")

    # (h) %!TeX program respected (LaTeXTools resolves it into self.engine)
    cmds, _ = run_builder(r"\documentclass{article}\begin{document}x\end{document}",
                          engine="lualatex")
    check("self.engine=lualatex respected",
          bool(cmds) and cmds[0][0][0] == "lualatex", cmds)

    # (i) quiz + pdflatex -> overridden to lualatex (quiz requires it)
    cmds, _ = run_builder(r"\documentclass{quiz}\begin{document}x\end{document}",
                          engine="pdflatex")
    check("quiz + pdflatex -> overridden to lualatex",
          bool(cmds) and cmds[0][0][0] == "lualatex", cmds)

    # (j) unknown mode -> falls back to default (no macro), with a warning
    cmds, disp = run_builder(r"\documentclass{article}\begin{document}x\end{document}",
                             options=["--texlib-mode=bogus"])
    check("unknown mode -> no macro injected (plain filename)",
          bool(cmds) and cmds[0][0][-1] == "doc.tex", cmds)
    check("unknown mode -> warning shown", "unknown build mode" in disp, repr(disp))

    # (j2) quick mode -> exactly one engine pass, plain filename, no biber even
    # when a .bcf is present, no mode macro.
    cmds, disp = run_builder(
        r"\documentclass{article}\begin{document}x\end{document}",
        options=["--texlib-mode=quick"],
        aux_files={"doc.bcf": "<bcf/>"})  # would trigger biber in a normal build
    check("quick -> exactly one build", len(cmds) == 1, f"{len(cmds)} builds")
    check("quick -> plain filename arg, no mode macro",
          bool(cmds) and cmds[0][0][-1] == "doc.tex", cmds)
    check("quick -> no biber despite .bcf present",
          not any(c[0][0] == "biber" for c in cmds), cmds)
    check("quick -> single-pass message shown",
          bool(cmds) and "quick" in cmds[0][1], cmds[0][1] if cmds else "")

    # (j3) biber change-detection
    BCF = "<bcf>cite-keys</bcf>"
    BCF_HASH = _fp(BCF)   # full fingerprint (bcf md5 + biber version if present)

    #   first build: .bcf present, no .bbl yet -> biber runs + forced re-pass
    cmds, _ = run_builder(
        r"\documentclass{article}\begin{document}x\end{document}",
        aux_files={"doc.bcf": BCF})
    biber_cmds = [c for c in cmds if c[0][0] == "biber"]
    check("biber: fresh .bcf, no .bbl -> biber runs", len(biber_cmds) == 1, cmds)
    check("biber: fresh .bcf -> forced post-biber re-pass (3 cmds)",
          len(cmds) == 3, f"{len(cmds)} cmds")

    #   unchanged rebuild: .bcf + matching .bbl + hash -> biber skipped
    cmds, _ = run_builder(
        r"\documentclass{article}\begin{document}x\end{document}",
        aux_files={"doc.bcf": BCF, "doc.bbl": "...", "doc.bcf.texlibhash": BCF_HASH})
    check("biber: unchanged .bcf -> biber skipped (1 cmd)",
          len(cmds) == 1 and not any(c[0][0] == "biber" for c in cmds),
          f"{len(cmds)} cmds")

    #   changed citations: .bbl present but stale hash -> biber re-runs
    cmds, _ = run_builder(
        r"\documentclass{article}\begin{document}x\end{document}",
        aux_files={"doc.bcf": BCF, "doc.bbl": "...", "doc.bcf.texlibhash": "stale"})
    check("biber: changed .bcf (stale hash) -> biber re-runs",
          any(c[0][0] == "biber" for c in cmds), cmds)

    # (j4) _force_remove deletes a Hidden file (the synctex copy-back / decompress
    # fix: open('wb')/copy2 over a hidden file is Errno 13 on Windows).
    tmp = tempfile.mkdtemp(prefix="texlib_fr_")
    hidden = os.path.join(tmp, "hidden.synctex")
    with open(hidden, "w", encoding="utf-8") as fh:
        fh.write("x")
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(hidden, 0x2)  # FILE_ATTRIBUTE_HIDDEN
    TexlibBuilder._force_remove(hidden)
    check("_force_remove: hidden file is deleted", not os.path.exists(hidden), hidden)
    TexlibBuilder._force_remove(hidden)  # idempotent: no error when absent
    check("_force_remove: no-op when file already gone", not os.path.exists(hidden))

    # (j5) rerun detection recognizes every "run LaTeX again" signal, but NOT a
    # bare undefined-reference warning (which may never resolve -> avoid looping
    # to MAX_RERUNS on a genuinely-missing label).
    rb = TexlibBuilder()
    rerun_cases = [
        ("Label(s) may have changed. Rerun to get cross-references right.", True),
        ("Package biblatex Warning: Please rerun LaTeX.", True),
        ("Package rerunfilecheck Warning: Rerun to get outlines right.", True),
        ("LaTeX Warning: There were undefined references.", False),
        ("Output written. No warnings.", False),
    ]
    for msg, want in rerun_cases:
        rb.out = msg
        check(f"rerun-detect: {msg[:34]!r} -> {want}",
              rb._needs_another_run() == want, msg)

    # (k) schedule .schedmap -> synctex.gz rewrite
    import gzip
    tmp = tempfile.mkdtemp(prefix="texlib_bt_synctex_")
    base = "doc"
    src_path = os.path.join(tmp, "doc.tex").replace("\\", "/")
    grid_path = os.path.join(tmp, "doc_schedule_grid.tex").replace("\\", "/")

    # Fake synctex stream: one source-file Input + two grid-file Inputs
    # (LuaTeX usually emits >1 due to its kpse lookup pass), plus typeset
    # records referencing the grid IDs at various grid_lines.
    fake_synctex = (
        f"SyncTeX Version:1\n"
        f"Input:1:{src_path}\n"
        f"Input:7:{grid_path}\n"
        f"Input:8:{grid_path}\n"
        f"!17\n"
        f"{{0\n"
        f"(7,1:1000,2000:5000,500,100\n"
        f"h7,1:1500,2200:3000,400,80\n"
        f"x7,1:1700,2200\n"
        f"(7,2:1000,5000:5000,500,100\n"
        f"h8,3:2000,8000:3000,400,80\n"
        f"(1,12:500,600:9000,500,0\n"           # NOT a grid record; leave alone
        f"}}0\n"
        f"Postamble:\n"
    )
    with gzip.open(os.path.join(tmp, base + ".synctex.gz"), "wt", encoding="utf-8") as fh:
        fh.write(fake_synctex)
    with open(os.path.join(tmp, base + ".schedmap"), "w", encoding="utf-8") as fh:
        fh.write("# schedule source map v1\n")
        fh.write("# grid_line|user_source_line\n")
        fh.write("1|34\n")
        fh.write("2|24\n")
        fh.write("3|38\n")

    b = TexlibBuilder()
    b._rewrite_synctex_for_schedmap(tmp, tmp, base)

    with gzip.open(os.path.join(tmp, base + ".synctex.gz"), "rt", encoding="utf-8") as fh:
        out = fh.read()

    check("schedmap rewrite: grid Input records repointed to source",
          out.count(f"Input:7:{src_path}") == 1 and out.count(f"Input:8:{src_path}") == 1,
          out)
    check("schedmap rewrite: grid_line 1 -> source line 34",
          "(7,34:1000,2000:" in out, out)
    check("schedmap rewrite: grid_line 2 -> source line 24",
          "(7,24:1000,5000:" in out, out)
    check("schedmap rewrite: cross-ID grid_line 3 -> source line 38",
          "h8,38:2000,8000:" in out, out)
    check("schedmap rewrite: non-grid record (1,12) left alone",
          "(1,12:500,600:" in out, out)
    check("schedmap rewrite: no orphan references to grid_lines remain",
          "(7,1:" not in out and "(7,2:" not in out and "h8,3:" not in out, out)

    # (l-pre) rewrite finds schedmap in source dir + synctex in separate aux dir
    src_dir = tempfile.mkdtemp(prefix="texlib_bt_synctex_src_")
    aux_dir = tempfile.mkdtemp(prefix="texlib_bt_synctex_aux_")
    src_path = os.path.join(src_dir, "doc.tex").replace("\\", "/")
    grid_path = os.path.join(src_dir, "doc_schedule_grid.tex").replace("\\", "/")
    fake = (
        f"SyncTeX Version:1\n"
        f"Input:1:{src_path}\n"
        f"Input:7:{grid_path}\n"
        f"!17\n"
        f"{{0\n"
        f"(7,1:1000,2000:5000,500,100\n"
        f"}}0\n"
        f"Postamble:\n"
    )
    # schedmap lands in source dir (lualatex's CWD)
    with open(os.path.join(src_dir, "doc.schedmap"), "w", encoding="utf-8") as fh:
        fh.write("1|34\n")
    # synctex.gz lands in aux dir (-output-directory route)
    with gzip.open(os.path.join(aux_dir, "doc.synctex.gz"), "wt", encoding="utf-8") as fh:
        fh.write(fake)
    b = TexlibBuilder()
    b._rewrite_synctex_for_schedmap(aux_dir, src_dir, "doc")
    with gzip.open(os.path.join(aux_dir, "doc.synctex.gz"), "rt", encoding="utf-8") as fh:
        split_out = fh.read()
    check("schedmap rewrite: handles schedmap-in-src + synctex-in-aux split",
          "(7,34:" in split_out and f"Input:7:{src_path}" in split_out,
          split_out)

    # (l) rewrite no-op when schedmap is missing
    tmp2 = tempfile.mkdtemp(prefix="texlib_bt_synctex_noop_")
    with gzip.open(os.path.join(tmp2, base + ".synctex.gz"), "wt", encoding="utf-8") as fh:
        fh.write(fake_synctex)
    b = TexlibBuilder()
    b._rewrite_synctex_for_schedmap(tmp2, tmp2, base)
    with gzip.open(os.path.join(tmp2, base + ".synctex.gz"), "rt", encoding="utf-8") as fh:
        unchanged = fh.read()
    check("schedmap rewrite: no-op when .schedmap is missing",
          unchanged == fake_synctex, "stream changed despite missing schedmap")
    check("schedmap rewrite: silent (no display) when schedmap is missing",
          b._displayed == "", b._displayed)

    # (m) diagnostic when schedmap is present but no grid-file Input record
    # is found in the synctex stream (the stale-builder / path-mismatch case).
    tmp3 = tempfile.mkdtemp(prefix="texlib_bt_synctex_diag_")
    src_path = os.path.join(tmp3, "doc.tex").replace("\\", "/")
    # synctex stream WITHOUT any grid-file Input record
    fake_no_grid = (
        f"SyncTeX Version:1\n"
        f"Input:1:{src_path}\n"
        f"!17\n{{0\n(1,5:1000,2000:5000,500,100\n}}0\nPostamble:\n"
    )
    with gzip.open(os.path.join(tmp3, base + ".synctex.gz"), "wt", encoding="utf-8") as fh:
        fh.write(fake_no_grid)
    with open(os.path.join(tmp3, base + ".schedmap"), "w", encoding="utf-8") as fh:
        fh.write("1|34\n")
    b = TexlibBuilder()
    b._rewrite_synctex_for_schedmap(tmp3, tmp3, base)
    check("schedmap rewrite: warns when grid Input record is missing",
          "no grid-file Input record" in b._displayed, b._displayed)
    with gzip.open(os.path.join(tmp3, base + ".synctex.gz"), "rt", encoding="utf-8") as fh:
        unchanged_diag = fh.read()
    check("schedmap rewrite: stream unchanged when grid Input is missing",
          unchanged_diag == fake_no_grid, "stream unexpectedly changed")

    # (n) diagnostic when schedmap is present but synctex.gz is missing
    tmp4 = tempfile.mkdtemp(prefix="texlib_bt_synctex_nosync_")
    with open(os.path.join(tmp4, base + ".schedmap"), "w", encoding="utf-8") as fh:
        fh.write("1|34\n")
    b = TexlibBuilder()
    b._rewrite_synctex_for_schedmap(tmp4, tmp4, base)
    check("schedmap rewrite: warns when .synctex.gz is missing",
          "no .synctex.gz" in b._displayed, b._displayed)

    # (n2) real-world xltabular case: every cell's raw line collapses to ONE
    # value absent from the schedmap (xltabular defers real box shipout to
    # end-of-file, so every typeset record lands on the grid file's own last
    # line -- see the docstring on _rewrite_synctex_for_schedmap). The Input
    # record must NOT be swapped in this case: doing so would repoint every
    # still-wrong grid-file line at the real source, turning an honestly
    # broken click target into a confidently WRONG one.
    tmp5 = tempfile.mkdtemp(prefix="texlib_bt_synctex_collapse_")
    src_path5 = os.path.join(tmp5, "doc.tex").replace("\\", "/")
    grid_path5 = os.path.join(tmp5, "doc_schedule_grid.tex").replace("\\", "/")
    # Every CELL record lands on grid_line 99 (the grid file's own EOF line),
    # which is NOT a key in the schedmap below -- but a source-file (fid=1)
    # record past boilerplate-after-line is ALSO present, mirroring the real
    # build this was modeled on (rewrites=0, boilerplate_rewrites>0), so the
    # early "nothing at all happened" return doesn't mask the cell-level
    # fallback path this case exists to test.
    fake_collapsed = (
        f"SyncTeX Version:1\n"
        f"Input:1:{src_path5}\n"
        f"Input:7:{grid_path5}\n"
        f"!17\n"
        f"{{0\n"
        f"(7,99:1000,2000:5000,500,100\n"
        f"h7,99:1500,2200:3000,400,80\n"
        f"(7,99:1000,5000:5000,500,100\n"
        f"(1,97:500,600:9000,500,0\n"
        f"}}0\n"
        f"Postamble:\n"
    )
    with gzip.open(os.path.join(tmp5, base + ".synctex.gz"), "wt", encoding="utf-8") as fh:
        fh.write(fake_collapsed)
    with open(os.path.join(tmp5, base + ".schedmap"), "w", encoding="utf-8") as fh:
        fh.write("# schedule source map v1\n")
        fh.write("# boilerplate-after-line: 96\n")
        fh.write("# boilerplate-target-line: 93\n")
        fh.write("4|34\n5|24\n6|38\n")  # grid_line 99 deliberately absent
    b = TexlibBuilder()
    b._rewrite_synctex_for_schedmap(tmp5, tmp5, base)
    with gzip.open(os.path.join(tmp5, base + ".synctex.gz"), "rt", encoding="utf-8") as fh:
        collapsed_out = fh.read()
    check("schedmap rewrite: Input record left pointing at the grid file "
          "when every cell line collapses to one value absent from the "
          "schedmap (honest fallback, not a confidently wrong source line)",
          f"Input:7:{grid_path5}" in collapsed_out
          and f"Input:7:{src_path5}" not in collapsed_out,
          collapsed_out)
    check("schedmap rewrite: reports the per-cell-unavailable fallback, "
          "not a false 'rewrote N records' success message",
          "per-cell SyncTeX could not be applied" in b._displayed, b._displayed)

    # ====================================================================== #
    # (o) Multi-pass orchestration sequences (simulation harness).
    #     These exercise the biber + rerun branches end-to-end by scripting
    #     the per-pass output and the aux files each pass produces.
    # ====================================================================== #
    ART = r"\documentclass{article}\begin{document}x\end{document}"
    RERUN = "Label(s) may have changed. Rerun to get cross-references right."

    # No bibliography, clean first pass -> exactly one engine run, no biber.
    cmds, _, _ = drive_builder(ART)
    check("seq: plain + clean -> 1 pass, no biber",
          heads(cmds) == ["pdflatex"], heads(cmds))

    # Cross-ref churn: rerun signal once, then clean -> two passes.
    cmds, _, _ = drive_builder(ART, steps=[{"out": RERUN}, {"out": ""}])
    check("seq: rerun signal then clean -> 2 passes",
          heads(cmds) == ["pdflatex", "pdflatex"], heads(cmds))

    # Persistent rerun signal -> capped at MAX_RERUNS (3) passes, never looping.
    cmds, _, _ = drive_builder(ART, steps=[{"out": RERUN}] * 6)
    check("seq: persistent rerun -> capped at 3 passes",
          heads(cmds) == ["pdflatex"] * 3, f"{len(cmds)} passes")

    # biblatex 'Please rerun LaTeX' is honored (the bug that shipped ?? refs).
    cmds, _, _ = drive_builder(
        ART, steps=[{"out": "Package biblatex Warning: Please rerun LaTeX."},
                    {"out": ""}])
    check("seq: 'Please rerun LaTeX' triggers another pass",
          heads(cmds) == ["pdflatex", "pdflatex"], heads(cmds))

    # Fresh bibliography: pass1 emits .bcf, biber runs, post-biber pass needs a
    # further rerun, then settles -> run, biber, run, run. Hash gets recorded.
    BCF = "<bcf>v1</bcf>"
    cmds, _, tmp = drive_builder(
        ART,
        steps=[
            {"write": {"doc.bcf": BCF}},                 # pass 1 wrote the .bcf
            {"write": {"doc.bbl": "bbl-v1"}},            # biber wrote the .bbl
            {"out": "Package biblatex Warning: Please rerun LaTeX."},
            {"out": ""},
        ])
    check("seq: fresh bib -> run, biber, run, run",
          heads(cmds) == ["pdflatex", "biber", "pdflatex", "pdflatex"], heads(cmds))
    check("seq: fresh bib -> .bcf hash recorded for next build",
          os.path.exists(os.path.join(tmp, "doc.bcf.texlibhash")))

    # The post-biber re-pass is unconditional (needed to read the new .bbl) even
    # if pass 1 reported nothing -> run, biber, run (then stops, output clean).
    cmds, _, _ = drive_builder(
        ART,
        steps=[{"write": {"doc.bcf": BCF}}, {"write": {"doc.bbl": "b"}}, {"out": ""}])
    check("seq: biber always forces one post-biber pass",
          heads(cmds) == ["pdflatex", "biber", "pdflatex"], heads(cmds))

    # Unchanged rebuild: .bcf + matching .bbl + hash already present -> biber and
    # its re-pass are BOTH skipped. This is the headline optimization.
    cmds, _, _ = drive_builder(
        ART,
        seed_files={"doc.bcf": BCF, "doc.bbl": "bbl-v1",
                    "doc.bcf.texlibhash": _fp(BCF)},
        steps=[{"out": ""}])
    check("seq: unchanged bib rebuild -> 1 pass, biber skipped",
          heads(cmds) == ["pdflatex"], heads(cmds))

    # Changed citations: stale hash -> biber re-runs even though a .bbl exists.
    cmds, _, _ = drive_builder(
        ART,
        seed_files={"doc.bcf": "<bcf>v2</bcf>", "doc.bbl": "bbl-v1",
                    "doc.bcf.texlibhash": _md5("<bcf>v1</bcf>")},
        steps=[{"out": ""}, {"out": ""}])
    check("seq: changed bib rebuild -> biber re-runs",
          "biber" in heads(cmds), heads(cmds))

    # biber + a bare undefined-references warning (no rerun hint) -> the loop
    # stops after the post-biber pass instead of churning to MAX_RERUNS.
    cmds, _, _ = drive_builder(
        ART,
        steps=[{"write": {"doc.bcf": BCF}}, {"write": {"doc.bbl": "b"}},
               {"out": "LaTeX Warning: There were undefined references."},
               {"out": ""}])
    check("seq: biber + bare undefined-refs -> no extra pass",
          heads(cmds) == ["pdflatex", "biber", "pdflatex"], heads(cmds))

    # ====================================================================== #
    # (p) biber change-detection helpers, exercised directly.
    # ====================================================================== #
    tmpc = tempfile.mkdtemp(prefix="texlib_cache_")
    bc = TexlibBuilder()
    bc.tex_dir = tmpc
    bc._aux_target = None
    check("cache: nothing present -> not current", not bc._biber_is_current("doc"))
    with open(os.path.join(tmpc, "doc.bcf"), "w") as fh:
        fh.write("X")
    check("cache: .bcf only (no .bbl) -> not current",
          not bc._biber_is_current("doc"))
    with open(os.path.join(tmpc, "doc.bbl"), "w") as fh:
        fh.write("b")
    check("cache: .bcf+.bbl but no hash -> not current",
          not bc._biber_is_current("doc"))
    bc._record_biber_hash("doc")
    check("cache: after record_biber_hash -> current",
          bc._biber_is_current("doc"))
    with open(os.path.join(tmpc, "doc.bcf"), "w") as fh:
        fh.write("Y")  # citations changed
    check("cache: .bcf changed -> not current",
          not bc._biber_is_current("doc"))

    # The fingerprint also tracks .bib datasource CONTENTS, so fixing a typo in
    # a bibliography entry (without touching a \cite) invalidates the cache.
    tmpb = tempfile.mkdtemp(prefix="texlib_bibdep_")
    bb = TexlibBuilder()
    bb.tex_dir = tmpb
    bb._aux_target = None
    with open(os.path.join(tmpb, "doc.bcf"), "w", encoding="utf-8") as fh:
        fh.write('<bcf:datasource type="file">refs.bib</bcf:datasource>')
    with open(os.path.join(tmpb, "doc.bbl"), "w", encoding="utf-8") as fh:
        fh.write("b")
    with open(os.path.join(tmpb, "refs.bib"), "w", encoding="utf-8") as fh:
        fh.write("@article{k, title={A}}")
    bb._record_biber_hash("doc")
    check("bibdep: after record -> current", bb._biber_is_current("doc"))
    with open(os.path.join(tmpb, "refs.bib"), "w", encoding="utf-8") as fh:
        fh.write("@article{k, title={B}}")  # edited .bib, same cite key
    check("bibdep: editing .bib invalidates the cache",
          not bb._biber_is_current("doc"))

    # An unresolvable datasource -> conservatively NOT current (re-run biber).
    tmpu = tempfile.mkdtemp(prefix="texlib_bibmiss_")
    bu = TexlibBuilder()
    bu.tex_dir = tmpu
    bu._aux_target = None
    with open(os.path.join(tmpu, "doc.bcf"), "w", encoding="utf-8") as fh:
        fh.write('<bcf:datasource type="file">nowhere.bib</bcf:datasource>')
    with open(os.path.join(tmpu, "doc.bbl"), "w", encoding="utf-8") as fh:
        fh.write("b")
    with open(os.path.join(tmpu, "doc.bcf.texlibhash"), "w", encoding="utf-8") as fh:
        fh.write("anything")
    check("bibdep: unresolvable .bib -> not current (safe re-run)",
          not bu._biber_is_current("doc"))
    with open(os.path.join(tmpu, "extra.bib"), "w", encoding="utf-8") as fh:
        fh.write("x")
    check("bibdep: datasource resolved with added .bib extension",
          bu._resolve_datasource("extra") is not None)
    check("bibdep: datasource resolved by exact name",
          bu._resolve_datasource("extra.bib") is not None)
    check("bibdep: genuinely missing datasource -> None",
          bu._resolve_datasource("ghost.bib") is None)

    # ====================================================================== #
    # (q) biber command construction (aux-directory routing).
    # ====================================================================== #
    bcmd = TexlibBuilder()
    bcmd.tex_dir = os.path.join(tempfile.gettempdir(), "texlib_q_src")
    bcmd._aux_target = None
    check("biber-cmd: no aux routing -> ['biber', jobname]",
          bcmd._biber_command("doc") == ["biber", "doc"],
          bcmd._biber_command("doc"))
    bcmd._aux_target = os.path.join(tempfile.gettempdir(), "texlib_q_aux")
    qcmd = bcmd._biber_command("doc")
    check("biber-cmd: aux routing -> --input/--output-directory + jobname",
          qcmd[0] == "biber" and qcmd[-1] == "doc"
          and any(str(a).startswith("--input-directory=") for a in qcmd)
          and any(str(a).startswith("--output-directory=") for a in qcmd),
          qcmd)

    # ====================================================================== #
    # (r) aux_directory resolution.
    # ====================================================================== #
    ab = TexlibBuilder()
    ab.tex_root = os.path.join(tempfile.gettempdir(), "proj", "doc.tex")
    proj = os.path.join(tempfile.gettempdir(), "proj")
    ab.aux_directory = ""
    check("aux-dir: empty -> None (routing disabled)",
          ab._resolve_aux_directory(proj) is None)
    ab.aux_directory = "<<root>>"
    check("aux-dir: <<root>> -> None", ab._resolve_aux_directory(proj) is None)
    ab.aux_directory = "<<temp>>"
    tdir = ab._resolve_aux_directory(proj)
    check("aux-dir: <<temp>> -> existing temp subdir",
          bool(tdir) and os.path.isdir(tdir), tdir)
    abs_dir = os.path.join(tempfile.gettempdir(), "texlib_abs_aux")
    ab.aux_directory = abs_dir
    check("aux-dir: absolute path passed through",
          ab._resolve_aux_directory(proj) == abs_dir,
          ab._resolve_aux_directory(proj))
    ab.aux_directory = "build"
    check("aux-dir: relative path joined onto tex dir",
          ab._resolve_aux_directory(proj) == os.path.normpath(
              os.path.join(proj, "build")),
          ab._resolve_aux_directory(proj))

    # ====================================================================== #
    # (r2) _set_aux_target resolves the aux dir onto the PER-BUILD instance
    # (self._aux_target). The runner injects THAT into each engine subprocess's
    # own env as TEXLIB_AUX_DIR (so raw-Lua-io.open engine scratch follows the
    # routing) rather than a shared os.environ -- concurrent builds of different
    # documents must not race one global. Here we assert the per-instance
    # resolution; the per-subprocess env injection is covered in
    # test_texlib_runner.py ("aux env: ...injected into ITS subprocess env").
    # ====================================================================== #
    ab.aux_directory = ""
    check("aux-dir: _aux_target is None when routing disabled",
          ab._set_aux_target(proj) is None and ab._aux_target is None,
          repr(ab._aux_target))
    ab.aux_directory = abs_dir
    check("aux-dir: _aux_target matches the resolved aux dir",
          ab._set_aux_target(proj) == abs_dir and ab._aux_target == abs_dir,
          repr(ab._aux_target))

    # ====================================================================== #
    # (s) _force_remove also clears a ReadOnly file (the other Errno-13 cause).
    # ====================================================================== #
    tmpr = tempfile.mkdtemp(prefix="texlib_ro_")
    ro = os.path.join(tmpr, "doc.synctex")
    with open(ro, "w") as fh:
        fh.write("x")
    os.chmod(ro, 0o444)  # read-only
    TexlibBuilder._force_remove(ro)
    check("_force_remove: read-only file is deleted", not os.path.exists(ro), ro)

    # ====================================================================== #
    # (u) biber hash is recorded AFTER the final pass, not mid-build.
    #     Regression: if the post-biber pass rewrites the .bcf, recording the
    #     hash right after biber captures the stale (pre-final) .bcf, so the
    #     NEXT build sees "not current" and re-runs biber needlessly. Recording
    #     in _postprocess (after the last pass settled the .bcf) fixes it.
    # ====================================================================== #
    BCF_V1 = "<bcf>v1</bcf>"
    BCF_SETTLED = "<bcf>v1-settled</bcf>"   # post-biber pass rewrote the .bcf
    _, _, tmp = drive_builder(
        ART,
        steps=[
            {"write": {"doc.bcf": BCF_V1}},              # pass 1 wrote the .bcf
            {"write": {"doc.bbl": "bbl-v1"}},            # biber wrote the .bbl
            {"out": "Package biblatex Warning: Please rerun LaTeX.",
             "write": {"doc.bcf": BCF_SETTLED}},         # post-biber pass settles .bcf
            {"out": ""},                                 # final pass, clean
        ])
    nb = TexlibBuilder()
    nb.tex_dir = tmp
    nb._aux_target = None
    check("biber-timing: recorded hash matches the FINAL .bcf "
          "(no spurious re-run next build)",
          nb._biber_is_current("doc"),
          "hash recorded against pre-final .bcf -> next build re-runs biber")

    # ====================================================================== #
    # (v) PDF split honoring a <base>.spl 'split_page=N' signal.
    # ====================================================================== #
    try:
        from pypdf import PdfReader, PdfWriter
        _have_pypdf = True
    except ImportError:
        _have_pypdf = False

    if _have_pypdf:
        tmps = tempfile.mkdtemp(prefix="texlib_spl_")

        def _blank_pdf(path, pages):
            w = PdfWriter()
            for _ in range(pages):
                w.add_blank_page(width=72, height=72)
            with open(path, "wb") as fh:
                w.write(fh)
            w.close()

        bp = os.path.join(tmps, "doc")
        _blank_pdf(bp + ".pdf", 5)
        with open(bp + ".spl", "w", encoding="utf-8") as fh:
            fh.write("split_page=2")
        sb = TexlibBuilder(); sb.tex_dir = tmps; sb._aux_target = None
        sb._split_pdf_if_signaled(bp)
        check("split: _Exam.pdf gets the first 2 pages",
              os.path.exists(bp + "_Exam.pdf")
              and len(PdfReader(bp + "_Exam.pdf").pages) == 2)
        check("split: _Solutions.pdf gets the remaining 3 pages",
              os.path.exists(bp + "_Solutions.pdf")
              and len(PdfReader(bp + "_Solutions.pdf").pages) == 3)
        check("split: .spl signal consumed", not os.path.exists(bp + ".spl"))

        bp2 = os.path.join(tmps, "doc2")
        _blank_pdf(bp2 + ".pdf", 3)
        with open(bp2 + ".spl", "w", encoding="utf-8") as fh:
            fh.write("split_page=9")   # out of range
        sb2 = TexlibBuilder(); sb2.tex_dir = tmps; sb2._aux_target = None
        sb2._split_pdf_if_signaled(bp2)
        check("split: out-of-range page -> no split files",
              not os.path.exists(bp2 + "_Exam.pdf"))
        check("split: out-of-range page -> warning shown",
              "out of range" in sb2._displayed, sb2._displayed)

        # aux routing active + .spl only in the aux dir (copy-back failed) -> warn.
        auxd = tempfile.mkdtemp(prefix="texlib_spl_aux_")
        bp3 = os.path.join(tmps, "doc3")
        with open(os.path.join(auxd, "doc3.spl"), "w", encoding="utf-8") as fh:
            fh.write("split_page=1")
        sb3 = TexlibBuilder(); sb3.tex_dir = tmps; sb3._aux_target = auxd
        sb3._split_pdf_if_signaled(bp3)
        check("split: warns when .spl is in aux but not copied back",
              "not copied back" in sb3._displayed, sb3._displayed)

        # ================================================================== #
        # (v2) Multi-copy PDF slicing honoring a <base>.vmap sidecar
        # (autoexam_run_versions / \AutoExamVmapRecord).
        # ================================================================== #
        tmpv = tempfile.mkdtemp(prefix="texlib_vmap_")
        bpv = os.path.join(tmpv, "doc")
        _blank_pdf(bpv + ".pdf", 6)
        with open(bpv + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\nB|stu|3\nA|sol|5\n")
        vb = TexlibBuilder(); vb.tex_dir = tmpv; vb.base_name = "doc"
        vb._aux_target = None
        vb._slice_versions_from_vmap(tmpv, bpv)
        check("vmap: doc_A.pdf gets pages 1-2",
              os.path.exists(bpv + "_A.pdf")
              and len(PdfReader(bpv + "_A.pdf").pages) == 2)
        check("vmap: doc_B.pdf gets pages 3-4",
              os.path.exists(bpv + "_B.pdf")
              and len(PdfReader(bpv + "_B.pdf").pages) == 2)
        check("vmap: doc_A_solutions.pdf gets the last 2 pages (no next record)",
              os.path.exists(bpv + "_A_solutions.pdf")
              and len(PdfReader(bpv + "_A_solutions.pdf").pages) == 2)
        check("vmap: .vmap consumed after slicing", not os.path.exists(bpv + ".vmap"))

        # No \versions{} (empty version label) -> no "_" version segment, just
        # <base>.pdf / <base>_solutions.pdf.
        tmpv2 = tempfile.mkdtemp(prefix="texlib_vmap_")
        bpv2 = os.path.join(tmpv2, "doc")
        _blank_pdf(bpv2 + ".pdf", 4)
        with open(bpv2 + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("|stu|1\n|sol|3\n")
        vb2 = TexlibBuilder(); vb2.tex_dir = tmpv2; vb2.base_name = "doc"
        vb2._aux_target = None
        vb2._slice_versions_from_vmap(tmpv2, bpv2)
        check("vmap: empty version label -> doc.pdf (student, no suffix)",
              os.path.exists(bpv2 + ".pdf") and len(PdfReader(bpv2 + ".pdf").pages) == 4,
              "the ORIGINAL combined doc.pdf must survive untouched")
        check("vmap: empty version label -> doc_solutions.pdf",
              os.path.exists(bpv2 + "_solutions.pdf")
              and len(PdfReader(bpv2 + "_solutions.pdf").pages) == 2)

        # A record whose computed range is out of bounds is skipped, not fatal.
        tmpv3 = tempfile.mkdtemp(prefix="texlib_vmap_")
        bpv3 = os.path.join(tmpv3, "doc")
        _blank_pdf(bpv3 + ".pdf", 2)
        with open(bpv3 + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\nB|stu|9\n")   # B starts past the PDF's own length
        vb3 = TexlibBuilder(); vb3.tex_dir = tmpv3; vb3.base_name = "doc"
        vb3._aux_target = None
        vb3._slice_versions_from_vmap(tmpv3, bpv3)
        check("vmap: valid record still sliced when a later one is out of range",
              os.path.exists(bpv3 + "_A.pdf"))
        check("vmap: out-of-range record skipped, not fatal",
              not os.path.exists(bpv3 + "_B.pdf") and "out of" in vb3._displayed,
              vb3._displayed)

        # No .vmap present at all (the common single-copy build) -> silent no-op.
        tmpv4 = tempfile.mkdtemp(prefix="texlib_vmap_")
        bpv4 = os.path.join(tmpv4, "doc")
        _blank_pdf(bpv4 + ".pdf", 2)
        vb4 = TexlibBuilder(); vb4.tex_dir = tmpv4; vb4.base_name = "doc"
        vb4._aux_target = None
        vb4._slice_versions_from_vmap(tmpv4, bpv4)
        check("vmap: no .vmap file -> no-op, no error",
              vb4._displayed == "", vb4._displayed)

        # aux routing active + .vmap only in the aux dir (the normal case,
        # since \write is kpathsea-routed like .aux/.log) -> still found and sliced.
        tmpv5 = tempfile.mkdtemp(prefix="texlib_vmap_")
        auxv5 = tempfile.mkdtemp(prefix="texlib_vmap_aux_")
        bpv5 = os.path.join(tmpv5, "doc")
        _blank_pdf(bpv5 + ".pdf", 2)
        with open(os.path.join(auxv5, "doc.vmap"), "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\n")
        vb5 = TexlibBuilder(); vb5.tex_dir = tmpv5; vb5.base_name = "doc"
        vb5._aux_target = auxv5
        vb5._slice_versions_from_vmap(tmpv5, bpv5)
        check("vmap: found in the aux dir when aux routing is active",
              os.path.exists(bpv5 + "_A.pdf"))

        # ================================================================== #
        # (v3) External-Python fallback plumbing. Under Sublime the in-process
        # `import pypdf` fails, so slicing/splitting is delegated to
        # texlib_pdfpost.py run under an external Python. Exercise that exact
        # path here (the CLI + interpreter discovery), since the tests above
        # only cover the in-process branch.
        # ================================================================== #
        import subprocess as _sp
        pdfpost = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "texlib_pdfpost.py")
        check("pdfpost: helper module deployed next to the builder",
              os.path.exists(pdfpost), pdfpost)

        # _external_python() must find a pypdf-capable interpreter (the one
        # running this test qualifies), and it must be cached.
        TexlibBuildCore._ext_python_cache = False  # reset (cache lives on the core)
        eb = TexlibBuilder()
        extpy = eb._external_python()
        check("external python: a pypdf-capable interpreter is found",
              bool(extpy), extpy)
        check("external python: result is cached",
              getattr(TexlibBuildCore, "_ext_python_cache", False) == extpy)

        # The CLI is what the fallback actually invokes: run it via subprocess
        # and confirm it slices + emits JSON, just as Sublime's build would.
        tmpc = tempfile.mkdtemp(prefix="texlib_cli_")
        bpc = os.path.join(tmpc, "doc")
        _blank_pdf(bpc + ".pdf", 6)
        with open(bpc + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\nB|stu|3\nA|sol|5\n")
        cli = _sp.run(
            (extpy or [sys.executable]) +
            [pdfpost, "slice", bpc + ".vmap", bpc + ".pdf", tmpc, "doc"],
            capture_output=True, text=True)
        check("pdfpost CLI: exit 0", cli.returncode == 0, cli.stderr)
        check("pdfpost CLI: sliced doc_A/doc_B/doc_A_solutions via subprocess",
              os.path.exists(bpc + "_A.pdf")
              and os.path.exists(bpc + "_B.pdf")
              and os.path.exists(bpc + "_A_solutions.pdf"))
        _cli_out = json.loads(cli.stdout or "{}")
        check("pdfpost CLI: JSON lists the produced files",
              sorted(_cli_out.get("produced", []))
              == ["doc_A.pdf", "doc_A_solutions.pdf", "doc_B.pdf"],
              _cli_out.get("produced"))

        # _run_pdfpost end to end (in-process branch here) returns produced.
        rb = TexlibBuilder(); rb.tex_dir = tmpc
        _blank_pdf(bpc + ".pdf", 6)
        with open(bpc + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\nB|stu|4\n")
        _produced, _msgs = rb._run_pdfpost(
            "slice", bpc + ".vmap", bpc + ".pdf", tmpc)
        check("_run_pdfpost: returns produced names",
              sorted(_produced) == ["doc_A.pdf", "doc_B.pdf"], _produced)
    else:
        print("  SKIP  pypdf not installed -- PDF split/vmap tests skipped")

    # ====================================================================== #
    # (w) gradebook xlsx -> report-view CSV conversion (report-card class).
    # ====================================================================== #
    import zipfile as _zip
    MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    PREL = "http://schemas.openxmlformats.org/package/2006/relationships"
    OREL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    def _mini_xlsx(path):
        """A 2-sheet workbook: Roster + Report View. The Report View 'Score'
        cell is a FORMULA carrying a cached <v>, and the name cell is a shared
        string -- so the test exercises both the cached-value and shared-string
        read paths."""
        wb = (f'<workbook xmlns="{MAIN}" xmlns:r="{OREL}"><sheets>'
              '<sheet name="Roster" sheetId="1" r:id="rId1"/>'
              '<sheet name="Report View" sheetId="2" r:id="rId2"/>'
              '</sheets></workbook>')
        rels = (f'<Relationships xmlns="{PREL}">'
                f'<Relationship Id="rId1" Type="{OREL}/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                f'<Relationship Id="rId2" Type="{OREL}/worksheet" '
                'Target="worksheets/sheet2.xml"/></Relationships>')
        sst = (f'<sst xmlns="{MAIN}" count="1" uniqueCount="1">'
               '<si><t>Tester</t></si></sst>')
        sheet1 = (f'<worksheet xmlns="{MAIN}"><sheetData>'
                  '<row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c>'
                  '</row></sheetData></worksheet>')
        sheet2 = (f'<worksheet xmlns="{MAIN}"><sheetData>'
                  '<row r="1">'
                  '<c r="A1" t="inlineStr"><is><t>Name</t></is></c>'
                  '<c r="B1" t="inlineStr"><is><t>Homework Avg. Weight</t></is></c>'
                  '<c r="C1" t="inlineStr"><is><t>Homework Avg. Score</t></is></c>'
                  '<c r="D1" t="inlineStr"><is><t>Current Total</t></is></c>'
                  '</row>'
                  '<row r="2">'
                  '<c r="A2" t="s"><v>0</v></c>'
                  '<c r="B2"><v>15</v></c>'
                  '<c r="C2"><f>AVERAGE(Roster!B2:D2)</f><v>85</v></c>'
                  '<c r="D2"><v>86</v></c>'
                  '</row></sheetData></worksheet>')
        ct = (f'<Types xmlns="{PREL.replace("relationships","content-types")}">'
              '<Default Extension="rels" ContentType="application/vnd.'
              'openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/></Types>')
        root_rels = (f'<Relationships xmlns="{PREL}"><Relationship Id="rIdW" '
                     f'Type="{OREL}/officeDocument" Target="xl/workbook.xml"/>'
                     '</Relationships>')
        with _zip.ZipFile(path, "w") as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("_rels/.rels", root_rels)
            z.writestr("xl/workbook.xml", wb)
            z.writestr("xl/_rels/workbook.xml.rels", rels)
            z.writestr("xl/sharedStrings.xml", sst)
            z.writestr("xl/worksheets/sheet1.xml", sheet1)
            z.writestr("xl/worksheets/sheet2.xml", sheet2)

    tmpg = tempfile.mkdtemp(prefix="texlib_gb_")
    xlsx = os.path.join(tmpg, "gradebook.xlsx")
    _mini_xlsx(xlsx)

    # _xlsx_rows picks "Report View" and reads cached values + shared strings.
    rows = TexlibBuilder._xlsx_rows(xlsx, GRADEBOOK_SHEETS)
    check("gradebook: picks the Report View sheet (not Roster)",
          rows and rows[0] == ["Name", "Homework Avg. Weight",
                               "Homework Avg. Score", "Current Total"], rows)
    check("gradebook: shared string read for the name cell",
          len(rows) > 1 and rows[1][0] == "Tester", rows)
    check("gradebook: cached formula value read (Score=85, not the formula)",
          len(rows) > 1 and rows[1][2] == "85", rows)
    check("gradebook: plain numeric cell read (Current Total=86)",
          len(rows) > 1 and rows[1][3] == "86", rows)

    # _convert_gradebooks writes a sibling CSV for a report-card document.
    gb = TexlibBuilder()
    gb.tex_dir = tmpg
    gb._convert_gradebooks(r"\documentclass{report-card}\begin{document}\end{document}")
    csv_out = os.path.join(tmpg, "gradebook.csv")
    check("gradebook: report-card doc -> sibling gradebook.csv written",
          os.path.exists(csv_out), csv_out)
    if os.path.exists(csv_out):
        with open(csv_out, encoding="utf-8") as fh:
            text = fh.read()
        check("gradebook: CSV contains the student row",
              "Tester" in text and "85" in text and "86" in text, text)

    # Non-gradebook class -> no conversion (article must not get a CSV).
    tmgn = tempfile.mkdtemp(prefix="texlib_gbn_")
    _mini_xlsx(os.path.join(tmgn, "gradebook.xlsx"))
    gn = TexlibBuilder()
    gn.tex_dir = tmgn
    gn._convert_gradebooks(r"\documentclass{article}\begin{document}\end{document}")
    check("gradebook: non-report-card class -> no CSV emitted",
          not os.path.exists(os.path.join(tmgn, "gradebook.csv")))

    # report-card is in the lualatex-forced set (it uses \directlua).
    cmds, _ = run_builder(
        r"\documentclass{report-card}\begin{document}\end{document}",
        engine="pdflatex")
    check("report-card + pdflatex -> overridden to lualatex",
          bool(cmds) and cmds[0][0][0] == "lualatex", cmds)

    # (bank fragment) no \documentclass but \begin{problem} blocks -> a
    # synthesized quiz.cls \printbankcatalog harness, forced lualatex,
    # --jobname pinned to base_name so copy-back needs no changes.
    bank_src = r"\begin{problem}{sample}[topic=x]Stem text.\end{problem}"
    cmds, disp = run_builder(bank_src, engine="pdflatex")
    check("bank fragment -> forced lualatex",
          bool(cmds) and cmds[0][0][0] == "lualatex", cmds)
    check("bank fragment -> --jobname=doc",
          bool(cmds) and "--jobname=doc" in cmds[0][0], cmds)
    arg = cmds[0][0][-1] if cmds else ""
    check("bank fragment -> \\loadbank{doc.tex} in synthesized arg",
          r"\loadbank{doc.tex}" in arg, arg)
    check("bank fragment -> \\printbankcatalog in synthesized arg",
          r"\printbankcatalog" in arg, arg)
    check("bank fragment -> quiz.cls harness synthesized",
          r"\documentclass{quiz}" in arg, arg)
    check("bank fragment -> detection message shown",
          "printbankcatalog listing" in disp, repr(disp))

    # A real document that happens to define a \begin{problem} inline must NOT
    # be treated as a bank fragment -- \documentclass wins the check.
    cmds, _ = run_builder(
        r"\documentclass{quiz}\begin{document}"
        r"\begin{problem}{sample}Stem\end{problem}"
        r"\end{document}"
    )
    check("real document with inline \\begin{problem} -> normal build",
          bool(cmds) and cmds[0][0][-1] == "doc.tex", cmds)

    # ====================================================================== #
    # (x) Publish step: shareable copies + desktop shortcut, driven by the
    #     <base>.pubmeta sidecar course-metadata.sty writes for a publishable
    #     class (syllabus, schedule). Shortcut/clipboard are stubbed so tests
    #     never touch the real desktop or clipboard.
    # ====================================================================== #
    # _coded_basename derivation.
    check("coded: section present -> Course.Section_Term",
          TexlibBuilder._coded_basename("Math 181", "1001", "Fall 2026")
          == "Math181.1001_Fall2026")
    check("coded: no section -> Course_Term (no stray dot)",
          TexlibBuilder._coded_basename("Math 181", "", "Fall 2026")
          == "Math181_Fall2026")
    check("coded: filename-illegal chars stripped",
          TexlibBuilder._coded_basename("Math/181", "10:01", "Fall 2026")
          == "Math181.1001_Fall2026")

    # _read_pubmeta: parse + consume, checked in the aux dir first.
    tmpp = tempfile.mkdtemp(prefix="texlib_pub_")
    auxp = tempfile.mkdtemp(prefix="texlib_pub_aux_")
    with open(os.path.join(auxp, "doc.pubmeta"), "w", encoding="utf-8") as fh:
        fh.write("kind=syllabus\ngeneric=Syllabus\nnoun=Syllabus\n"
                 "course=Math 181\nsection=1001\nterm=Fall 2026\npublish-name=\n")
    pb = TexlibBuilder(); pb.tex_dir = tmpp; pb.base_name = "doc"
    pb._aux_target = auxp
    meta = pb._read_pubmeta(tmpp)
    check("pubmeta: parsed key=value map",
          bool(meta) and meta.get("course") == "Math 181"
          and meta.get("term") == "Fall 2026", meta)
    check("pubmeta: sidecar consumed (deleted) after read",
          not os.path.exists(os.path.join(auxp, "doc.pubmeta")))
    check("pubmeta: absent -> None", pb._read_pubmeta(tmpp) is None)

    def _publish_case(base, kind, generic, noun, course, section, term,
                      settings=None, publish_name=""):
        d = tempfile.mkdtemp(prefix="texlib_pub_")
        with open(os.path.join(d, base + ".pdf"), "wb") as fh:
            fh.write(b"%PDF-1.5 test")
        with open(os.path.join(d, base + ".pubmeta"), "w", encoding="utf-8") as fh:
            fh.write(f"kind={kind}\ngeneric={generic}\nnoun={noun}\n"
                     f"course={course}\nsection={section}\nterm={term}\n"
                     f"publish-name={publish_name}\n")
        b = TexlibBuilder(); b.tex_dir = d; b.base_name = base
        b._aux_target = None
        if settings is not None:
            b.builder_settings = settings
        shortcuts, clips = [], []
        b._make_desktop_shortcut = lambda label, target: (
            shortcuts.append((label, os.path.basename(target))) or True)
        b._copy_to_clipboard = lambda text: clips.append(os.path.basename(text))
        b._publish_shareable_copies(d, os.path.join(d, base))
        pdfs = sorted(f for f in os.listdir(d) if f.endswith(".pdf"))
        return d, pdfs, shortcuts, clips, b._displayed

    # Distinct source/generic names -> both copies + shortcut + clipboard.
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "schedule", "schedule", "Tentative Schedule", "Schedule",
        "Math 181", "1001", "Fall 2026")
    check("publish: coded + generic copies made (source name distinct)",
          "Math181.1001_Fall2026.pdf" in pdfs
          and "Tentative Schedule.pdf" in pdfs and "schedule.pdf" in pdfs, pdfs)
    check("publish: shortcut label is '<course> <term> <noun>' -> coded copy",
          shortcuts == [("Math 181 Fall 2026 Schedule",
                         "Math181.1001_Fall2026.pdf")], shortcuts)
    check("publish: shareable path put on the clipboard",
          clips == ["Math181.1001_Fall2026.pdf"], clips)
    check("publish: sidecar consumed", not os.path.exists(
        os.path.join(d, "schedule.pubmeta")))

    # Case-only collision (source syllabus.pdf vs generic Syllabus.pdf): the
    # source must survive and the coded copy must still be made. (On a case-
    # insensitive volume the generic copy is skipped as the same file; on a
    # case-sensitive one both exist -- either way these invariants hold.)
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "syllabus", "syllabus", "Syllabus", "Syllabus",
        "Math 181", "1001", "Fall 2026")
    check("publish: source PDF preserved on case-only generic collision",
          "syllabus.pdf" in pdfs, pdfs)
    check("publish: coded copy still made alongside the collision",
          "Math181.1001_Fall2026.pdf" in pdfs, pdfs)
    check("publish: no spurious 'could not write' on collision",
          "could not write" not in disp, disp)

    # Sanity guard: term unset -> no copies, explanatory message.
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "doc", "syllabus", "Syllabus", "Syllabus", "Math 181", "1001", "")
    check("publish: guard skips copies when term is unset",
          pdfs == ["doc.pdf"] and not shortcuts, pdfs)
    check("publish: guard explains the skip", "publish skipped" in disp, disp)

    # publish-name override names the coded copy.
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "doc", "syllabus", "Syllabus", "Syllabus", "Math 181", "1001",
        "Fall 2026", publish_name="M181-Syllabus-F26")
    check("publish: publish-name overrides the coded basename",
          "M181-Syllabus-F26.pdf" in pdfs, pdfs)

    # Disabled via builder_settings -> sidecar still consumed, no copies made.
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "doc", "syllabus", "Syllabus", "Syllabus", "Math 181", "1001",
        "Fall 2026", settings={"publish_shareable_copies": False})
    check("publish: disabled -> only source PDF, sidecar still consumed",
          pdfs == ["doc.pdf"]
          and not os.path.exists(os.path.join(d, "doc.pubmeta")), pdfs)

    # _setting_on precedence: builder_settings > env > default.
    so = TexlibBuilder()
    so.builder_settings = {"k": False}
    check("setting: builder_settings wins over default",
          so._setting_on("k", "TEXLIB_UNUSED_ENV", True) is False)
    so.builder_settings = {}
    check("setting: default applies when unset and no env",
          so._setting_on("k", "TEXLIB_UNUSED_ENV_XYZ", True) is True)
    os.environ["TEXLIB_TESTTOGGLE"] = "off"
    try:
        check("setting: env override 'off' -> False",
              so._setting_on("k", "TEXLIB_TESTTOGGLE", True) is False)
    finally:
        os.environ.pop("TEXLIB_TESTTOGGLE", None)

    # _human_size formatting.
    check("human-size: bytes", TexlibBuilder._human_size(512) == "512 B")
    check("human-size: KB", TexlibBuilder._human_size(2048) == "2.0 KB")

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return _FAIL


if __name__ == "__main__":
    sys.exit(main())
