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

from _testkit import install_native_builder  # noqa: E402
TexlibBuilder = install_native_builder()
from texlib_build import (  # noqa: E402  (native core)
    GRADEBOOK_SHEETS, MAX_RERUNS, STATE_ONLY_RERUNS, TexlibBuildCore, _surname,
)
import texlib_build as _tb  # noqa: E402  (module handle: stubbing in case (y))


# --- 2. Harness ------------------------------------------------------------

# The builder object the last harness call drove, for the few assertions that
# are about host-facing STATE rather than the command stream.
_LAST_BUILDER = [None]


def run_builder(doc_src, options=None, engine="pdflatex", aux_files=None):
    """Build a TexlibBuilder over a synthetic document; return (commands, display).

    `commands` is the list of (command_list, message) tuples the builder would
    run. We feed exit status 0 back for every command (so no rerun fires, since
    self.out is empty).

    `aux_files` (optional) maps filename -> contents to pre-create in the tex
    dir before building -- used to exercise the biber change-detection path
    (e.g. a doc.bcf / doc.bbl / doc.bcf.texlibhash trio).

    With no `options`, the mode is `base', NOT `default'. Every case that
    passes none is about the single-compile path -- engine selection, the
    biber cache, the rerun loop -- and `default' now fans out into a whole
    variant set, which would drown those assertions in unrelated commands.
    The fan-out has its own cases below (see the variant-plan section); do not
    "fix" a fan-out test by relying on this helper's default.
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
    # `base', not `default': these harnesses exercise the single-compile path
    # and `default' now fans out into a variant set. See run_builder's docstring.
    b.options = list(options if options is not None
                     else ["--texlib-mode=base"])
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
    # `base', not `default': these harnesses exercise the single-compile path
    # and `default' now fans out into a variant set. See run_builder's docstring.
    b.options = list(options if options is not None
                     else ["--texlib-mode=base"])
    b.out = ""
    _LAST_BUILDER[0] = b

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

    # (j1b) The variant fan-out. `default' is no longer one compile: it builds
    # the base, reads the .buildmeta sidecar the base just wrote, and dispatches
    # one compile per planned variant plus a tagged twin of each. These cases
    # replace the incidental coverage the base-mode repoint above removed.
    PSET = r"\documentclass{pset}\begin{document}x\end{document}"

    def _args(cmds):
        return [c[0][-1] for c in cmds]

    # No sidecar (a class that loads no TeXLib build package, or a build that
    # died before \end{document}): plan nothing, say so, still pair the tagged
    # twin -- that pairing predates the fan-out and is what `accessible' did.
    cmds, disp = run_builder(PSET, options=["--texlib-mode=default"])
    check("fan-out/no sidecar -> base + its tagged twin only",
          len(cmds) == 3, f"{len(cmds)} builds: {_args(cmds)}")
    check("fan-out/no sidecar -> says why it planned nothing",
          "no .buildmeta sidecar" in disp, repr(disp[:300]))

    # A sidecar declaring all three, with solution content present.
    FULL_META = ("variants=student,solutions,instructor\n"
                 "has-solutions=1\nhas-rubric=1\n"
                 "has-commonerrors=0\nhas-partsolution=0\n")
    cmds, disp = run_builder(PSET, options=["--texlib-mode=default"],
                             aux_files={"doc.buildmeta": FULL_META})
    args = " ".join(_args(cmds))
    check("fan-out -> student variant compiled",
          r"\def\StudentMode{}" in args, args[:400])
    check("fan-out -> solutions variant is the STUDENT key (\\ShowKey)",
          r"\def\ShowKey{}" in args, args[:400])
    check("fan-out -> instructor variant carries rubric + \\InstructorMode",
          r"\def\ShowRubric{}" in args and r"\def\InstructorMode{}" in args,
          args[:400])
    # Count output DIRECTORIES, not commands: every variant is a fixed 2-pass
    # build, so counting commands double-counts each one.
    a11y_dirs = {c for cmd in cmds for c in cmd[0]
                 if str(c).startswith("-output-directory=")
                 and str(c).endswith("-a11y")}
    check("fan-out -> tagged twin for the base and each variant",
          len(a11y_dirs) == 4, sorted(a11y_dirs))

    # Same declaration, but the document turns out to hold no solutions: the
    # answer-bearing variants would be byte-identical to the base.
    BARE_META = ("variants=student,solutions,instructor\n"
                 "has-solutions=0\nhas-rubric=0\n"
                 "has-commonerrors=0\nhas-partsolution=0\n")
    cmds, disp = run_builder(PSET, options=["--texlib-mode=default"],
                             aux_files={"doc.buildmeta": BARE_META})
    args = " ".join(_args(cmds))
    check("prune -> no solutions content means no \\ShowKey compile",
          r"\def\ShowKey{}" not in args, args[:400])
    check("prune -> student variant still built (it does not need solutions)",
          r"\def\StudentMode{}" in args, args[:400])
    check("prune -> the omission is REPORTED, not silent",
          "no solution content" in disp, repr(disp[:400]))

    # A document can pin its own set with \metasetup{build-variants=...}, which
    # texlib-build.sty writes into the sidecar's variants= line -- so the
    # planner needs no second discovery mechanism for it.
    PINNED_META = ("variants=student\nhas-solutions=1\nhas-rubric=1\n"
                   "has-commonerrors=0\nhas-partsolution=0\n")
    cmds, _ = run_builder(PSET, options=["--texlib-mode=default"],
                          aux_files={"doc.buildmeta": PINNED_META})
    args = " ".join(_args(cmds))
    check("document pin: only the pinned variant is built",
          r"\def\StudentMode{}" in args and r"\def\ShowKey{}" not in args,
          args[:400])

    # `none' is a DECISION, and must not look like a planner that gave up.
    NONE_META = ("variants=none\nhas-solutions=1\nhas-rubric=1\n"
                 "has-commonerrors=0\nhas-partsolution=0\n")
    cmds, disp = run_builder(PSET, options=["--texlib-mode=default"],
                             aux_files={"doc.buildmeta": NONE_META})
    args = " ".join(_args(cmds))
    check("document pin: none -> no variant compiles",
          r"\def\StudentMode{}" not in args and r"\def\ShowKey{}" not in args,
          args[:400])
    check("document pin: none is reported, not silent",
          "build-variants = none" in disp, repr(disp[:300]))

    # `full' is the same plan with the content gate switched off -- that is the
    # entire difference between the two modes.
    cmds, _ = run_builder(PSET, options=["--texlib-mode=full"],
                          aux_files={"doc.buildmeta": BARE_META})
    check("full -> builds answer variants even with no solutions detected",
          r"\def\ShowKey{}" in " ".join(_args(cmds)), _args(cmds))

    # A retired token must remap LOUDLY: `key' became `solutions', and
    # `solutions' still exists meaning something else, so a silent fallback
    # would hand back an instructor copy to someone who asked for a key.
    cmds, disp = run_builder(PSET, options=["--texlib-mode=key"])
    check("renamed mode: key -> solutions macro",
          bool(cmds) and r"\def\ShowKey{}" in cmds[0][0][-1], _args(cmds))
    check("renamed mode: the rename is announced",
          "renamed to 'solutions'" in disp, repr(disp[:300]))

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

    # (k) accessible mode is a PAIRED build: the class's own engine produces the
    # normal PDF first, then lualatex re-typesets the same source with the
    # DocumentMetadata prefix into an a11y/ output dir. syllabus is a pdflatex
    # class, so this also pins that the normal half is NOT dragged onto lualatex
    # -- that would silently change the primary PDF's rendering in this mode.
    cmds, disp = run_builder(
        r"\documentclass{syllabus}\begin{document}x\end{document}",
        options=["--texlib-mode=accessible"])
    normal = [c for c in cmds if r"\DocumentMetadata" not in str(c[0][-1])]
    tagged = [c for c in cmds if r"\DocumentMetadata" in str(c[0][-1])]
    check("accessible -> produces both halves",
          bool(normal) and bool(tagged), [c[1] for c in cmds])
    check("accessible -> normal half runs FIRST (publish reads the primary PDF)",
          bool(cmds) and r"\DocumentMetadata" not in str(cmds[0][0][-1]),
          cmds[0][1] if cmds else "")
    check("accessible -> normal half keeps the class's own engine (pdflatex)",
          bool(normal) and normal[0][0][0] == "pdflatex",
          normal[0][0] if normal else "")
    check("accessible -> normal half gets a plain filename arg (untagged)",
          bool(normal) and normal[0][0][-1] == "doc.tex",
          normal[0][0] if normal else "")
    check("accessible -> normal half NOT written into a11y",
          bool(normal) and not any(str(c).endswith("a11y") for c in normal[0][0]),
          normal[0][0] if normal else "")
    check("accessible -> tagged half forced to lualatex",
          bool(tagged) and all(c[0][0] == "lualatex" for c in tagged), tagged)
    check("accessible -> engine-split message shown",
          "tagged PDF needs lualatex" in disp, repr(disp))
    aarg = tagged[0][0][-1] if tagged else ""
    check("accessible -> \\DocumentMetadata injected", r"\DocumentMetadata" in aarg, aarg)
    check("accessible -> tagging=on requested", "tagging=on" in aarg, aarg)
    check("accessible -> DocumentMetadata precedes \\input",
          r"\DocumentMetadata" in aarg
          and aarg.index(r"\DocumentMetadata") < aarg.index(r"\input"), aarg)
    check("accessible -> \\def\\TeXLibAccessibleMode injected",
          r"\def\TeXLibAccessibleMode{}" in aarg, aarg)
    # AF is what Firefox's viewer and Foxit read -- the in-browser path from an
    # LMS link -- and SE is Acrobat's. Run 1 asks for both; a document that
    # trips the luamml mathml-SE bug is retried with AF alone. See
    # ACCESSIBLE_DOCMETA.
    check("accessible -> MathML AF requested",
          "mathml-AF" in aarg, aarg)
    check("accessible -> MathML SE requested (Acrobat's path)",
          "mathml-SE" in aarg, aarg)
    # The jobname must stay the REAL base name: autoexam reads its document body
    # from <jobname>.tex, so a suffixed jobname truncated the tagged exam. The
    # output is separated by directory (aux/a11y) instead, and _postprocess
    # copies it out as <base>_accessible.pdf.
    check("accessible -> --jobname stays the real base name",
          bool(tagged) and "--jobname=doc" in tagged[0][0]
          and "--jobname=doc_accessible" not in tagged[0][0],
          tagged[0][0] if tagged else "")
    check("accessible -> tagged half redirected to an a11y output dir",
          bool(tagged) and any(str(c).startswith("-output-directory=")
                               and str(c).endswith("a11y") for c in tagged[0][0]),
          tagged[0][0] if tagged else "")
    check("accessible -> exactly one -output-directory (base one replaced)",
          bool(tagged) and sum(1 for c in tagged[0][0]
                               if str(c).startswith("-output-directory=")) == 1,
          tagged[0][0] if tagged else "")
    check("accessible -> two settle passes on the tagged half",
          len(tagged) == 2, f"{len(tagged)} tagged passes")
    check("accessible -> --texlib-mode token NOT passed to engine",
          not any("--texlib-mode" in str(x) for c in cmds for x in c[0]), cmds)

    # (k1) the mathml-SE fallback. luamml 0.9.2 aborts a document with two
    # \sqrt[n]{...} in one formula, and only the SE path reaches the code that
    # does it, so run 1 asks for both methods and is spent again on AF alone
    # when that abort appears. The document is never edited; the builder just
    # asks for less of the tagged output. See ACCESSIBLE_DOCMETA.
    _ACC_DOC = r"\documentclass{syllabus}\begin{document}x\end{document}"
    _ACC_OPT = ["--texlib-mode=accessible"]
    _plan, _, _ = drive_builder(_ACC_DOC, options=_ACC_OPT)
    _t1 = next((i for i, c in enumerate(_plan)
                if r"\DocumentMetadata" in str(c[0][-1])), None)
    check("accessible fallback: found the tagged run-1 slot to script",
          _t1 is not None, [c[1] for c in _plan])

    _ABORT = ("! error:  (nodes): trying to delete an attribute reference of "
              "a non attribute node")
    cmds, disp, _ = drive_builder(
        _ACC_DOC, options=_ACC_OPT,
        steps=[{} for _ in range(_t1 or 0)] + [{"out": _ABORT}])
    tagged = [c for c in cmds if r"\DocumentMetadata" in str(c[0][-1])]
    check("accessible fallback: SE abort spends one extra tagged pass",
          len(tagged) == 3, [c[1] for c in tagged])
    check("accessible fallback: run 1 asked for SE",
          bool(tagged) and "mathml-SE" in tagged[0][0][-1],
          tagged[0][0][-1] if tagged else "")
    check("accessible fallback: every pass after the abort drops SE",
          len(tagged) == 3
          and all("mathml-SE" not in c[0][-1] and "mathml-AF" in c[0][-1]
                  for c in tagged[1:]),
          [c[0][-1] for c in tagged[1:]])
    check("accessible fallback: the retry is otherwise the same command",
          len(tagged) == 3 and tagged[1][0][:-1] == tagged[0][0][:-1],
          tagged[1][0] if len(tagged) > 1 else "")
    check("accessible fallback: the reason is shown, not silently swallowed",
          "mathml-SE" in disp and "nth-root" in disp, repr(disp))

    # The abort is deliberate and recovered from, so the host must not report
    # the whole build as failed -- see TexlibBuildCore's _forget_last_pass.
    check("accessible fallback: host told to forget the aborted pass",
          getattr(_LAST_BUILDER[0], "_forget_last_pass", False) is True,
          "flag never set")

    #   a document that does NOT trip the bug keeps SE and spends no extra pass.
    cmds, disp, _ = drive_builder(_ACC_DOC, options=_ACC_OPT)
    check("accessible fallback: clean document never sets the forget flag",
          getattr(_LAST_BUILDER[0], "_forget_last_pass", False) is False)
    tagged = [c for c in cmds if r"\DocumentMetadata" in str(c[0][-1])]
    check("accessible fallback: clean document keeps SE on both passes",
          len(tagged) == 2
          and all("mathml-SE" in c[0][-1] for c in tagged),
          [c[0][-1] for c in tagged])
    check("accessible fallback: clean document says nothing about MathML",
          "mathml-SE" not in disp, repr(disp))

    #   an ordinary LaTeX error must NOT trigger the retry.
    cmds, _, _ = drive_builder(
        _ACC_DOC, options=_ACC_OPT,
        steps=[{} for _ in range(_t1 or 0)]
        + [{"out": "! Undefined control sequence.\nl.7 \\nope"}])
    tagged = [c for c in cmds if r"\DocumentMetadata" in str(c[0][-1])]
    check("accessible fallback: an ordinary error does not spend a retry",
          len(tagged) == 2
          and all("mathml-SE" in c[0][-1] for c in tagged),
          [c[0][-1] for c in tagged])

    # (k2) a lualatex class in accessible mode: same pairing, one engine.
    cmds, _ = run_builder(
        r"\documentclass{quiz}\begin{document}x\end{document}",
        options=["--texlib-mode=accessible"])
    check("accessible (lua class) -> still produces both halves",
          any(r"\DocumentMetadata" not in str(c[0][-1]) for c in cmds)
          and any(r"\DocumentMetadata" in str(c[0][-1]) for c in cmds),
          [c[1] for c in cmds])
    check("accessible (lua class) -> every pass is lualatex",
          all(c[0][0] == "lualatex" for c in cmds), cmds)

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

    # Cross-ref churn: rerun signal once, then clean -> two passes. The pass
    # must also MOVE the aux state, which is what really makes LaTeX print that
    # warning -- a rerun request over byte-stable state is vetoed (below).
    cmds, _, _ = drive_builder(ART, steps=[{"out": RERUN,
                                            "write": {"doc.aux": "v1"}},
                                           {"out": ""}])
    check("seq: rerun signal then clean -> 2 passes",
          heads(cmds) == ["pdflatex", "pdflatex"], heads(cmds))

    # Persistent rerun signal over genuinely churning state -> capped at
    # MAX_RERUNS passes, never looping, and the cap is reported.
    cmds, disp, _ = drive_builder(
        ART, steps=[{"out": RERUN, "write": {"doc.aux": f"v{n}"}}
                    for n in range(MAX_RERUNS + 2)])
    check(f"seq: persistent rerun -> capped at {MAX_RERUNS} passes",
          heads(cmds) == ["pdflatex"] * MAX_RERUNS, f"{len(cmds)} passes")
    check("seq: hitting the pass ceiling is reported",
          "unsettled after" in disp, disp)

    # The veto: the log keeps asking but the state never moved. Another pass
    # would consume identical input and produce identical output, so it is
    # skipped -- this is where the rerun loop stops costing passes for nothing.
    cmds, _, _ = drive_builder(ART, steps=[{"out": RERUN}] * 6)
    check("seq: stable state vetoes a log-requested rerun -> 1 pass",
          heads(cmds) == ["pdflatex"], heads(cmds))

    # The log's blind spot: no warning at all, but the aux state moved (an
    # autoexam footer label shifting pages -- the class defines \@testdef away,
    # so nothing is printed). Earns a settling pass on the state alone.
    cmds, _, _ = drive_builder(
        ART, steps=[{"out": "", "write": {"doc.aux": r"\newlabel{@lastqpage}{{}{4}}"}},
                    {"out": ""}])
    check("seq: silent log + moved state -> settling pass",
          heads(cmds) == ["pdflatex", "pdflatex"], heads(cmds))

    # ...but a document that never converges with a silent log (problem_engine
    # re-randomizes an unversioned bank doc every pass) is bounded well short of
    # MAX_RERUNS.
    cmds, _, _ = drive_builder(
        ART, steps=[{"out": "", "write": {"doc.aux": f"r{n}"}} for n in range(6)])
    check("seq: silent-log churn stops at STATE_ONLY_RERUNS",
          heads(cmds) == ["pdflatex"] * (1 + STATE_ONLY_RERUNS), f"{len(cmds)} passes")

    # biblatex 'Please rerun LaTeX' is honored (the bug that shipped ?? refs).
    cmds, _, _ = drive_builder(
        ART, steps=[{"out": "Package biblatex Warning: Please rerun LaTeX.",
                     "write": {"doc.aux": "v1"}},
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
            {"out": "Package biblatex Warning: Please rerun LaTeX.",
             "write": {"doc.aux": "cites-resolved"}},    # post-biber pass
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

        # A VARIANT's combined PDF is sliced too. Before this, only the base
        # build's .vmap was read -- a variant writes its map into its own output
        # directory -- so a \versions document's <base>_instructor.pdf came out
        # as one collated blob while the base came out per version.
        #
        # The suffix is what keeps the two apart: the instructor copies must not
        # be written over the key's <base>_A_solutions.pdf, which is the name
        # collate_keys.py and the SyncTeX slicer look for.
        tmpvv = tempfile.mkdtemp(prefix="texlib_vmapvar_")
        outv = os.path.join(tmpvv, "variants", "instructor")
        os.makedirs(outv)
        variant_pdf = os.path.join(tmpvv, "doc_instructor.pdf")
        _blank_pdf(variant_pdf, 4)
        with open(os.path.join(outv, "doc.vmap"), "w", encoding="utf-8") as fh:
            fh.write("A|sol|1\nB|sol|3\n")
        vv = TexlibBuilder(); vv.tex_dir = tmpvv; vv.base_name = "doc"
        vv._aux_target = None
        vv._slice_variant_versions("instructor", outv, tmpvv, variant_pdf)
        check("variant vmap: instructor slices carry _instructor, not _solutions",
              os.path.exists(os.path.join(tmpvv, "doc_A_instructor.pdf"))
              and os.path.exists(os.path.join(tmpvv, "doc_B_instructor.pdf")),
              sorted(os.listdir(tmpvv)))
        check("variant vmap: does NOT overwrite the key's _solutions names",
              not os.path.exists(os.path.join(tmpvv, "doc_A_solutions.pdf")),
              sorted(os.listdir(tmpvv)))
        check("variant vmap: each slice gets its 2 pages",
              len(PdfReader(os.path.join(tmpvv, "doc_A_instructor.pdf")).pages) == 2)
        check("variant vmap: the variant's map is consumed",
              not os.path.exists(os.path.join(outv, "doc.vmap")))

        # The `solutions' variant keeps the historic name -- those copies ARE
        # the answer key, and downstream tooling is built on that spelling.
        tmpvs = tempfile.mkdtemp(prefix="texlib_vmapsol_")
        outs = os.path.join(tmpvs, "variants", "solutions")
        os.makedirs(outs)
        sol_pdf = os.path.join(tmpvs, "doc_solutions.pdf")
        _blank_pdf(sol_pdf, 4)
        with open(os.path.join(outs, "doc.vmap"), "w", encoding="utf-8") as fh:
            fh.write("A|sol|1\nB|sol|3\n")
        vs = TexlibBuilder(); vs.tex_dir = tmpvs; vs.base_name = "doc"
        vs._aux_target = None
        vs._slice_variant_versions("solutions", outs, tmpvs, sol_pdf)
        check("variant vmap: solutions slices keep _solutions",
              os.path.exists(os.path.join(tmpvs, "doc_A_solutions.pdf"))
              and os.path.exists(os.path.join(tmpvs, "doc_B_solutions.pdf")),
              sorted(os.listdir(tmpvs)))

        # A single-version document writes no .vmap at all: the common case must
        # stay a silent no-op, not an error.
        tmpvn = tempfile.mkdtemp(prefix="texlib_vmapnone_")
        none_pdf = os.path.join(tmpvn, "doc_solutions.pdf")
        _blank_pdf(none_pdf, 2)
        vn = TexlibBuilder(); vn.tex_dir = tmpvn; vn.base_name = "doc"
        vn._aux_target = None
        vn._slice_variant_versions("solutions", tmpvn, tmpvn, none_pdf)
        check("variant vmap: no .vmap -> no-op, PDF untouched",
              len(os.listdir(tmpvn)) == 1)

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
        # The one copy lives inside the plugin package (texlib_build.py locates
        # it as dirname(__file__)/texlib_pdfpost.py). A sibling copy used to sit
        # next to the legacy builder for the LaTeXTools-era shell-out; that
        # usage died in the Phase 2 native cutover and the byte-identical
        # duplicate is gone.
        pdfpost = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "texlib", "texlib_pdfpost.py")
        check("pdfpost: helper module ships inside the plugin package",
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
        check("_run_pdfpost: absorbs the produced names in typeset order",
              rb.produced_pdfs == ["doc_A.pdf", "doc_B.pdf"], rb.produced_pdfs)
        check("_run_pdfpost: absorbs each copy's page span",
              rb._copy_ranges == {"doc_A.pdf": (1, 3), "doc_B.pdf": (4, 6)},
              rb._copy_ranges)

        # ================================================================== #
        # (v4) preferred_pdf resolution against what the build produced.
        # ================================================================== #
        tmpp = tempfile.mkdtemp(prefix="texlib_pref_")
        bpp = os.path.join(tmpp, "doc")
        _blank_pdf(bpp + ".pdf", 6)
        with open(bpp + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\nB|stu|2\nA|sol|3\nB|sol|5\n")
        pb = TexlibBuilder(); pb.tex_dir = tmpp; pb.base_name = "doc"
        pb._aux_target = None
        pb.produced_pdfs, pb._copy_ranges = [], {}
        pb._slice_versions_from_vmap(tmpp, bpp)
        check("preferred_pdf: 'solutions' -> the FIRST solutions copy",
              pb.preferred_pdf_path("solutions") == bpp + "_A_solutions.pdf",
              pb.preferred_pdf_path("solutions"))
        check("preferred_pdf: 'student' -> the first student copy",
              pb.preferred_pdf_path("student") == bpp + "_A.pdf")
        check("preferred_pdf: an explicit suffix resolves against <base>",
              pb.preferred_pdf_path("_B_solutions") == bpp + "_B_solutions.pdf")
        check("preferred_pdf: unset -> the combined PDF",
              pb.preferred_pdf_path(None) == bpp + ".pdf")
        check("preferred_pdf: 'combined' -> the combined PDF",
              pb.preferred_pdf_path("combined") == bpp + ".pdf")
        check("preferred_pdf: a suffix that wasn't produced falls back",
              pb.preferred_pdf_path("_Z_solutions") == bpp + ".pdf")
        check("preferred_pdf: the combined PDF survives the slicing",
              len(PdfReader(bpp + ".pdf").pages) == 6,
              "<base>.pdf must still be produced whatever the preference")

        # A student-mode build slices no solutions copy: the preference must
        # fall back rather than open nothing.
        tmpp2 = tempfile.mkdtemp(prefix="texlib_pref_")
        bpp2 = os.path.join(tmpp2, "doc")
        _blank_pdf(bpp2 + ".pdf", 4)
        with open(bpp2 + ".vmap", "w", encoding="utf-8") as fh:
            fh.write("A|stu|1\nB|stu|3\n")
        pb2 = TexlibBuilder(); pb2.tex_dir = tmpp2; pb2.base_name = "doc"
        pb2._aux_target = None
        pb2.produced_pdfs, pb2._copy_ranges = [], {}
        pb2._slice_versions_from_vmap(tmpp2, bpp2)
        check("preferred_pdf: no solutions copy produced -> combined PDF",
              pb2.preferred_pdf_path("solutions") == bpp2 + ".pdf")

        # And a build that produced no copies at all (any ordinary document).
        pb3 = TexlibBuilder(); pb3.tex_dir = tmpp2; pb3.base_name = "doc"
        check("preferred_pdf: nothing sliced at all -> combined PDF",
              pb3.preferred_pdf_path("solutions") == bpp2 + ".pdf")
    else:
        print("  SKIP  pypdf not installed -- PDF split/vmap tests skipped")

    # ====================================================================== #
    # (v5) SyncTeX maps for the sliced copies. Needs no pypdf -- the page spans
    # are handed over by the slicer, and the cut is pure text surgery.
    # ====================================================================== #

    def _synthetic_synctex(pages, eol="\n"):
        """A minimal but structurally real .synctex: preamble, Content: with one
        sheet per page (an Input: row between sheets, as a real one has),
        Postamble. Anchors deliberately WRONG so a correct rewrite is visible."""
        out = ["SyncTeX Version:1",
               "Input:1:/tmp/doc.tex",
               "Output:pdf", "Magnification:1000", "Unit:1",
               "X Offset:0", "Y Offset:0", "Content:"]
        for p in range(1, pages + 1):
            out += ["!999", "{%d" % p,
                    "[1,%d:0,0:100,100,0" % (10 * p), "]", "!999", "}%d" % p]
            if p < pages:
                out.append("Input:%d:/tmp/bank%d.tex" % (p + 1, p))
        out += ["!999", "Postamble:", "Count:%d" % (pages * 2),
                "!999", "Post scriptum:", ""]
        return eol.join(out).encode("utf-8")

    _cut = TexlibBuildCore._synctex_page_slice

    def _sheets(blob, eol=b"\n"):
        return [l for l in blob.split(eol)
                if l[:1] in (b"{", b"}") and l[1:].isdigit()]

    def _anchors_consistent(blob, eol=b"\n"):
        """Each !N must equal its own byte offset minus the previous anchor's."""
        off = last = 0
        for line in blob.split(eol):
            if line.startswith(b"!"):
                if int(line[1:]) != off - last:
                    return False
                last = off
            off += len(line) + len(eol)
        return True

    six = _synthetic_synctex(6)
    cut = _cut(six, 3, 4)
    check("synctex cut: keeps only the requested pages, renumbered from 1",
          _sheets(cut) == [b"{1", b"}1", b"{2", b"}2"], _sheets(cut))
    check("synctex cut: the kept records travel with their page",
          b"[1,30:" in cut and b"[1,40:" in cut
          and b"[1,10:" not in cut and b"[1,50:" not in cut)
    check("synctex cut: anchors are recomputed, not copied", _anchors_consistent(cut))
    check("synctex cut: every Input: row survives (they are the tag table)",
          cut.count(b"Input:") == six.count(b"Input:"),
          "%d vs %d" % (cut.count(b"Input:"), six.count(b"Input:")))
    check("synctex cut: postamble survives",
          b"Postamble:" in cut and b"Post scriptum:" in cut)
    check("synctex cut: a span holding no page -> None", _cut(six, 9, 9) is None)
    check("synctex cut: not a SyncTeX file -> None",
          _cut(b"hello\nworld\n", 1, 1) is None)
    _crlf = _synthetic_synctex(3, eol="\r\n")
    check("synctex cut: CRLF map stays CRLF",
          b"\n" not in _cut(_crlf, 2, 2).replace(b"\r\n", b""))
    check("synctex cut: CRLF anchors measured in CRLF bytes",
          _anchors_consistent(_cut(_crlf, 2, 3), eol=b"\r\n"))

    # Round-trip: keeping every page must reproduce a REAL map byte-for-byte,
    # which is the strongest available statement that the rewrite is faithful.
    _real = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "Exams", "template.synctex")
    if os.path.exists(_real):
        with open(_real, "rb") as fh:
            _rd = fh.read()
        _npages = sum(1 for l in _rd.split(b"\n")
                      if l[:1] == b"{" and l[1:].isdigit())
        check("synctex cut: keeping every page round-trips a real map exactly",
              _cut(_rd, 1, _npages) == _rd)
    else:
        print("  SKIP  Exams/template.synctex absent -- round-trip check skipped")

    # The build step: one .synctex per sliced copy, beside the source.
    tmps = tempfile.mkdtemp(prefix="texlib_synccut_")
    with open(os.path.join(tmps, "doc.synctex"), "wb") as fh:
        fh.write(_synthetic_synctex(6))
    sb = TexlibBuilder(); sb.tex_dir = tmps; sb.base_name = "doc"
    sb._copy_ranges = {"doc_A.pdf": (1, 2), "doc_A_solutions.pdf": (3, 6)}
    sb._slice_synctex_for_copies(tmps)
    check("synctex cut: a map is written for each sliced copy",
          os.path.exists(os.path.join(tmps, "doc_A.synctex"))
          and os.path.exists(os.path.join(tmps, "doc_A_solutions.synctex")))
    with open(os.path.join(tmps, "doc_A_solutions.synctex"), "rb") as fh:
        _sol = fh.read()
    check("synctex cut: the solutions map holds its own 4 pages",
          _sheets(_sol) == [b"{1", b"}1", b"{2", b"}2", b"{3", b"}3", b"{4", b"}4"],
          _sheets(_sol))
    check("synctex cut: the parent map is left alone",
          _sheets(open(os.path.join(tmps, "doc.synctex"), "rb").read())
          == _sheets(_synthetic_synctex(6)))
    check("synctex cut: no complaint on the happy path", sb._displayed == "",
          sb._displayed)

    # Nothing was sliced (the ordinary single-copy build) -> silent no-op.
    tmps2 = tempfile.mkdtemp(prefix="texlib_synccut_")
    with open(os.path.join(tmps2, "doc.synctex"), "wb") as fh:
        fh.write(_synthetic_synctex(2))
    sb2 = TexlibBuilder(); sb2.tex_dir = tmps2; sb2.base_name = "doc"
    sb2._slice_synctex_for_copies(tmps2)
    check("synctex cut: no sliced copies -> no-op, no stray maps",
          os.listdir(tmps2) == ["doc.synctex"] and sb2._displayed == "",
          os.listdir(tmps2))

    # A build with -synctex=0 (or a map that never landed) must not complain:
    # the copies simply have no inverse search, as before this existed.
    tmps3 = tempfile.mkdtemp(prefix="texlib_synccut_")
    sb3 = TexlibBuilder(); sb3.tex_dir = tmps3; sb3.base_name = "doc"
    sb3._copy_ranges = {"doc_A.pdf": (1, 2)}
    sb3._slice_synctex_for_copies(tmps3)
    check("synctex cut: no parent map -> silent no-op",
          os.listdir(tmps3) == [] and sb3._displayed == "", sb3._displayed)

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
    check("bank fragment -> bank.cls catalog harness synthesized",
          r"\documentclass{bank}" in arg, arg)
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
    # _coded_basename derivation -- the Math & Stat Office submission convention
    # "MATH XXX.YYYY_Fall 2026_InstructorLastName" (department mail of 2026-08-20,
    # in force since August 2025). Spaces are part of the convention and are kept.
    check("coded: department convention (subject upper, spaces kept, surname)",
          TexlibBuilder._coded_basename("Math 181", "1001", "Fall 2026",
                                        "Landon Fox")
          == "MATH 181.1001_Fall 2026_Fox")
    check("coded: STAT courses take the same shape",
          TexlibBuilder._coded_basename("Stat 152", "1002", "Fall 2026",
                                        "Landon Fox")
          == "STAT 152.1002_Fall 2026_Fox")
    check("coded: lettered course number stays upper ('126EE')",
          TexlibBuilder._coded_basename("Math 126EE", "1001", "Spring 2026",
                                        "Landon Fox")
          == "MATH 126EE.1001_Spring 2026_Fox")
    check("coded: no section -> no stray dot",
          TexlibBuilder._coded_basename("Math 181", "", "Fall 2026",
                                        "Landon Fox")
          == "MATH 181_Fall 2026_Fox")
    check("coded: no instructor -> no trailing underscore",
          TexlibBuilder._coded_basename("Math 181", "1001", "Fall 2026", "")
          == "MATH 181.1001_Fall 2026")
    check("coded: filename-illegal chars stripped, legal spaces kept",
          TexlibBuilder._coded_basename("Math 18/1", "10:01", "Fall 2026",
                                        "Landon Fox")
          == "MATH 181.1001_Fall 2026_Fox")

    # _surname: the free-text `instructor` field, reduced to the last name the
    # department convention wants.
    for raw, want in (("Landon Fox", "Fox"), ("Dr. Landon Fox", "Fox"),
                      ("Fox, Landon", "Fox"), ("Landon Fox, Ph.D.", "Fox"),
                      ("Landon Fox Jr.", "Fox"), ("  Landon   Fox  ", "Fox"),
                      ("Fox", "Fox"), ("", "")):
        check("surname: %r -> %r" % (raw, want),
              _surname(raw) == want, _surname(raw))

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
                      settings=None, publish_name="",
                      accessible_build=False, tagged_present=False,
                      instructor="Landon Fox", coded_suffix=""):
        d = tempfile.mkdtemp(prefix="texlib_pub_")
        with open(os.path.join(d, base + ".pdf"), "wb") as fh:
            fh.write(b"%PDF-1.5 normal")
        # tagged_present is deliberately independent of accessible_build so the
        # stale case (file left by an EARLIER accessible run, current build
        # normal) can be pinned: it must never be published.
        if tagged_present:
            with open(os.path.join(d, base + "_accessible.pdf"), "wb") as fh:
                fh.write(b"%PDF-1.5 tagged")
        with open(os.path.join(d, base + ".pubmeta"), "w", encoding="utf-8") as fh:
            fh.write(f"kind={kind}\ngeneric={generic}\nnoun={noun}\n"
                     f"coded-suffix={coded_suffix}\n"
                     f"course={course}\nsection={section}\nterm={term}\n"
                     f"instructor={instructor}\n"
                     f"publish-name={publish_name}\n")
        b = TexlibBuilder(); b.tex_dir = d; b.base_name = base
        b._aux_target = None
        b._accessible_build = accessible_build
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
        "Math 181", "1001", "Fall 2026", coded_suffix="Schedule")
    check("publish: coded + generic copies made (source name distinct)",
          "MATH 181.1001_Fall 2026_Fox_Schedule.pdf" in pdfs
          and "Tentative Schedule.pdf" in pdfs and "schedule.pdf" in pdfs, pdfs)
    check("publish: shortcut label is '<course> <term> <noun>' -> coded copy",
          shortcuts == [("Math 181 Fall 2026 Schedule",
                         "MATH 181.1001_Fall 2026_Fox_Schedule.pdf")], shortcuts)
    check("publish: shareable path put on the clipboard",
          clips == ["MATH 181.1001_Fall 2026_Fox_Schedule.pdf"], clips)
    check("publish: sidecar consumed", not os.path.exists(
        os.path.join(d, "schedule.pubmeta")))

    # The coded name is course-identified but not kind-identified, so every
    # publishable class BUT the syllabus declares a coded-suffix. Without it the
    # syllabus and schedule of one course clone to a single filename and the
    # later build silently wins -- and the loser is what gets mailed to the
    # department. Pin that they differ, and that the syllabus keeps the bare
    # convention name.
    _, syl_pdfs, _, _, _ = _publish_case(
        "syllabus-doc", "syllabus", "Syllabus", "Syllabus",
        "Math 181", "1001", "Fall 2026")
    _, sch_pdfs, _, _, _ = _publish_case(
        "schedule-doc", "schedule", "Tentative Schedule", "Schedule",
        "Math 181", "1001", "Fall 2026", coded_suffix="Schedule")
    check("publish: syllabus coded name is the bare department convention",
          "MATH 181.1001_Fall 2026_Fox.pdf" in syl_pdfs, syl_pdfs)
    check("publish: schedule coded name does not collide with the syllabus",
          "MATH 181.1001_Fall 2026_Fox.pdf" not in sch_pdfs
          and "MATH 181.1001_Fall 2026_Fox_Schedule.pdf" in sch_pdfs, sch_pdfs)

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
          "MATH 181.1001_Fall 2026_Fox.pdf" in pdfs, pdfs)
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

    # publish-name is course-wide, so the kind-discriminating suffix has to ride
    # on the override too -- otherwise setting the key re-collides every
    # publishable class in the course onto one filename.
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "doc", "schedule", "Tentative Schedule", "Schedule", "Math 181", "1001",
        "Fall 2026", publish_name="M181-F26", coded_suffix="Schedule")
    check("publish: coded-suffix still applies over a publish-name override",
          "M181-F26_Schedule.pdf" in pdfs, pdfs)

    # Disabled via builder_settings -> sidecar still consumed, no copies made.
    d, pdfs, shortcuts, clips, disp = _publish_case(
        "doc", "syllabus", "Syllabus", "Syllabus", "Math 181", "1001",
        "Fall 2026", settings={"publish_shareable_copies": False})
    check("publish: disabled -> only source PDF, sidecar still consumed",
          pdfs == ["doc.pdf"]
          and not os.path.exists(os.path.join(d, "doc.pubmeta")), pdfs)

    # Publish source selection. The shareable copies are the files that go up to
    # WebCampus, so an accessible build publishes its TAGGED half -- an untagged
    # PDF is exactly what the LMS accessibility checker flags.
    def _published_bytes(d, name):
        with open(os.path.join(d, name), "rb") as fh:
            return fh.read()

    d, pdfs, _, _, disp = _publish_case(
        "schedule", "schedule", "Tentative Schedule", "Schedule",
        "Math 181", "1001", "Fall 2026", coded_suffix="Schedule",
        accessible_build=True, tagged_present=True)
    check("publish (accessible): generic copy carries the TAGGED bytes",
          _published_bytes(d, "Tentative Schedule.pdf") == b"%PDF-1.5 tagged",
          _published_bytes(d, "Tentative Schedule.pdf"))
    check("publish (accessible): coded copy carries the TAGGED bytes",
          _published_bytes(d, "MATH 181.1001_Fall 2026_Fox_Schedule.pdf")
          == b"%PDF-1.5 tagged",
          _published_bytes(d, "MATH 181.1001_Fall 2026_Fox_Schedule.pdf"))
    check("publish (accessible): both halves survive next to the source",
          "schedule.pdf" in pdfs and "schedule_accessible.pdf" in pdfs, pdfs)
    check("publish (accessible): says so", "tagged PDF" in disp, repr(disp))

    # A stale <base>_accessible.pdf from an earlier run must NOT hijack a normal
    # build's publish -- it would ship content from whenever that run happened.
    d, pdfs, _, _, _ = _publish_case(
        "schedule", "schedule", "Tentative Schedule", "Schedule",
        "Math 181", "1001", "Fall 2026",
        accessible_build=False, tagged_present=True)
    check("publish (normal build, stale tagged file): publishes the NORMAL bytes",
          _published_bytes(d, "Tentative Schedule.pdf") == b"%PDF-1.5 normal",
          _published_bytes(d, "Tentative Schedule.pdf"))

    # Accessible build whose tagged half failed to appear: fall back rather than
    # publishing nothing.
    d, pdfs, _, _, _ = _publish_case(
        "schedule", "schedule", "Tentative Schedule", "Schedule",
        "Math 181", "1001", "Fall 2026",
        accessible_build=True, tagged_present=False)
    check("publish (accessible, tagged missing): falls back to the normal PDF",
          _published_bytes(d, "Tentative Schedule.pdf") == b"%PDF-1.5 normal",
          _published_bytes(d, "Tentative Schedule.pdf"))

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

    # ====================================================================== #
    # Copy-back from the aux dir. The .schedmeta case is the one with an
    # out-of-build consumer: TeXLib Sync reads it from beside the source, so a
    # builder build that left it in %TEMP% would look to that tool like "the
    # schedule was never built" -- or worse, hand it a stale in-place copy.
    # ====================================================================== #
    tmpc = tempfile.mkdtemp(prefix="texlib_copyback_")
    src_dir = os.path.join(tmpc, "src")
    aux_dir = os.path.join(tmpc, "aux")
    os.makedirs(src_dir)
    os.makedirs(aux_dir)
    for name in ("doc.pdf", "doc.synctex.gz", "doc.spl", "doc.schedmeta",
                 "doc_A.pdf", "doc.aux", "doc.log", "doc.schedmap"):
        with open(os.path.join(aux_dir, name), "w", encoding="utf-8") as fh:
            fh.write("x")

    cb = TexlibBuilder()
    cb.base_name = "doc"
    cb._aux_target = aux_dir
    cb.display = lambda *a, **k: None
    cb._copy_back_from_aux(src_dir)

    landed = set(os.listdir(src_dir))
    check("copy-back: .schedmeta lands next to the source",
          "doc.schedmeta" in landed, sorted(landed))
    check("copy-back: pdf/synctex/spl still land",
          {"doc.pdf", "doc.synctex.gz", "doc.spl", "doc_A.pdf"} <= landed,
          sorted(landed))
    check("copy-back: aux files stay in the aux dir",
          not ({"doc.aux", "doc.log"} & landed), sorted(landed))
    check("copy-back: .schedmap is NOT copied (its consumer is the builder, "
          "which probes both dirs)",
          "doc.schedmap" not in landed, sorted(landed))
    for d in (src_dir, aux_dir):
        for n in os.listdir(d):
            os.remove(os.path.join(d, n))
        os.rmdir(d)
    os.rmdir(tmpc)

    # -----------------------------------------------------------------------
    # Build spec is single-sourced.
    #
    # LUALATEX_CLASSES / ACCESSIBLE_DOCMETA / ACCESSIBLE_MACRO were literals in
    # BOTH texlib_build.py and smoke_test.py and had drifted: bingo was in the
    # harness copy and not the builder's. A class missing from the builder's set
    # silently gets pdflatex, and every lua class fatals under it -- that is the
    # failure that cost a session when thesis was missing from both. They now
    # live once in texlib_buildspec.py; assert no copy creeps back.
    # -----------------------------------------------------------------------
    _repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _spec_path = os.path.join(_repo, "Sublime", "texlib", "texlib_buildspec.py")
    check("buildspec: the single source exists", os.path.isfile(_spec_path))

    _redefiners = []
    for _dirpath, _dirnames, _filenames in os.walk(_repo):
        if any(part in _dirpath for part in (os.sep + ".git", os.sep + ".claude")):
            continue
        for _fn in _filenames:
            if not _fn.endswith(".py") or _fn == "texlib_buildspec.py":
                continue
            _p = os.path.join(_dirpath, _fn)
            try:
                _txt = open(_p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # Markers assembled at runtime: spelled out literally, this file
            # would match itself and the check would fail on its own source.
            for _marker in ("LUALATEX_CLASSES = " + "{",
                            "ACCESSIBLE_DOCMETA = " + "(",
                            "ACCESSIBLE_MACRO = " + "ACCESSIBLE_DOCMETA"):
                if _marker in _txt:
                    _redefiners.append(os.path.relpath(_p, _repo) + " :: " + _marker)
    check("buildspec: no module redefines the shared constants",
          not _redefiners, "; ".join(_redefiners))

    # Every lua class must actually be one -- bingo and schedule \directlua at
    # class load, thesis loads fontspec; pdflatex cannot compile any of them.
    sys.path.insert(0, os.path.join(_repo, "Sublime", "texlib"))
    import texlib_buildspec as _bs  # noqa: E402
    check("buildspec: bingo is in LUALATEX_CLASSES",
          "bingo" in _bs.LUALATEX_CLASSES)
    check("buildspec: thesis is in LUALATEX_CLASSES",
          "thesis" in _bs.LUALATEX_CLASSES)
    check("buildspec: accessible macro carries MathML AF",
          "mathml-AF" in _bs.ACCESSIBLE_MACRO)
    check("buildspec: accessible macro carries MathML SE",
          "mathml-SE" in _bs.ACCESSIBLE_MACRO)
    # The fallback prefix differs from the attempt in exactly one thing.
    check("buildspec: AF-only fallback drops SE and nothing else",
          "mathml-SE" not in _bs.ACCESSIBLE_MACRO_AF_ONLY
          and _bs.ACCESSIBLE_MACRO_AF_ONLY
          == _bs.ACCESSIBLE_MACRO.replace(",mathml-SE", ""),
          _bs.ACCESSIBLE_MACRO_AF_ONLY)
    # The retry fires on luamml's abort and on nothing else -- an ordinary
    # LaTeX error must stay the document's own failure.
    check("buildspec: luamml_se_aborted recognises the abort",
          _bs.luamml_se_aborted(
              "! error:  (nodes): trying to delete an attribute reference of "
              "a non attribute node"))
    check("buildspec: luamml_se_aborted ignores an ordinary error",
          not _bs.luamml_se_aborted("! Undefined control sequence.\nl.7 \\foo")
          and not _bs.luamml_se_aborted("")
          and not _bs.luamml_se_aborted(None))

    # accessible_macro_for: a document with its OWN \DocumentMetadata (the
    # thesis template's layout) must get the marker only -- the TL2026 kernel
    # fatals on a second declaration -- while everything else keeps the full
    # injected prefix, and a commented-out declaration does not count.
    with tempfile.TemporaryDirectory() as _amd:
        _own = os.path.join(_amd, "own.tex")
        with open(_own, "w", encoding="utf-8") as f:
            f.write("\\DocumentMetadata{tagging=on}\n\\documentclass{thesis}\n")
        _plain = os.path.join(_amd, "plain.tex")
        with open(_plain, "w", encoding="utf-8") as f:
            f.write("\\documentclass{didactic}\n")
        _commented = os.path.join(_amd, "commented.tex")
        with open(_commented, "w", encoding="utf-8") as f:
            f.write("% \\DocumentMetadata{tagging=on}\n\\documentclass{pset}\n")
        check("buildspec: own \\DocumentMetadata -> marker only, no second declaration",
              _bs.accessible_macro_for(_own) == _bs.ACCESSIBLE_MARKER_ONLY)
        check("buildspec: no declaration -> full accessible prefix",
              _bs.accessible_macro_for(_plain) == _bs.ACCESSIBLE_MACRO)
        check("buildspec: commented-out declaration still gets the full prefix",
              _bs.accessible_macro_for(_commented) == _bs.ACCESSIBLE_MACRO)
        check("buildspec: unreadable path falls back to the full prefix",
              _bs.accessible_macro_for(os.path.join(_amd, "missing.tex"))
              == _bs.ACCESSIBLE_MACRO)
        check("buildspec: se=False asks for the AF-only prefix",
              _bs.accessible_macro_for(_plain, se=False)
              == _bs.ACCESSIBLE_MACRO_AF_ONLY)
        # A document with its own \DocumentMetadata picks its own MathML
        # methods, so the retry has nothing to change for it.
        check("buildspec: se=False still yields marker only for an own declaration",
              _bs.accessible_macro_for(_own, se=False)
              == _bs.ACCESSIBLE_MARKER_ONLY)

    # -----------------------------------------------------------------------
    # The example corpus is declared once, and every declared file exists.
    #
    # A manifest that lists a path which is not there fails silently in the
    # worst way: the example never runs, and a green suite reports nothing.
    # -----------------------------------------------------------------------
    sys.path.insert(0, os.path.join(_repo, "examples"))
    import manifest as _mf  # noqa: E402

    _missing = []
    for _e in _mf.EXAMPLES:
        _p = os.path.join(_repo, _e.module.replace("/", os.sep), _e.template)
        if not os.path.isfile(_p):
            _missing.append(os.path.relpath(_p, _repo))
    check("manifest: every declared example file exists", not _missing,
          "; ".join(_missing))

    check("manifest: smoke corpus is non-empty", len(_mf.modules("smoke")) > 0)
    check("manifest: showcase corpus is non-empty", len(_mf.showcase()) > 0)

    # Visual diffing only makes sense for deterministic output. autoexam and
    # quiz shuffle versions and pull random bank problems, so a pixel diff of
    # them is pure noise -- if either is ever tagged visual, that is a mistake.
    _nondet = {"Exams", "Quizzes"} & _mf.visual_modules()
    check("manifest: randomized modules are not tagged visual", not _nondet,
          str(sorted(_nondet)))

    # Every scenario area must map to a module, or its scenarios stage without
    # the class assets they need and fail for a reason that looks unrelated.
    _areas = set()
    _sc = os.path.join(_repo, "examples", "scenarios")
    if os.path.isdir(_sc):
        _areas = {d for d in os.listdir(_sc)
                  if os.path.isdir(os.path.join(_sc, d))}
    _unmapped = _areas - set(_mf.SCENARIO_AREA_MODULE)
    check("manifest: every scenario area maps to a module", not _unmapped,
          str(sorted(_unmapped)))

    # -----------------------------------------------------------------------
    # (y) Accessibility report. The accessible build writes veraPDF's
    # conformance report beside <base>_accessible.pdf. veraPDF is NOT required
    # to run these: the binary and the subprocess are both stubbed, because this
    # suite is the builder's logic harness and must stay runnable on a machine
    # with no JRE. smoke_test --accessible is what exercises the real tool.
    # -----------------------------------------------------------------------
    def _report_case(returncode, settings=None, exe="VP", stdout=b"<html/>"):
        d = tempfile.mkdtemp(prefix="texlib_a11y_")
        pdf = os.path.join(d, "doc_accessible.pdf")
        with open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.7 tagged")
        calls = []

        class _Proc:
            def __init__(self):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = b"boom"

        def _fake_run(cmd, **kw):
            calls.append(cmd)
            return _Proc()

        b = TexlibBuilder(); b.tex_dir = d; b.base_name = "doc"
        if settings is not None:
            b.builder_settings = settings
        _old_find, _old_run = _tb.find_verapdf, _tb.subprocess.run
        _tb.find_verapdf = lambda: exe
        _tb.subprocess.run = _fake_run
        try:
            b._write_accessible_report(d, pdf)
        finally:
            _tb.find_verapdf, _tb.subprocess.run = _old_find, _old_run
        files = sorted(os.listdir(d))
        return files, calls, "".join(b._displayed)

    files, calls, disp = _report_case(0)
    check("a11y report: written beside the tagged PDF, on by default",
          "doc_accessible-report.html" in files, files)
    check("a11y report: a conforming file is reported PASSED",
          "PASSED" in disp and "FAILED" not in disp, repr(disp))
    check("a11y report: validated as PDF/UA-2",
          calls and "ua2" in calls[0], calls)
    check("a11y report: lean by default (no --success)",
          calls and "--success" not in calls[0], calls)
    check("a11y report: points at the itemized form",
          "accessible_report_full" in disp, repr(disp))

    # The report matters MOST when it fails, so exit 1 -- veraPDF's
    # "non-conformant" status, not an error -- must still write the file.
    files, calls, disp = _report_case(1)
    check("a11y report: a NON-conforming file still gets its report",
          "doc_accessible-report.html" in files, files)
    check("a11y report: non-conformance is reported FAILED",
          "FAILED" in disp, repr(disp))

    # Exit >1 is veraPDF itself failing; there is no report to write.
    files, calls, disp = _report_case(2)
    check("a11y report: a veraPDF tool error writes no report",
          "doc_accessible-report.html" not in files, files)
    check("a11y report: the tool error names its exit code",
          "exit 2" in disp, repr(disp))

    files, calls, disp = _report_case(0, settings={"accessible_report_full": True})
    check("a11y report: accessible_report_full adds --success",
          calls and "--success" in calls[0], calls)

    files, calls, disp = _report_case(0, settings={"accessible_report": False})
    check("a11y report: accessible_report off writes nothing",
          "doc_accessible-report.html" not in files, files)
    check("a11y report: accessible_report off does not run veraPDF",
          not calls, calls)

    files, calls, disp = _report_case(0, exe=None)
    check("a11y report: a missing veraPDF is a soft skip, not a failure",
          "doc_accessible-report.html" not in files and "veraPDF not found" in disp,
          repr(disp))

    # The variant fan-out (a plain Ctrl+B) copies its tagged twins out through
    # _copy_back_variant, NOT _copy_back_accessible -- which finds nothing,
    # since the variant builds write to <aux>/<variant>-a11y/ and it looks in
    # <aux>/a11y/. Without a hook there the primary workflow produced tagged
    # PDFs and no report at all. Base only: one veraPDF run per build.
    def _variant_case(variant, tagged):
        d = tempfile.mkdtemp(prefix="texlib_var_")
        out = os.path.join(d, "out"); os.makedirs(out)
        with open(os.path.join(out, "doc.pdf"), "wb") as fh:
            fh.write(b"%PDF-1.7 tagged")
        b = TexlibBuilder(); b.tex_dir = d; b.base_name = "doc"
        b._variant_pdfs = []
        reported = []
        b._write_accessible_report = lambda td, p: reported.append(
            os.path.basename(p))
        b._copy_back_variant(d, variant, tagged, out)
        return reported, sorted(os.listdir(d))

    reported, files = _variant_case("base", True)
    check("a11y report: the fan-out's BASE tagged PDF gets a report",
          reported == ["doc_accessible.pdf"], reported)
    reported, files = _variant_case("base", False)
    check("a11y report: the untagged base gets none", not reported, reported)
    reported, files = _variant_case("solutions", True)
    check("a11y report: other tagged variants get none (one run per build)",
          not reported, reported)

    # The finder must not regress to shutil.which: veraPDF's installer does not
    # put it on PATH, which is what made local conformance checks soft-skip.
    import texlib_buildspec as _bs
    check("a11y report: finder probes install roots, not just PATH",
          any("verapdf" in p for p in _bs._verapdf_candidates()))
    check("a11y report: report name pairs with the tagged PDF",
          _bs.VERAPDF_REPORT_SUFFIX.startswith("_accessible"),
          _bs.VERAPDF_REPORT_SUFFIX)

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return _FAIL


if __name__ == "__main__":
    sys.exit(main())
