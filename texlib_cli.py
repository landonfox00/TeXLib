#!/usr/bin/env python3
# texlib_cli.py
# ============================================================================
# TeXLib -- the editor-independent command line.
#
# WHY THIS FILE EXISTS
#
# Everything that makes TeXLib worth using over a bare `lualatex` -- the variant
# fan-out, the tagged PDF/UA twins, the veraPDF conformance reports, per-version
# exam slicing, the biber cache, the rerun-until-settled loop, SyncTeX
# redirection -- lived behind Sublime Text. A colleague on VS Code, TeXShop,
# TeXstudio, Emacs or a Makefile got the .cls files and was left to hand-write
#
#     lualatex "\def\ShowSolutions{}\def\ShowRubric{}\input{exam}"
#
# and to know, unprompted, that the answer is different for an exam than for a
# lecture note. That is not a library anyone else can adopt.
#
# Nothing about the build logic required an editor. `TexlibBuildCore` was
# already written host-agnostic (see its docstring): it reads a small contract
# -- display / tex_root / tex_name / base_name / engine / options / out /
# aux_directory -- and yields (argv, message) pairs for a host to run. It
# imports the standard library and nothing else. There were two hosts, both
# inside Sublime; this is the third, and it is the one that needs no editor at
# all.
#
# So this file is deliberately NOT a third implementation of the build. It is a
# host: resolve the root document, derive TEXINPUTS, drive commands(), print
# what happens, return an exit code. The logic stays in ONE place, exactly as
# `texlib_builder.py` says it must, and a bug fixed for Ctrl+B is fixed here
# too.
#
# USAGE
#
#     python texlib_cli.py build exam.tex                  # every applicable variant
#     python texlib_cli.py build exam.tex --mode solutions # just the key
#     python texlib_cli.py build notes.tex --mode accessible
#     python texlib_cli.py install                         # classes -> TEXMFHOME
#     python texlib_cli.py doctor                          # what's wired up?
#
# From another editor, that first line is the whole integration: a VS Code
# task, a latexmk rule, a Makefile target, a CI step.
# ============================================================================

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# The build core lives in the Sublime plugin package because THAT is the
# consumer with the hard constraint -- Sublime's plugin host cannot reach
# repo-root modules, while anything at the root can reach down. Same reasoning
# as texlib_buildspec.py's docstring, and the same direction of travel.
PLUGIN_PKG = os.path.join(HERE, "Sublime", "texlib")

# Windows: don't flash a console window for the short-lived probes (kpsewhich,
# mktexlsr). The engine passes inherit this console on purpose -- their output
# is the point.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# --- Document probes ---------------------------------------------------------
# Same magic comments the editors honour, read from the file rather than from a
# live buffer. `% !TeX root` matters more here than in an editor: a build fired
# from a Makefile is likelier to name a chapter than the master.
ROOT_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+root\s*=\s*(.+?)\s*$")
PROGRAM_RE = re.compile(r"(?im)^%\s*!\s*T[Ee]X\s+program\s*=\s*(\S+)")

# file:line:col: message, from -file-line-error. Identical to the regex the
# Sublime build system matches on, so both hosts call the same output an error.
RESULT_RE = re.compile(r"^((?:.:)?[^:\n\r]*):([0-9]+):?([0-9]+)?:? (.*)$")
FATAL_RE = re.compile(r"^!\s|! LaTeX Error|Emergency stop|Fatal error")
WARNING_RE = re.compile(r"\bWarning:")

# The probe that decides whether a directory really is a TeXLib library, shared
# with the plugin and the installer so a coincidental parent cannot pass for one.
CORE_LIBRARY_FILES = ("course-metadata.sty", "texlib-build.sty", "basic-utilities.sty")
TEX_SOURCE_EXTS = (".sty", ".cls", ".lua")

MAX_WARNINGS = 500


# --- Importing the build core ------------------------------------------------

