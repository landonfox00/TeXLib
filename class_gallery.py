#!/usr/bin/env python3
"""class_gallery.py — a browsable page of what every TeXLib class produces.

WHAT THIS IS FOR

"What does a report card actually look like? What does `exam-days = F` do to a
schedule?" Answering that meant finding a template, remembering the TEXINPUTS
incantation, and building it. This renders every declared example once and puts
the pages on one page, grouped by class.

WHY IT CANNOT GO STALE

It renders from `examples/manifest.py` and the scenario corpus -- the same
declarations `smoke_test.py` builds in CI. There is no curated list of "things
worth showing" to fall out of date: if an example exists and is tested, it is in
here, and if it is deleted it disappears from both at once.

The prose is the documents' own leading `%` comment blocks. That is deliberate:
it means the gallery cannot describe an example differently from how the example
describes itself, and it makes "write a header comment saying what this
demonstrates" the price of appearing properly in the gallery.

RELATIONSHIP TO a11y_gallery.py

Sibling, not fork. Both drive `gallery_harness.py` for staging, building,
rasterising and HTML embedding. This one answers "what does it look like"; that
one answers "how does the tagged build differ from the normal one", with pixel
diffs, tag trees and veraPDF verdicts. Neither needs the other's machinery.

Usage:
    python class_gallery.py                 # every class
    python class_gallery.py Exams Schedule  # a subset, by class name
    python class_gallery.py --dpi 140       # sharper thumbnails (bigger file)
    python class_gallery.py -o out.html     # write somewhere else
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples"))

import smoke_test as S          # noqa: E402
import gallery_harness as H     # noqa: E402
import manifest as MF           # noqa: E402

DEFAULT_OUT = os.path.join(S.TEXLIB_ROOT, "class_gallery.html")
DEFAULT_DPI = 110


# ---------------------------------------------------------------------------
# Collecting what to render
# ---------------------------------------------------------------------------
def _home_module(tex_path: str) -> str | None:
    """The module directory supplying this document's class assets, resolved
    from its \\documentclass through smoke_test's CLASS_HOME_MODULE."""
    try:
        with open(tex_path, encoding="utf-8", errors="replace") as f:
            m = S.DOCCLASS_RE.search(f.read())
    except OSError:
        return None
    return S.CLASS_HOME_MODULE.get(m.group(1)) if m else None


def collect(classes: list[str] | None) -> list[H.Item]:
    """Every showcase example plus every scenario, as gallery Items.

    Both corpora are included because they answer different questions: a
    template shows what the class produces out of the box, a scenario shows one
    configuration doing one thing. Seeing them side by side under the same class
    heading is the whole point.
    """
    items: list[H.Item] = []

    for e in MF.showcase():
        src_dir = os.path.join(S.TEXLIB_ROOT, e.module.replace("/", os.sep))
        # Which module supplies the class assets is decided by the document's
        # OWN \documentclass, not by where the file sits -- exactly how
        # smoke_test does it. A course folder holds documents of several
        # different classes (schedule.tex, quiz-01.tex, syllabus.tex), so
        # deriving the module from the directory stages the wrong assets and the
        # build dies somewhere unrelated: schedule.tex without Schedule's .lua
        # engine fails at a brace, not at a missing file.
        module = _home_module(os.path.join(src_dir, e.template)) \
            or e.module.rsplit("/", 1)[-1]
        items.append(H.Item(
            src_dir=src_dir,
            template=e.template,
            module=module,
            slug=S.safe_name(e.module) + "__" + os.path.splitext(e.template)[0],
            label=e.module.rsplit("/", 1)[-1],
            kind=e.kind,
        ))

    for scen in S.discover_scenarios(None, include_full=True):
        module = MF.SCENARIO_AREA_MODULE.get(scen["area"])
        if not module:
            continue
        items.append(H.Item(
            src_dir=scen["dir"],
            template="template.tex",
            module=module,
            slug="scenario__" + S.safe_name(scen["slug"]),
            label=module,
            kind="scenario",
        ))

    if classes:
        wanted = {c.lower() for c in classes}
        items = [i for i in items if i.label.lower() in wanted]
    return items


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
CSS = """
:root{--bg:#fbfbfd;--fg:#1a1a1f;--mut:#5a5a6a;--line:#e4e4ec;--card:#fff;
--accent:#0b5fff;--ok:#0a7a4a;--bad:#c0392b;--shadow:0 1px 3px rgba(0,0,0,.07)}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#131317;--fg:#ececf2;--mut:#a0a0b0;--line:#2c2c36;--card:#1b1b21;
--accent:#7aa2ff;--ok:#5ddba4;--bad:#ff7b6b;--shadow:0 1px 3px rgba(0,0,0,.4)}}
:root[data-theme=dark]{--bg:#131317;--fg:#ececf2;--mut:#a0a0b0;--line:#2c2c36;
--card:#1b1b21;--accent:#7aa2ff;--ok:#5ddba4;--bad:#ff7b6b;
--shadow:0 1px 3px rgba(0,0,0,.4)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);
border-bottom:1px solid var(--line);padding:1rem 1.5rem}
h1{margin:0;font-size:1.3rem;letter-spacing:-.01em}
.meta{color:var(--mut);font-size:.85rem;margin-top:.15rem}
nav{margin-top:.6rem;display:flex;flex-wrap:wrap;gap:.4rem}
nav a{font-size:.8rem;text-decoration:none;color:var(--accent);
border:1px solid var(--line);border-radius:99px;padding:.15rem .6rem}
main{padding:1.5rem;max-width:110rem;margin:0 auto}
section{margin:0 0 2.5rem}
h2{font-size:1.05rem;margin:0 0 .2rem;letter-spacing:-.01em;
border-bottom:1px solid var(--line);padding-bottom:.4rem}
.count{color:var(--mut);font-weight:400;font-size:.85rem}
.grid{display:grid;gap:1rem;margin-top:1rem;
grid-template-columns:repeat(auto-fill,minmax(20rem,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
overflow:hidden;box-shadow:var(--shadow);display:flex;flex-direction:column}
.card h3{margin:0;padding:.7rem .9rem .2rem;font-size:.92rem;letter-spacing:-.01em}
.kind{display:inline-block;font-size:.65rem;text-transform:uppercase;
letter-spacing:.06em;font-weight:700;color:var(--mut);
border:1px solid var(--line);border-radius:99px;padding:.05rem .45rem;
margin-left:.35rem;vertical-align:middle}
.desc{padding:0 .9rem .7rem;color:var(--mut);font-size:.83rem}
.pages{display:flex;gap:.5rem;overflow-x:auto;padding:.6rem .9rem .9rem;
background:linear-gradient(0deg,rgba(128,128,150,.06),transparent)}
.pages img{height:15rem;width:auto;border:1px solid var(--line);border-radius:4px;
background:#fff;flex:0 0 auto}
.err{margin:.6rem .9rem .9rem;padding:.5rem .65rem;border-radius:6px;
background:rgba(192,57,43,.1);color:var(--bad);font-size:.8rem;
font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
white-space:pre-wrap;overflow-x:auto}
footer{color:var(--mut);font-size:.8rem;padding:1.5rem;border-top:1px solid var(--line)}
"""


