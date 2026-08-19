#!/usr/bin/env python3
"""gallery_harness.py — the staging/build/render machinery both galleries share.

WHY THIS EXISTS

`a11y_gallery.py` grew the ability to take an example, stage it with the right
class assets, build it, rasterise the pages and embed them in a self-contained
HTML page. `class_gallery.py` needs exactly that and nothing else — it does not
diff pixels, read tag trees or run veraPDF.

Copying those ~150 lines would have left two generators that both know how to
stage a build, and they would diverge the first time staging changed. Extracted
instead, so there is one answer to "how is an example built for a gallery".

WHAT IS *NOT* HERE

The accessibility-specific half stays in `a11y_gallery.py`: the normal-vs-tagged
pixel diff, the MCID/tag-tree extraction, the veraPDF verdicts. Those are that
gallery's whole reason to exist and belong to it.

ITEMS

A gallery item is deliberately looser than a scenario: `class_gallery` renders
BOTH the scenario packs (`examples/scenarios/<area>/<name>/template.tex`) and the
module templates (`examples/templates/<Module>/<class>-template.tex`), which do
not share a directory shape or a filename. An Item carries the three things
staging actually needs — where the source lives, which file is the root, and
which module supplies the class assets — so either corpus maps onto it.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess

import smoke_test as S

# Cap pages per document. A gallery is a browsing aid: a 40-page course schedule
# contributes nothing after the first few, and every page is embedded as base64
# in a single HTML file that has to stay openable.
MAX_PAGES = 6


class Item:
    """One document a gallery renders.

    src_dir   directory holding the root file (staged first, wins name clashes)
    template  the root filename within src_dir
    module    module directory supplying the class + its .lua/library defaults
    slug      filesystem-safe id, unique across the gallery
    label     short human name for the card
    kind      free-form grouping tag ("template", "scenario", ...)
    """

    __slots__ = ("src_dir", "template", "module", "slug", "label", "kind")

    def __init__(self, src_dir, template, module, slug, label, kind):
        self.src_dir = src_dir
        self.template = template
        self.module = module
        self.slug = slug
        self.label = label
        self.kind = kind


def stage(src_dir: str, module: str, dest: str) -> bool:
    """Copy the document's own files, then the module's class assets, then the
    shared root files, into `dest`. Source files win name clashes so an example
    can override a library default.

    Order matters and is the same order smoke_test.build_one uses -- staging an
    example differently from the way CI builds it would make the gallery a
    picture of something nobody ships.
    """
    module_dir = os.path.join(S.TEXLIB_ROOT, module)
    if not os.path.isdir(src_dir) or not os.path.isdir(module_dir):
        return False
    for entry in os.listdir(src_dir):
        src = os.path.join(src_dir, entry)
        if os.path.isfile(src):
            shutil.copy2(src, dest)
    for entry in os.listdir(module_dir):
        src = os.path.join(module_dir, entry)
        if os.path.isfile(src) and not os.path.exists(os.path.join(dest, entry)):
            shutil.copy2(src, dest)
    S._copy_shared_into(dest)
    return True


def build(item: Item, work: str, mode: str, timeout: int):
    """Build one item in its own directory. `mode` is one of:

        "normal"     the class's own engine, no tagging -- what actually ships
        "accessible" lualatex + the \\DocumentMetadata tagging prefix
        "lua"        lualatex, NO tagging: a same-engine baseline that separates
                     accessibility-induced changes from pdflatex->lualatex drift

    Returns (pdf_path | None, err).
    """
    dest = os.path.join(work, S.safe_name(item.slug), mode)
    os.makedirs(dest, exist_ok=True)
    if not stage(item.src_dir, item.module, dest):
        return None, f"could not stage '{item.slug}' (module '{item.module}')"

    accessible = (mode == "accessible")
    engine = "lualatex" if mode in ("accessible", "lua") else S.detect_engine(
        os.path.join(dest, item.template))

    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    env["TEXINPUTS"] = f".{sep}{S.TEXLIB_ROOT}//{sep}{env.get('TEXINPUTS', '')}"

    # The engine's jobname must match the root file's base name: the autoexam
    # bank engine re-reads the document body from <jobname>.tex, so renaming the
    # job makes it look for a file that does not exist.
    jobname = os.path.splitext(item.template)[0]
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error"]
    if engine == "lualatex":
        cmd.append("-shell-escape")
    if accessible:
        cmd.append(f"--jobname={jobname}")
        cmd.append(f"{S.ACCESSIBLE_MACRO}\\input{{{item.template}}}")
    else:
        cmd.append(item.template)

    pdf = os.path.join(dest, jobname + ".pdf")
    try:
        rc, log_text, stdout_text, _elapsed, _passes = S._run_with_reruns(
            cmd, dest, env, timeout, jobname)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    if rc != 0 or not os.path.exists(pdf):
        return None, S.extract_tex_errors(log_text or stdout_text) or f"exit={rc}, no pdf"
    return pdf, ""


def render(pdf: str, work: str, prefix: str, dpi: int) -> list[str]:
    """Rasterise up to MAX_PAGES pages to PNGs on disk; return sorted paths.

    -png specifically: it is universally compiled into pdftoppm, where some
    Windows poppler builds omit JPEG support.
    """
    if not S.PDFTOPPM or not pdf:
        return []
    outbase = os.path.join(work, prefix)
    try:
        subprocess.run(
            [S.PDFTOPPM, "-png", "-r", str(dpi), "-l", str(MAX_PAGES), pdf, outbase],
            check=True, capture_output=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []
    return [os.path.join(work, name) for name in sorted(os.listdir(work))
            if name.startswith(prefix + "-") and name.lower().endswith(".png")]


def uri(path: str) -> str:
    """base64 data URI for a PNG ('' if unreadable). Galleries are single files
    that must survive being copied anywhere, so images are embedded, not linked."""
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


def wh(path: str) -> tuple[int, int] | None:
    """(width, height) of an image via ImageMagick, or None if unavailable."""
    if not S.MAGICK:
        return None
    try:
        r = subprocess.run([S.MAGICK, "identify", "-format", "%w %h", path],
                           capture_output=True, text=True, timeout=30)
        w, h = r.stdout.split()[:2]
        return int(w), int(h)
    except Exception:  # noqa: BLE001 - a bad image must not kill the gallery
        return None


def describe(tex_path: str) -> tuple[str, str]:
    """(title, description) from a document's leading `%` comment block.

    This is why every example in the corpus opens with a comment saying what it
    demonstrates and why: that block is the gallery's prose. A document with no
    header comment renders as an untitled thumbnail, which is the incentive to
    write one.

    A leading "Scenario: <area> / <name>" line becomes the title; the rest is
    joined into the description.
    """
    lines = []
    try:
        with open(tex_path, encoding="utf-8") as f:
            for ln in f:
                s = ln.rstrip("\n")
                if s.startswith("%"):
                    lines.append(s.lstrip("%").strip())
                elif s.strip() == "":
                    if lines:
                        break
                else:
                    break
    except OSError:
        return "", ""
    # Drop rule lines ("=====", "-----") used as visual dividers in headers.
    lines = [l for l in lines if l.strip("=-# ")]
    title = ""
    if lines and lines[0].lower().startswith("scenario:"):
        title = lines.pop(0).split(":", 1)[1].strip()
    return title, " ".join(l for l in lines if l)
