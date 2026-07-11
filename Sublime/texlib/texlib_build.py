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
#   * Cross-reference reruns -- re-runs the engine (up to MAX_RERUNS) while the
#     log still says "Rerun to get cross-references right."
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
#     (see _run_pdfpost / _external_python).
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
# commands(). Kept in sync with texlib_builder.py until that builder is retired
# (Phase 2).
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

# Document classes that must be compiled with lualatex.
# report-card uses \directlua (the gradebook engine), so it belongs here too.
LUALATEX_CLASSES = {"autoexam", "quiz", "schedule", "report-card"}

# Document classes whose gradebook.xlsx is auto-converted to a report-view CSV
# before the build (see _convert_gradebooks). The report-view tab name tried in
# order; falls back to the first sheet.
GRADEBOOK_CLASSES = {"report-card"}
GRADEBOOK_SHEETS = ("Report View", "Report Cards")

# Build mode  ->  the compile-time macro the TeXLib classes respond to.
# texlib-build.sty turns these \def's into the \ifsolutions / \ifkey / ...
# conditionals that every TeXLib class branches on.
MODE_MACROS = {
    "default":   "",
    "key":       r"\def\ShowKey{}",
    "solutions": r"\def\ShowSolutions{}",
    "student":   r"\def\StudentMode{}",
    "rubric":    r"\def\ShowRubric{}",
    "draft":     r"\def\ShowDraft{}",
}

# A pseudo-mode: a single engine pass with no biber and no rerun loop, for fast
# preview while writing. Cross-references / citations may be stale; a normal
# build settles them.
MODE_QUICK = "quick"

# How many times to re-run the engine chasing stable cross-references.
MAX_RERUNS = 3

