# texlib_build.py
# ============================================================================
# TexlibBuild -- the host-agnostic TeXLib build engine (ported from the
# LaTeXTools 'texlib' builder; the native runner in texlib.py drives it).
#
# Host-agnostic build brain. Ported from the LaTeXTools 'texlib' builder by
# dropping the PdfBuilder base; the native runner in texlib.py constructs a
# TexlibBuild and drives commands(). See PLUGIN-DESIGN.md.
#
# What it adds over the stock `basic` builder:
#
#   * Engine selection -- honors the %!TeX program magic comment (LaTeXTools
#     resolves that into self.engine for us), and additionally falls back to
#     lualatex automatically for \documentclass{autoexam|quiz|schedule}, which
#     require it. A plain pdflatex document still builds with pdflatex.
#
#   * Build modes -- Default / Answer Key / Solutions / Student / Rubric /
#     Draft / Quick. Selected via the TeXLib.sublime-build *variants* (Ctrl+Shift+B,
#     or the "TeXLib: Build ..." entries in the command palette). Each variant
#     passes  --texlib-mode=<mode>  through LaTeXTools' documented `options`
#     channel; this builder pops that token out of self.options and injects the
#     matching TeXLib flag (\def\ShowKey{}, \def\StudentMode{}, ...). You never
#     edit the .tex to switch modes.
#
#   * autoexam versions -- a normal build of a \versions{A,B,C} (or
#     \examversions{...}) document compiles every version (and, under
#     \solutions dual/only mode, every solutions copy) into ONE combined
#     PDF, then slices <base>_A.pdf, <base>_B.pdf, <base>_A_solutions.pdf,
#     ... out of it afterward -- see _slice_versions_from_vmap, keyed off
#     the <base>.vmap sidecar autoexam.cls writes per copy. No extra clicks
#     or separate recompiles needed.
#
#   * Rerun convergence -- after every pass the cross-pass state files in the
#     aux dir (.aux/.toc/.out/.bbl/...) are fingerprinted and compared with the
#     state that pass started from; the engine re-runs (up to MAX_RERUNS) while
#     that state keeps changing, or while the log asks. The fingerprint beats
#     the log in both directions: it sees reruns the log never mentions (a
#     shifted "page X of Y" footer under autoexam, which defines \@testdef away)
#     and it vetoes a log-requested pass once the state is byte-stable, which is
#     provably a fixed point. See _needs_another_run.
#
#   * biber change-detection -- biber (and its forced re-pass) only runs when
#     the .bcf changed since the .bbl was last built. Editing prose in a
#     biblatex document no longer pays for a biber run plus an extra pass.
#     The "Quick" mode goes further: a single pass, no biber, no reruns.
#
#   * PDF splitting -- if the engine drops a <base>.spl signal file containing
#     "split_page=N", the resulting <base>.pdf is split into <base>_Exam.pdf
#     and <base>_Solutions.pdf (the autoexam key-build workflow). Likewise a
#     multi-copy exam's <base>.vmap is sliced into a PDF per version/solutions
#     copy. Both need pypdf; Sublime's embedded Python has none, so the work is
#     delegated to texlib_pdfpost.py, run under an external Python that does
#     (see _run_pdfpost / _external_python). Every sliced copy also gets its own
#     <name>.synctex, cut from the parent's by page span, so inverse search works
#     inside it and not only in the combined PDF (_slice_synctex_for_copies).
#
#   * Which PDF the host opens -- a multi-copy build produces the combined
#     <base>.pdf AND one file per copy, and preferred_pdf_path resolves the
#     host's setting ("solutions" / "student" / a literal suffix) against what
#     THIS build produced, falling back to <base>.pdf. Nothing about what gets
#     built changes; this only names the copy to put in front of the user.
#
#   * aux_directory routing -- honors LaTeXTools' aux_directory setting
#     (typically "<<temp>>"). On TeX Live there is no separate -aux-directory
#     flag, so the builder routes EVERYTHING via -output-directory and then,
#     in _postprocess, copies the PDF / .synctex.gz / .spl back next to the
#     source so PDF viewing and SyncTeX keep working. Aux files (.aux/.log/
#     .out/.toc/.bcf/.bbl/.fls/.fdb_latexmk) stay in the aux dir, keeping
#     the source dir clean and reducing OneDrive sync churn. biber runs are
#     redirected to the aux dir via --input-directory / --output-directory
#     so biblatex cross-references resolve correctly. _set_aux_target also
#     exports the resolved dir as TEXLIB_AUX_DIR so problem_engine.lua's own
#     build-time scratch (per-version body files, .sco, .srcmap, per-problem
#     SyncTeX-fallback files -- all written via raw Lua io.open, which
#     -output-directory does not touch) follows the same routing instead of
#     landing next to the source.
#
#   * Tidy -- on Windows, hides the <base>.synctex.gz build artifact.
#
# No LaTeXTools/PdfBuilder dependency: the native runner (texlib.py) supplies
# the host contract (display / out / tex_root / engine / options) and drives
# commands().
# ============================================================================

import csv
import glob
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from xml.etree import ElementTree as ET

# Windows: keep short-lived subprocesses (our own pypdf/probe/powershell calls,
# and the native runner's own engine spawns)
# from flashing a console window. 0 elsewhere (creationflags=0 is valid on every
# platform).
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW

# (host-agnostic: no PdfBuilder base class -- see the header note above)


# The console-flash suppression that LaTeXTools lacked is done by the native
# runner, which owns its own Popen and passes CREATE_NO_WINDOW directly.


# --- Configuration ----------------------------------------------------------

# LUALATEX_CLASSES, ACCESSIBLE_DOCMETA and ACCESSIBLE_MACRO are declared ONCE in
# texlib_buildspec.py and imported here and by smoke_test.py. They were literals
# in both, and had already drifted (bingo was in the harness copy and not this
# one). Same in-package import shape texlib.py uses for texlib_build itself.
try:
    from TeXLib import texlib_buildspec as _spec
except ImportError:  # plain import outside the Sublime package (tests, CLI)
    import texlib_buildspec as _spec

LUALATEX_CLASSES = _spec.LUALATEX_CLASSES

# Document classes whose gradebook.xlsx is auto-converted to a report-view CSV
# before the build (see _convert_gradebooks). The report-view tab name tried in
# order; falls back to the first sheet.
GRADEBOOK_CLASSES = {"report-card"}
GRADEBOOK_SHEETS = ("Report View", "Report Cards")

# --- Variants ----------------------------------------------------------------
# A VARIANT is one rendering of the document: the same source, a different
# audience. Each is its own compile -- the flags change what is typeset
# globally, so they cannot share a run -- and each lands as
# <base>_<variant>.pdf beside the source.
#
# The names are the audience, not the mechanism, which is the whole point of
# the 0.8.0 rename: `solutions' is the copy a STUDENT gets after the fact
# (answers, no grading apparatus) and `instructor' is the copy that carries the
# rubric and the common-error notes. The underlying TeX flags are unchanged --
# \ifkey, \ifsolutions, \ifrubric still mean exactly what they meant, so no
# course document and no class file had to move -- only these mode tokens did.
#
# \InstructorMode rides along on `instructor' so \ifinstructor finally means
# something: it is how a class tells an instructor copy from a student key when
# both reveal the same answers (the badge wording), which is the only
# difference for the classes that have no rubric machinery at all.
VARIANT_MACROS = {
    "student":    r"\def\StudentMode{}",
    "solutions":  r"\def\ShowKey{}",
    "instructor": r"\def\ShowSolutions{}\def\ShowRubric{}\def\InstructorMode{}",
    # Same answers as `solutions', drawn INTO the student's reserved answer
    # space instead of replacing it, so the page geometry matches the student
    # copy. Only meaningful for problems authored with {partsolution}; the
    # planner offers it only when the sidecar reports one.
    "solutions-inline": r"\def\ShowKeyInline{}",
}

# Variants the planner will consider, in emission order. `solutions-inline' is
# deliberately absent: it is a layout preference, not an audience, so it is
# opt-in per document rather than something a default build fans out into.
PLANNED_VARIANTS = ("student", "solutions", "instructor")

# Modes that fan out into a whole variant set rather than building once.
# `default' prunes against what the document actually contains; `full' does not
# -- that is the entire difference between them, and it is what makes `full'
# the "I don't trust the detection" escape hatch.
MULTI_VARIANT_MODES = ("default", "full")

# Aux subdirectory holding one output directory per variant. Variants cannot
# share an output directory (same \jobname -- see _build_accessible on why the
# jobname must not change), so each gets its own.
VARIANT_SUBDIR = "variants"

# builder_settings knob: pin the variant set for every build, bypassing the
# planner. A list of variant names, or ["base"] for the old single-PDF
# behaviour.
VARIANT_SETTING = "default_variants"
VARIANT_ENV = "TEXLIB_VARIANTS"

# Build mode  ->  the compile-time macro the TeXLib classes respond to.
# texlib-build.sty turns these \def's into the \ifsolutions / \ifkey / ...
# conditionals that every TeXLib class branches on.
MODE_MACROS = {
    # Both fan out; see MULTI_VARIANT_MODES. The empty macro is the BASE
    # compile they each start from -- the plain build, which is also what
    # writes the .buildmeta the planner then reads.
    "default":   "",
    "full":      "",
    # The plain build ALONE: one compile, no fan-out, but the full biber +
    # cross-reference settling loop. This is what `default' meant before the
    # variant fan-out, and it is the mode to want when you need one correct
    # PDF now -- `quick' is faster but leaves references unsettled, which is a
    # different trade.
    "base":      "",
    # Single-variant modes: build exactly this one rendering and stop. These are
    # what the Ctrl+Shift+B picker offers for when you want one file, now.
    "student":    VARIANT_MACROS["student"],
    "solutions":  VARIANT_MACROS["solutions"],
    "instructor": VARIANT_MACROS["instructor"],
    "solutions-inline": VARIANT_MACROS["solutions-inline"],
    # No "rubric" mode. A rubric annotates a worked solution, so rubric-without-
    # solutions is of no use to anyone; \ShowRubric implies \ifsolutions
    # (texlib-build.sty) and "instructor" above is how you ask for both.
    "draft":     r"\def\ShowDraft{}",
    "accessible": None,  # special-cased: see ACCESSIBLE_* and _build_accessible.
}

# Retired mode tokens -> their replacement. Kept so a stale keybinding, a
# scripted --texlib-mode=, or muscle memory reports the rename instead of
# silently falling back to `default' and quietly building the wrong thing --
# which is exactly what `solutions' would have done, since the token survived
# the rename with a DIFFERENT meaning.
RENAMED_MODES = {
    "key": "solutions",
    "key-inline": "solutions-inline",
}

# --- Accessible (tagged PDF/UA) mode ----------------------------------------
# A PAIRED build: the document is typeset twice and both PDFs are kept, as
# <base>.pdf (normal) and <base>_accessible.pdf (tagged). Pairing rather than
# replacing is deliberate -- tagging=on costs real visual fidelity (tcolorbox
# wraps are dropped because their inner list breaks under tagging; see
# texlib-thmenv.sty), so the normal PDF stays the pretty one for print and
# lecture while the tagged twin is the one a screen reader can navigate.
#
# The two halves use DIFFERENT engines on purpose. The normal half keeps the
# class's natural engine (pdflatex for syllabus/notes/pset), so the primary PDF
# is byte-for-byte what a plain Ctrl+B produces; the tagged half forces lualatex
# because MathML math tagging is a Unicode-engine feature. Overriding the engine
# for both would silently change the normal PDF's rendering in accessible mode.
#
# Tagging can only be switched on by \DocumentMetadata issued BEFORE
# \documentclass, so the builder injects it on the command line ahead of
# \input{<doc>} (the same prefix trick used for \def\ShowKey{}).
# \TeXLibAccessibleMode lets the TeXLib classes/packages adapt
# (texlib-build.sty -> \ifTeXLibAccessible).
ACCESSIBLE_MODE   = "accessible"
ACCESSIBLE_SUFFIX = "_accessible"
ACCESSIBLE_ENGINE = "lualatex"
# math/setup carries BOTH MathML methods because PDF readers split on which one
# they understand, and the split falls across how a student actually opens the
# file. AF (associated files) is what Firefox's viewer and Foxit read -- i.e.
# the in-browser path from an LMS link -- while SE (structure elements) is what
# Adobe Acrobat reads. Emitting only one silently drops the math to "x 2 plus y
# 2" on the other half of the readers. a-4f's "f" (files) is the conformance
# level that permits the AF attachments, and was already being paid for.
#
# NOT set, deliberately: \tagpdfsetup{math/alt/use}. It raises the score an
# Ally/UDOIT-style checker reports, but it does so by replacing the MathML with
# flat alt text that hides the real markup from screen readers -- a better
# number for worse accessibility. See CHANGELOG 0.6.0.
ACCESSIBLE_DOCMETA = _spec.ACCESSIBLE_DOCMETA

# --- Sliced copies ----------------------------------------------------------
# How the version slicer names an instructor copy (texlib_pdfpost.slice_from_vmap
# appends it, and the .spl split's <base>_Solutions.pdf matches case-insensitively).
# preferred_pdf_path tells the two kinds of copy apart by this and nothing else.
SOLUTION_COPY_SUFFIX = "_solutions.pdf"
ACCESSIBLE_MACRO = _spec.ACCESSIBLE_MACRO
ACCESSIBLE_MACRO_AF_ONLY = _spec.ACCESSIBLE_MACRO_AF_ONLY
accessible_macro_for = _spec.accessible_macro_for
luamml_se_aborted = _spec.luamml_se_aborted

# The luamml sidecars a crashed tagged run can leave truncated; removed before
# the AF-only retry so it does not read back a half-written file.
LUAMML_SIDECARS = ("-luamml-mathml.html", "-mathml.html")

# veraPDF conformance reporting for the accessible build. Located via the shared
# finder rather than shutil.which: the installer does not put veraPDF on PATH.
ACCESSIBLE_REPORT_SUFFIX = _spec.VERAPDF_REPORT_SUFFIX
find_verapdf = _spec.find_verapdf
verapdf_report_cmd = _spec.verapdf_report_cmd

# A pseudo-mode: a single engine pass with no biber and no rerun loop, for fast
# preview while writing. Cross-references / citations may be stale; a normal
# build settles them.
MODE_QUICK = "quick"

# Ceiling on engine passes per build. The state fingerprint ends the loop the
# moment the aux state settles, so this is only a backstop for a document that
# genuinely refuses to converge -- which is why it can afford headroom (a
# three-deep toc/pageref chain settles on pass 4) where the old log-only loop
# had to stay tight at 3 to bound the "Label(s) may have changed" oscillation.
MAX_RERUNS = 5

# How many passes may be justified by a state change ALONE (no rerun request in
# the log). Bounds a document that cannot converge: problem_engine.lua seeds the
# unversioned case from os.time(), so a bank-driven quiz draws fresh values on
# every pass -- invisible here while the draw moves no page break, but once one
# moves, the .aux never repeats. Two keeps the classic label -> page -> label
# chain reachable without letting such a document run to MAX_RERUNS every build.
STATE_ONLY_RERUNS = 2

