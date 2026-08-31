#!/usr/bin/env python3
"""Coverage for texlib_cli.py -- the editor-independent command line.

Pure logic only: root resolution, TEXINPUTS derivation, the TEXMF payload
filter, mode validation. No TeX toolchain, so this runs in the fast CI job.
The build path itself is not re-tested here -- it is TexlibBuildCore, which
Sublime/test_texlib_builder.py already covers, and the whole point of the CLI
is that it adds no second implementation to test.
"""
import os
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import texlib_cli as C


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


ok = True
HERE = os.path.dirname(os.path.abspath(__file__))


# --- The core imports at all, outside Sublime --------------------------------
# This is the claim the whole CLI rests on. If TexlibBuildCore ever grows a
# real `import sublime`, every other test here would still pass while the CLI
# became unusable -- so assert it directly.
core = C.import_core()
ok &= check(hasattr(core, "TexlibBuild"), "build core imports outside Sublime")
ok &= check("sublime" not in sys.modules,
            "importing the core does not pull in the sublime module")
ok &= check(isinstance(core.MODE_MACROS, dict) and "default" in core.MODE_MACROS,
            "core exposes the mode table")


# --- Root resolution ---------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="texlibcli")
try:
    plain = os.path.join(tmp, "plain.tex")
    with open(plain, "w", encoding="utf-8") as fh:
        fh.write("\\documentclass{didactic}\n\\begin{document}x\\end{document}\n")
    root, src = C.resolve_root(plain)
    ok &= check(root == plain and "documentclass" in src,
                "resolve_root: a file with no magic comment is its own root")

    master = os.path.join(tmp, "master.tex")
    with open(master, "w", encoding="utf-8") as fh:
        fh.write("\\documentclass{pset}\n% the master\n")
    chapter = os.path.join(tmp, "chapter.tex")
    with open(chapter, "w", encoding="utf-8") as fh:
        fh.write("% !TeX root = master.tex\n\\section{One}\n")
    root, src = C.resolve_root(chapter)
    ok &= check(root == master and "the master" in src,
                "resolve_root: %!TeX root redirects to the master")

    # Extensionless target -- '% !TeX root = master' is common and legal.
    noext = os.path.join(tmp, "noext.tex")
    with open(noext, "w", encoding="utf-8") as fh:
        fh.write("% !TeX root = master\n")
    root, _ = C.resolve_root(noext)
    ok &= check(root == master, "resolve_root: extensionless root gets .tex")

    # A root pointing nowhere must NOT silently build the wrong file.
    bad = os.path.join(tmp, "bad.tex")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("% !TeX root = nonexistent.tex\n\\documentclass{quiz}\n")
    root, _ = C.resolve_root(bad)
    ok &= check(root == bad, "resolve_root: unreadable root falls back to the file")

    ok &= check(C.raw_engine("% !TeX program = lualatex\n") == "lualatex",
                "raw_engine: honours %!TeX program")
    ok &= check(C.raw_engine("\\documentclass{didactic}\n") == "pdflatex",
                "raw_engine: defaults to pdflatex")

    # looks_like_library_root must reject a directory that merely looks plausible.
    ok &= check(not C.looks_like_library_root(tmp),
                "looks_like_library_root: rejects an unrelated directory")
    ok &= check(C.looks_like_library_root(HERE),
                "looks_like_library_root: accepts the real checkout")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# --- TEXINPUTS ---------------------------------------------------------------
# The empty trailing segment is load-bearing: without it TEXINPUTS REPLACES
# kpathsea's default path instead of extending it, texmf-dist drops out, and
# every build dies before it reaches the document.
ok &= check(C.finalize_texinputs("/a" + os.pathsep + "/b").endswith(os.pathsep),
            "finalize_texinputs: appends the empty segment")
ok &= check(C.finalize_texinputs(["/a", "/b"]).count(os.pathsep) == 2,
            "finalize_texinputs: accepts a list")
already = "/a" + os.pathsep
ok &= check(C.finalize_texinputs(already) == already,
            "finalize_texinputs: does not double an existing empty segment")
ok &= check(C.finalize_texinputs("") == "",
            "finalize_texinputs: empty stays empty (inherit the environment)")

derived = C.derive_texinputs(HERE)
segs = derived.split(os.pathsep)
ok &= check(segs[0] == "." and HERE.replace("\\", "/") in segs,
            "derive_texinputs: leads with '.' then the library root")
ok &= check(not any(s.endswith("/Sublime") for s in segs),
            "derive_texinputs: excludes Sublime/ (editor integration, not library)")
ok &= check(any(s.endswith("/Notes") for s in segs),
            "derive_texinputs: includes a module directory holding a .cls")
ok &= check(not any("//" in s for s in segs if s),
            "derive_texinputs: no recursive '//' segments")