def card_html(it: H.Item, title: str, desc: str, pages: list[str], err: str) -> str:
    head = html.escape(title or it.slug)
    body = [f'<div class=card><h3>{head}<span class=kind>{html.escape(it.kind)}</span></h3>']
    if desc:
        body.append(f'<div class=desc>{html.escape(desc)}</div>')
    if pages:
        imgs = "".join(
            f'<img loading=lazy alt="{head} page {n}" src="{u}">'
            for n, u in enumerate(pages, 1) if u)
        body.append(f'<div class=pages>{imgs}</div>')
    if err:
        body.append(f'<div class=err>{html.escape(err[:600])}</div>')
    body.append("</div>")
    return "".join(body)


def page_html(groups: dict, stats: dict) -> str:
    nav = "".join(
        f'<a href="#{S.safe_name(g)}">{html.escape(g)}</a>'
        for g in sorted(groups))
    secs = []
    for g in sorted(groups):
        cards = "".join(groups[g])
        secs.append(
            f'<section id="{S.safe_name(g)}"><h2>{html.escape(g)} '
            f'<span class=count>{len(groups[g])}</span></h2>'
            f'<div class=grid>{cards}</div></section>')
    warn = ""
    if not S.PDFTOPPM:
        warn = ("<div class=err>pdftoppm (poppler-utils) is not installed, so no "
                "pages could be rendered. Every card below is text only.</div>")
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<title>TeXLib class gallery</title>"
        f"<style>{CSS}</style></head><body>"
        "<header><h1>TeXLib class gallery</h1>"
        f'<div class=meta>{stats["ok"]}/{stats["total"]} documents rendered '
        f'&middot; {stats["elapsed"]:.0f}s &middot; generated from '
        f'examples/manifest.py and the scenario corpus</div>'
        f"<nav>{nav}</nav></header><main>{warn}{''.join(secs)}</main>"
        "<footer>Every document here is one CI builds. The descriptions are the "
        "documents&rsquo; own leading comment blocks &mdash; if a card reads "
        "poorly, the fix is in that file&rsquo;s header.</footer>"
        "</body></html>")


# ---------------------------------------------------------------------------
def render_one(it: H.Item, work: str, dpi: int, timeout: int):
    tex = os.path.join(it.src_dir, it.template)
    title, desc = H.describe(tex)
    if not title:
        title = f"{it.label} / {os.path.splitext(it.template)[0]}"
    pdf, err = H.build(it, work, "normal", timeout)
    pages = []
    if pdf:
        pages = [H.uri(p) for p in
                 H.render(pdf, os.path.dirname(pdf), it.slug, dpi)]
    return it, title, desc, pages, err


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the TeXLib class gallery.")
    ap.add_argument("classes", nargs="*", help="limit to these classes")
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("-o", "--out", default=DEFAULT_OUT)
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    items = collect(args.classes or None)
    if not items:
        print("No examples matched.", file=sys.stderr)
        return 1

    print(f"TeXLib class gallery\n  documents : {len(items)}\n"
          f"  dpi       : {args.dpi}\n  out       : {args.out}\n")

    started = time.time()
    groups: dict[str, list[str]] = {}
    ok = 0
    work = tempfile.mkdtemp(prefix="texlib_classgallery_")
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = [ex.submit(render_one, it, work, args.dpi, args.timeout)
                    for it in items]
            for fut in concurrent.futures.as_completed(futs):
                it, title, desc, pages, err = fut.result()
                if not err:
                    ok += 1
                status = "ok " if not err else "FAIL"
                print(f"  [{status}] {it.slug}" + (f"  ({err[:70]})" if err else ""))
                groups.setdefault(it.label, []).append(
                    card_html(it, title, desc, pages, err))

        stats = {"ok": ok, "total": len(items), "elapsed": time.time() - started}
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(page_html(groups, stats))
    finally:
        # The work tree holds a rasterised copy of every page; the HTML has them
        # embedded, so keeping it around would double the cost for nothing.
        import shutil
        shutil.rmtree(work, ignore_errors=True)

    size = os.path.getsize(args.out) / 1e6
    print(f"\n  {ok}/{len(items)} rendered in {time.time() - started:.0f}s"
          f"  ->  {args.out}  ({size:.1f} MB)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
