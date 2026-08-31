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


def drive(host, outs, writes=None):
    """Run the coroutine, feeding outs[i] as self.out after the i-th command.

    writes[i], when given, is the .aux contents that pass "left behind" -- the
    cross-pass state the rerun detector fingerprints. The cases set
    aux_directory="<<root>>", so the aux dir IS the tex dir. A pass with no
    entry writes nothing, i.e. leaves the state byte-stable.
    """
    aux = os.path.join(os.path.dirname(host.tex_root), host.base_name + ".aux")
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
            if writes and i < len(writes) and writes[i] is not None:
                with open(aux, "w", encoding="utf-8") as fh:
                    fh.write(writes[i])
            i += 1
            item = next(gen)
    except StopIteration:
        pass
    return cmds, msgs


def run_case(name, **kw):
    disp = []
    outs = kw.pop("outs", [])
    writes = kw.pop("writes", None)
    with tempfile.TemporaryDirectory() as tmp:
        host = make_host(tmp, kw["docclass"], kw["engine"], kw["mode"],
                         lambda t: disp.append(t))
        cmds, msgs = drive(host, outs, writes)
    return cmds, msgs, "".join(disp)


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True

# 1. autoexam, no magic comment, default mode -> lua force + file-line-error.
cmds, msgs, disp = run_case("autoexam-default",
                            docclass="autoexam", engine="pdflatex", mode="base")
ok &= check(len(cmds) == 1, "autoexam/base: single pass (no rerun signal)")
ok &= check(cmds and cmds[0][0] == "lualatex", "autoexam: engine forced to lualatex")
ok &= check(cmds and "-file-line-error" in cmds[0], "autoexam: -file-line-error present")
ok &= check("requires lualatex" in disp, "autoexam: force message displayed")
ok &= check(cmds and cmds[0][-1] == "doc.tex", "autoexam/base: bare \\input arg")

# 2. pset, key mode -> pdflatex kept, macro injected.
cmds, msgs, disp = run_case("pset-key",
                            docclass="pset", engine="pdflatex", mode="key")
ok &= check(cmds and cmds[0][0] == "pdflatex", "pset: engine stays pdflatex")
ok &= check(cmds and cmds[0][-1] == r"\def\ShowKey{}\input{doc.tex}",
            "pset/key: \\ShowKey macro injected before \\input")
ok &= check(cmds and "-file-line-error" in cmds[0], "pset: -file-line-error present")

# 3. rerun loop: a "Rerun to get..." pass that also moved the aux state (which
#    is what really produces that warning) triggers exactly one more pass, and
#    the settled pass ends it.
cmds, msgs, disp = run_case(
    "pset-rerun", docclass="pset", engine="pdflatex", mode="base",
    outs=["Rerun to get cross-references right.", ""],
    writes=[r"\newlabel{a}{{1}{7}}", None])
ok &= check(len(cmds) == 2, "rerun: 'Rerun to get' -> 2 passes then settles")
ok &= check("rerun 2" in msgs[1], "rerun: second pass labeled a rerun")

# 4. quick mode -> exactly one pass, no rerun even if the log asks.
cmds, msgs, disp = run_case(
    "pset-quick", docclass="pset", engine="pdflatex", mode="quick",
    outs=["Rerun to get cross-references right."],
    writes=[r"\newlabel{a}{{1}{7}}"])
ok &= check(len(cmds) == 1, "quick: single pass regardless of rerun signal")
ok &= check(msgs and "quick" in msgs[0], "quick: labeled a quick single pass")

# --- state-fingerprint convergence ----------------------------------------

# 5. The veto: the log asks for a rerun but the pass consumed and produced
#    byte-identical state -> another pass is provably a no-op, so it is skipped.
cmds, msgs, disp = run_case(
    "pset-stable-veto", docclass="pset", engine="pdflatex", mode="base",
    outs=["Rerun to get cross-references right."] * 4)
ok &= check(len(cmds) == 1, "veto: stable aux state overrides a log rerun request")

