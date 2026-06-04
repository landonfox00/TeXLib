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
#     Draft / Quick. Selected via the TeXLib.sublime-build *variants* (Ctrl+Shift+B,
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
#   * biber change-detection -- biber (and its forced re-pass) only runs when
#     the .bcf changed since the .bbl was last built. Editing prose in a
#     biblatex document no longer pays for a biber run plus an extra pass.
#     The "Quick" mode goes further: a single pass, no biber, no reruns.
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
import gzip
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

# A pseudo-mode: a single engine pass with no biber and no rerun loop, for fast
# preview while writing. Cross-references / citations may be stale; a normal
# build settles them.
MODE_QUICK = "quick"

# How many times to re-run the engine chasing stable cross-references.
MAX_RERUNS = 3

# Regexes over the root document / engine output.
DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{(\w[\w-]*)\}")
VERSIONS_RE = re.compile(r"\\(?:exam)?versions\s*\{([^}]+)\}")
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
        elif mode == MODE_QUICK:
            yield from self._build_quick(base, engine)
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
        if mode not in MODE_MACROS and mode not in (MODE_ALLVERSIONS, MODE_QUICK):
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

        # biblatex: run biber only when the bibliography actually changed since
        # the .bbl was last built. The .bbl persists in the aux dir, so an edit
        # that doesn't touch citations skips both biber and its forced re-pass.
        if self._biber_needed(self.base_name) and not self._biber_is_current(
            self.base_name
        ):
            yield (self._biber_command(self.base_name), "biber...")
            self._record_biber_hash(self.base_name)
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

        # biblatex: same change-detection, scoped to the version's jobname, so
        # a rebuilt version reuses its .bbl when its bibliography is unchanged.
        if self._biber_needed(jobname) and not self._biber_is_current(jobname):
            yield (self._biber_command(jobname), f"biber [{version}]...")
            self._record_biber_hash(jobname)
            run += 1
            yield (cmd, f"version {version} rerun {run} (post-biber)...")

        while run < MAX_RERUNS and self._needs_another_run():
            run += 1
            yield (cmd, f"version {version} rerun {run}...")

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

        Called right after biber runs (biber reads the .bcf + .bib files and
        writes the .bbl but alters none of them), so this records the exact
        inputs the new .bbl corresponds to.
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

        self._finalize_synctex(tex_dir)

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
            if os.name == "nt":
                try:
                    os.system(f'attrib +h "{plain}"')
                except Exception:
                    pass

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

        # 1) Rewrite each grid-file Input record to point at the user source.
        def _rewrite_input(match):
            fid = int(match.group(1))
            if fid in grid_ids:
                return "Input:%d:%s" % (fid, src_path)
            return match.group(0)
        content = re.sub(r"^Input:(\d+):.+$", _rewrite_input,
                         content, flags=re.MULTILINE)

        # 2) Remap line numbers in typeset records.
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

        msg = (
            "TeXLib: rewrote %d schedule SyncTeX records "
            "(%d cell(s) mapped to user source"
            % (rewrites, len(line_map))
        )
        if boilerplate_rewrites:
            msg += "; %d boilerplate record(s) redirected to line %d" % (
                boilerplate_rewrites, boilerplate_target_line
            )
        msg += ").\n"
        self.display(msg)

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
