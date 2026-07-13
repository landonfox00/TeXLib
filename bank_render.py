"""bank_render.py -- render one bank problem to SVG with the real engine.

The faithful, full-fidelity preview (TikZ and all): compile a tiny quiz-class
harness that ``\\loadbank``s the real bank and emits the single problem in a
starred ``\\begin{problems}*`` / ``\\begin{mcproblems}*`` section (star = no
"Part N" heading), with ``\\def\\ShowSolutions{}`` so the worked solution shows.

Mirrors the build tooling's engine invocation (Sublime/texlib/texlib_build.py):
lualatex through the comma-free ``C:\\_texlibjunc`` junction
(``TEXINPUTS=.;C:/_texlibjunc//;``) with aux routed to ``%TEMP%``, cwd = the
bank's own directory so ``\\loadbank`` resolves.  The PDF is tight-cropped
(pdfcrop) and converted to SVG (dvisvgm, else pdftocairo).  Results are cached
by (id, bank mtime, solution flag); a background pre-warm renders the whole bank.

Every external tool is probed with shutil.which and absence raises
RenderUnavailable so the server can degrade to the source view.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

JUNCTION = r"C:\_texlibjunc"
TEXINPUTS_JUNCTION = ".;C:/_texlibjunc//;"
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_CACHE_ROOT = os.path.join(tempfile.gettempdir(), "texlib-bankstudio")
_RERUN_RE = re.compile(r"Rerun to get .* right\.|Label\(s\) may have changed")

_lock = threading.Lock()      # serialize compiles (one engine at a time)


class RenderUnavailable(Exception):
    """The TeX toolchain needed for rendering is missing."""


class RenderError(Exception):
    """The problem failed to compile; message carries a log tail."""


def _which(name):
    return shutil.which(name)


def available():
    """True if at least lualatex + one PDF->SVG converter are present."""
    return bool(_which("lualatex") and (_which("dvisvgm") or _which("pdftocairo")))


def _texinputs(bank_dir):
    """The junction TEXINPUTS when the junction exists, else a relative
    fallback that reaches the repo root without crossing the comma path."""
    if os.path.isdir(JUNCTION):
        return TEXINPUTS_JUNCTION
    # Fallback: bank dir + walk up to a repo root (holds the .cls/.sty), plus
    # the default trees.  Relative '..//' avoids the comma-bearing absolute path.
    return os.pathsep.join([".", "..//", "../..//", "../../..//", ""])


def _cache_dir(bank_file):
    key = hashlib.md5(os.path.abspath(bank_file).encode("utf-8")).hexdigest()[:12]
    d = os.path.join(_CACHE_ROOT, key)
    os.makedirs(d, exist_ok=True)
    return d


def _cache_path(bank_file, pid, show_solution):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", pid)
    mtime = int(os.path.getmtime(bank_file))
    tag = "sol" if show_solution else "nosol"
    return os.path.join(_cache_dir(bank_file), f"{safe}.{mtime}.{tag}.svg")


def _harness(bank_name, pid, is_mc):
    # Crop to the content at the TeX level with preview/tightpage -- avoids
    # pdfcrop (Perl + a Windows-blocked hard-link) and dvisvgm's PDF path (needs
    # an older Ghostscript than is installed).  lualatex emits an already-tight
    # PDF; pdftocairo then converts it.  The starred env drops the "Part N"
    # heading; ShowSolutions (injected on the command line) shows the solution.
    env = "mcproblems" if is_mc else "problems"
    return (
        "\\documentclass{quiz}\n"
        "\\usepackage[active,tightpage]{preview}\n"
        "\\setlength\\PreviewBorder{10pt}\n"
        # Let TeX absorb tight lines by stretching interword glue rather than
        # overflowing past \linewidth (tightpage crops to the declared width, so
        # an overfull hbox would be clipped on the right).
        "\\setlength\\emergencystretch{3em}\\hbadness=10000\n"
        "\\loadbank{" + bank_name + "}\n"
        "\\begin{document}\n"
        "\\begin{preview}\n"
        "\\begin{" + env + "}*\n"
        "\\problem{" + pid + "}\n"
        "\\end{" + env + "}\n"
        "\\end{preview}\n"
        "\\end{document}\n"
    )


def _run(cmd, cwd, env=None):
    return subprocess.run(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=_NO_WINDOW, timeout=120,
    )


def render_svg(problem, show_solution=True, use_cache=True):
    """Render `problem` (a bank_parser.Problem) to an SVG string.

    Raises RenderUnavailable if tools are missing, RenderError on a compile
    failure.
    """
    if not available():
        raise RenderUnavailable("need lualatex + dvisvgm/pdftocairo on PATH")

    bank_file = problem.source_file
    if not os.path.isfile(bank_file):
        raise RenderError(f"bank file not found: {bank_file}")

    cache = _cache_path(bank_file, problem.id, show_solution)
    if use_cache and os.path.isfile(cache) and os.path.getsize(cache) > 0:
        with open(cache, "r", encoding="utf-8") as fh:
            return fh.read()

    bank_dir = os.path.dirname(os.path.abspath(bank_file))
    bank_name = os.path.basename(bank_file)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", problem.id)
    harness_name = f"_bankstudio_{safe}.tex"
    harness_path = os.path.join(bank_dir, harness_name)
    base = os.path.splitext(harness_name)[0]

    aux = os.path.join(_CACHE_ROOT, "aux",
                       hashlib.md5(harness_path.encode()).hexdigest()[:12])
    os.makedirs(aux, exist_ok=True)

    env = dict(os.environ)
    env["TEXINPUTS"] = _texinputs(bank_dir)
    env["TEXLIB_AUX_DIR"] = aux

    with _lock:
        try:
            with open(harness_path, "w", encoding="utf-8") as fh:
                fh.write(_harness(bank_name, problem.id, problem.is_mc))

            sol = "\\def\\ShowSolutions{}" if show_solution else ""
            cmd = [
                "lualatex", "-interaction=nonstopmode", "-halt-on-error",
                "-shell-escape", f"-output-directory={aux}",
                f"{sol}\\input{{{harness_name}}}",
            ]
            proc = _run(cmd, bank_dir, env)
            pdf = os.path.join(aux, base + ".pdf")
            if proc.returncode != 0 or not os.path.isfile(pdf):
                raise RenderError(_log_tail(aux, base, proc.stdout))
            svg = _pdf_to_svg(pdf, aux, base)
        finally:
            _quiet_remove(harness_path)
            _quiet_remove(os.path.join(bank_dir, base + ".synctex.gz"))

    if use_cache:
        with open(cache, "w", encoding="utf-8") as fh:
            fh.write(svg)
    return svg


def _pdf_to_svg(pdf, aux, base):
    # pdftocairo first (works with the installed poppler); dvisvgm only as a
    # fallback -- its PDF path needs Ghostscript < 10.01 or mutool, absent here.
    out = os.path.join(aux, base + ".svg")
    if _which("pdftocairo"):
        proc = _run(["pdftocairo", "-svg", "-f", "1", "-l", "1", pdf, out], aux)
        if proc.returncode == 0 and os.path.isfile(out):
            return _read(out)
    if _which("dvisvgm"):
        proc = _run(["dvisvgm", "--pdf", "--page=1", "--no-fonts",
                     "--output=" + out, pdf], aux)
        if proc.returncode == 0 and os.path.isfile(out):
            return _read(out)
    raise RenderError("PDF->SVG conversion failed (need pdftocairo or dvisvgm)")


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _log_tail(aux, base, stdout, n=25):
    log = os.path.join(aux, base + ".log")
    text = _read(log) if os.path.isfile(log) else (
        stdout.decode("utf-8", "replace") if stdout else "")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "compile failed:\n" + "\n".join(lines[-n:])


def _quiet_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def prewarm(problems, show_solution=True, on_done=None):
    """Render every problem in a background thread, populating the cache so the
    UI is instant after warm-up.  Silent on per-problem failure."""
    def worker():
        for p in problems:
            try:
                render_svg(p, show_solution=show_solution)
            except (RenderUnavailable, RenderError, OSError):
                pass
            if on_done:
                on_done(p.id)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # Render one problem to a PNG for eyeballing:
    #   python bank_render.py <exam-or-bank.tex> <problem-id> [out.png]
    import bank_parser
    if len(sys.argv) < 3:
        sys.exit("usage: python bank_render.py <tex> <id> [out.png]")
    _, probs = bank_parser.discover(sys.argv[1])
    target = next((p for p in probs if p.id == sys.argv[2]), None)
    if not target:
        sys.exit(f"no problem with id {sys.argv[2]!r}")
    svg = render_svg(target)
    out = sys.argv[3] if len(sys.argv) > 3 else "render.svg"
    with open(out if out.endswith(".svg") else "render.svg", "w",
              encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote SVG ({len(svg)} bytes)")