ok &= check(C.derive_texinputs(tempfile.gettempdir()) == "",
            "derive_texinputs: empty for a non-library directory")


# --- TEXMF payload -----------------------------------------------------------
payload = C.payload_files(HERE)
names = [n for _src, n in payload]
ok &= check(bool(payload), "payload_files: finds the library payload")
ok &= check(len(names) == len(set(names)),
            "payload_files: basenames are unique (a flat TDS dir needs that)")
                                       # Two shapes, and nothing else:
_flat = [n for n in names if "/" not in n]
ok &= check(all(n.lower().endswith(C.TEX_SOURCE_EXTS)
                or n.lower().endswith("-instructions.tex") for n in _flat),
            "payload_files: the flat half is .cls/.sty/.lua + -instructions.tex")
ok &= check(all(n.startswith(("statements/", "profiles/"))
                for n in names if "/" in n),
            "payload_files: the nested half is statements/ and profiles/ only")
ok &= check(len(_flat) == len(set(_flat)),
            "payload_files: flat basenames do not collide")
# Regression: the first cut of this shipped test_shuffle.lua and six siblings
# into TEXMFHOME, putting 'test_shuffle' in every TeX installation's global
# namespace. Same class of mistake the installer's Copy-LibraryTree guards.
ok &= check(not any(n.startswith("test_") for n in names),
            "payload_files: excludes test_*.lua")
ok &= check(not any(os.sep + "Sublime" + os.sep in s for s, _n in payload),
            "payload_files: excludes Sublime/")
ok &= check(not any(os.sep + "examples" + os.sep in s for s, _n in payload),
            "payload_files: excludes examples/")
for required in ("didactic.cls", "course-metadata.sty", "texlib-build.sty",
                 "problem_engine.lua"):
    ok &= check(required in names, "payload_files: ships %s" % required)

# Syllabus policy statements are the one part of the payload that must NOT be
# flattened: syllabus.cls resolves them by relative subpath, and
# unr/disability.tex and generic/disability.tex share a basename on purpose --
# they are alternatives to each other. A flat install would collide them.
stmts = [n for n in names if n.startswith("statements/")]
ok &= check(bool(stmts), "payload_files: ships the policy statements")
ok &= check(all(n.count("/") == 2 for n in stmts),
            "payload_files: statements keep statements/<profile>/<slug>.tex")
ok &= check("statements/generic/disability.tex" in stmts
            and "statements/unr/disability.tex" in stmts,
            "payload_files: same slug survives in two profiles")
ok &= check(all(n.endswith(".tex") for n in stmts),
            "payload_files: statements are .tex only")
# Every slug a profile carries must have a neutral fallback, or an adopter who
# sets no institution-profile gets a red placeholder where a real statement
# should be -- which is the failure the generic set exists to prevent.
_prof = {}
for n in stmts:
    _, profile, slug = n.split("/")
    _prof.setdefault(profile, set()).add(slug)
_gaps = sorted(s for p, v in _prof.items() if p != "generic"
               for s in v - _prof.get("generic", set()))
ok &= check(not _gaps,
            "every profile slug has a generic fallback"
            + (" -- missing: %s" % ", ".join(_gaps) if _gaps else ""))

# Regression: the payload shipped only .cls/.sty/.lua, so the four
# <prefix>-instructions.tex defaults were missing from every install and every
# Overleaf bundle. A quiz then died at build time with "File
# `quiz-instructions.tex' not found", which reads like the author's missing file
# rather than a broken install. Caught only because the Overleaf probe built a
# quiz; the earlier TEXMF install test used a syllabus and a lecture note.
_instr = [n for n in names if n.endswith("-instructions.tex")]
ok &= check(len(_instr) == 4,
            "payload_files: ships the four -instructions.tex defaults (got %d)"
            % len(_instr))
for _want in ("quiz-instructions.tex", "autoexam-instructions.tex",
              "pset-instructions.tex", "bingo-instructions.tex"):
    ok &= check(_want in names, "payload_files: ships %s" % _want)
# ...and nothing else .tex from a module dir. Quizzes/title.tex is \input by
# nothing and would put `title' in the global TeX search namespace.
ok &= check("title.tex" not in names,
            "payload_files: does NOT ship the generically-named title.tex")


# --- Overleaf bundle ----------------------------------------------------------
_ov = C.build_parser().parse_args(["overleaf", "-n"])
ok &= check(_ov.dry_run and _ov.func is C.cmd_overleaf, "parser: overleaf -n")
ok &= check(C.build_parser().parse_args(["overleaf"]).output is None,
            "parser: overleaf defaults its output path")
ok &= check("Compiler" in C.OVERLEAF_README
            and "LuaLaTeX" in C.OVERLEAF_README,
            "overleaf README names the compiler setting")