def import_core():
    """Import the shared build core, or exit with a diagnosis.

    texlib_build.py tries `from TeXLib import texlib_buildspec` first (its name
    inside Sublime's package namespace) and falls back to a bare
    `import texlib_buildspec`, which is what resolves once its own directory is
    on sys.path. No shim required -- that fallback was put there for the test
    harness and works just as well for us.
    """
    if PLUGIN_PKG not in sys.path:
        sys.path.insert(0, PLUGIN_PKG)
    try:
        import texlib_build  # noqa: PLC0415 - deliberately deferred
    except ImportError as exc:
        sys.stderr.write(
            "texlib: cannot import the build core from\n"
            "  %s\n"
            "%s\n\n"
            "This file must stay at the root of a TeXLib checkout; the core it "
            "drives lives in Sublime/texlib/.\n" % (PLUGIN_PKG, exc)
        )
        raise SystemExit(2)
    return texlib_build


# --- Paths and TEXINPUTS -----------------------------------------------------

def looks_like_library_root(path):
    """True only when the core .sty files are actually in `path`."""
    try:
        return all(os.path.isfile(os.path.join(path, f)) for f in CORE_LIBRARY_FILES)
    except OSError:
        return False


def derive_texinputs(root=HERE):
    """TEXINPUTS covering the library: its root plus every immediate
    subdirectory that actually holds a .cls/.sty/.lua.

    Explicit and non-recursive, matching the plugin and the installer. A
    recursive `<root>//` re-walks the whole tree on every pass and lets a stale
    .aux shadow a same-named source. Generated rather than hardcoded, so a new
    module directory needs no code change here.

    Returns "" if this checkout does not look like a library -- in which case
    the classes had better be installed in TEXMF (see `install`), and inheriting
    the ambient TEXINPUTS is the right answer.
    """
    if not looks_like_library_root(root):
        return ""
    segments = [".", root.replace("\\", "/")]
    for name in sorted(os.listdir(root)):
        sub = os.path.join(root, name)
        if name.startswith(".") or name == "Sublime" or not os.path.isdir(sub):
            continue
        try:
            entries = os.listdir(sub)
        except OSError:
            continue
        if any(e.lower().endswith(TEX_SOURCE_EXTS) for e in entries):
            segments.append((root + "/" + name).replace("\\", "/"))
    return os.pathsep.join(segments)


def finalize_texinputs(raw):
    """Guarantee the trailing empty segment.

    kpathsea only APPENDS its default search path where it finds an empty
    segment. Without one, TEXINPUTS *replaces* the default: texmf-dist drops out
    and every build dies at startup because luaotfload cannot find its Unicode
    data. No working configuration can want that, so this is not negotiable and
    not a user preference.
    """
    if isinstance(raw, (list, tuple)):
        raw = os.pathsep.join(raw)
    if raw and "" not in raw.split(os.pathsep):
        raw += os.pathsep
    return raw