# --- Publish step -----------------------------------------------------------
# A class that calls \TeXLibDeclarePublishable (syllabus, schedule) drops a
# <base>.pubmeta sidecar; _postprocess then clones the built PDF to shareable
# names (<course>.<section>_<term>.pdf + a generic <kind>.pdf) and, on Windows,
# a desktop shortcut. Enabled by default; toggle via builder_settings in
# LaTeXTools.sublime-settings or the env override (0/false/no/off = disabled).
PUBLISH_SETTING      = "publish_shareable_copies"
PUBLISH_ENV          = "TEXLIB_PUBLISH"
PUBLISH_CLIP_SETTING = "copy_published_path_to_clipboard"
PUBLISH_CLIP_ENV     = "TEXLIB_PUBLISH_CLIPBOARD"
# Desktop subfolder the shortcuts land in, so they don't pile up loose on the
# desktop as terms accumulate.
PUBLISH_SHORTCUT_DIR = "Course Materials"

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
    """

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
            self._version_sources = []
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

        if mode == MODE_QUICK:
            yield from self._count_passes(self._build_quick(base, engine))
        else:
            yield from self._count_passes(self._build_once(base, engine, mode))

        self._postprocess()

    def _count_passes(self, inner):
        """Pass-through generator that tallies engine passes and biber runs for
        the build summary, without altering the (command, message) stream it
        forwards. Wrapping every build sub-coroutine here keeps the tally in one
        place instead of threading a counter through each of them.
        """
        try:
            item = next(inner)
            while True:
                head = item[0][0] if item and item[0] else ""
                if head == "biber":
                    self._biber_count += 1
                elif head:
                    self._pass_count += 1
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

    def _build_bank_catalog(self, base, engine):
        """Build a problem-bank fragment directly: synthesize a minimal quiz.cls
        harness on the command line (the same \\def...\\input trick _build_once
        uses for mode injection) that \\loadbank's this file and calls
        \\printbankcatalog, so a bank can be perused without hand-authoring a
        companion root document. --jobname pins the output to
        <base>.pdf/.log/... like every other build, so _postprocess's copy-back
        (which globs by self.base_name) needs no changes. quiz.cls's "X of Y"
        footer needs the usual second pass, handled by the normal rerun loop.
        """
        arg = (
            r"\documentclass{quiz}\begin{document}"
            f"\\loadbank{{{self.tex_name}}}"
            r"\printbankcatalog\end{document}"
        )
        cmd = base + [f"--jobname={self.base_name}", arg]

        run = 1
        yield (cmd, f"{engine} [bank catalog] run {run}...")
        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"{engine} [bank catalog] rerun {run}...")

    def _build_quick(self, base, engine):
        """One engine pass, no biber, no rerun loop -- fast preview while writing.

        Cross-references and the bibliography may be stale (a ?? or an
        unresolved citation can show up); run a normal build to settle them
        before sharing. Builds in the default visual mode (no \\Show... flag).
        """
        cmd = base + [self.tex_name]
        yield (cmd, f"{engine} [quick] single pass (refs may be stale)...")

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
        that same routing; os.environ is inherited by the lualatex
        subprocess LaTeXTools spawns for the command we yield. Empty string
        (not None) when aux routing is disabled, so a stale value from a
        previous build in the same process can't leak into this one.
        """
        self._aux_target = self._resolve_aux_directory(tex_dir)
        os.environ["TEXLIB_AUX_DIR"] = self._aux_target or ""
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
            import subprocess

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
        """Apply the Hidden attribute on Windows via the Win32 API.

        Uses SetFileAttributesW directly rather than `os.system('attrib +h')`,
        which would be a shell-quoting hazard for paths with special characters
        and spawns a console window (ironic in a builder that works to suppress
        console flashes). No-op off Windows.
        """
        if os.name != "nt":
            return
        try:
            import ctypes

            FILE_ATTRIBUTE_HIDDEN = 0x2
            ctypes.windll.kernel32.SetFileAttributesW(
                str(path), FILE_ATTRIBUTE_HIDDEN
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

    def _needs_another_run(self):
        """Check for a standard cross-ref rerun OR a biblatex rerun signal."""
        out = self._last_output()
        return bool(RERUN_RE.search(out)) or bool(BIBER_RERUN_RE.search(out))

    def _last_output(self):
        """The most recent command's combined output, or '' if unavailable."""
        return getattr(self, "out", "") or ""

    # ------------------------------------------------------------------ #
    # Post-processing
    # ------------------------------------------------------------------ #
    def _postprocess(self):
        tex_dir = self._tex_dir()
        base_path = os.path.join(tex_dir, self.base_name)

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

        self._split_pdf_if_signaled(base_path)

        self._slice_versions_from_vmap(tex_dir, base_path)

        # Clone a published class's PDF (syllabus/schedule) to shareable names +
        # a desktop shortcut, driven by the <base>.pubmeta sidecar. Runs after
        # copy-back so the final <base>.pdf is already next to the source.
        self._publish_shareable_copies(tex_dir, base_path)

        self._finalize_synctex(tex_dir)

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

    def _copy_back_from_aux(self, tex_dir):
        """If aux routing is active, copy viewer-facing artifacts back.

        We copy <base>*.pdf, <base>*.synctex.gz, and <base>*.spl. The glob
        catches per-version outputs too (e.g. template_A.pdf for autoexam).
        Aux/log/etc. stay in the aux dir.
        """
        aux_target = getattr(self, "_aux_target", None)
        if not aux_target or aux_target == tex_dir or not os.path.isdir(aux_target):
            return
        patterns = (
            f"{self.base_name}*.pdf",
            f"{self.base_name}*.synctex.gz",
            f"{self.base_name}*.spl",
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

          * <course>.<section>_<term>.pdf   (or <publish-name>.pdf if that key is
            set), the section segment dropped when the course has none
          * <generic>.pdf                   (Syllabus.pdf / Tentative Schedule.pdf)

        and a "<course> <term> <noun>" shortcut in the desktop's Course Materials
        folder pointing at the coded copy. The sidecar is always consumed so it
        never litters; a no-op for every non-publishable build. Disabling publish
        (builder_settings / env) still consumes the sidecar but skips the copies.
        """
        meta = self._read_pubmeta(tex_dir)   # consumes the sidecar if present
        if meta is None:
            return                           # not a publishable build
        if not self._publish_enabled():
            return                           # feature off: copies/shortcut skipped
        pdf = base_path + ".pdf"
        if not os.path.exists(pdf):
            return
        course   = meta.get("course", "").strip()
        section  = meta.get("section", "").strip()
        term     = meta.get("term", "").strip()
        generic  = meta.get("generic", "").strip()
        noun     = meta.get("noun", "").strip()
        override = meta.get("publish-name", "").strip()
        # Sanity guard: never emit a "Math181__.pdf"-style name from a document
        # whose coursemeta is missing the identifying pieces. The PDF built fine;
        # only the shareable clones are skipped.
        if not course or not term:
            self.display(
                "TeXLib: publish skipped -- course/term unset in coursemeta "
                "(need course-subject + course-number and season + year, or an "
                "explicit term). The PDF built normally.\n"
            )
            return
        coded = override or self._coded_basename(course, section, term)
        if override:
            coded = self._sanitize_filename(coded)
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
    def _coded_basename(course, section, term):
        """Build "<Course>.<Section>_<Term>" with whitespace stripped from each
        token; the ".<Section>" segment is dropped when the course has no section.

          ("Math 181", "1001", "Fall 2026") -> "Math181.1001_Fall2026"
          ("Math 181", "",     "Fall 2026") -> "Math181_Fall2026"
        """
        c = re.sub(r"\s+", "", course)
        s = re.sub(r"\s+", "", section)
        t = re.sub(r"\s+", "", term)
        core = f"{c}.{s}" if s else c
        name = f"{core}_{t}" if t else core
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

    def _run_pdfpost(self, op, sidecar_path, pdf_path, out_dir):
        """Run a pypdf post-processing op (slice a .vmap, split a .spl).

        Runs in-process when pypdf is importable here (the CLI test harness /
        system Python), else via texlib_pdfpost.py under an external Python that
        has pypdf (Sublime's embedded one does not). Both paths call the SAME
        module functions, so there is one implementation. Returns
        (produced_names, messages); messages are user-facing. Never raises --
        every failure becomes a message the caller can display.
        """
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
                sidecar_path, pdf_path, out_dir, base_name
            )
            return result["produced"], result["messages"]
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
                py + [pdfpost, op, sidecar_path, pdf_path, out_dir, base_name],
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
        return result.get("produced", []), result.get("messages", [])


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
