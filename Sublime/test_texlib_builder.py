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

from texlib_builder import TexlibBuilder  # noqa: E402


# --- 2. Harness ------------------------------------------------------------

def run_builder(doc_src, options=None, engine="pdflatex"):
    """Build a TexlibBuilder over a synthetic document; return (commands, display).

    `commands` is the list of (command_list, message) tuples the builder would
    run. We feed exit status 0 back for every command (so no rerun fires, since
    self.out is empty).
    """
    tmp = tempfile.mkdtemp(prefix="texlib_bt_")
    tex_path = os.path.join(tmp, "doc.tex")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(doc_src)

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

    # (f) autoexam + allversions -> one build per version, jobnames + \def\Version
    cmds, disp = run_builder(
        r"\documentclass{autoexam}\versions{A, B, C}\begin{document}x\end{document}",
        options=["--texlib-mode=allversions"])
    check("allversions -> 3 builds", len(cmds) == 3, f"{len(cmds)} builds")
    jobnames = [
        next((a for a in c[0] if str(a).startswith("--jobname=")), None) for c in cmds
    ]
    check("allversions -> jobnames doc_A / doc_B / doc_C",
          jobnames == ["--jobname=doc_A", "--jobname=doc_B", "--jobname=doc_C"],
          jobnames)
    check("allversions -> \\def\\Version{A} in first build",
          bool(cmds) and r"\def\Version{A}" in cmds[0][0][-1],
          cmds[0][0][-1] if cmds else "")

    # (g) \examversions alias also parsed
    cmds, _ = run_builder(
        r"\documentclass{autoexam}\examversions{A,B}\begin{document}x\end{document}",
        options=["--texlib-mode=allversions"])
    check("\\examversions alias -> 2 builds", len(cmds) == 2, f"{len(cmds)} builds")

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

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return _FAIL


if __name__ == "__main__":
    sys.exit(main())
