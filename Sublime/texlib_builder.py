# texlib_builder.py
# ============================================================================
# TexlibBuilder -- a LaTeXTools custom builder for the TeXLib teaching library.
#
# Deploy: drop this file into Sublime Text's  Packages/User/  folder, then set
#   "builder": "texlib"
# in LaTeXTools.sublime-settings (the consolidated settings file in this folder
# already does that).
#
# What it adds over the stock `basic` builder:
#
#   * Engine selection -- honors the %!TeX program magic comment (LaTeXTools
#     resolves that into self.engine for us), and additionally falls back to
#     lualatex automatically for \documentclass{autoexam|quiz|schedule}, which
#     require it. A plain pdflatex document still builds with pdflatex.
#
#   * Build modes -- Default / Answer Key / Solutions / Student / Rubric /
#     Draft. Selected via the TeXLib.sublime-build *variants* (Ctrl+Shift+B,
#     or the "TeXLib: Build ..." entries in the command palette). Each variant
#     passes  --texlib-mode=<mode>  through LaTeXTools' documented `options`
#     channel; this builder pops that token out of self.options and injects the
#     matching TeXLib flag (\def\ShowKey{}, \def\StudentMode{}, ...). You never
#     edit the .tex to switch modes.
#
#   * autoexam versions -- the "All Versions" variant detects \versions{A,B,C}
#     (or \examversions{...}) in the root document and builds one separate PDF
#     per version: <base>_A.pdf, <base>_B.pdf, ... via \def\Version{X}.
#
#   * Cross-reference reruns -- re-runs the engine (up to MAX_RERUNS) while the
#     log still says "Rerun to get cross-references right."
#
#   * PDF splitting -- if the engine drops a <base>.spl signal file containing
#     "split_page=N", the resulting <base>.pdf is split into <base>_Exam.pdf
#     and <base>_Solutions.pdf (the autoexam key-build workflow).
#
#   * aux_directory routing -- honors LaTeXTools' aux_directory setting
#     (typically "<<temp>>"). On TeX Live there is no separate -aux-directory
#     flag, so the builder routes EVERYTHING via -output-directory and then,
#     in _postprocess, copies the PDF / .synctex.gz / .spl back next to the
#     source so PDF viewing and SyncTeX keep working. Aux files (.aux/.log/
#     .out/.toc/.bcf/.bbl/.fls/.fdb_latexmk) stay in the aux dir, keeping
#     the source dir clean and reducing OneDrive sync churn. biber runs are
#     redirected to the aux dir via --input-directory / --output-directory
#     so biblatex cross-references resolve correctly.
#
#   * Tidy -- on Windows, hides the <base>.synctex.gz build artifact.
#
# Requires a LaTeXTools with the PdfBuilder API. The import below tries the
# modern location (plugins/builder/) first, then the legacy one (builders/).
# ============================================================================

import glob
import hashlib
import os
import re
import shutil
import tempfile

# Note on the brief Windows console flash during builds: LaTeXTools' build
# path runs lualatex through `subprocess.Popen` (via its own external_command
# helper). On Windows this can briefly show a console window even with
# CREATE_NO_WINDOW + SW_HIDE passed to CreateProcess. We attempted to suppress
# it from this builder; the patch worked for ordinary subprocess.Popen calls
# but not for the build path, and bypassing LaTeXTools' spawn helper has more
# downside than the flash is worth. If you want to eliminate it, the cleanest
# route is a Windows shell-level wrapper that detaches lualatex (a tiny .cmd
# shim using `start "" /B`), pointed to via the LaTeXTools texpath setting.

try:
    # Modern LaTeXTools layout.
    from LaTeXTools.plugins.builder.pdf_builder import PdfBuilder
except ImportError:
    try:
        # Legacy LaTeXTools layout.
        from LaTeXTools.builders.pdfBuilder import PdfBuilder
    except ImportError as _exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "TexlibBuilder: could not import PdfBuilder from LaTeXTools. "
            "Tried both 'LaTeXTools.plugins.builder.pdf_builder' (modern) and "
            "'LaTeXTools.builders.pdfBuilder' (legacy). Is LaTeXTools installed "
            "and reasonably up to date?"
        ) from _exc


# --- Configuration ----------------------------------------------------------

# Document classes that must be compiled with lualatex.
LUALATEX_CLASSES = {"autoexam", "quiz", "schedule"}

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

# A pseudo-mode: build every \versions{...} entry as its own PDF.
MODE_ALLVERSIONS = "allversions"

# How many times to re-run the engine chasing stable cross-references.
MAX_RERUNS = 3

# Regexes over the root document / engine output.
DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{(\w[\w-]*)\}")
VERSIONS_RE = re.compile(r"\\(?:exam)?versions\s*\{([^}]+)\}")
RERUN_RE = re.compile(r"Rerun to get .* right\.")
# biblatex's "please run biber" message (varies slightly across versions).
BIBER_RERUN_RE = re.compile(r"Please \(?re\)?(?:run|rerun) Biber", re.IGNORECASE)
MODE_OPT_RE = re.compile(r"^--texlib-mode=(.+)$")