# Files one pass writes and the next pass reads back -- the state whose
# stability decides whether another pass is needed. Deliberately just the
# genuine cross-pass state: the Lua engine's per-pass scratch (.sco, .srcmap,
# *_autoexam_body_*.tex) is regenerated wholesale every pass and is not what a
# rerun resolves, and whatever it derives from page numbers reaches us through
# the .aux anyway.
STATE_EXTS = frozenset({
    ".aux",                          # labels, refs, counters, exam point totals
    ".toc", ".lof", ".lot", ".lol",  # contents lists
    ".out",                          # hyperref bookmarks
    ".bbl",                          # biber output
    ".idx", ".ind", ".glo", ".gls",  # index / glossary
    ".nav", ".snm", ".vrb", ".brf",  # beamer / backref
})

# .aux lines that are biblatex asking ITSELF for a rerun -- \abx@aux@read@bblrerun
# and the .bbl checksum beside it. They are not document state: they flip on the
# pass after biblatex settles even in a document with no bibliography, which
# would buy a pointless third pass on every cold build of a class that merely
# loads biblatex (didactic does). Nothing is lost by ignoring them -- that
# request reaches us through the log (BIBER_RERUN_RE) and the .bcf/.bbl hash
# cache, and a real .bbl change still shows up because .bbl is itself state.
STATE_NOISE_RE = re.compile(r"^\\abx@aux@read@bbl")

# --- Publish step -----------------------------------------------------------
# A class that calls \TeXLibDeclarePublishable (syllabus, schedule) drops a
# <base>.pubmeta sidecar; _postprocess then clones the built PDF to shareable
# names (the department's <SUBJECT> <number>.<section>_<term>_<LastName>.pdf +
# a generic <kind>.pdf) and, on Windows,
# a desktop shortcut. Enabled by default; toggle via builder_settings in
# LaTeXTools.sublime-settings or the env override (0/false/no/off = disabled).
PUBLISH_SETTING      = "publish_shareable_copies"
PUBLISH_ENV          = "TEXLIB_PUBLISH"
PUBLISH_CLIP_SETTING = "copy_published_path_to_clipboard"
PUBLISH_CLIP_ENV     = "TEXLIB_PUBLISH_CLIPBOARD"
# Desktop subfolder the shortcuts land in, so they don't pile up loose on the
# desktop as terms accumulate.
PUBLISH_SHORTCUT_DIR = "Course Materials"

# Name suffixes that must not be mistaken for a surname when the coded basename
# takes the last token of `instructor` (see _surname).
NAME_SUFFIXES = frozenset(
    ("jr", "sr", "ii", "iii", "iv", "v", "phd", "ph.d", "md", "m.d", "edd", "ed.d")
)


def _collapse_ws(text):
    """Squeeze internal whitespace runs to one space and trim the ends. Unlike
    the old strip-every-space rule this KEEPS the single spaces the department's
    filename convention is written with ("MATH 181", "Fall 2026")."""
    return re.sub(r"\s+", " ", text).strip()


def _surname(instructor):
    """Best-effort surname from a free-text `instructor` field, for the trailing
    "_InstructorLastName" segment of the coded name.

      "Landon Fox"        -> "Fox"     "Dr. Landon Fox"     -> "Fox"
      "Fox, Landon"       -> "Fox"     "Landon Fox, Ph.D."  -> "Fox"

    Everything from the first comma on is dropped (that comma is either the
    "Last, First" separator -- in which case the surname is already all that is
    left -- or a degree/suffix tail), then trailing generational and degree
    tokens go, then the last remaining token wins. A multi-token surname
    ("van der Meer") is beyond this and needs the `publish-name` override; the
    field is free text with no structure to lean on, and guessing at particles
    would silently mangle names it guessed wrong about. Empty in, empty out."""
    head = _collapse_ws(instructor.split(",", 1)[0])
    tokens = head.split()
    while tokens and tokens[-1].rstrip(".").lower() in NAME_SUFFIXES:
        tokens.pop()
    return tokens[-1] if tokens else ""

# Regexes over the root document / engine output.
DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{(\w[\w-]*)\}")
# A problem-bank fragment (bank.tex, chN.tex, ...): no \documentclass of its
# own -- normally only ever \loadbank'd/\input from a real quiz/exam/didactic
# root -- but it does define \begin{problem} blocks. See _build_bank_catalog.
BANK_FRAGMENT_RE = re.compile(r"\\begin\{problem\}")
# Engine/package signals that another LaTeX pass will resolve something:
#   * "...Rerun to get cross-references right." / "Rerun to get outlines right."
#   * "Label(s) may have changed. Rerun..."   (cross-references / toc)
#   * biblatex's "Please rerun LaTeX."        (emitted after biber writes .bbl;
#     without this the post-biber pass leaves undefined references behind)
RERUN_RE = re.compile(
    r"Rerun to get .* right\.|Label\(s\) may have changed|Please re-?run LaTeX",
    re.IGNORECASE,
)
# biblatex's "please run biber" message (varies slightly across versions).
BIBER_RERUN_RE = re.compile(r"Please \(?re\)?(?:run|rerun) Biber", re.IGNORECASE)
MODE_OPT_RE = re.compile(r"^--texlib-mode=(.+)$")


