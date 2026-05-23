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
#   * Tidy -- on Windows, hides the <base>.synctex.gz build artifact.
#
# Requires a LaTeXTools with the PdfBuilder API. The import below tries the
# modern location (plugins/builder/) first, then the legacy one (builders/).
# ============================================================================

import os
import re

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

        base = [engine, "-interaction=nonstopmode", "-synctex=1"]
        if engine in ("lualatex", "xelatex"):
            base.append("-shell-escape")
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
            yield (["biber", self.base_name], "biber...")
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
            yield (["biber", jobname], f"biber [{version}]...")
            run += 1
            yield (cmd, f"version {version} rerun {run} (post-biber)...")

        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"version {version} rerun {run}...")

    def _biber_needed(self, jobname):
        """True if biblatex wrote a .bcf for `jobname` next to the root doc."""
        tex_dir = getattr(self, "tex_dir", None) or os.path.dirname(
            getattr(self, "tex_root", "") or ""
        )
        return os.path.exists(os.path.join(tex_dir, jobname + ".bcf"))

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
        tex_dir = getattr(self, "tex_dir", None) or os.path.dirname(
            getattr(self, "tex_root", "") or ""
        )
        base_path = os.path.join(tex_dir, self.base_name)

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