# 6. The blind spot: state moved but the log said nothing (autoexam guts
#    \@testdef, so a shifted "page X of Y" footer never warns) -> settle it.
cmds, msgs, disp = run_case(
    "autoexam-silent", docclass="autoexam", engine="lualatex", mode="base",
    outs=["", ""], writes=[r"\newlabel{@lastqpage@A}{{}{4}}", None])
ok &= check(len(cmds) == 2, "silent log: aux change alone earns a settling pass")
ok &= check(len(msgs) == 2 and "rerun 2" in msgs[1],
            "silent log: the extra pass is labeled a rerun")

# 7. ...but bounded. A document that re-randomizes every pass (problem_engine
#    seeds the unversioned case from os.time()) never converges; a silent log
#    buys STATE_ONLY_RERUNS extra passes, not the whole MAX_RERUNS budget.
cmds, msgs, disp = run_case(
    "quiz-churn", docclass="quiz", engine="lualatex", mode="base",
    outs=[""] * 6, writes=["v%d" % n for n in range(6)])
ok &= check(len(cmds) == 1 + texlib_build.STATE_ONLY_RERUNS,
            "churn: silent-log reruns stop at STATE_ONLY_RERUNS (%d passes)"
            % len(cmds))

# 8. Oscillation A -> B -> A: no fixed point exists, so stop at the cycle
#    instead of spending the rest of MAX_RERUNS rediscovering it.
cmds, msgs, disp = run_case(
    "pset-oscillate", docclass="pset", engine="pdflatex", mode="base",
    outs=["Rerun to get cross-references right."] * 5,
    writes=["A", "B", "A", "B", "A"])
ok &= check(len(cmds) == 3, "oscillation: stops at the repeat (3 passes)")
ok &= check("oscillating" in disp, "oscillation: reported, not silent")

# 9. Hitting the ceiling is reported rather than silently truncating the build.
cmds, msgs, disp = run_case(
    "pset-unsettled", docclass="pset", engine="pdflatex", mode="base",
    outs=["Rerun to get cross-references right."] * 6,
    writes=["v%d" % n for n in range(6)])
ok &= check(len(cmds) == texlib_build.MAX_RERUNS,
            "ceiling: stops at MAX_RERUNS (%d passes)" % len(cmds))
ok &= check("unsettled after" in disp, "ceiling: reported, not silent")

# 10. biblatex's own rerun bookkeeping is not document state: an .aux that
#     differs ONLY in \abx@aux@read@bbl* lines must not buy a pass. (It flips on
#     the pass after biblatex settles even with no bibliography, which cost a
#     pointless third pass on every cold didactic build before it was filtered.)
BBL_A = "\\relax\n\\abx@aux@read@bbl@mdfivesum{nohash}\n\\abx@aux@read@bblrerun\n"
BBL_B = "\\relax\n\\abx@aux@read@bbl@mdfivesum{nobblfile}\n"
cmds, msgs, disp = run_case(
    "didactic-bbl-noise", docclass="didactic", engine="pdflatex", mode="base",
    outs=["", ""], writes=[BBL_A, BBL_B])
ok &= check(len(cmds) == 2,
            "bbl noise: pass 1 creating the aux still earns its settling pass")
cmds, msgs, disp = run_case(
    "didactic-bbl-settled", docclass="didactic", engine="pdflatex", mode="base",
    outs=["", "", ""], writes=[BBL_A, BBL_B, BBL_B])
ok &= check(len(cmds) == 2,
            "bbl noise: an aux differing only in biblatex rerun flags is settled")

# 11. Opt-out: with state detection off the loop is the old log-only behavior
#     (a log request wins even though the state never moved).
os.environ["TEXLIB_STATE_RERUN"] = "0"
try:
    cmds, msgs, disp = run_case(
        "pset-optout", docclass="pset", engine="pdflatex", mode="base",
        outs=["Rerun to get cross-references right.", ""])
finally:
    del os.environ["TEXLIB_STATE_RERUN"]
ok &= check(len(cmds) == 2, "opt-out: TEXLIB_STATE_RERUN=0 restores log-only reruns")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