# The README tells Overleaf users to reach for the source-level switches,
# because they have no build tool to pass compile-time flags. If a switch it
# names stops existing, the instructions become wrong silently.
_switches = ("\\solutions", "\\keys", "\\rubrics", "\\studentmode", "\\drafts")
_declared = open(os.path.join(HERE, "texlib-build.sty"),
                 encoding="utf-8", errors="replace").read()
for _sw in _switches:
    ok &= check(_sw in C.OVERLEAF_README and _sw in _declared,
                "overleaf README's %s switch exists in texlib-build.sty" % _sw)
# Thesis profiles keep their directory the same way statements do, and for the
# same reason: the class resolves profiles/<name>.tex by relative subpath. This
# was missed when statements/ was special-cased -- the two landed on branches
# that could not see each other -- and the symptom is quiet, because an install
# with no profiles makes profile=unr fall back to the neutral pages, which look
# entirely plausible.
_profiles = [n for n in names if n.startswith("profiles/")]
ok &= check("profiles/unr.tex" in _profiles,
            "payload_files: ships the thesis profiles (%d)" % len(_profiles))
ok &= check(all(n.endswith(".tex") for n in _profiles),
            "payload_files: thesis profiles are .tex only")
# institutions.csv and its .source sidecar are the worklist, not library
# payload; a TEXMF tree has no use for 2,135 university names.
ok &= check(not any("institutions" in n for n in names),
            "payload_files: the institution worklist does NOT ship")


# --- Off-PATH TeX detection --------------------------------------------------
# "lualatex: not on PATH" is true and useless when a whole TeX Live is sitting
# in the default location -- which is the state a machine is in for as long as
# any program started before the installer keeps running. Contract: either None
# or a real file, never a stale guess, and never year-pinned.
for tool in ("lualatex", "kpsewhich", "definitely-not-a-tex-tool"):
    found = C.find_tex_offpath(tool)
    ok &= check(found is None or os.path.isfile(found),
                "find_tex_offpath(%s): None or a real file (%s)" % (tool, found))
ok &= check(C.find_tex_offpath("definitely-not-a-tex-tool") is None,
            "find_tex_offpath: None for a tool no distribution ships")


# --- Argument parsing / mode validation --------------------------------------
p = C.build_parser()
args = p.parse_args(["build", "a.tex"])
ok &= check(args.mode == "default" and args.files == ["a.tex"],
            "parser: build defaults to --mode default")
args = p.parse_args(["build", "a.tex", "b.tex", "-m", "solutions", "-q"])
ok &= check(args.files == ["a.tex", "b.tex"] and args.mode == "solutions"
            and args.quiet,
            "parser: multiple files, mode, quiet")
args = p.parse_args(["install", "--dry-run"])
ok &= check(args.dry_run and args.func is C.cmd_install, "parser: install --dry-run")

# Every mode the CLI advertises must be one the core actually knows, or the
# help text is a promise the build breaks.
known = set(core.MODE_MACROS) | {core.MODE_QUICK}
_phantom = sorted(set(C._MODE_HELP) - known)
_undocumented = sorted(known - set(C._MODE_HELP))
ok &= check(not _phantom,
            "every advertised mode exists in the core"
            + (" -- phantom: %s" % ", ".join(_phantom) if _phantom else ""))
ok &= check(not _undocumented,
            "every core mode is documented in --help"
            + (" -- missing: %s" % ", ".join(_undocumented) if _undocumented else ""))
ok &= check(set(core.RENAMED_MODES).isdisjoint(known),
            "retired tokens are not also live modes")

# --variants must beat an already-exported TEXLIB_VARIANTS. _configured_variants
# reads the env var FIRST and only then builder_settings -- the opposite
# precedence from _setting_on -- so routing the flag through builder_settings
# would let a stale export silently override the argument just typed.
_saved = os.environ.get(core.VARIANT_ENV)
try:
    os.environ[core.VARIANT_ENV] = "student"
    probe = core.TexlibBuild(tex_root=__file__, engine="pdflatex",
                             options=[], display=lambda _t: None)
    probe.builder_settings = {core.VARIANT_SETTING: ["instructor"]}
    ok &= check(probe._configured_variants() == ["student"],
                "core precedence: TEXLIB_VARIANTS beats builder_settings")
    os.environ[core.VARIANT_ENV] = "none"
    ok &= check(probe._configured_variants() == [],
                "--variants none pins the base PDF alone")
    os.environ[core.VARIANT_ENV] = "student,instructor"
    ok &= check(probe._configured_variants() == ["student", "instructor"],
                "--variants accepts a comma-separated list")
finally:
    if _saved is None:
        os.environ.pop(core.VARIANT_ENV, None)
    else:
        os.environ[core.VARIANT_ENV] = _saved

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
