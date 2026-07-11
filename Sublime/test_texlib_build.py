#!/usr/bin/env python
"""Parity smoke for the ported host-agnostic build brain (texlib/texlib_build.py).

No Sublime, no TeX toolchain: instantiates TexlibBuild directly and drives its
commands() coroutine with a fake engine (scripted self.out) to prove the build
decisions survived the port -- mode injection, the lua-class force, the rerun
loop, quick mode, and the -file-line-error flag (PLUGIN-DESIGN Risk #1).

Run:  python Sublime/test_texlib_build.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "texlib"))
import texlib_build  # noqa: E402


def make_host(tmp, docclass, engine, mode, display):
    root = os.path.join(tmp, "doc.tex")
    with open(root, "w", encoding="utf-8") as fh:
        fh.write("\\documentclass{%s}\n\\begin{document}\nhi\n\\end{document}\n"
                 % docclass)
    return texlib_build.TexlibBuild(
        tex_root=root, engine=engine,
        options=["--texlib-mode=%s" % mode], display=display,
        aux_directory="<<root>>",  # disable aux routing -> no temp-dir side effects
    )


def drive(host, outs):
    """Run the coroutine, feeding outs[i] as self.out after the i-th command."""
    cmds, msgs = [], []
    gen = host.commands()
    i = 0
    try:
        item = next(gen)
        while True:
            cmd, msg = item
            cmds.append(cmd)
            msgs.append(msg)
            host.out = outs[i] if i < len(outs) else ""
            i += 1
            item = next(gen)
    except StopIteration:
        pass
    return cmds, msgs


def run_case(name, **kw):
    disp = []
    outs = kw.pop("outs", [])
    with tempfile.TemporaryDirectory() as tmp:
        host = make_host(tmp, kw["docclass"], kw["engine"], kw["mode"],
                         lambda t: disp.append(t))
        cmds, msgs = drive(host, outs)
    return cmds, msgs, "".join(disp)


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# 1. autoexam, no magic comment, default mode -> lua force + file-line-error.
cmds, msgs, disp = run_case("autoexam-default",
                            docclass="autoexam", engine="pdflatex", mode="default")
ok &= check(len(cmds) == 1, "autoexam/default: single pass (no rerun signal)")
ok &= check(cmds and cmds[0][0] == "lualatex", "autoexam: engine forced to lualatex")
ok &= check(cmds and "-file-line-error" in cmds[0], "autoexam: -file-line-error present")
ok &= check("requires lualatex" in disp, "autoexam: force message displayed")
ok &= check(cmds and cmds[0][-1] == "doc.tex", "autoexam/default: bare \\input arg")

# 2. pset, key mode -> pdflatex kept, macro injected.
cmds, msgs, disp = run_case("pset-key",
                            docclass="pset", engine="pdflatex", mode="key")
ok &= check(cmds and cmds[0][0] == "pdflatex", "pset: engine stays pdflatex")
ok &= check(cmds and cmds[0][-1] == r"\def\ShowKey{}\input{doc.tex}",
            "pset/key: \\ShowKey macro injected before \\input")
ok &= check(cmds and "-file-line-error" in cmds[0], "pset: -file-line-error present")

# 3. rerun loop: a "Rerun to get..." on pass 1 triggers exactly one more pass.
cmds, msgs, disp = run_case(
    "pset-rerun", docclass="pset", engine="pdflatex", mode="default",
    outs=["Rerun to get cross-references right.", ""])
ok &= check(len(cmds) == 2, "rerun: 'Rerun to get' -> 2 passes then settles")
ok &= check("rerun 2" in msgs[1], "rerun: second pass labeled a rerun")

# 4. quick mode -> exactly one pass, no rerun even if the log asks.
cmds, msgs, disp = run_case(
    "pset-quick", docclass="pset", engine="pdflatex", mode="quick",
    outs=["Rerun to get cross-references right."])
ok &= check(len(cmds) == 1, "quick: single pass regardless of rerun signal")
ok &= check(msgs and "quick" in msgs[0], "quick: labeled a quick single pass")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