def resolve_root(path):
    """(root_path, source_text) for the document to build.

    Honours `% !TeX root`; otherwise the named file is its own root.
    """
    path = os.path.abspath(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError as exc:
        sys.stderr.write("texlib: cannot read %s: %s\n" % (path, exc))
        raise SystemExit(2)
    m = ROOT_RE.search(src[:1024])
    if not m:
        return path, src
    root = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
    if not os.path.splitext(root)[1]:
        root += ".tex"
    try:
        with open(root, "r", encoding="utf-8", errors="replace") as fh:
            return root, fh.read()
    except OSError:
        # A broken magic comment should not silently redirect the build to a
        # file that isn't there; fall back to the file we were handed and say so.
        sys.stderr.write(
            "texlib: %% !TeX root points at %s, which cannot be read -- "
            "building %s itself.\n" % (root, os.path.basename(path))
        )
        return path, src


def raw_engine(src):
    """The `% !TeX program` engine, else pdflatex.

    No lua-class forcing here on purpose: the core's _select_engine owns that,
    and duplicating the rule is how the two copies of LUALATEX_CLASSES drifted
    the last time (see texlib_buildspec.py).
    """
    m = PROGRAM_RE.search(src)
    return m.group(1).strip().lower() if m else "pdflatex"


# --- TEXMF install -----------------------------------------------------------

def kpsewhich(*args):
    exe = shutil.which("kpsewhich")
    if not exe:
        return ""
    try:
        out = subprocess.run(
            [exe, *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=_NO_WINDOW, timeout=15,
        )
        return (out.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def texmfhome():
    """The user-writable TEXMFHOME, asked of the live TeX installation."""
    return kpsewhich("-var-value=TEXMFHOME") or os.path.join(
        os.path.expanduser("~"), "texmf")


def find_tex_offpath(tool):
    """A `tool` that exists in a well-known TeX installation but is NOT on PATH.

    "lualatex: not on PATH" is a true statement and a useless one when there is
    a complete TeX Live sitting in the default location. The usual causes are
    mundane and all have the same fix: a terminal (or editor, or agent) started
    before the installer ran and inherited the old environment; an upgrade that
    moved the year directory out from under a PATH entry; a MacTeX install
    whose `/Library/TeX/texbin` the login shell has not picked up yet.

    Globbed by year and taken newest-first, never pinned: hardcoding a year
    works right up until the next one, and the failure is silent because a
    missing tool downgrades to a skip rather than an error.
    """
    import glob  # noqa: PLC0415 - only needed on the diagnostic path

    roots = []
    if os.name == "nt":
        roots += [r"C:\texlive\*\bin\*",
                  r"C:\texlive\*\bin\windows",
                  os.path.join(os.environ.get("LOCALAPPDATA", ""),
                               "TeXLib", "TexLive", "*", "bin", "*"),
                  r"C:\Program Files\MiKTeX\miktex\bin\x64"]
        exts = (".exe", ".bat", "")
    else:
        roots += ["/usr/local/texlive/*/bin/*",     # TeX Live, Linux + macOS
                  "/Library/TeX/texbin",            # MacTeX's stable symlink dir
                  "/opt/texlive/*/bin/*",
                  os.path.expanduser("~/texlive/*/bin/*")]
        exts = ("",)
    for pattern in roots:
        if not pattern:
            continue
        for d in sorted(glob.glob(pattern), reverse=True):
            for ext in exts:
                cand = os.path.join(d, tool + ext)
                if os.path.isfile(cand):
                    return cand
    return None


def texmf_target():
    """Where an installed copy of the classes belongs."""
    return os.path.join(texmfhome(), "tex", "latex", "texlib")


def payload_files(root=HERE):
    """What an install copies, as (source, destination-relative-path) pairs.

    Two shapes, deliberately:

    * `.cls`/`.sty`/`.lua` land FLAT. Their basenames are unique across the
      tree and kpathsea searches a TDS leaf directory as one namespace, so a
      flat drop is what `\\documentclass{didactic}` needs.
    * `Syllabi/statements/**` keeps its `statements/<profile>/<slug>.tex`
      structure, because that structure IS the lookup key -- syllabus.cls
      resolves `statements/unr/disability.tex` by relative subpath, and
      `unr/disability.tex` and `generic/disability.tex` deliberately share a
      basename. Flattening them would collide two files whose whole purpose is
      to be alternatives to each other. kpathsea resolves the relative subpath
      from a TEXMF tree (verified in test_texlib_cli.py), so this works the
      same installed as it does on TEXINPUTS.

    `test_*` is excluded at any depth for the same reason the installer's
    Copy-LibraryTree drops `test_*.py`: the Lua test files sit right next to
    the engines they exercise, and shipping them puts a file called
    `test_shuffle` into every TeX installation's global search namespace --
    where the next person's `\\input{test_shuffle}` finds ours.
    """
    out = []
    seen = {}
    # Directories whose internal structure IS the lookup key, so they keep it
    # through an install instead of being flattened. Both are resolved by
    # relative subpath from a class -- statements/<profile>/<slug>.tex and
    # profiles/<name>.tex -- and both deliberately reuse filenames across
    # subdirectories, which a flat drop would collide.
    #
    # Thesis/profiles was missed when statements/ was special-cased, because the
    # two landed on separate branches that could not see each other. The symptom
    # is quiet: an installed copy has no profiles, so profile=unr warns once and
    # renders the institution-neutral pages, which look entirely plausible.
    STRUCTURED = [os.path.join(root, "Syllabi", "statements"),
                  os.path.join(root, "Thesis", "profiles")]

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in
            ("Sublime", "SublimeUser", "__pycache__", "dist", "tests", "examples")
        ]
        structured_root = None
        for _root in STRUCTURED:
            if os.path.isdir(_root) and os.path.commonpath(
                    [os.path.abspath(dirpath), _root]) == _root:
                structured_root = _root
                break

        for fn in sorted(filenames):
            if fn.startswith("test_") or fn.startswith("_test"):
                continue
            src = os.path.join(dirpath, fn)

            if structured_root:
                # .tex only: institutions.csv and its .source sidecar are the
                # worklist, not library payload, and have no business in a
                # TEXMF tree.
                if not fn.lower().endswith(".tex"):
                    continue
                rel = os.path.relpath(src, os.path.dirname(structured_root))
                out.append((src, rel.replace(os.sep, "/")))
                continue

            if not fn.lower().endswith(TEX_SOURCE_EXTS):
                continue
            if fn in seen:
                sys.stderr.write(
                    "texlib: two files named %s (%s and %s); a flat TEXMF "
                    "install cannot hold both.\n" % (fn, seen[fn], src)
                )
                raise SystemExit(2)
            seen[fn] = src
            out.append((src, fn))
    return sorted(out, key=lambda p: p[1])


def refresh_texmf_db():
    """Rebuild the filename database so kpathsea sees the change.

    TEXMFHOME is usually scanned live rather than indexed, so this is often a
    no-op -- but it is cheap, and on the installations that DO index it, a
    skipped mktexlsr is an install that mysteriously does nothing.
    """
    exe = shutil.which("mktexlsr") or shutil.which("texhash")
    if not exe:
        return
    try:
        subprocess.run([exe], capture_output=True,
                       creationflags=_NO_WINDOW, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass


def cmd_install(args):
    target = args.target or texmf_target()
    files = payload_files()
    if not files:
        sys.stderr.write("texlib: no .cls/.sty/.lua found; is this a checkout?\n")
        return 2
    if args.dry_run:
        print("texlib: would install %d file(s) into" % len(files))
        print("  %s" % target)
        for _src, name in files:
            print("    %s" % name)
        return 0
    os.makedirs(target, exist_ok=True)
    for src, rel in files:
        dest = os.path.join(target, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
    refresh_texmf_db()
    print("texlib: installed %d file(s) into" % len(files))
    print("  %s" % target)
    print()
    print("\\documentclass{didactic} now resolves in any editor, with no")
    print("TEXINPUTS setting. Re-run after pulling library updates.")
    print()
    print("Note: this copy SHADOWS a checkout you build from directly.")
    print("If you develop the library itself, use `texlib_cli.py uninstall`")
    print("and let TEXINPUTS resolve the classes from your working tree.")
    return 0


def installed_count(target):
    """How many library files an install left at `target`.

    Walks rather than listing one level: since the statements keep their
    `statements/<profile>/` structure, a flat listdir undercounts an install by
    every statement in it and would report a populated tree as nearly empty.
    """
    if not os.path.isdir(target):
        return 0
    exts = TEX_SOURCE_EXTS + (".tex",)
    return sum(1 for d, _sub, files in os.walk(target)
               for f in files if f.lower().endswith(exts))


def cmd_uninstall(args):
    target = args.target or texmf_target()
    n = installed_count(target)
    if not n:
        print("texlib: nothing installed at %s" % target)
        return 0
    if args.dry_run:
        print("texlib: would remove %d file(s) from %s" % (n, target))
        return 0
    shutil.rmtree(target)
    refresh_texmf_db()
    print("texlib: removed %d file(s) from %s" % (n, target))
    return 0


# --- doctor ------------------------------------------------------------------

def cmd_doctor(args):
    """Report what a build would actually use. Pastes into a bug report."""
    ok = True

    def line(status, label, value=""):
        nonlocal ok
        if status == "FAIL":
            ok = False
        print("  [%-4s] %-22s %s" % (status, label, value))

    print("TeXLib CLI doctor")
    print()
    print("Library")
    root_ok = looks_like_library_root(HERE)
    line("OK" if root_ok else "FAIL", "checkout root",
         HERE if root_ok else "%s (missing core .sty)" % HERE)

    print()
    print("Toolchain")
    offpath = []
    for tool, required in (("lualatex", True), ("pdflatex", True),
                           ("biber", False), ("kpsewhich", False),
                           ("synctex", False)):
        found = shutil.which(tool)
        if found:
            line("OK", tool, found)
            continue
        elsewhere = find_tex_offpath(tool)
        if elsewhere:
            offpath.append(elsewhere)
            line("FAIL" if required else "WARN", tool,
                 "not on PATH -- but present at %s" % elsewhere)
        else:
            line("FAIL" if required else "WARN", tool, "not on PATH")
    try:
        spec_mod = import_core()
        vera = spec_mod.find_verapdf()
    except SystemExit:
        vera = None
    line("OK" if vera else "WARN", "veraPDF",
         vera or "not found -- accessible builds skip the conformance report")

    try:
        import pypdf  # noqa: F401,PLC0415
        line("OK", "pypdf", "version slicing available")
    except ImportError:
        line("WARN", "pypdf", "not installed -- exam version slicing is skipped")

    if offpath:
        # One diagnosis, not one per tool: they share a cause and a fix, and
        # repeating it five times buries it.
        print()
        print("  A TeX installation exists but this process cannot see it.")
        print("  Add to PATH:  %s" % os.path.dirname(offpath[0]))
        print("  If you just installed or upgraded TeX, a program started")
        print("  beforehand keeps the old PATH until it restarts -- restart")
        print("  this terminal (and your editor) before anything else.")

    print()
    print("Resolution")
    installed = texmf_target()
    n_installed = installed_count(installed)
    if n_installed:
        line("OK", "TEXMF install", "%d file(s) in %s" % (n_installed, installed))
        if root_ok:
            line("WARN", "shadowing",
                 "the TEXMF copy wins over this checkout; uninstall to "
                 "develop the library")
    else:
        line("WARN", "TEXMF install", "none -- builds rely on TEXINPUTS")

    derived = derive_texinputs()
    line("OK" if derived else "WARN", "derived TEXINPUTS",
         "%d segment(s)" % len(derived.split(os.pathsep)) if derived
         else "empty -- inheriting the environment")
    if args.verbose and derived:
        for seg in finalize_texinputs(derived).split(os.pathsep):
            print("           %s" % (seg or "(empty -> kpathsea defaults)"))

    print()
    return 0 if ok else 1


# --- The build host ----------------------------------------------------------

class CliHost:
    """Drives TexlibBuildCore.commands() from a terminal.

    This is the whole of the CLI's build implementation: run each yielded argv,
    stream its output, feed it back as host.out, resume. The Sublime runner
    (texlib.py _drive) does the same thing wrapped in threads, cancellation and
    status-bar animation; none of that belongs in a foreground command.
    """

    def __init__(self, core_mod, root, mode, texinputs, settings, quiet):
        self.core_mod = core_mod
        self.root = root
        self.mode = mode
        self.texinputs = texinputs
        self.quiet = quiet
        self.tex_dir = os.path.dirname(root) or "."
        self.errors = []
        self.warnings = []
        self.fatal = False

        with open(root, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()

        self.host = core_mod.TexlibBuild(
            tex_root=root,
            engine=raw_engine(src),
            options=["--texlib-mode=%s" % mode],
            display=self.emit,
        )
        if settings:
            # The core reads builder_settings first, then the matching TEXLIB_*
            # env var, then its default -- same precedence as in Sublime.
            self.host.builder_settings = settings

    def emit(self, text):
        if not self.quiet:
            sys.stdout.write(text)
            sys.stdout.flush()

    def collect(self, line):
        self.emit(line)
        s = line.rstrip("\r\n")
        m = RESULT_RE.match(s)
        if m:
            self.fatal = True
            # Source errors are the actionable ones; a generated .aux is noise.
            if not m.group(1).lower().endswith(".aux"):
                self.errors.append(s)
        elif FATAL_RE.search(s):
            self.fatal = True
        elif WARNING_RE.search(s) and len(self.warnings) < MAX_WARNINGS:
            self.warnings.append(s)

    def run_argv(self, cmd):
        """One engine/biber pass. Returns the captured text for host.out.

        TEXLIB_AUX_DIR goes into THIS subprocess's env rather than os.environ so
        two concurrent CLI builds of different documents cannot race a shared
        value -- the same reason the Sublime runner does it per-process.
        """
        env = dict(os.environ)
        if self.texinputs:
            env["TEXINPUTS"] = self.texinputs
        env["TEXLIB_AUX_DIR"] = getattr(self.host, "_aux_target", None) or ""
        try:
            proc = subprocess.Popen(
                cmd, cwd=self.tex_dir, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            self.emit("texlib: failed to launch %s: %s\n" % (cmd[0], exc))
            self.fatal = True
            return ""
        chunks = []
        try:
            for line in proc.stdout:
                chunks.append(line)
                self.collect(line)
        finally:
            if proc.stdout:
                proc.stdout.close()
            proc.wait()
        return "".join(chunks)

    def build(self):
        """Consume commands() to exhaustion. _postprocess runs inside it, so
        StopIteration means the build is genuinely finished."""
        gen = self.host.commands()
        try:
            item = next(gen)
            while True:
                cmd, msg = item
                self.emit(msg + "\n")
                self.host.out = self.run_argv(cmd)
                item = next(gen)
        except StopIteration:
            pass
        except KeyboardInterrupt:
            self.emit("\ntexlib: build interrupted.\n")
            return 130
        return 1 if self.fatal else 0

    def report(self):
        """A condensed tail, because a 2000-line engine log buries the one line
        that matters. Errors always; warnings only when they are all there is.

        Deduplicated: a build runs the engine until the aux state settles, and a
        document that fails on pass 1 fails identically on every pass after it.
        Reporting the same line five times reads as five problems.
        """
        errors = list(dict.fromkeys(self.errors))
        if errors:
            sys.stderr.write("\ntexlib: %d error(s) in %s\n"
                             % (len(errors), os.path.basename(self.root)))
            for e in errors[:20]:
                sys.stderr.write("  %s\n" % e)
            if len(errors) > 20:
                sys.stderr.write("  ... and %d more\n" % (len(errors) - 20))
        elif self.fatal:
            sys.stderr.write("\ntexlib: build failed (no file:line error "
                             "reported -- see the log above)\n")
        elif self.warnings and not self.quiet:
            sys.stderr.write("\ntexlib: %d warning(s)\n" % len(self.warnings))


def cmd_build(args):
    core = import_core()

    if args.mode in core.RENAMED_MODES:
        replacement = core.RENAMED_MODES[args.mode]
        sys.stderr.write("texlib: mode %r was renamed to %r; using %r.\n"
                         % (args.mode, replacement, replacement))
        args.mode = replacement

    known = set(core.MODE_MACROS) | {core.MODE_QUICK}
    if args.mode not in known:
        sys.stderr.write("texlib: unknown mode %r. Known modes: %s\n"
                         % (args.mode, ", ".join(sorted(known))))
        return 2

    texinputs = finalize_texinputs(
        args.texinputs if args.texinputs is not None else derive_texinputs())

    settings = {}
    if args.variants is not None:
        # Set the ENV var, not builder_settings. _configured_variants reads
        # TEXLIB_VARIANTS first and only falls back to builder_settings, which
        # is the opposite precedence from _setting_on -- so a user with
        # TEXLIB_VARIANTS already exported would have silently overridden the
        # flag they just typed. An explicit argument has to win.
        # The core parses a comma/space-separated string, and "none"/"base"
        # both mean the single-PDF behaviour.
        os.environ[core.VARIANT_ENV] = args.variants
    if args.no_publish:
        settings[core.PUBLISH_SETTING] = False

    status = 0
    for path in args.files:
        root, _src = resolve_root(path)
        if len(args.files) > 1:
            print("=== %s ===" % os.path.basename(root))
        host = CliHost(core, root, args.mode, texinputs, settings, args.quiet)
        rc = host.build()
        host.report()
        status = status or rc
    return status


def cmd_modes(args):
    core = import_core()
    print("Build modes (--mode):")
    for name in ("default", "base", "student", "solutions", "solutions-inline",
                 "instructor", "draft", "quick", "full", "accessible"):
        print("  %-18s %s" % (name, _MODE_HELP.get(name, "")))
    if core.RENAMED_MODES:
        print()
        print("Retired tokens (accepted, with a warning):")
        for old, new in sorted(core.RENAMED_MODES.items()):
            print("  %-18s -> %s" % (old, new))
    return 0


_MODE_HELP = {
    "default": "base PDF + every variant the document actually supports",
    "base": "the plain PDF alone, references fully settled",
    "student": "blank answer space",
    "solutions": "the student's key: answers, no grading apparatus",
    "solutions-inline": "answers drawn into the student's blank",
    "instructor": "answers plus rubric and common-error notes",
    "draft": "adds a DRAFT watermark",
    "quick": "one pass, no biber; references may be stale",
    "full": "every variant, skipping the content check",
    "accessible": "normal PDF + tagged PDF/UA twin + veraPDF report",
}


# --- Argument parsing --------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="texlib",
        description="Build TeXLib documents from any editor, or none.",
        epilog="Run `texlib modes` for what --mode accepts.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="build one or more documents")
    b.add_argument("files", nargs="+", metavar="FILE.tex")
    b.add_argument("-m", "--mode", default="default",
                   help="build mode (default: %(default)s)")
    b.add_argument("--variants", metavar="LIST",
                   help="pin the variant set, e.g. student,instructor "
                        "or 'none' for the base PDF alone")
    b.add_argument("--texinputs", metavar="PATH",
                   help="override TEXINPUTS (default: derived from this checkout)")
    b.add_argument("--no-publish", action="store_true",
                   help="skip the shareable-copy step")
    b.add_argument("-q", "--quiet", action="store_true",
                   help="suppress the engine log; report errors only")
    b.set_defaults(func=cmd_build)

    i = sub.add_parser("install",
                       help="copy the classes into TEXMFHOME so any editor "
                            "resolves them")
    i.add_argument("--target", metavar="DIR",
                   help="override the install directory")
    i.add_argument("-n", "--dry-run", action="store_true")
    i.set_defaults(func=cmd_install)

    u = sub.add_parser("uninstall", help="remove an installed copy from TEXMFHOME")
    u.add_argument("--target", metavar="DIR")
    u.add_argument("-n", "--dry-run", action="store_true")
    u.set_defaults(func=cmd_uninstall)

    d = sub.add_parser("doctor", help="report what a build would use")
    d.add_argument("-v", "--verbose", action="store_true")
    d.set_defaults(func=cmd_doctor)

    m = sub.add_parser("modes", help="list the build modes")
    m.set_defaults(func=cmd_modes)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