class TexlibBuilder(PdfBuilder):
    """Custom LaTeXTools builder for the TeXLib library. Builder name: 'texlib'.

    Class name uses a single leading capital (Texlib, not TeXLib) on purpose:
    LaTeXTools derives the builder name by stripping `Builder` and converting
    the remainder from PascalCase to snake_case, inserting an underscore at
    each lowercase->uppercase boundary. `TeXLibBuilder` would convert to
    `te_xlib`, not `texlib`, and the `"builder": "texlib"` setting would fail
    with "Cannot find builder texlib". `TexlibBuilder` -> `Texlib` (one word)
    -> `texlib`, which matches.
    """

    name = "TeXLib Builder"

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

        mode, engine_options = self._extract_mode(self.options or [])
        engine = self._select_engine(src)

        # Resolve LaTeXTools' aux_directory setting (typically <<temp>>) and
        # add -output-directory if needed. On TeX Live there's no separate
        # -aux-directory flag, so aux + PDF both land in this dir; _postprocess
        # then copies the PDF / .synctex.gz / .spl back next to the source so
        # the PDF viewer and SyncTeX both keep working.
        tex_dir = self._tex_dir()
        self._aux_target = self._resolve_aux_directory(tex_dir)
        base = [engine, "-interaction=nonstopmode", "-synctex=1"]
        if engine in ("lualatex", "xelatex"):
            base.append("-shell-escape")
        if self._aux_target and self._aux_target != tex_dir:
            base.append(f"-output-directory={self._aux_target}")
        base += engine_options

        if mode == MODE_ALLVERSIONS:
            versions = self._parse_versions(src)
            if not versions:
                self.display(
                    "TeXLib: 'All Versions' requested but no \\versions{...} "
                    "found in the root document -- building once instead.\n"
                )
                yield from self._build_once(base, engine, "default")
            else:
                self.display(
                    "TeXLib: building "
                    f"{len(versions)} version(s): {', '.join(versions)}\n"
                )
                for version in versions:
                    yield from self._build_version(base, engine, version)
        else:
            yield from self._build_once(base, engine, mode)

        self._postprocess()

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
        if mode not in MODE_MACROS and mode != MODE_ALLVERSIONS:
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

    @staticmethod
    def _parse_versions(src):
        match = VERSIONS_RE.search(src)
        if not match:
            return []
        return [v.strip() for v in match.group(1).split(",") if v.strip()]

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

        # biblatex: if the first pass produced a .bcf, run biber and force
        # one additional engine pass so the freshly written .bbl is read in.
        if self._biber_needed(self.base_name):
            yield (self._biber_command(self.base_name), "biber...")
            run += 1
            yield (cmd, f"{label} rerun {run} (post-biber)...")

        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"{label} rerun {run}...")

    def _build_version(self, base, engine, version, mode="default"):
        """One \\versions{} entry, built as <base>_<version>.pdf."""
        macro = MODE_MACROS.get(mode, "")
        jobname = f"{self.base_name}_{version}"
        arg = f"\\def\\Version{{{version}}}{macro}\\input{{{self.tex_name}}}"
        cmd = base + [f"--jobname={jobname}", arg]

        run = 1
        yield (cmd, f"version {version} run {run}...")

        # biblatex: same .bcf detection, scoped to the version's jobname.
        if self._biber_needed(jobname):
            yield (self._biber_command(jobname), f"biber [{version}]...")
            run += 1
            yield (cmd, f"version {version} rerun {run} (post-biber)...")

        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"version {version} rerun {run}...")

    def _tex_dir(self):
        """The directory containing the root .tex file."""
        return getattr(self, "tex_dir", None) or os.path.dirname(
            getattr(self, "tex_root", "") or ""
        )

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
        if os.path.isabs(s):
            return s
        return os.path.normpath(os.path.join(tex_dir, s))

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

        # If we built into a separate aux dir (via -output-directory), copy
        # the PDF, SyncTeX file, and any .spl signal back next to the source.
        # Aux files (.aux/.log/.out/.toc/.bcf/.bbl/.fls/.fdb_latexmk/...) stay
        # in the aux dir for cross-reference resolution across builds.
        self._copy_back_from_aux(tex_dir)

        self._split_pdf_if_signaled(base_path)

        # Hide the synctex artifact on Windows -- it is needed for sync but is
        # noise in the folder listing (and in OneDrive's change feed).
        if os.name == "nt":
            synctex = base_path + ".synctex.gz"
            if os.path.exists(synctex):
                try:
                    os.system(f'attrib +h "{synctex}"')
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
                try:
                    shutil.copy2(src, dst)
                except Exception as exc:  # noqa: BLE001 - best-effort copy
                    self.display(
                        f"TeXLib: could not copy {os.path.basename(src)} "
                        f"back to source: {exc}\n"
                    )

    def _split_pdf_if_signaled(self, base_path):
        """Honor a <base>.spl 'split_page=N' signal: split the PDF in two."""
        spl_file = base_path + ".spl"
        pdf_file = base_path + ".pdf"
        if not os.path.exists(spl_file) or not os.path.exists(pdf_file):
            return
        try:
            with open(spl_file, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
            if "split_page=" not in content:
                return
            split_page = int(content.split("=", 1)[1].strip())

            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(pdf_file)
            total = len(reader.pages)
            if not (0 < split_page < total):
                self.display(
                    f"TeXLib: .spl split_page={split_page} out of range "
                    f"(PDF has {total} pages); skipping split.\n"
                )
                return

            exam = PdfWriter()
            for i in range(split_page):
                exam.add_page(reader.pages[i])
            with open(base_path + "_Exam.pdf", "wb") as fh:
                exam.write(fh)

            solutions = PdfWriter()
            for i in range(split_page, total):
                solutions.add_page(reader.pages[i])
            with open(base_path + "_Solutions.pdf", "wb") as fh:
                solutions.write(fh)

            os.remove(spl_file)
            self.display(
                "TeXLib: split into "
                f"{os.path.basename(base_path)}_Exam.pdf / _Solutions.pdf.\n"
            )
        except ImportError:
            self.display(
                "TeXLib: pypdf not installed -- skipping the .spl PDF split. "
                "Install it with: pip install pypdf\n"
            )
        except Exception as exc:
            self.display(f"TeXLib: PDF split failed: {exc}\n")