class TexlibBuildCore:
    """The single source of TeXLib build LOGIC -- host-agnostic.

    Reads a small host contract -- self.display, self.tex_root, self.tex_name,
    self.base_name, self.engine, self.options, self.out, self.aux_directory --
    and drives commands(), a coroutine yielding (argv, message) pairs; after
    running each argv the host feeds the command's output back via self.out
    before resuming (rerun/biber checks read it). Two hosts supply that
    contract: the native TexlibBuild (below, via __init__) and the LaTeXTools
    TexlibBuilder (texlib_builder.py, via PdfBuilder). One core -> no drift.

    One signal travels the other way. When the core sets self._forget_last_pass
    on resuming, the pass just run was a probe whose failure the core has
    already handled, and the host must roll its error state back to what it was
    before that pass -- otherwise a deliberate, recovered-from abort (the
    mathml-SE retry in _build_accessible) leaves the whole build reported as
    failed. A host that ignores the flag still builds correctly; it just
    misreports that one case, so the flag is read with getattr.
    """

    # Set by the core, cleared by the host. See the class docstring.
    _forget_last_pass = False

    # ------------------------------------------------------------------ #
    # Entry point: a coroutine that yields (command, message) pairs and
    # receives each command's exit status back from the build back-end.
    # ------------------------------------------------------------------ #
    def commands(self):
        root = getattr(self, "tex_root", None) or getattr(self, "tex_name", "")
        try:
            with open(root, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError as exc:
            self.display(f"TeXLib: cannot read root document {root!r}: {exc}\n")
            return

        # Build-summary state (elapsed time + pass/biber tally). _count_passes
        # increments the tallies as commands stream past it; _display_build_summary
        # reports them at the end of _postprocess.
        self._build_start = time.monotonic()
        self._pass_count = 0
        self._biber_count = 0

        # Variant fan-out state, reset per build so a single-variant build
        # after a Ctrl+B cannot inherit the previous plan and sweep away PDFs
        # it knows nothing about.
        self._variant_build = False
        self._variant_pdfs = []
        self._variants_built = None
        self._variants_skipped = []

        # Convergence state (see _record_state_baseline / _needs_another_run):
        # the aux fingerprint the current pass started from, and every
        # fingerprint seen this build, for cycle detection.
        self._state_digest = None
        self._state_history = set()
        self._state_warned = False

        mode, engine_options = self._extract_mode(self.options or [])

        # Problem-bank fragments (bank.tex, chN.tex, ...) have no root document
        # of their own -- \documentclass never matches, but \begin{problem}
        # blocks do. Building one directly synthesizes a throwaway quiz.cls
        # harness instead of running the normal mode/version dispatch below.
        if not DOCCLASS_RE.search(src) and BANK_FRAGMENT_RE.search(src):
            self.display(
                "TeXLib: no \\documentclass here, but \\begin{problem} blocks "
                "are -- building a \\printbankcatalog listing of this bank.\n"
            )
            tex_dir = self._tex_dir()
            self._set_aux_target(tex_dir)
            self._biber_ran = []
            base = self._base_engine_cmd(
                "lualatex", self._aux_target, tex_dir, engine_options
            )
            yield from self._count_passes(
                self._build_bank_catalog(base, "lualatex")
            )
            self._postprocess()
            return

        engine = self._select_engine(src)

        # Accessible mode deliberately does NOT override `engine` here. Its
        # normal half must keep the class's natural engine so the primary PDF is
        # what a plain build would have produced; only the tagged half is forced
        # to lualatex, inside _build_accessible.

        # Report cards: turn the one gradebook.xlsx (source of truth) into the
        # report-view CSV the class reads. Done in-process before the engine
        # runs so the build always sees fresh grades.
        self._convert_gradebooks(src)

        # Resolve LaTeXTools' aux_directory setting (typically <<temp>>) and
        # add -output-directory if needed. On TeX Live there's no separate
        # -aux-directory flag, so aux + PDF both land in this dir; _postprocess
        # then copies the PDF / .synctex.gz / .spl back next to the source so
        # the PDF viewer and SyncTeX both keep working.
        tex_dir = self._tex_dir()
        self._set_aux_target(tex_dir)
        # Jobnames whose biber ran this build; their input fingerprint is
        # recorded in _postprocess, AFTER the final engine pass settles the
        # .bcf (recording mid-build would capture a .bcf the post-biber pass
        # then rewrites -> a spurious biber re-run on the next build).
        self._biber_ran = []
        base = self._base_engine_cmd(
            engine, self._aux_target, tex_dir, engine_options
        )

        self._accessible_build = (mode == ACCESSIBLE_MODE)
        if mode == MODE_QUICK:
            yield from self._count_passes(self._build_quick(base, engine))
        elif mode == ACCESSIBLE_MODE:
            yield from self._count_passes(
                self._build_accessible(base, engine, tex_dir, engine_options)
            )
        elif mode in MULTI_VARIANT_MODES:
            # The fan-out also produces tagged twins, so the publish step must
            # treat this like an accessible build and clone from the tagged
            # half (an untagged PDF on WebCampus is exactly what UDOIT flags).
            self._accessible_build = True
            yield from self._count_passes(
                self._build_variants(base, engine, tex_dir, engine_options,
                                     prune=(mode != "full"))
            )
        else:
            yield from self._count_passes(self._build_once(base, engine, mode))

        self._postprocess()

    def _count_passes(self, inner):
        """Pass-through generator that tallies engine passes and biber runs for
        the build summary, and snapshots the aux state each pass is about to
        consume -- without altering the (command, message) stream it forwards.
        Wrapping every build sub-coroutine here keeps both the tally and the
        convergence baseline in one place instead of threading them through
        each of them.

        The snapshot lands on the engine branch only. Taking it before a biber
        run too would make the baseline for the forced post-biber pass predate
        the .bbl biber just wrote, so that pass would always look like it
        changed something and win a free rerun.
        """
        try:
            item = next(inner)
            while True:
                head = item[0][0] if item and item[0] else ""
                if head == "biber":
                    self._biber_count += 1
                elif head:
                    self._pass_count += 1
                    self._record_state_baseline()
                item = inner.send((yield item))
        except StopIteration:
            return

    # ------------------------------------------------------------------ #
    # Mode + engine resolution
    # ------------------------------------------------------------------ #
    def _extract_mode(self, options):
        """Split self.options into (mode, real-engine-options).

        The TeXLib.sublime-build variants pass --texlib-mode=<mode> through the
        `options` channel; every other entry is a genuine engine flag.
        """
        mode = "default"
        passthrough = []
        for opt in options:
            match = MODE_OPT_RE.match(str(opt).strip())
            if match:
                mode = match.group(1).strip().lower()
            else:
                passthrough.append(opt)
        # A retired token is remapped LOUDLY, never silently dropped to default:
        # `key' became `solutions', and `solutions' still exists meaning
        # something else, so a silent fallback here would build an instructor
        # copy for someone who asked for a student key.
        if mode in RENAMED_MODES:
            new = RENAMED_MODES[mode]
            self.display(
                f"TeXLib: build mode {mode!r} was renamed to {new!r} in 0.8.0 "
                f"(the names are the audience now); building {new!r}.\n"
            )
            mode = new
        if mode not in MODE_MACROS and mode != MODE_QUICK:
            self.display(
                f"TeXLib: unknown build mode {mode!r}; falling back to default.\n"
            )
            mode = "default"
        return mode, passthrough

    def _select_engine(self, src):
        """Pick the compile engine.

        self.engine already reflects the %!TeX program directive and the
        LaTeXTools build configuration. On top of that, force lualatex for the
        document classes that require it, unless the user explicitly asked for
        something other than pdflatex.
        """
        engine = (getattr(self, "engine", None) or "pdflatex").strip()
        match = DOCCLASS_RE.search(src)
        docclass = match.group(1) if match else ""
        if docclass in LUALATEX_CLASSES and engine == "pdflatex":
            self.display(
                f"TeXLib: \\documentclass{{{docclass}}} requires lualatex "
                "-- overriding pdflatex.\n"
            )
            return "lualatex"
        return engine

    # ------------------------------------------------------------------ #
    # Gradebook xlsx -> report-view CSV  (report-card class)
    # ------------------------------------------------------------------ #
    def _convert_gradebooks(self, src):
        """For report-card documents, convert each *.xlsx in the source dir to a
        sibling .csv (its report-view tab) before the engine runs.

        Best-effort: a malformed/locked workbook logs a warning and is skipped
        rather than failing the build. Mirrors the standalone
        Report Cards/gradebook_to_csv.py — kept inline because the deployed
        builder lives in Sublime's Packages/User, detached from the TeXLib tree,
        so it can't import that module at runtime.
        """
        match = DOCCLASS_RE.search(src)
        docclass = match.group(1) if match else ""
        if docclass not in GRADEBOOK_CLASSES:
            return
        tex_dir = self._tex_dir()
        for xlsx in sorted(glob.glob(os.path.join(tex_dir, "*.xlsx"))):
            csv_path = xlsx[:-5] + ".csv"
            try:
                rows = self._xlsx_rows(xlsx, GRADEBOOK_SHEETS)
                self._write_csv(csv_path, rows)
                self.display(
                    "TeXLib: gradebook %s -> %s (%d student row(s)).\n"
                    % (os.path.basename(xlsx), os.path.basename(csv_path),
                       max(len(rows) - 1, 0))
                )
            except Exception as exc:  # noqa: BLE001 - never fail a build on this
                self.display(
                    "TeXLib: could not convert gradebook %s: %s\n"
                    % (os.path.basename(xlsx), exc)
                )

    @staticmethod
    def _xlsx_local(tag):
        """Strip the XML namespace from an ElementTree tag."""
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _xlsx_col_index(ref):
        """'B7' -> 2 (1-based column index)."""
        m = re.match(r"[A-Za-z]+", ref or "")
        if not m:
            return None
        n = 0
        for ch in m.group(0).upper():
            n = n * 26 + (ord(ch) - 64)
        return n

    @classmethod
    def _xlsx_rows(cls, xlsx_path, preferred_sheets=()):
        """Read a worksheet to a list of row lists, preferring the named sheets.

        Reads each cell's cached value (the <v> element next to any formula),
        so a report-view tab built from formulas converts correctly.
        """
        loc = cls._xlsx_local
        with zipfile.ZipFile(xlsx_path) as zf:
            shared = []
            try:
                sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in sroot:
                    shared.append("".join(
                        t.text or "" for t in si.iter() if loc(t.tag) == "t"))
            except KeyError:
                pass
            wb = ET.fromstring(zf.read("xl/workbook.xml"))
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rid_to_target = {}
            for rel in rels:
                tgt = rel.attrib.get("Target", "")
                tgt = (tgt.lstrip("/") if tgt.startswith("/")
                       else "xl/" + tgt.lstrip("/"))
                rid_to_target[rel.attrib.get("Id")] = tgt
            sheets = []
            for el in wb.iter():
                if loc(el.tag) != "sheet":
                    continue
                rid = next((v for k, v in el.attrib.items()
                            if loc(k) == "id"), None)
                sheets.append((el.attrib.get("name", ""), rid_to_target.get(rid)))
            target = None
            for pref in preferred_sheets:
                for name, tgt in sheets:
                    if name.strip().lower() == pref.lower():
                        target = tgt
                        break
                if target:
                    break
            if target is None and sheets:
                target = sheets[0][1]
            if target is None:
                return []
            root = ET.fromstring(zf.read(target))
            rows = []
            for row in root.iter():
                if loc(row.tag) != "row":
                    continue
                cells, maxc = {}, 0
                for c in row:
                    if loc(c.tag) != "c":
                        continue
                    ci = cls._xlsx_col_index(c.attrib.get("r", "")) or (maxc + 1)
                    t = c.attrib.get("t")
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter()
                                      if loc(x.tag) == "t")
                    else:
                        v = next((ch.text for ch in c
                                  if loc(ch.tag) == "v"), None)
                        if v is None:
                            val = ""
                        elif t == "s":
                            try:
                                val = shared[int(v)]
                            except (ValueError, IndexError):
                                val = ""
                        else:
                            val = v
                    cells[ci] = val
                    maxc = max(maxc, ci)
                rows.append([cells.get(i, "") for i in range(1, maxc + 1)])
        while rows and not any(s.strip() for s in rows[-1]):
            rows.pop()
        return rows

    @staticmethod
    def _write_csv(path, rows):
        width = max((len(r) for r in rows), default=0)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for r in rows:
                w.writerow(list(r) + [""] * (width - len(r)))

    @staticmethod
    def _base_engine_cmd(engine, aux_target=None, tex_dir=None, options=()):
        """Assemble the shared engine command prefix.

        Single source of truth for the base flags every build step (_build_once,
        _build_quick) starts from. Adds -output-directory only when routing to a
        distinct aux dir; appends any genuine engine options last.
        """
        cmd = [engine, "-interaction=nonstopmode", "-synctex=1", "-file-line-error"]
        if engine in ("lualatex", "xelatex"):
            cmd.append("-shell-escape")
        if aux_target and aux_target != tex_dir:
            cmd.append(f"-output-directory={aux_target}")
        cmd += list(options)
        return cmd

    # ------------------------------------------------------------------ #
    # Build steps (each is a sub-coroutine delegated to via `yield from`)
    # ------------------------------------------------------------------ #
    def _build_once(self, base, engine, mode):
        """One document, one mode, with biblatex+cross-reference rerun loop."""
        macro = MODE_MACROS.get(mode, "")
        if macro:
            arg = f"{macro}\\input{{{self.tex_name}}}"
            label = f"{engine} [{mode}]"
        else:
            arg = self.tex_name
            label = engine
        cmd = base + [arg]

        run = 1
        yield (cmd, f"{label} run {run}...")

        # biblatex: run biber only when the bibliography actually changed since
        # the .bbl was last built. The .bbl persists in the aux dir, so an edit
        # that doesn't touch citations skips both biber and its forced re-pass.
        if self._biber_needed(self.base_name) and not self._biber_is_current(
            self.base_name
        ):
            yield (self._biber_command(self.base_name), "biber...")
            self._biber_ran.append(self.base_name)
            run += 1
            yield (cmd, f"{label} rerun {run} (post-biber)...")

        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"{label} rerun {run}...")
        self._warn_if_unsettled(run)

    def _build_bank_catalog(self, base, engine):
        """Build a problem-bank fragment directly: synthesize a minimal
        \\documentclass{bank} harness on the command line (the same \\def...\\input
        trick _build_once uses for mode injection) that \\loadbank's this file and
        calls \\printbankcatalog, so a bank can be perused without hand-authoring a
        companion root document. bank.cls is the first-class catalog/preview class
        (it replaced the old synthesized-quiz harness). --jobname pins the output
        to <base>.pdf/.log/... like every other build, so _postprocess's copy-back
        (which globs by self.base_name) needs no changes.
        """
        arg = (
            r"\documentclass{bank}\begin{document}"
            f"\\loadbank{{{self.tex_name}}}"
            r"\printbankcatalog\end{document}"
        )
        cmd = base + [f"--jobname={self.base_name}", arg]

        run = 1
        yield (cmd, f"{engine} [bank catalog] run {run}...")
        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"{engine} [bank catalog] rerun {run}...")
        self._warn_if_unsettled(run)

    def _build_quick(self, base, engine):
        """One engine pass, no biber, no rerun loop -- fast preview while writing.

        Cross-references and the bibliography may be stale (a ?? or an
        unresolved citation can show up); run a normal build to settle them
        before sharing. Builds in the default visual mode (no \\Show... flag).
        """
        cmd = base + [self.tex_name]
        yield (cmd, f"{engine} [quick] single pass (refs may be stale)...")

    def _build_accessible(self, base, engine, tex_dir, engine_options):
        """Build the document twice -- normal, then tagged -- and keep both.

        The normal half runs first, through the ordinary _build_once path, so it
        gets the full biber + cross-reference settling loop and lands as
        <base>.pdf exactly as a plain build would: same engine, same flags, same
        output. The tagged half then re-typesets the same source under
        \\DocumentMetadata and is copied out as <base>_accessible.pdf.

        Order matters. _postprocess copies the primary PDF back from the aux dir
        and only afterwards reads the .pubmeta sidecar and publishes; running the
        tagged half first would leave the primary copy-back looking at whichever
        PDF happened to be newest, and the publish step guesses nothing.

        The jobname MUST stay the document's real base name. A suffixed jobname
        looked like the tidy way to avoid clobbering <base>.pdf, but several
        TeXLib engines key off \\jobname: autoexam reads the document body from
        <jobname>.tex and simply aborts ("AutoExam: Cannot read document body")
        when it does not exist, which silently truncated the tagged exam from 6
        pages to 2. So instead of renaming the job, the tagged half is redirected
        to an `a11y` subdirectory of the aux dir; _postprocess copies the result
        out as <base>_accessible.pdf. \\jobname is unchanged, every jobname-keyed
        engine behaves exactly as in a normal build, and the two halves never
        share an output directory, so neither can clobber the other.

        The DocumentMetadata prefix goes AHEAD of \\input{<doc>} so it precedes
        the document's \\documentclass, the only position from which tagging can
        be enabled -- and pinning --jobname also stops LuaTeX naming the output
        after the support file DocumentMetadata opens before the \\input.

        Two fixed passes settle cross-references and the "page X of Y" footer;
        no biber loop on the tagged half yet, so a bibliography-bearing class may
        need one when the rollout reaches it.

        Run 1 asks for both MathML methods. A document that trips the luamml
        mathml-SE bug (see ACCESSIBLE_DOCMETA) aborts there without a PDF, and
        run 1 is spent again on the AF-only prefix, which is unaffected. That
        costs one wasted pass on the few documents with two nth-roots in a
        formula, and gives every other document the Acrobat path.
        """
        yield from self._build_once(base, engine, None)

        # MathML math tagging is a Unicode-engine feature, so the tagged half is
        # always lualatex -- including for the pdflatex classes (syllabus, notes,
        # pset), whose normal half above ran under their own engine.
        if engine != ACCESSIBLE_ENGINE:
            self.display(
                f"TeXLib: normal PDF built with {engine}; tagged PDF needs "
                f"{ACCESSIBLE_ENGINE}.\n"
            )
        tagged_base = self._base_engine_cmd(
            ACCESSIBLE_ENGINE, self._aux_target, tex_dir, engine_options
        )
        out_dir = self._accessible_out_dir()
        head = [c for c in tagged_base
                if not str(c).startswith("-output-directory=")]
        head += [f"-output-directory={out_dir}", f"--jobname={self.base_name}"]
        doc = os.path.join(tex_dir, self.tex_name)

        def tagged_cmd(se):
            return head + [accessible_macro_for(doc, se=se)
                           + f"\\input{{{self.tex_name}}}"]

        cmd = tagged_cmd(True)
        yield (cmd, f"{ACCESSIBLE_ENGINE} [accessible] run 1...")
        if luamml_se_aborted(self.out):
            self.display(
                "TeXLib: this document trips the luamml mathml-SE bug (two "
                "nth-roots in one formula); retrying the tagged half with "
                "MathML associated files only. Screen readers that read AF "
                "(Firefox, Foxit) are unaffected; Acrobat falls back to the "
                "flattened text for this document.\n"
            )
            self._clear_luamml_sidecars(out_dir, tex_dir)
            self._forget_last_pass = True
            cmd = tagged_cmd(False)
            yield (cmd, f"{ACCESSIBLE_ENGINE} [accessible] run 1 (MathML-AF)...")
        yield (cmd, f"{ACCESSIBLE_ENGINE} [accessible] run 2 (settle)...")

    def _clear_luamml_sidecars(self, *dirs):
        """Remove the luamml MathML sidecars from each directory.

        luamml writes <jobname>-luamml-mathml.html as it typesets and reads the
        previous run's copy back at \\begin{document}. A run that died mid-write
        leaves it cut inside an element, and the next run fails at
        \\begin{document} on a runaway argument -- which would make the AF-only
        retry look like a second, unrelated failure.
        """
        for d in dirs:
            if not d:
                continue
            for suffix in LUAMML_SIDECARS:
                path = os.path.join(d, self.base_name + suffix)
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ------------------------------------------------------------------ #
    # Variant planning + fan-out
    # ------------------------------------------------------------------ #
    def _read_buildmeta(self, tex_dir):
        """Read the <base>.buildmeta sidecar texlib-build.sty writes at
        \\AtEndDocument; return its key=value map, or None when absent.

        Absent means one of: a class that does not load texlib-build (thesis),
        a build that died before \\end{document}, or a document predating the
        sidecar. All three mean "plan nothing extra", which is the safe answer.

        Unlike .pubmeta this is NOT deleted after reading -- a later
        single-variant build in the same aux dir can reuse it, and it is
        gitignored scratch either way.
        """
        path = self._find_in_dirs(
            self.base_name + ".buildmeta",
            [getattr(self, "_aux_target", None), tex_dir],
        )
        if not path:
            return None
        meta = {}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    meta[key.strip()] = val.strip()
        except OSError:
            return None
        return meta

    def _plan_variants(self, meta, prune):
        """Decide which variants this build should emit.

        Returns (variants, skipped) where `skipped` is a list of
        (variant, reason) so the summary can say what it did NOT build --
        silent pruning is the one way autodetection goes wrong, so every
        omission is reported.

        Two independent gates:
          * DECLARED. The class says which variants it distinguishes
            (\\TeXLibDeclareVariants). A class that declares nothing produces
            one PDF, which is right for syllabus/schedule/report-card -- none
            branches on a solution flag.
          * DETECTED. The document says what it actually contains. No
            {solution} anywhere means `solutions' and `instructor' would be
            byte-identical to the plain build; no \\rubric and no
            {commonerrors} means `instructor' differs from `solutions' by its
            badge alone -- still worth having (the badge is how you tell the
            copies apart in a stack) but worth SAYING, so it is reported.

        `prune=False' (the `full' mode) applies the declared gate only. There
        is no point offering a variant the class cannot render differently,
        but "I don't believe the content detection" is a real thing to want.
        """
        declared = [v.strip() for v in (meta or {}).get("variants", "").split(",")
                    if v.strip()]
        variants, skipped = [], []
        # An explicit \metasetup{build-variants = none} is a decision, not an
        # absence, and it has to read as one: a document that quietly produced a
        # single PDF would look identical to a planner that had failed.
        if [v.lower() for v in declared] == ["none"]:
            return [], [("all", "this document pins build-variants = none")]
        for name in PLANNED_VARIANTS:
            if name not in declared:
                continue
            if prune and name in ("solutions", "instructor") \
                    and (meta or {}).get("has-solutions") != "1":
                skipped.append((name, "no solution content in this document"))
                continue
            variants.append(name)
        # An inline key is only meaningful where {partsolution} is used, so it
        # is never planned into a default set -- but say so when the document
        # could have had it, or nobody will ever discover the mode exists.
        if (meta or {}).get("has-partsolution") == "1" \
                and "solutions-inline" in declared:
            skipped.append(("solutions-inline",
                            "layout preference; build it explicitly"))
        return variants, skipped

    def _configured_variants(self):
        """The `default_variants' override, or None to let the planner decide.
        ["base"] (or an empty list) pins the old single-PDF behaviour."""
        raw = os.environ.get(VARIANT_ENV)
        if raw is None:
            getter = getattr(self, "builder_settings", None) or {}
            try:
                raw = getter.get(VARIANT_SETTING)
            except AttributeError:
                raw = None
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = [v for v in re.split(r"[,\s]+", raw) if v]
        names = [str(v).strip().lower() for v in raw if str(v).strip()]
        if names in ([], ["base"], ["none"]):
            return []
        unknown = [n for n in names if n not in VARIANT_MACROS]
        if unknown:
            self.display(
                f"TeXLib: ignoring unknown {VARIANT_SETTING} entries "
                f"{unknown!r}; known variants are "
                f"{sorted(VARIANT_MACROS)}.\n"
            )
        return [n for n in names if n in VARIANT_MACROS]

    def _variant_out_dir(self, tag):
        """Aux output directory for one variant compile (created on demand).

        Each variant needs its OWN directory because \\jobname must stay the
        document's real base name -- autoexam reads its body from
        <jobname>.tex and truncates silently otherwise (see
        _build_accessible). Same reason the accessible half gets a11y/.
        """
        parent = getattr(self, "_aux_target", None) or self._tex_dir()
        out_dir = os.path.join(parent, VARIANT_SUBDIR, tag)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            return parent
        return out_dir

    @staticmethod
    def _variant_pdf_name(base_name, variant, tagged):
        """<base>_<variant>[_accessible].pdf, with the BASE variant keeping the
        plain names <base>.pdf / <base>_accessible.pdf so every existing
        consumer -- the viewer, forward sync, preferred_pdf, the publish step,
        package_for_lms -- keeps working untouched."""
        stem = base_name if variant == "base" else f"{base_name}_{variant}"
        return stem + (ACCESSIBLE_SUFFIX if tagged else "") + ".pdf"

    def _build_variants(self, base, engine, tex_dir, engine_options, prune):
        """Base compile, then one compile per planned variant, then the tagged
        twins -- the fan-out behind Ctrl+B.

        The base compile runs FIRST and unflagged for three reasons: it is the
        artifact <base>.pdf has always meant, it is what the publish step and
        forward sync read, and it is what writes the .buildmeta the plan is
        computed from. That last point is what makes the detection exact from
        the very first build rather than one build late: solution bodies are
        typeset into a discarded \\vbox even when hidden, so the plain compile
        already knows everything the planner needs.
        """
        self._variant_build = True
        self._variant_pdfs = []
        yield from self._build_once(base, engine, None)

        meta = self._read_buildmeta(tex_dir)
        override = self._configured_variants()
        if override is not None:
            variants, skipped = override, []
            if variants:
                self.display(
                    f"TeXLib: {VARIANT_SETTING} pins the variant set to "
                    f"{', '.join(variants)}.\n")
        else:
            variants, skipped = self._plan_variants(meta, prune)
            if meta is None:
                self.display(
                    "TeXLib: no .buildmeta sidecar -- building the base PDF "
                    "only. (Expected for thesis, which loads no TeXLib build "
                    "package; otherwise the build may have stopped before "
                    "\\end{document}.)\n")

        # Tracked as (variant, tagged) pairs actually PRODUCED, not as variant
        # names: the summary and the stale sweep both need to know exactly
        # which artifacts this build stands behind, and those two axes do not
        # always both apply (a pinned base-only build emits no tagged twin).
        self._variants_built = [("base", False)]
        self._variants_skipped = list(skipped)

        # An explicit base-only pin means the pre-0.8.0 single PDF: no
        # variants, and no tagged twin either. Returning here rather than
        # falling through the empty loops keeps that promise literal -- and the
        # sweep below still runs, so pinning back to base cleans up the variant
        # PDFs an earlier fan-out left behind.
        if override == []:
            return

        for variant in variants:
            macro = VARIANT_MACROS[variant]
            yield from self._build_one_variant(
                variant, macro, engine, tex_dir, engine_options, tagged=False)
            self._variants_built.append((variant, False))

        # Tagged twins last: they are the slowest half (a second full compile
        # each, forced to lualatex regardless of the class's own engine), so
        # every normal PDF is on disk before the first one starts.
        for variant in ["base"] + variants:
            yield from self._build_one_variant(
                variant, VARIANT_MACROS.get(variant, ""), engine, tex_dir,
                engine_options, tagged=True)
            self._variants_built.append((variant, True))

    def _build_one_variant(self, variant, macro, engine, tex_dir,
                           engine_options, tagged):
        """One variant compile into its own output directory.

        Two fixed passes rather than the convergence loop: the loop's state
        digest is keyed on the aux dir the BASE build owns, and a variant
        writing its own .aux there would make every subsequent variant look
        unsettled. Two passes is what the accessible half has always used and
        settles the "page X of Y" footer and \\pageref the same way.
        """
        tag = variant + ("-a11y" if tagged else "")
        out_dir = self._variant_out_dir(tag)
        engine_for = ACCESSIBLE_ENGINE if tagged else engine
        cmd_base = self._base_engine_cmd(
            engine_for, self._aux_target, tex_dir, engine_options)
        cmd = [c for c in cmd_base
               if not str(c).startswith("-output-directory=")]
        prefix = macro or ""
        if tagged:
            prefix = accessible_macro_for(
                os.path.join(tex_dir, self.tex_name)) + prefix
        cmd += [f"-output-directory={out_dir}",
                f"--jobname={self.base_name}",
                (f"{prefix}\\input{{{self.tex_name}}}" if prefix
                 else self.tex_name)]
        label = f"{engine_for} [{tag}]"
        yield (cmd, f"{label} run 1...")
        yield (cmd, f"{label} run 2 (settle)...")
        self._copy_back_variant(tex_dir, variant, tagged, out_dir)

    def _copy_back_variant(self, tex_dir, variant, tagged, out_dir):
        """Copy one finished variant out as <base>_<variant>[_accessible].pdf."""
        src = os.path.join(out_dir, self.base_name + ".pdf")
        if not os.path.exists(src):
            self.display(
                f"TeXLib: variant {variant!r}"
                f"{' (tagged)' if tagged else ''} produced no PDF; skipped.\n")
            return
        dest = os.path.join(
            tex_dir, self._variant_pdf_name(self.base_name, variant, tagged))
        self._force_remove(dest)
        try:
            shutil.copy2(src, dest)
            # Held separately, NOT appended to produced_pdfs: _postprocess
            # resets that list after the build finishes, so anything recorded
            # here would be thrown away. It merges this list back in.
            self._variant_pdfs.append(os.path.basename(dest))
        except OSError as exc:
            self.display(f"TeXLib: could not write {dest}: {exc}\n")
            return
        # The conformance report, for the BASE tagged PDF only. The fan-out
        # reaches here rather than through _copy_back_accessible (which finds
        # nothing: the variant builds write to <aux>/<variant>-a11y/, not
        # <aux>/a11y/), so without this a plain Ctrl+B would produce tagged
        # PDFs and no report at all. Base only, deliberately: every variant is
        # the same document with different content revealed, so their tag
        # structure is the same structure, and one veraPDF run per build keeps
        # a JVM launch per variant out of the edit loop.
        if tagged and variant == "base":
            self._write_accessible_report(tex_dir, dest)
        # A versioned exam emits every copy into ONE PDF plus a .vmap. The base
        # build's map is sliced in _postprocess; a variant's map lives in that
        # variant's own output directory and was never read, so a \versions
        # document's variant PDFs came out as collated blobs while the base's
        # came out per version. Slice them here, from the copy that just landed
        # beside the source.
        if not tagged:
            self._slice_variant_versions(variant, out_dir, tex_dir, dest)

    # Which suffix a variant's answer-bearing per-version slices carry. The
    # `solutions' variant keeps the historic "_solutions" because those copies
    # ARE the answer key -- <base>_A_solutions.pdf is the name collate_keys.py
    # and the SyncTeX slicer have always looked for. `instructor' needs its own
    # or it would overwrite them copy for copy.
    VARIANT_SLICE_SUFFIX = {
        "solutions": "_solutions",
        "solutions-inline": "_solutions",
        "instructor": "_instructor",
    }

    def _slice_variant_versions(self, variant, out_dir, tex_dir, pdf_path):
        """Slice one variant's combined multi-version PDF, if it wrote a .vmap.

        No-op for the overwhelmingly common single-version document, which
        writes no .vmap at all. `base_name` stays the document's real base so
        the slices read <base>_A_solutions.pdf rather than
        <base>_solutions_A_solutions.pdf -- the variant is expressed by the
        suffix, not by a doubled stem.
        """
        vmap = os.path.join(out_dir, self.base_name + ".vmap")
        if not os.path.exists(vmap) or not os.path.exists(pdf_path):
            return
        suffix = self.VARIANT_SLICE_SUFFIX.get(variant)
        if suffix is None:
            return
        try:
            _produced, messages = self._run_pdfpost(
                "slice", vmap, pdf_path, tex_dir, extra=(suffix,),
                base_name=self.base_name)
            for m in messages:
                self.display(m + "\n")
        finally:
            self._force_remove(vmap)

    def _sweep_stale_variants(self, tex_dir):
        """Delete variant PDFs this build deliberately did NOT produce.

        A leftover <base>_instructor.pdf from before the rubrics came out of a
        document is worse than no file: it looks current, it is named as
        though the planner chose it, and nothing about it says it is three
        edits old. Only names this scheme owns are ever removed, and only when
        the build actually planned a set (never after a single-variant build,
        which is not evidence about any other variant).
        """
        built = getattr(self, "_variants_built", None)
        if built is None:
            return
        keep = {self._variant_pdf_name(self.base_name, variant, tagged).lower()
                for variant, tagged in built}
        removed = []
        for variant in VARIANT_MACROS:
            for tagged in (False, True):
                name = self._variant_pdf_name(self.base_name, variant, tagged)
                if name.lower() in keep:
                    continue
                path = os.path.join(tex_dir, name)
                if not os.path.exists(path):
                    continue
                # _force_remove returns None whether or not it succeeded, so
                # confirm by absence rather than by its return value.
                self._force_remove(path)
                if not os.path.exists(path):
                    removed.append(name)
        # The conformance report describes the base tagged PDF specifically, so
        # it goes when that PDF does. A report outliving the file it certifies
        # is the same failure mode as a stale _instructor.pdf, and worse in
        # kind: this one is EVIDENCE, and it would be filed with a thesis.
        base_tagged = self._variant_pdf_name(self.base_name, "base", True)
        if base_tagged.lower() not in keep:
            report = os.path.join(
                tex_dir, self.base_name + ACCESSIBLE_REPORT_SUFFIX)
            if os.path.exists(report):
                self._force_remove(report)
                if not os.path.exists(report):
                    removed.append(os.path.basename(report))
        if removed:
            self.display(
                "TeXLib: removed stale artifacts no longer planned: "
                + ", ".join(sorted(removed)) + "\n")

    def _accessible_out_dir(self):
        """Aux subdirectory the accessible build writes into (created on demand)."""
        parent = getattr(self, "_aux_target", None) or self._tex_dir()
        out_dir = os.path.join(parent, "a11y")
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            return parent
        return out_dir

    def _copy_back_accessible(self, tex_dir):
        """Copy the tagged build out as <base>_accessible.pdf beside the source."""
        out_dir = self._accessible_out_dir()
        src = os.path.join(out_dir, self.base_name + ".pdf")
        if not os.path.exists(src):
            return
        dest = os.path.join(tex_dir, self.base_name + ACCESSIBLE_SUFFIX + ".pdf")
        try:
            shutil.copy2(src, dest)
            self.display(
                f"TeXLib: accessible copy -> {os.path.basename(dest)}\n")
        except OSError as exc:
            self.display(f"TeXLib: could not write {dest}: {exc}\n")
            return
        self._write_accessible_report(tex_dir, dest)

    def _write_accessible_report(self, tex_dir, pdf_path):
        """Write veraPDF's conformance report beside <base>_accessible.pdf.

        A tagged PDF's accessibility is invisible in the render, so the build
        that produces one should also produce the evidence that it conforms --
        UNR now requires an accessibility report to be filed with a thesis, and
        a reviewer asking "is this actually accessible?" about any handout wants
        the same artifact. veraPDF was already being run over these files by
        `smoke_test.check_verapdf`, which parses the failed clauses out and
        DISCARDS the report; this writes it out where the author can read it.

        Never fails the build. veraPDF is optional in the same way pdftotext and
        ImageMagick are, and a missing report is not a reason to lose a PDF that
        built cleanly.

        Exit status is load-bearing and is NOT an error condition: veraPDF exits
        0 for a conforming file and 1 for a non-conforming one, and writes a
        valid report either way -- a failing report is precisely when the author
        most needs to read it. Only >1 is a tool error.
        """
        if not self._setting_on(
                "accessible_report", "TEXLIB_A11Y_REPORT", True):
            return
        exe = find_verapdf()
        if not exe:
            self.display(
                "TeXLib: veraPDF not found -- no accessibility report written. "
                "Install it or set accessible_report off to silence this.\n")
            return
        itemize = self._setting_on(
            "accessible_report_full", "TEXLIB_A11Y_REPORT_FULL", False)
        dest = os.path.join(
            tex_dir, self.base_name + ACCESSIBLE_REPORT_SUFFIX)
        try:
            proc = subprocess.run(
                verapdf_report_cmd(exe, pdf_path, "html", itemize),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=_NO_WINDOW, timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.display(f"TeXLib: veraPDF report not written ({exc}).\n")
            return
        if proc.returncode > 1:
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            self.display(
                f"TeXLib: veraPDF error (exit {proc.returncode}) "
                f"-- no accessibility report. {err[:200]}\n")
            return
        try:
            with open(dest, "wb") as f:
                f.write(proc.stdout or b"")
        except OSError as exc:
            self.display(f"TeXLib: could not write {dest}: {exc}\n")
            return
        verdict = "PASSED" if proc.returncode == 0 else "FAILED"
        detail = "" if itemize else " (set accessible_report_full for the itemized form)"
        self.display(
            f"TeXLib: PDF/UA-2 {verdict} -- accessibility report -> "
            f"{os.path.basename(dest)}{detail}\n")

    def _tex_dir(self):
        """The directory containing the root .tex file."""
        return getattr(self, "tex_dir", None) or os.path.dirname(
            getattr(self, "tex_root", "") or ""
        )

    def _set_aux_target(self, tex_dir):
        """Resolve the aux directory and export it for the Lua engine too.

        problem_engine.lua writes its own build-time scratch (per-version
        body files, .sco, .srcmap, per-problem SyncTeX-fallback files) via
        raw Lua io.open, which -output-directory does not redirect (unlike
        \\openout, which kpathsea already routes -- why .aux/.log land in the
        aux dir but this engine's scratch always landed next to the source).
        TEXLIB_AUX_DIR lets problem_engine.lua's texlib_scratch_path mirror
        that same routing. The runner (texlib._run_argv) injects this build's
        _aux_target into each engine subprocess's OWN env rather than a shared
        os.environ, so concurrent builds of different documents never race a
        global -- each engine gets exactly its own build's aux dir (or "" when
        aux routing is disabled). _aux_target is a per-instance (per-build)
        attribute, so the Python-side post-steps that read it stay correct too.
        """
        self._aux_target = self._resolve_aux_directory(tex_dir)
        return self._aux_target

    def _resolve_aux_directory(self, tex_dir):
        """Resolve LaTeXTools' aux_directory setting to an absolute path.

        Returns the resolved path or None if aux routing is disabled.

        Supported values:
          - ""             -> aux routing disabled (return None).
          - "<<temp>>"     -> per-document subdirectory under the system temp
                              dir, keyed by a hash of the tex root. Persistent
                              across builds so .aux / .bcf cross-references
                              survive.
          - "<<root>>"     -> the tex root directory (same as disabled, in
                              effect, but explicit).
          - absolute path  -> used as-is.
          - relative path  -> resolved relative to the tex root directory.

        Note: TeX Live engines accept only -output-directory, not the
        MiKTeX-specific -aux-directory. So routing here moves the PDF + .log
        + .aux + .synctex.gz all together; _postprocess copies the PDF and
        .synctex.gz back to the tex_dir so the viewer + SyncTeX still work.
        """
        raw = getattr(self, "aux_directory", "") or ""
        s = str(raw).strip()
        if not s or s == "<<root>>":
            return None
        if s == "<<temp>>":
            key = hashlib.md5(
                (getattr(self, "tex_root", "") or "").encode("utf-8")
            ).hexdigest()[:12]
            target = os.path.join(tempfile.gettempdir(), "texlib-aux", key)
            try:
                os.makedirs(target, exist_ok=True)
            except OSError as exc:
                self.display(
                    f"TeXLib: could not create aux directory {target}: {exc}; "
                    "falling back to building in source dir.\n"
                )
                return None
            return target
        target = s if os.path.isabs(s) else os.path.normpath(
            os.path.join(tex_dir, s)
        )
        # Create it: TeX Live's -output-directory does not auto-create the dir,
        # so an explicit aux_directory that doesn't exist yet would make every
        # pass fail. (<<temp>> above is created the same way.)
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as exc:
            self.display(
                f"TeXLib: could not create aux directory {target}: {exc}; "
                "falling back to building in source dir.\n"
            )
            return None
        return target

    def _biber_needed(self, jobname):
        """True if biblatex wrote a .bcf for `jobname`.

        Looks in the aux directory if one is active, else the tex directory.
        """
        search_dir = getattr(self, "_aux_target", None) or self._tex_dir()
        return os.path.exists(os.path.join(search_dir, jobname + ".bcf"))

    def _biber_command(self, jobname):
        """Build the biber command line, redirecting I/O to the aux dir if set.

        biber's default working layout assumes the .bcf and .bbl live next to
        the document, but with -output-directory routing the .bcf is in the
        aux dir. --input-directory + --output-directory tell biber where to
        look for and write the .bcf / .bbl.
        """
        cmd = ["biber"]
        aux = getattr(self, "_aux_target", None)
        if aux and aux != self._tex_dir():
            cmd += [
                f"--input-directory={aux}",
                f"--output-directory={aux}",
            ]
        cmd.append(jobname)
        return cmd

    def _aux_path(self, name):
        """Absolute path for an aux artifact, honoring -output-directory routing."""
        search_dir = getattr(self, "_aux_target", None) or self._tex_dir()
        return os.path.join(search_dir, name)

    @staticmethod
    def _hash_file(path):
        """MD5 of a file's bytes, or None if it can't be read."""
        try:
            with open(path, "rb") as fh:
                return hashlib.md5(fh.read()).hexdigest()
        except OSError:
            return None

    _biber_version_cache = None

    @classmethod
    def _biber_version(cls):
        """biber's version string, or '' if biber can't be probed (cached).

        Folded into the biber-inputs fingerprint so that upgrading the biber
        binary while the .bcf/.bib are byte-identical still invalidates a stale
        .bbl (mirroring latexmk). Degrades to '' when biber isn't on PATH, in
        which case the fingerprint is unchanged from the no-version form.
        """
        if cls._biber_version_cache is not None:
            return cls._biber_version_cache
        ver = ""
        try:
            exe = shutil.which("biber")
            if exe:
                out = subprocess.run(
                    [exe, "--version"], capture_output=True, text=True,
                    timeout=10, creationflags=_NO_WINDOW,
                )
                first = (out.stdout or "").strip().splitlines()
                ver = first[0].strip() if first else ""
        except Exception:  # noqa: BLE001 - probe is best-effort
            ver = ""
        cls._biber_version_cache = ver
        return ver

    @staticmethod
    def _force_remove(path):
        """Delete `path` if present, clearing Hidden/ReadOnly first (Windows).

        Overwriting an existing Hidden or ReadOnly file with open('wb') or
        shutil.copy2 raises PermissionError (Errno 13) on Windows. We hide
        <base>.synctex after every build, and OneDrive can dehydrate
        <base>.synctex.gz into a hidden reparse-point placeholder -- so the next
        build's decompress / copy-back would fail on the stale hidden file, and
        keep failing forever once it does. Removing it first self-heals that.
        """
        if not os.path.exists(path):
            return
        try:
            os.remove(path)
            return
        except OSError:
            pass
        if os.name == "nt":
            try:
                import ctypes

                FILE_ATTRIBUTE_NORMAL = 0x80
                ctypes.windll.kernel32.SetFileAttributesW(
                    str(path), FILE_ATTRIBUTE_NORMAL
                )
            except Exception:  # noqa: BLE001 - best-effort attribute reset
                pass
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def _set_hidden(path):
        """Hide the file and pin it against OneDrive dehydration (Windows).

        Uses SetFileAttributesW directly rather than `os.system('attrib +h')`,
        which would be a shell-quoting hazard for paths with special characters
        and spawns a console window (ironic in a builder that works to suppress
        console flashes). No-op off Windows.

        PINNED is here for inverse search. SetFileAttributesW writes the whole
        settable mask, so passing HIDDEN alone also CLEARED the file's PINNED
        ("always keep on this device") bit. Under OneDrive -- the teaching
        courses, not this repo -- that left <base>.synctex as the one build
        artifact eligible for dehydration, while its own .pdf and .tex siblings
        stayed pinned. A dehydrated SyncTeX map makes SumatraPDF's first
        double-click pay a hydration round-trip, which is the likeliest cause of
        inverse search needing a second click to land. Set both flags in the one
        call; HIDDEN on its own un-pins the file again.
        """
        if os.name != "nt":
            return
        try:
            import ctypes

            FILE_ATTRIBUTE_HIDDEN = 0x2
            FILE_ATTRIBUTE_PINNED = 0x00080000
            ctypes.windll.kernel32.SetFileAttributesW(
                str(path), FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_PINNED
            )
        except Exception:  # noqa: BLE001 - best-effort attribute set
            pass

    @staticmethod
    def _bcf_datasources(bcf_path):
        """The .bib datasource filenames a .bcf references (as written inside)."""
        try:
            with open(bcf_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            return []
        return re.findall(
            r"<bcf:datasource[^>]*>([^<]+)</bcf:datasource>", text
        )

    def _resolve_datasource(self, name):
        """Locate a .bcf datasource on disk, or None if it can't be found.

        Checks the tex dir and aux dir (and treats absolute paths as-is), with
        and without a .bib extension. None means "can't prove it's unchanged",
        which the caller treats as a reason to re-run biber.
        """
        name = name.strip()
        bases = [name]
        if not name.lower().endswith(".bib"):
            bases.append(name + ".bib")
        for base in bases:
            if os.path.isabs(base):
                if os.path.isfile(base):
                    return base
                continue
            for d in (self._tex_dir(), getattr(self, "_aux_target", None)):
                if d:
                    cand = os.path.join(d, base)
                    if os.path.isfile(cand):
                        return cand
        return None

    def _biber_inputs_hash(self, jobname):
        """Fingerprint of everything biber consumes: the .bcf + its .bib files.

        Returns None if any referenced datasource can't be located -- the caller
        then re-runs biber rather than risk reusing a stale .bbl. Keying on the
        .bcf alone is not enough: editing a .bib entry (without touching a
        \\cite) leaves the .bcf unchanged, so the .bib contents must be folded in
        too. This mirrors how latexmk tracks biber's dependencies.
        """
        bcf_hash = self._hash_file(self._aux_path(jobname + ".bcf"))
        if bcf_hash is None:
            return None
        parts = [bcf_hash]
        for src in self._bcf_datasources(self._aux_path(jobname + ".bcf")):
            path = self._resolve_datasource(src)
            if path is None:
                return None
            src_hash = self._hash_file(path)
            if src_hash is None:
                return None
            parts.append(src.strip() + ":" + src_hash)
        ver = self._biber_version()
        if ver:
            parts.append("biber:" + ver)
        return "|".join(parts)

    def _biber_is_current(self, jobname):
        """True if the existing .bbl already reflects the current biber inputs.

        The engine rewrites the .bcf on every pass, but biber's output only
        changes when the .bcf or a referenced .bib changes. We stash a
        fingerprint of those inputs in a sidecar; if it still matches and the
        .bbl is present, biber and its forced re-pass can both be skipped. This
        is the change-detection latexmk does, scoped to our persistent aux dir.
        """
        if not os.path.exists(self._aux_path(jobname + ".bbl")):
            return False
        current = self._biber_inputs_hash(jobname)
        if current is None:
            return False
        try:
            with open(
                self._aux_path(jobname + ".bcf.texlibhash"), "r", encoding="utf-8"
            ) as fh:
                return fh.read().strip() == current
        except OSError:
            return False

    def _record_biber_hash(self, jobname):
        """Persist the current biber-inputs fingerprint (best effort).

        Called from _postprocess, AFTER the final engine pass has settled the
        .bcf, so the fingerprint matches the .bcf that will be on disk for the
        next build's cache check. (Recording right after biber instead would
        capture the pre-final-pass .bcf, which the post-biber pass can rewrite,
        causing a spurious biber re-run next time.)
        """
        current = self._biber_inputs_hash(jobname)
        if current is None:
            return
        try:
            with open(
                self._aux_path(jobname + ".bcf.texlibhash"), "w", encoding="utf-8"
            ) as fh:
                fh.write(current)
        except OSError:
            pass

    def _aux_state_digest(self):
        """Fingerprint of the cross-pass state files in the aux dir.

        One digest over (name, content hash) for every STATE_EXTS file at the
        top level of the aux dir, sorted so it does not depend on listing order.
        None only when the directory cannot be listed -- the caller then falls
        back to the log. An EMPTY directory still hashes to a real value rather
        than None: a cold aux dir differing from the populated one pass 1 leaves
        behind is exactly the "a first build needs a settling pass" signal.

        Top level only. With aux routing the dir is this document's own temp dir
        (keyed by a hash of the tex root), but with routing disabled it is the
        source dir, which must not be walked recursively -- a module dir can sit
        above the whole examples tree. Sibling documents' aux files landing in
        the digest is harmless: they do not change while our pass runs.
        """
        search_dir = getattr(self, "_aux_target", None) or self._tex_dir()
        if not search_dir:
            return None
        try:
            names = sorted(os.listdir(search_dir))
        except OSError:
            return None
        digest = hashlib.md5()
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext not in STATE_EXTS:
                continue
            path = os.path.join(search_dir, name)
            content = (self._hash_aux_file(path) if ext == ".aux"
                       else self._hash_file(path))
            if content is None:  # vanished mid-build; nothing to compare
                continue
            digest.update(name.encode("utf-8", "replace"))
            digest.update(content.encode("ascii"))
        return digest.hexdigest()

    @staticmethod
    def _hash_aux_file(path):
        """Hash of an .aux with the STATE_NOISE_RE bookkeeping lines dropped,
        or None if it can't be read."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            return None
        keep = [ln for ln in lines if not STATE_NOISE_RE.match(ln)]
        return hashlib.md5("\n".join(keep).encode("utf-8")).hexdigest()

    def _record_state_baseline(self):
        """Snapshot the aux state the pass about to run will consume."""
        self._state_digest = self._aux_state_digest()
        if self._state_digest is None:
            return
        if getattr(self, "_state_history", None) is None:
            self._state_history = set()
        self._state_history.add(self._state_digest)

    def _needs_another_run(self):
        """Decide whether another engine pass would change anything.

        Two sources of evidence, because neither is sufficient alone:

          * the log -- "Rerun to get ... right", "Label(s) may have changed",
            biblatex's "Please rerun LaTeX";
          * the aux-state fingerprint this pass started from (recorded by
            _count_passes) against the state on disk now.

        The fingerprint outranks the log wherever the two disagree, in both
        directions:

          * More complete. autoexam defines \\@testdef as a no-op to silence the
            multi-version label oscillation (autoexam.cls), so an exam whose
            "page X of Y" footer -- \\pageref{@lastqpage@<ver>} -- just moved to
            another page says nothing at all in the log. The .aux changing is
            the only evidence there is.
          * More honest. When a pass consumed and produced byte-identical
            state, the next pass gets identical input and so produces identical
            output: a log line still asking for one is asking for nothing. That
            veto is what lets MAX_RERUNS carry headroom for free.

        Pure -- callers may invoke it more than once per pass (the cap warning
        does). The baseline and history it reads advance once per pass, in
        _count_passes.
        """
        out = self._last_output()
        asked = bool(RERUN_RE.search(out)) or bool(BIBER_RERUN_RE.search(out))

        baseline = getattr(self, "_state_digest", None)
        if baseline is None or not self._setting_on(
            "detect_reruns_by_state", "TEXLIB_STATE_RERUN", True
        ):
            return asked
        current = self._aux_state_digest()
        if current is None:
            return asked

        if current == baseline:
            return False  # fixed point: identical in, identical out
        if current in getattr(self, "_state_history", ()):
            # A -> B -> A. The document has no fixed point, so further passes
            # only pick which of the two states the PDF ends on. Stop at the
            # cycle instead of spending the rest of MAX_RERUNS discovering that.
            self._warn_once(
                "TeXLib: aux state is oscillating between passes; stopping. "
                "Cross-references may be unstable.\n"
            )
            return False
        if asked:
            return True
        # State moved but the log never asked: the case the log cannot see.
        # Worth a settling pass, but capped (see STATE_ONLY_RERUNS) so a
        # document that re-randomizes every pass cannot make every build pay
        # the full rerun budget.
        #
        # On a COLD aux dir this branch always fires once, because the baseline
        # is the absence of state and pass 1 necessarily writes some. That costs
        # a pass on a first build whose first pass was already complete
        # (report-card-template is one: its .aux is a fixed point from pass 1).
        # Keep it anyway -- it is the same transition that catches the exam
        # footer, where the log is silent BY CONSTRUCTION: autoexam guards
        # \pageref{@lastqpage@<ver>} with \@ifundefined and falls back to
        # \numpages, so a cold pass 1 reports no undefined reference, and the
        # gutted \@testdef means pass 2 reports no changed label either. Nothing
        # would ask for the pass that fixes the footer. The cost is one pass per
        # document per aux-dir lifetime; warm builds are unaffected.
        return getattr(self, "_pass_count", 0) < 1 + STATE_ONLY_RERUNS

    def _warn_if_unsettled(self, run):
        """Report giving up at the ceiling rather than stopping silently."""
        if run < MAX_RERUNS or not self._needs_another_run():
            return
        self._warn_once(
            f"TeXLib: document still unsettled after {run} passes "
            f"(MAX_RERUNS); cross-references or the page-count footer may be "
            f"stale.\n"
        )

    def _warn_once(self, message):
        """Emit a convergence warning at most once per build."""
        if getattr(self, "_state_warned", False):
            return
        self._state_warned = True
        self.display(message)

    def _last_output(self):
        """The most recent command's combined output, or '' if unavailable."""
        return getattr(self, "out", "") or ""

    # ------------------------------------------------------------------ #
    # Post-processing
    # ------------------------------------------------------------------ #
    def _postprocess(self):
        tex_dir = self._tex_dir()
        base_path = os.path.join(tex_dir, self.base_name)

        # Reset per-build: the post-processing steps below append every extra
        # PDF they cut out of the combined build (in typeset order) and the page
        # span each was cut from. The host reads produced_pdfs to resolve its
        # preferred_pdf setting (see preferred_pdf_path); _slice_synctex_for_copies
        # reads the spans.
        self.produced_pdfs = []
        self._copy_ranges = {}

        # Record biber-input fingerprints now that the final engine pass has
        # settled each .bcf, so the next build's cache check compares against
        # the real on-disk .bcf. (See _record_biber_hash for why mid-build
        # recording caused spurious biber re-runs.)
        for jobname in getattr(self, "_biber_ran", []):
            self._record_biber_hash(jobname)
        self._biber_ran = []

        # The schedule class emits a <base>.schedmap sidecar.  Rewrite the
        # build's .synctex.gz BEFORE copy-back so the user-visible file
        # already has the right line attributions.  schedmap is written by
        # Lua to CWD (source dir); synctex.gz lands wherever -output-directory
        # routes — pass BOTH dirs so the rewriter can find each file
        # independently.
        build_dir = getattr(self, "_aux_target", None) or tex_dir
        if build_dir and os.path.isdir(build_dir):
            self._rewrite_synctex_for_schedmap(build_dir, tex_dir, self.base_name)

        # If we built into a separate aux dir (via -output-directory), copy
        # the PDF, SyncTeX file, and any .spl signal back next to the source.
        # Aux files (.aux/.log/.out/.toc/.bcf/.bbl/.fls/.fdb_latexmk/...) stay
        # in the aux dir for cross-reference resolution across builds.
        self._copy_back_from_aux(tex_dir)

        # An accessible build wrote into the aux dir's a11y/ subdirectory under
        # the document's REAL jobname (see _build_accessible); bring it out under
        # the _accessible name so it lands beside, not on top of, the primary PDF.
        # The variant fan-out sets _accessible_build too (so the publish step
        # clones from the tagged half) but routes through variants/<name>-a11y/
        # and has already copied each twin out, so it must not run this.
        if getattr(self, "_accessible_build", False) \
                and not getattr(self, "_variant_build", False):
            self._copy_back_accessible(tex_dir)

        # Merge the fan-out's artifacts into produced_pdfs, which was reset
        # above, then delete variant PDFs this build deliberately did not plan.
        self.produced_pdfs.extend(getattr(self, "_variant_pdfs", []))
        self._sweep_stale_variants(tex_dir)

        self._split_pdf_if_signaled(base_path)

        self._slice_versions_from_vmap(tex_dir, base_path)

        # Clone a published class's PDF (syllabus/schedule) to shareable names +
        # a desktop shortcut, driven by the <base>.pubmeta sidecar. Runs after
        # copy-back so the final <base>.pdf is already next to the source.
        self._publish_shareable_copies(tex_dir, base_path)

        self._finalize_synctex(tex_dir)

        # After finalize, because that is what leaves a plain <base>.synctex to
        # cut from (before it, the map is still gzipped and possibly still in
        # the aux dir).
        self._slice_synctex_for_copies(tex_dir)

        self._display_build_summary(tex_dir, base_path)
    def _finalize_synctex(self, tex_dir):
        """Reduce inverse-search artifacts to a single uncompressed <base>.synctex.

        A build leaves up to three SyncTeX-related files in the source folder;
        this collapses them to one:

          * <base>.synctex.gz  — lualatex's gzipped map. We decompress it to a
            plain <base>.synctex and delete the .gz. A PDF viewer reads an
            uncompressed .synctex directly, so SumatraPDF no longer spawns its
            own <base>.synctex.gz.sum.synctex decompression cache — that second
            file simply never appears.
          * <base>_synctex.tex — the build-time scratch the bank/exam SyncTeX
            redirect serves its content through. SyncTeX records the bank/source
            file, never this scratch, so once the build is done it is pure
            leftover. Removed. (Also sweeps the legacy per-problem
            <base>_synctex_<id>.tex files from before the single-file change.)

        Globs cover per-version outputs (e.g. template_A.synctex.gz). On
        Windows the resulting .synctex is hidden, matching the old behaviour of
        keeping it out of the folder listing and OneDrive's change feed.
        """
        # 1. Decompress <base>*.synctex.gz -> <base>*.synctex; drop the .gz.
        for gz in glob.glob(os.path.join(tex_dir, self.base_name + "*.synctex.gz")):
            plain = gz[:-3]  # strip the ".gz" suffix
            # The previous build hid <base>.synctex; open('wb') over a hidden
            # file is an Errno 13 on Windows, so drop the stale one first.
            self._force_remove(plain)
            try:
                with gzip.open(gz, "rb") as fin, open(plain, "wb") as fout:
                    shutil.copyfileobj(fin, fout)
                os.remove(gz)
            except Exception as exc:  # noqa: BLE001 - best-effort
                self.display(
                    f"TeXLib: could not decompress {os.path.basename(gz)}: {exc}\n"
                )
                continue
            self._set_hidden(plain)

        # 2. Remove the build-time SyncTeX scratch file(s).
        scratch = glob.glob(os.path.join(tex_dir, self.base_name + "_synctex.tex"))
        scratch += glob.glob(os.path.join(tex_dir, self.base_name + "_synctex_*.tex"))
        for f in scratch:
            try:
                os.remove(f)
            except Exception:
                pass

    def _slice_synctex_for_copies(self, tex_dir):
        """Cut a matching <name>.synctex for every PDF the slicer produced.

        A sliced copy (<base>_A_solutions.pdf, <base>_Solutions.pdf, ...) is
        pages carved out of the combined PDF with pypdf, so it ships with no
        SyncTeX map of its own -- and a PDF viewer looks for <its own
        name>.synctex, never the parent's. Without this step, double-clicking
        anywhere in a sliced copy does nothing: inverse search silently dies the
        moment you look at anything but <base>.pdf. That matters now that the
        preferred_pdf setting can make a slice the copy the viewer opens.

        The cut is the same page selection the PDF got: keep the {n ... }n sheet
        blocks in the copy's page span, renumber them to start at 1, and leave
        every record inside untouched (a record carries a file tag and a source
        LINE, never a page, so slicing cannot invalidate one). Every Input:
        declaration is kept wherever it stood, including those for sheets that
        were dropped: they define the tag -> file table the surviving records
        index into, and an unused entry costs nothing.

        No-op unless the build actually sliced something. Best-effort
        throughout: a copy whose map cannot be written just has no inverse
        search, exactly as before this existed.
        """
        ranges = getattr(self, "_copy_ranges", None)
        if not ranges:
            return
        src = os.path.join(tex_dir, self.base_name + ".synctex")
        try:
            with open(src, "rb") as fh:
                data = fh.read()
        except OSError:
            return  # no map to cut from (-synctex=0, or finalize found nothing)
        for pdf_name in sorted(ranges):
            first, last = ranges[pdf_name]
            out = os.path.join(
                tex_dir, os.path.splitext(pdf_name)[0] + ".synctex")
            if os.path.normcase(out) == os.path.normcase(src):
                # Never cut the parent's own map down: every other copy is cut
                # FROM it, and <base>.pdf's inverse search is it. The slicer
                # already refuses to emit a copy under the combined PDF's name,
                # so this only fires if that guard is ever lost.
                continue
            try:
                sliced = self._synctex_page_slice(data, first, last)
            except Exception as exc:  # noqa: BLE001 - best-effort
                self.display(
                    f"TeXLib: could not cut a SyncTeX map for {pdf_name}: "
                    f"{exc}\n")
                continue
            if sliced is None:
                continue
            # Clear the previous build's (hidden) copy first -- open('wb') over
            # a hidden file is an Errno 13 on Windows, same as in _finalize_synctex.
            self._force_remove(out)
            try:
                with open(out, "wb") as fh:
                    fh.write(sliced)
            except OSError as exc:
                self.display(
                    f"TeXLib: could not write {os.path.basename(out)}: {exc}\n")
                continue
            self._set_hidden(out)

    @staticmethod
    def _synctex_page_slice(data, first_page, last_page):
        """Return `data` (a whole .synctex) reduced to pages first..last, or None.

        Format, from the one this build just wrote:

            SyncTeX Version:1        preamble: Input: table, Magnification, ...
            Content:
            !20315                   anchor, then one sheet per page
            {1                         <- sheet 1 opens
            ...records...
            !11059
            }1                         <- sheet 1 closes
            Input:251:...            more Input: rows may appear between sheets
            !422
            {2
            ...
            Postamble:
            Count:1029
            Post scriptum:

        The `!N` anchors are the only thing that makes this non-trivial: N is
        the byte distance from the previous anchor's own offset (from the file
        start, for the first), and SyncTeX seeks with them, so a rewrite that
        left them alone would send a reader into the middle of a record. They
        are dropped on the way in and recomputed on the way out, which also
        means this round-trips a file it does not change byte-for-byte.

        `Count:` is left as the parent's -- it sizes the parser's record table,
        so an over-estimate is harmless where a wrong-but-plausible value is not.
        Returns None if `data` is not a SyncTeX map or the span holds no page.
        """
        eol = b"\r\n" if data[:200].find(b"\r\n") != -1 else b"\n"
        lines = data.split(eol)
        if not lines or not lines[0].startswith(b"SyncTeX Version:"):
            return None

        out = []          # emitted lines, anchors excluded (added while writing)
        anchored = set()  # indices in `out` that an anchor must precede
        sheet = None      # page number of the sheet currently being buffered
        buf = []
        kept = 0

        def emit(line, anchor=False):
            if anchor:
                anchored.add(len(out))
            out.append(line)

        for line in lines:
            if line.startswith(b"!"):
                continue  # recomputed below
            if sheet is None:
                if line[:1] == b"{" and line[1:].isdigit():
                    sheet, buf = int(line[1:]), []
                    continue
                emit(line, anchor=line in (b"Postamble:", b"Post scriptum:"))
                continue
            # Inside a sheet: only its own closing brace ends it. Records use
            # (, ), [, ], h, v, x, g, k, $ -- never a bare-number brace.
            if line == b"}" + str(sheet).encode():
                if first_page <= sheet <= last_page:
                    kept += 1
                    emit(b"{" + str(kept).encode(), anchor=True)
                    for r in buf:
                        emit(r)
                    emit(b"}" + str(kept).encode(), anchor=True)
                sheet, buf = None, []
                continue
            buf.append(line)

        if not kept:
            return None

        # Write out, recomputing each anchor as the byte delta from the previous
        # anchor's own offset (0 for the first).
        blob, last_at = bytearray(), 0
        for i, line in enumerate(out):
            if i in anchored:
                here = len(blob)
                blob += b"!" + str(here - last_at).encode() + eol
                last_at = here
            blob += line + eol
        # split() left a trailing empty element for the file's final newline;
        # the loop turned it back into one, so strip the extra it also added.
        return bytes(blob[:-len(eol)]) if out and out[-1] == b"" else bytes(blob)

    def _copy_back_from_aux(self, tex_dir):
        """If aux routing is active, copy viewer-facing artifacts back.

        We copy <base>*.pdf, <base>*.synctex.gz, <base>*.spl and
        <base>*.schedmeta. The glob catches per-version outputs too (e.g.
        template_A.pdf for autoexam). Aux/log/etc. stay in the aux dir.

        .schedmeta is here because its consumer is OUTSIDE the build (the
        standalone TeXLib Sync program reads it from beside the source, like a
        reader opens the PDF from beside the source). Without this it lands in
        %TEMP%\\texlib-aux\\<hash> on every builder build and the sync tool either
        reports "build the schedule first" for a schedule just built, or reads a
        stale copy from an older in-place CLI build. Contrast .schedmap, whose
        consumer *is* this builder -- it probes both directories itself.
        """
        aux_target = getattr(self, "_aux_target", None)
        if not aux_target or aux_target == tex_dir or not os.path.isdir(aux_target):
            return
        patterns = (
            f"{self.base_name}*.pdf",
            f"{self.base_name}*.synctex.gz",
            f"{self.base_name}*.spl",
            f"{self.base_name}*.schedmeta",
        )
        for pat in patterns:
            for src in glob.glob(os.path.join(aux_target, pat)):
                dst = os.path.join(tex_dir, os.path.basename(src))
                # Clear any stale Hidden/ReadOnly dest first -- shutil.copy2 onto
                # a hidden file (e.g. a OneDrive-dehydrated .synctex.gz) is an
                # Errno 13 on Windows.
                self._force_remove(dst)
                try:
                    shutil.copy2(src, dst)
                except Exception as exc:  # noqa: BLE001 - best-effort copy
                    self.display(
                        f"TeXLib: could not copy {os.path.basename(src)} "
                        f"back to source: {exc}\n"
                    )

    @staticmethod
    def _find_in_dirs(name, dirs):
        """Return the first existing path for `name` across the candidate dirs."""
        for d in dirs:
            if not d:
                continue
            candidate = os.path.join(d, name)
            if os.path.exists(candidate):
                return candidate
        return None

    def _rewrite_synctex_for_schedmap(self, build_dir, tex_dir, base_name):
        """Rewrite synctex.gz to remap schedule grid-file refs at user-source lines.

        The schedule class writes each calendar row into <base>_schedule_grid.tex
        in week order and `\\input`s that file, so without intervention SyncTeX
        records typeset nodes as coming from the grid file.  At render time the
        class also writes <base>.schedmap, recording the user-source line that
        each grid_line was generated from (the line of the first contributing
        \\section / \\holiday / etc. directive).

        Here we read .schedmap, locate the grid-file Input records in the
        SyncTeX stream by basename, and:
          1) Rewrite those Input records to point at <base>.tex instead, so the
             editor opens the user's source file on inverse search.
          2) Remap the line component of every typeset record that references a
             grid-file ID, swapping the grid_line for the user-source line.

        Records left untouched: typeset records that reference grid_lines NOT
        in the schedmap (rare, but they remain attributable to the grid file),
        and file-scope markers ({N / }N) which only carry IDs, not lines.

        Path discovery: with -output-directory routing (LaTeXTools' default
        aux_directory=<<temp>>), .schedmap is written by Lua to the source
        dir (lualatex's CWD) while .synctex.gz lands in build_dir.  Without
        routing the two coincide.  We check both dirs for each file so the
        rewrite works in either configuration.

        No-op if there's no .schedmap, no .synctex.gz, no matching Input
        record, or no matching <base>.tex Input to confirm the source file
        exists in the stream.
        """
        schedmap = self._find_in_dirs(base_name + ".schedmap", [tex_dir, build_dir])
        if not schedmap:
            return
        synctex = self._find_in_dirs(base_name + ".synctex.gz", [build_dir, tex_dir])
        if not synctex:
            self.display(
                "TeXLib: schedule .schedmap is present but no .synctex.gz "
                "was found; inverse search won't be repointed at the source "
                "(is -synctex=1 set?).\n"
            )
            return

        # Parse .schedmap.  Body lines are "grid_line|user_source_line".
        # Header comments may carry two extra hints:
        #   # boilerplate-after-line: N
        #   # boilerplate-target-line: M
        # Records the rewriter uses to redirect Schedule.tex records on any
        # line > N (e.g. content attributed to \end{document}: the table's
        # bottom rule from \endlastfoot, page footers, shipout artifacts) to
        # line M (the last directive line).
        line_map = {}
        boilerplate_after_line  = None
        boilerplate_target_line = None
        header_re = re.compile(
            r"#\s*(boilerplate-after-line|boilerplate-target-line)\s*:\s*(\d+)"
        )
        try:
            with open(schedmap, "r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    s = raw.strip()
                    if not s:
                        continue
                    if s.startswith("#"):
                        hm = header_re.match(s)
                        if hm:
                            try:
                                val = int(hm.group(2))
                            except ValueError:
                                continue
                            if hm.group(1) == "boilerplate-after-line":
                                boilerplate_after_line = val
                            else:
                                boilerplate_target_line = val
                        continue
                    parts = s.split("|", 1)
                    if len(parts) != 2:
                        continue
                    try:
                        line_map[int(parts[0])] = int(parts[1])
                    except ValueError:
                        continue
        except OSError:
            return
        if not line_map:
            return

        # Load synctex.gz
        try:
            with gzip.open(synctex, "rt", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            return

        # Locate file IDs for the grid file (multiple Input records possible —
        # LuaTeX often emits one per open + kpse-lookup pass) and the source.
        grid_basename = base_name + "_schedule_grid.tex"
        src_basename  = base_name + ".tex"

        grid_ids = set()
        src_ids  = set()
        src_path = None
        for m in re.finditer(r"^Input:(\d+):(.+)$", content, re.MULTILINE):
            fid = int(m.group(1))
            path = m.group(2).rstrip()
            bn = os.path.basename(path.replace("\\", "/"))
            if bn == grid_basename:
                grid_ids.add(fid)
            elif bn == src_basename:
                src_ids.add(fid)
                if src_path is None:
                    src_path = path

        if not grid_ids or src_path is None:
            missing = "grid-file" if not grid_ids else "source-file"
            self.display(
                "TeXLib: schedule SyncTeX rewrite skipped: .schedmap is "
                f"present but no {missing} Input record was found in "
                f"{os.path.basename(synctex)}. Inverse search will land "
                "in the grid file instead of the source.\n"
            )
            return

        # 1) Remap line numbers in typeset records FIRST (order matters here --
        #    see the Input-record step below, which depends on whether this
        #    pass actually maps anything).
        #    Record prefix is one of: ( [ h v x g k r $  (boxes, nodes, math).
        #    Format: "<prefix><fileID>,<line>:..."
        #    File-scope markers ({N / }N) carry no line so they're untouched.
        #    Two rewrites apply:
        #      a) fileID in grid_ids and line in line_map  -> map cell -> directive.
        #      b) fileID is the source AND line > boilerplate-after-line -> map
        #         to boilerplate-target-line (page footers, table bottom rule).
        record_re = re.compile(r"([(\[hvxgkr$])(\d+),(\d+):")

        do_boilerplate = (
            boilerplate_after_line is not None
            and boilerplate_target_line is not None
            and src_ids
        )

        rewrites = 0
        boilerplate_rewrites = 0
        def _rewrite_record(match):
            nonlocal rewrites, boilerplate_rewrites
            fid  = int(match.group(2))
            line = int(match.group(3))
            if fid in grid_ids and line in line_map:
                rewrites += 1
                return "%s%d,%d:" % (match.group(1), fid, line_map[line])
            if do_boilerplate and fid in src_ids and line > boilerplate_after_line:
                boilerplate_rewrites += 1
                return "%s%d,%d:" % (match.group(1), fid, boilerplate_target_line)
            return match.group(0)
        content = record_re.sub(_rewrite_record, content)

        if rewrites == 0 and boilerplate_rewrites == 0:
            return

        # 2) Rewrite each grid-file Input record to point at the user source --
        #    ONLY when at least one CELL record was actually remapped above
        #    (rewrites > 0).
        #
        #    xltabular/longtable defer real box shipout until the output
        #    routine fires (page-full or end-of-table), by which point every
        #    cell's raw SyncTeX line has collapsed to whatever line the input
        #    stream had reached by then -- typically the grid file's OWN last
        #    line, which is never a key in line_map. When that happens
        #    `rewrites` stays 0 even though `boilerplate_rewrites` may still
        #    fire (a separate, independent mechanism keyed off the SOURCE
        #    file's own fid, unaffected by this). Swapping the Input record in
        #    that situation would repoint every still-wrong grid-file line at
        #    the real source file, turning an honestly-broken click target
        #    (lands in the auto-generated grid file, self-evidently a scratch
        #    file) into a confidently WRONG one (lands on a plausible-looking
        #    but unrelated real source line). Leaving the Input record alone
        #    keeps the same honest fallback plain CLI builds already get.
        if rewrites > 0:
            def _rewrite_input(match):
                fid = int(match.group(1))
                if fid in grid_ids:
                    return "Input:%d:%s" % (fid, src_path)
                return match.group(0)
            content = re.sub(r"^Input:(\d+):.+$", _rewrite_input,
                             content, flags=re.MULTILINE)

        # Write back.  Re-gzip to keep the file format unchanged.
        try:
            with gzip.open(synctex, "wt", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            self.display(
                "TeXLib: schedule SyncTeX rewrite couldn't write %s: %s\n"
                % (os.path.basename(synctex), exc)
            )
            return

        if rewrites > 0:
            msg = (
                "TeXLib: rewrote %d schedule SyncTeX cell record(s) to the "
                "user source (%d cell(s) in the schedmap)"
                % (rewrites, len(line_map))
            )
        else:
            msg = (
                "TeXLib: schedule per-cell SyncTeX could not be applied (0 "
                "of %d schedmap entries matched a real record -- likely "
                "every cell's raw attribution collapsed to one line, a "
                "known xltabular limitation); calendar cells will open the "
                "auto-generated grid file instead of the real source"
                % len(line_map)
            )
        if boilerplate_rewrites:
            msg += "; %d boilerplate record(s) redirected to line %d" % (
                boilerplate_rewrites, boilerplate_target_line
            )
        msg += ".\n"
        self.display(msg)

    def _split_pdf_if_signaled(self, base_path):
        """Honor a <base>.spl 'split_page=N' signal: split the PDF in two."""
        spl_file = base_path + ".spl"
        pdf_file = base_path + ".pdf"
        if not os.path.exists(spl_file):
            # A .spl produced in the aux dir but missing next to the source
            # means the copy-back failed; warn rather than silently skip the
            # exam/solutions split (the copy-back step logs its own error too).
            aux = getattr(self, "_aux_target", None)
            if aux and aux != self._tex_dir():
                aux_spl = os.path.join(aux, os.path.basename(base_path) + ".spl")
                if os.path.exists(aux_spl):
                    self.display(
                        "TeXLib: a .spl split signal exists in the aux dir but "
                        "was not copied back to the source, so the PDF was not "
                        "split. Check the copy-back step above for an error.\n"
                    )
            return
        if not os.path.exists(pdf_file):
            return
        produced, messages = self._run_pdfpost(
            "split", spl_file, pdf_file, os.path.dirname(base_path)
        )
        for m in messages:
            self.display(m + "\n")
        # Consume the signal only on a real split -- an out-of-range split_page
        # leaves the .spl in place (matching the pre-delegation behaviour).
        if produced:
            self._force_remove(spl_file)

    def _slice_versions_from_vmap(self, tex_dir, base_path):
        """Slice ONE combined multi-copy PDF into a PDF per version/solutions
        copy, honoring a <base>.vmap sidecar autoexam writes for a build with
        more than one copy (multiple \\versions, \\solutions dual/only mode,
        or both) that was NOT already forced to a single version/state by the
        builder itself (see \\AutoExamVmapRecord in autoexam.cls and
        autoexam_run_versions in problem_engine.lua).

        Each line is "version|stu-or-sol|start_page" in typeset order (version
        may be empty for a solutions-only/no-\\versions document). A record's
        last page is inferred as one before the next record's start page, or
        the PDF's actual last page for the final record -- no explicit end
        marker is written, so this is a no-op-safe design even if a page
        count changes between writing the .vmap and reading the final PDF.

        Written via \\immediate\\write (kpathsea-routed, like .aux/.log), so
        -output-directory places it in the aux dir like any other aux file;
        _find_in_dirs checks there first, then the source dir (aux routing
        disabled). No-op if no .vmap exists -- the overwhelmingly common case
        of a single-copy build, where the combined PDF already IS the only
        "per-version" PDF there is to produce.
        """
        vmap_path = self._find_in_dirs(
            self.base_name + ".vmap",
            [getattr(self, "_aux_target", None), tex_dir],
        )
        if not vmap_path:
            return
        pdf_path = base_path + ".pdf"
        if not os.path.exists(pdf_path):
            return
        try:
            _produced, messages = self._run_pdfpost(
                "slice", vmap_path, pdf_path, tex_dir
            )
            for m in messages:
                self.display(m + "\n")
        finally:
            self._force_remove(vmap_path)

    # ------------------------------------------------------------------ #
    # Publish step + build summary
    # ------------------------------------------------------------------ #
    def _publish_shareable_copies(self, tex_dir, base_path):
        """Clone a published class's PDF to shareable names + a desktop shortcut.

        Driven by the <base>.pubmeta sidecar course-metadata.sty writes for a
        class that called \\TeXLibDeclarePublishable (syllabus, schedule). Its
        RESOLVED course / section / term (coursemeta defaults + option overrides
        + the derived term -- none reconstructable from coursemeta.tex by a build
        tool) name the copies made next to the source:

          * <SUBJECT> <number>.<section>_<term>_<LastName>.pdf -- the Math & Stat
            Office submission name (or <publish-name>.pdf if that key is set),
            each segment dropped when its source field is unset, plus the
            declaring class's coded-suffix so two publishable classes in one
            course cannot clone to the same filename
          * <generic>.pdf                   (Syllabus.pdf / Tentative Schedule.pdf)

        and a "<course> <term> <noun>" shortcut in the desktop's Course Materials
        folder pointing at the coded copy. The sidecar is always consumed so it
        never litters; a no-op for every non-publishable build. Disabling publish
        (builder_settings / env) still consumes the sidecar but skips the copies.

        On an accessible build the copies are cloned from the TAGGED PDF -- see
        _publish_source_pdf for why the LMS-bound files get that half.
        """
        meta = self._read_pubmeta(tex_dir)   # consumes the sidecar if present
        if meta is None:
            return                           # not a publishable build
        if not self._publish_enabled():
            return                           # feature off: copies/shortcut skipped
        pdf = self._publish_source_pdf(base_path)
        if not pdf:
            return
        course   = meta.get("course", "").strip()
        section  = meta.get("section", "").strip()
        term     = meta.get("term", "").strip()
        generic  = meta.get("generic", "").strip()
        noun     = meta.get("noun", "").strip()
        instr    = meta.get("instructor", "").strip()
        suffix   = meta.get("coded-suffix", "").strip()
        override = meta.get("publish-name", "").strip()
        # Sanity guard: never emit a "MATH 181__.pdf"-style name from a document
        # whose coursemeta is missing the identifying pieces. The PDF built fine;
        # only the shareable clones are skipped.
        if not course or not term:
            self.display(
                "TeXLib: publish skipped -- course/term unset in coursemeta "
                "(need course-subject + course-number and season + year, or an "
                "explicit term). The PDF built normally.\n"
            )
            return
        coded = override or self._coded_basename(course, section, term, instr)
        if override:
            coded = self._sanitize_filename(coded)
        # The kind-discriminating suffix rides on the override too: publish-name
        # is course-wide, so without this every publishable class in the course
        # would clone to the one overridden name again.
        if suffix:
            coded = self._sanitize_filename(coded + "_" + suffix)
        made = []
        coded_pdf = os.path.join(tex_dir, coded + ".pdf")
        if self._copy_pdf(pdf, coded_pdf):
            made.append(os.path.basename(coded_pdf))
        if generic:
            generic_pdf = os.path.join(
                tex_dir, self._sanitize_filename(generic) + ".pdf"
            )
            if self._copy_pdf(pdf, generic_pdf):
                made.append(os.path.basename(generic_pdf))
        extra = ""
        if noun:
            label = f"{course} {term} {noun}"
            if self._make_desktop_shortcut(label, coded_pdf):
                extra = f'; desktop shortcut "{label}"'
        # QOL: leave the shareable path on the clipboard, ready to paste into the
        # LMS. Only fires on a publish (not every build), so it's not intrusive.
        if self._clipboard_enabled():
            self._copy_to_clipboard(coded_pdf)
        if made:
            self.display("TeXLib: published " + ", ".join(made) + extra + ".\n")

    def _publish_source_pdf(self, base_path):
        """Which PDF the shareable copies are cloned from; None if there is none.

        An accessible build publishes its TAGGED half. The shareable copies are
        precisely the files that go up to WebCampus, where an untagged PDF is
        what the LMS accessibility checker flags -- and where the tagged twin
        costs nothing visually for the only two publishable classes: syllabus and
        schedule box no theorems, so the tcolorbox fallback that makes the tagged
        variant plainer elsewhere never fires for them.

        Gated on THIS build having produced the tagged file. A stale
        <base>_accessible.pdf left behind by an earlier accessible run must never
        be published behind a normal build's back -- it would ship content from
        whenever that run happened.
        """
        normal = base_path + ".pdf"
        if getattr(self, "_accessible_build", False):
            tagged = base_path + ACCESSIBLE_SUFFIX + ".pdf"
            if os.path.exists(tagged):
                self.display(
                    "TeXLib: publishing the tagged PDF -- shareable copies are "
                    "screen-reader ready.\n"
                )
                return tagged
        return normal if os.path.exists(normal) else None

    def _read_pubmeta(self, tex_dir):
        """Read and DELETE the <base>.pubmeta sidecar; return its key=value map,
        or None when absent (every non-publishable build). Checked in the aux dir
        first (\\openout routes there under -output-directory, like .vmap) then
        the source dir."""
        path = self._find_in_dirs(
            self.base_name + ".pubmeta",
            [getattr(self, "_aux_target", None), tex_dir],
        )
        if not path:
            return None
        meta = {}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    meta[key.strip()] = val.strip()
        except OSError:
            meta = None
        self._force_remove(path)
        return meta

    @staticmethod
    def _coded_basename(course, section, term, instructor=""):
        """Build the Math & Stat Office submission name for a shareable PDF:

          "<SUBJECT> <number>.<section>_<term>_<LastName>"

        matching the convention the department has asked for since August 2025
        ("MATH XXX.YYYY_Fall 2026_InstructorLastName"), so the published syllabus
        can be mailed to math@unr.edu as-is with no manual rename.

          ("Math 181", "1001", "Fall 2026", "Landon Fox") -> "MATH 181.1001_Fall 2026_Fox"
          ("Stat 152", "1002", "Fall 2026", "Landon Fox") -> "STAT 152.1002_Fall 2026_Fox"
          ("Math 181", "",     "Fall 2026", "Landon Fox") -> "MATH 181_Fall 2026_Fox"
          ("Math 181", "1001", "Fall 2026", "")           -> "MATH 181.1001_Fall 2026"

        Spaces are PRESERVED (only runs collapsed and the ends trimmed) -- the
        convention is written with them, and they are legal in a filename on
        every platform TeXLib builds on. The course is upper-cased whole: the
        subject is the only alphabetic part, and a number suffix that carries
        letters ("126EE") is already upper-case.

        A segment whose source field is unset drops out rather than leaving an
        empty "__" gap. Set the course-wide `publish-name` key to override the
        whole basename when a course needs a name this cannot express (an
        instructor whose surname is not the last token of `instructor`, say)."""
        c = _collapse_ws(course).upper()
        s = _collapse_ws(section)
        t = _collapse_ws(term)
        last = _surname(instructor)
        name = f"{c}.{s}" if s else c
        for part in (t, last):
            if part:
                name += "_" + part
        return TexlibBuildCore._sanitize_filename(name)

    @staticmethod
    def _sanitize_filename(name):
        """Drop characters illegal in a Windows filename, preserving the dots and
        underscores the coded name relies on."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
        return cleaned.strip().rstrip(".")

    def _copy_pdf(self, src, dst):
        """Copy src -> dst, clearing a stale Hidden/ReadOnly dest first (the same
        Errno-13 hazard the copy-back guards against). Returns True on success;
        a no-op (False) when src and dst are the same file.

        The same-file test is case-insensitive (normcase) and also asks the OS
        (samefile), because on a case-insensitive Windows volume "Syllabus.pdf"
        and a source "syllabus.pdf" are ONE file: without this guard the
        \\force_remove below would delete the just-built source PDF and the copy
        would then fail. A source already named like the target simply is the
        shareable copy, so skipping is correct."""
        src_abs, dst_abs = os.path.abspath(src), os.path.abspath(dst)
        same = os.path.normcase(src_abs) == os.path.normcase(dst_abs)
        if not same and os.path.exists(dst_abs):
            try:
                same = os.path.samefile(src_abs, dst_abs)
            except OSError:
                same = False
        if same:
            return False
        self._force_remove(dst)
        try:
            shutil.copy2(src, dst)
            return True
        except Exception as exc:  # noqa: BLE001 - best-effort
            self.display(
                f"TeXLib: could not write {os.path.basename(dst)}: {exc}\n"
            )
            return False

    def _make_desktop_shortcut(self, label, target):
        """Create/refresh a .lnk to `target` in the desktop's PUBLISH_SHORTCUT_DIR
        (Windows only; no-op elsewhere). Values pass through the environment so a
        course name with quotes/spaces can't break the PowerShell command. Uses
        GetFolderPath('Desktop') so the OneDrive-redirected desktop resolves.
        Returns True on success."""
        if os.name != "nt":
            return False
        label = self._sanitize_filename(label)
        if not label:
            return False
        env = dict(os.environ)
        env["TEXLIB_LNK_LABEL"] = label
        env["TEXLIB_LNK_TARGET"] = os.path.abspath(target)
        env["TEXLIB_LNK_SUBDIR"] = PUBLISH_SHORTCUT_DIR
        ps = (
            "$ErrorActionPreference='Stop';"
            "$d=[Environment]::GetFolderPath('Desktop');"
            "$dir=Join-Path $d $env:TEXLIB_LNK_SUBDIR;"
            "New-Item -ItemType Directory -Force -Path $dir | Out-Null;"
            "$p=Join-Path $dir ($env:TEXLIB_LNK_LABEL + '.lnk');"
            "$w=New-Object -ComObject WScript.Shell;"
            "$s=$w.CreateShortcut($p);"
            "$s.TargetPath=$env:TEXLIB_LNK_TARGET;"
            "$s.Save()"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", ps],
                env=env, capture_output=True, text=True,
                creationflags=_NO_WINDOW, timeout=30,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort
            self.display(f"TeXLib: desktop shortcut not created ({exc}).\n")
            return False
        if proc.returncode != 0:
            self.display(
                "TeXLib: desktop shortcut not created "
                f"({(proc.stderr or '').strip()[:200]}).\n"
            )
            return False
        return True

    def _copy_to_clipboard(self, text):
        """Best-effort: put `text` on the Windows clipboard (for pasting the
        shareable PDF path into the LMS). No-op off Windows / on any error."""
        if os.name != "nt":
            return
        env = dict(os.environ)
        env["TEXLIB_CLIP"] = str(text)
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "Set-Clipboard -Value $env:TEXLIB_CLIP"],
                env=env, capture_output=True, creationflags=_NO_WINDOW,
                timeout=15,
            )
        except Exception:  # noqa: BLE001 - a convenience, never fatal
            pass

    def _publish_enabled(self):
        return self._setting_on(PUBLISH_SETTING, PUBLISH_ENV, True)

    def _clipboard_enabled(self):
        return self._setting_on(PUBLISH_CLIP_SETTING, PUBLISH_CLIP_ENV, True)

    def _setting_on(self, key, env_var, default):
        """Resolve a boolean toggle: builder_settings[key] wins, else the env var
        (0/false/no/off/'' = off), else `default`. builder_settings is absent on
        the bare instances the logic tests construct, hence the getattr."""
        settings = getattr(self, "builder_settings", None) or {}
        if key in settings:
            return bool(settings[key])
        raw = os.environ.get(env_var)
        if raw is not None:
            return raw.strip().lower() not in ("0", "false", "no", "off", "")
        return default

    def _display_build_summary(self, tex_dir, base_path):
        """One-line wrap-up: elapsed time, engine passes, biber runs, PDF size."""
        start = getattr(self, "_build_start", None)
        if start is None:
            return
        elapsed = time.monotonic() - start
        passes = getattr(self, "_pass_count", 0)
        bibers = getattr(self, "_biber_count", 0)
        biber_str = f", {bibers} biber" if bibers else ""
        size_str = ""
        pdf = base_path + ".pdf"
        try:
            if os.path.exists(pdf):
                size_str = (
                    f"; {os.path.basename(pdf)} "
                    f"{self._human_size(os.path.getsize(pdf))}"
                )
        except OSError:
            pass
        self.display(
            f"TeXLib: build finished in {elapsed:.1f}s -- "
            f"{passes} pass(es){biber_str}{size_str}.\n"
        )
        self._display_variant_summary(tex_dir)

    def _display_variant_summary(self, tex_dir):
        """List what the fan-out produced AND what it chose not to.

        The omissions are the important half. Autodetection that silently
        drops a variant is indistinguishable from autodetection that is wrong,
        and the person reading this is the only one who can tell which it was.
        """
        built = getattr(self, "_variants_built", None)
        if built is None:
            return
        lines = []
        for name, tagged in built:
            pdf = self._variant_pdf_name(self.base_name, name, tagged)
            path = os.path.join(tex_dir, pdf)
            if not os.path.exists(path):
                continue
            try:
                size = self._human_size(os.path.getsize(path))
            except OSError:
                size = "?"
            lines.append(f"    {pdf}  ({size})")
        if lines:
            self.display("TeXLib: variants produced:\n" + "\n".join(lines) + "\n")
        for name, reason in getattr(self, "_variants_skipped", []):
            self.display(f"TeXLib: variant {name!r} not built -- {reason}.\n")

    @staticmethod
    def _human_size(n):
        """Human-readable byte count (B / KB / MB / GB)."""
        size = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return (f"{size:.0f} {unit}" if unit == "B"
                        else f"{size:.1f} {unit}")
            size /= 1024

    def _external_python(self):
        """A command prefix for an external Python that can import pypdf, or None.

        Sublime Text's embedded interpreter has no site-packages, so the
        in-process `import pypdf` in _run_pdfpost fails under a real build; the
        pypdf work is then handed to this interpreter instead. Candidates, in
        order: $TEXLIB_PYTHON, the current interpreter (only if it actually
        looks like python -- inside Sublime sys.executable is the plugin host,
        which must never be run with -c), then python / python3 / py -3 from
        PATH. The first whose `-c "import pypdf"` succeeds wins; the result
        (including None) is cached for the process.
        """
        cached = getattr(TexlibBuildCore, "_ext_python_cache", False)
        if cached is not False:
            return cached
        candidates = []
        override = os.environ.get("TEXLIB_PYTHON")
        if override:
            candidates.append([override])
        exe = sys.executable or ""
        if os.path.basename(exe).lower().startswith("python"):
            candidates.append([exe])
        candidates += [["python"], ["python3"], ["py", "-3"]]
        found = None
        for cand in candidates:
            try:
                probe = subprocess.run(
                    cand + ["-c", "import pypdf"],
                    capture_output=True, creationflags=_NO_WINDOW,
                )
            except Exception:  # noqa: BLE001 - candidate not on PATH, etc.
                continue
            if probe.returncode == 0:
                found = cand
                break
        TexlibBuildCore._ext_python_cache = found
        return found

    def _run_pdfpost(self, op, sidecar_path, pdf_path, out_dir, extra=(),
                     base_name=None):
        """Run a pypdf post-processing op (slice a .vmap, split a .spl).

        Runs in-process when pypdf is importable here (the CLI test harness /
        system Python), else via texlib_pdfpost.py under an external Python that
        has pypdf (Sublime's embedded one does not). Both paths call the SAME
        module functions, so there is one implementation. Returns
        (produced_names, messages); messages are user-facing. Never raises --
        every failure becomes a message the caller can display. The op's page
        spans are absorbed on the way past (see _absorb_pdfpost) rather than
        returned, so existing two-value callers are untouched.
        """
        # Normally the output stem IS the input PDF's stem. A variant slice is
        # the exception: its source is <base>_instructor.pdf but its slices must
        # read <base>_A_instructor.pdf, not <base>_instructor_A_instructor.pdf.
        if base_name is None:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pdfpost = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "texlib_pdfpost.py"
        )
        # 1) In-process: pypdf present (tests / CLI). The op imports pypdf
        #    itself, so an ImportError here means "no pypdf" -> fall through.
        try:
            import pypdf  # noqa: F401
            import texlib_pdfpost
            result = texlib_pdfpost._OPS[op](
                sidecar_path, pdf_path, out_dir, base_name, *extra
            )
            return self._absorb_pdfpost(result)
        except ImportError:
            pass
        except Exception as exc:  # noqa: BLE001 - best-effort
            return [], [f"TeXLib: {op} PDF post-processing failed: {exc}"]
        # 2) External Python that has pypdf.
        if not os.path.exists(pdfpost):
            return [], [
                f"TeXLib: {os.path.basename(pdfpost)} is missing, so PDFs were "
                "not post-processed. Redeploy the Sublime integration."
            ]
        py = self._external_python()
        if not py:
            return [], [
                "TeXLib: pypdf is unavailable to Sublime's Python and no "
                "external Python with pypdf was found on PATH, so per-version / "
                "split PDFs were not produced. Install pypdf for your system "
                "Python (pip install pypdf), or set TEXLIB_PYTHON to one that "
                "has it."
            ]
        try:
            proc = subprocess.run(
                py + [pdfpost, op, sidecar_path, pdf_path, out_dir, base_name]
                + [str(e) for e in extra],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", creationflags=_NO_WINDOW,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort
            return [], [f"TeXLib: could not run PDF post-processing: {exc}"]
        if proc.returncode == 3:  # texlib_pdfpost.PYPDF_MISSING_EXIT
            return [], [
                "TeXLib: the external Python found also lacks pypdf, so PDFs "
                "were not post-processed. Install it: pip install pypdf"
            ]
        if proc.returncode != 0:
            return [], [
                f"TeXLib: PDF post-processing exited {proc.returncode} "
                f"({(proc.stderr or '').strip()[:300]})"
            ]
        try:
            import json
            result = json.loads((proc.stdout or "").strip() or "{}")
        except ValueError:
            return [], ["TeXLib: PDF post-processing returned unreadable output."]
        return self._absorb_pdfpost(result)

    def _absorb_pdfpost(self, result):
        """Record what a pypdf op produced, and return its (produced, messages).

        produced_pdfs accumulates in call order across the ops of one build --
        which for a version slice is typeset order (every student copy, then
        every solutions copy), the order preferred_pdf_path resolves "solutions"
        / "student" against. _copy_ranges carries each name's page span for
        _slice_synctex_for_copies.
        """
        names = getattr(self, "produced_pdfs", None)
        if names is None:
            names = self.produced_pdfs = []
        spans = getattr(self, "_copy_ranges", None)
        if spans is None:
            spans = self._copy_ranges = {}

        produced = result.get("produced", []) or []
        for name in produced:
            if name not in names:
                names.append(name)
        for name, span in (result.get("ranges", {}) or {}).items():
            try:
                spans[name] = (int(span[0]), int(span[1]))
            except (TypeError, ValueError, IndexError):
                continue
        return produced, result.get("messages", [])

    # ------------------------------------------------------------------ #
    # Which PDF the host should present
    # ------------------------------------------------------------------ #
    def preferred_pdf_path(self, preference):
        """Resolve the host's `preferred_pdf` setting to a PDF to open.

        A multi-copy exam build produces the combined <base>.pdf AND one sliced
        copy per version/state, and which of those you actually want in front of
        you while writing is a matter of habit, not of what the build produced:
        an author checking worked solutions wants <base>_A_solutions.pdf every
        time. This resolves that preference against what THIS build produced.

          "combined" / unset  <base>.pdf, the whole build (the default -- and
                              the only value that keeps forward sync, since
                              LaTeXTools' jumpto_pdf can only aim at <root>.pdf)
          "solutions"         the first solutions copy produced: _A_solutions
                              for \\versions{A,B,C}, _Solutions for a .spl key
                              build
          "student"           likewise the first student copy (_A, _Exam)
          anything else       a literal suffix -- "_B_solutions" resolves to
                              <base>_B_solutions.pdf

        Always falls back to <base>.pdf: a preference is a preference, and a
        student-mode build, a single-version document, or a build whose slicing
        was skipped for want of pypdf simply has no such copy to open.
        """
        tex_dir = self._tex_dir()
        combined = os.path.join(tex_dir, self.base_name + ".pdf")
        pref = (preference or "").strip()
        if not pref or pref.lower() in ("combined", "default", "main"):
            return combined

        # A variant name resolves to that variant's PDF directly. Checked before
        # the slice logic below because the two vocabularies overlap: "student"
        # is both a variant and a kind of exam slice, and the slice branch would
        # otherwise answer "the first produced PDF that isn't a solutions copy"
        # -- which, after a fan-out, can be the instructor variant.
        if pref.lower() in VARIANT_MACROS:
            candidate = os.path.join(
                tex_dir, self._variant_pdf_name(self.base_name, pref.lower(),
                                                False))
            if os.path.exists(candidate):
                return candidate

        def _is_solution(name):
            return name.lower().endswith(SOLUTION_COPY_SUFFIX)

        produced = getattr(self, "produced_pdfs", []) or []
        if pref.lower() == "solutions":
            pick = next((n for n in produced if _is_solution(n)), None)
        elif pref.lower() == "student":
            pick = next((n for n in produced if not _is_solution(n)), None)
        else:
            pick = self.base_name + pref + ".pdf"
        if pick:
            candidate = os.path.join(tex_dir, pick)
            if os.path.exists(candidate):
                return candidate
        return combined


class TexlibBuild(TexlibBuildCore):
    """Native host for the shared core: supplies the build contract via the
    constructor; the runner in texlib.py then drives commands()."""

    def __init__(self, tex_root, engine, options, display,
                 aux_directory="<<temp>>"):
        self.tex_root = tex_root
        self.tex_name = os.path.basename(tex_root)
        self.base_name = os.path.splitext(self.tex_name)[0]
        self.engine = engine
        self.options = list(options or [])
        self.display = display
        self.aux_directory = aux_directory
        self.out = ""
