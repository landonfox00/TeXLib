#!/usr/bin/env python3
"""
a11y_gallery.py — a navigable normal-vs-accessible feature gallery for TeXLib.

Builds every self-contained feature scenario under tests/scenarios/ in BOTH the
normal and the accessible (tagged PDF/UA) build modes, renders each to page
images, validates the accessible copy with veraPDF, and extracts its PDF tag
tree. It then assembles one self-contained, searchable HTML page — a11y_gallery.html
— with a section per feature showing three panels side by side:

    normal render   |   accessible render   |   accessible tag tree + veraPDF badge

Point a browser at the file, Ctrl-F (or the search box) for a feature, and see
how the two builds differ — both visually (the deliberate accessible fallbacks:
multicol->single column, tcolorbox theorems->plain amsthm, ...) and structurally
(the tag tree, which is where accessibility actually lives and is otherwise
invisible in a plain render).

This is a DEV/QA aid, a sibling of `smoke_test.py --scenarios --accessible`; it
reuses that harness's scenario discovery, staging, accessible build recipe, and
veraPDF check. It needs lualatex + poppler's pdftoppm; veraPDF and pdfminer are
optional (their panels degrade to a note when absent). The catalog is exactly
the committed scenario set, so it grows as scenarios are added.

Usage:
    python a11y_gallery.py                 # all scenarios -> a11y_gallery.html
    python a11y_gallery.py schedule exam   # only these scenario areas
    python a11y_gallery.py --full          # include tier=full scenarios too
    python a11y_gallery.py --dpi 130       # render at a higher resolution
    python a11y_gallery.py -o out.html     # write somewhere else
"""

from __future__ import annotations

import argparse
import base64
import html
import os
import shutil
import subprocess
import tempfile
import time

import smoke_test as S

DEFAULT_OUT = os.path.join(S.TEXLIB_ROOT, "a11y_gallery.html")
DEFAULT_DPI = 100
MAX_PAGES = 8            # cap page renders per build (a long month-pages schedule)
MAX_TREE_NODES = 240     # cap tag-tree nodes rendered per feature
COLLAPSE_RUN = 3         # collapse runs of >COLLAPSE_RUN same-role siblings

# Human labels for the scenario "area" keys (tests/scenarios/<area>/...).
AREA_LABEL = {
    "exam": "Exams", "quiz": "Quizzes", "notes": "Notes",
    "report-cards": "Report Cards", "schedule": "Schedule", "syllabi": "Syllabi",
}


# ---------------------------------------------------------------------------
# Build (both modes) — mirrors smoke_test.build_scenario staging, but keeps the
# PDFs and builds the accessible variant too.
# ---------------------------------------------------------------------------
def _stage(scen: dict, dest: str) -> str | None:
    """Stage a scenario's files + its module's .cls/.lua + shared root files into
    dest (scenario files win name clashes). Returns the module, or None."""
    module = S.SCENARIO_AREA_MODULE.get(scen["area"])
    if not module:
        return None
    sdir = scen["dir"]
    module_dir = os.path.join(S.TEXLIB_ROOT, module)
    for entry in os.listdir(sdir):
        src = os.path.join(sdir, entry)
        if os.path.isfile(src):
            shutil.copy2(src, dest)
    for entry in os.listdir(module_dir):
        src = os.path.join(module_dir, entry)
        if os.path.isfile(src) and not os.path.exists(os.path.join(dest, entry)):
            shutil.copy2(src, dest)
    S._copy_shared_into(dest)
    return module


def _build(scen: dict, work: str, accessible: bool, timeout: int):
    """Build one scenario in its own dir. Returns (pdf_path|None, err_str)."""
    tag = "accessible" if accessible else "normal"
    dest = os.path.join(work, S.safe_name(scen["slug"]), tag)
    os.makedirs(dest, exist_ok=True)
    if _stage(scen, dest) is None:
        return None, f"no module mapping for area '{scen['area']}'"

    template = "template.tex"
    engine = "lualatex" if accessible else S.detect_engine(os.path.join(dest, template))
    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    env["TEXINPUTS"] = f".{sep}{S.TEXLIB_ROOT}//{sep}{env.get('TEXINPUTS', '')}"

    jobname = "template"
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error"]
    if engine == "lualatex":
        cmd.append("-shell-escape")
    if accessible:
        cmd.append(f"--jobname={jobname}")
        cmd.append(f"{S.ACCESSIBLE_MACRO}\\input{{{template}}}")
    else:
        cmd.append(template)

    pdf = os.path.join(dest, jobname + ".pdf")
    try:
        rc, log_text, stdout_text, _elapsed, _passes = S._run_with_reruns(
            cmd, dest, env, timeout, jobname)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    if rc != 0 or not os.path.exists(pdf):
        return None, S.extract_tex_errors(log_text or stdout_text) or f"exit={rc}, no pdf"
    return pdf, ""


# ---------------------------------------------------------------------------
# Render pages -> data URIs
# ---------------------------------------------------------------------------
def _render(pdf: str, work: str, prefix: str, dpi: int) -> list[str]:
    """Render pdf pages to PNGs; return a list of base64 data-URI strings.
    Uses -png (universally compiled into pdftoppm; some Windows poppler builds
    omit JPEG support)."""
    if not S.PDFTOPPM or not pdf:
        return []
    outbase = os.path.join(work, prefix)
    try:
        subprocess.run(
            [S.PDFTOPPM, "-png", "-r", str(dpi), "-l", str(MAX_PAGES), pdf, outbase],
            check=True, capture_output=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []
    uris = []
    for name in sorted(os.listdir(work)):
        if name.startswith(prefix + "-") and name.lower().endswith(".png"):
            with open(os.path.join(work, name), "rb") as f:
                uris.append("data:image/png;base64," + base64.b64encode(f.read()).decode())
    return uris


# ---------------------------------------------------------------------------
# Tag tree (accessible PDF) -> collapsed HTML
# ---------------------------------------------------------------------------
def _mcid_text_map(pdf: str) -> dict:
    """Best-effort {(page_index, mcid): text} via pdfminer. Empty on any failure."""
    try:
        import io
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
        from pdfminer.converter import PDFConverter
    except Exception:
        return {}

    out: dict = {}

    class C(PDFConverter):
        def __init__(self, rm):
            super().__init__(rm, io.StringIO())
            self.stack = []
            self.page = 0

        def begin_tag(self, tag, props=None):
            self.stack.append(props.get("MCID") if props and "MCID" in props else None)

        def end_tag(self):
            if self.stack:
                self.stack.pop()

        def render_string(self, ts, seq, ncs, gs):
            mcid = next((m for m in reversed(self.stack) if m is not None), None)
            if mcid is None:
                return
            font, buf = ts.font, ""
            for obj in seq:
                if isinstance(obj, bytes):
                    for cid in font.decode(obj):
                        try:
                            buf += font.to_unichr(cid)
                        except Exception:
                            buf += " "
            key = (self.page, mcid)
            out[key] = out.get(key, "") + buf

    try:
        rm = PDFResourceManager()
        dev = C(rm)
        interp = PDFPageInterpreter(rm, dev)
        with open(pdf, "rb") as f:
            doc = PDFDocument(PDFParser(f))
            for i, pg in enumerate(PDFPage.create_pages(doc)):
                dev.page = i
                interp.process_page(pg)
    except Exception:
        return {}
    return out


def _tag_tree_html(pdf: str) -> str:
    """Walk StructTreeRoot -> a collapsed, indented HTML tree of roles + snippets."""
    try:
        from pypdf import PdfReader
    except Exception:
        return '<p class="muted">pypdf not installed — tag tree unavailable.</p>'
    try:
        r = PdfReader(pdf)
        st = r.trailer["/Root"]["/StructTreeRoot"]
    except Exception:
        return '<p class="muted">No StructTreeRoot (document is not tagged).</p>'

    # page ref idnum -> index, for resolving MCID leaves to a page
    page_index = {}
    for i, pg in enumerate(r.pages):
        ref = getattr(pg, "indirect_reference", None)
        if ref is not None:
            page_index[ref.idnum] = i
    mcid_text = _mcid_text_map(pdf)

    budget = [MAX_TREE_NODES]
    esc = html.escape

    def snippet(txt: str) -> str:
        txt = " ".join((txt or "").split())
        return (txt[:60] + "…") if len(txt) > 60 else txt

    def render(node, page_hint) -> str:
        if budget[0] <= 0:
            return ""
        budget[0] -= 1
        o = node.get_object()
        role = (o.get("/S") or "?")
        role = role[1:] if isinstance(role, str) and role.startswith("/") else str(role)
        pg = o.get("/Pg")
        if pg is not None and getattr(pg, "idnum", None) in page_index:
            page_hint = page_index[pg.idnum]
        extra = ""
        for key in ("/ActualText", "/Alt"):
            if o.get(key):
                extra = ' <span class="snip">“' + esc(snippet(str(o.get(key)))) + '”</span>'
                break

        K = o.get("/K")
        kids = K if isinstance(K, list) else ([K] if K is not None else [])
        child_html, leaf_text = [], ""
        struct_kids = []
        for k in kids:
            ko = k.get_object() if hasattr(k, "get_object") else k
            if isinstance(ko, dict) and ("/S" in ko or "/K" in ko):
                struct_kids.append(k)
            else:
                mcid = ko.get("/MCID") if isinstance(ko, dict) else (ko if isinstance(ko, int) else None)
                if mcid is not None and (page_hint, mcid) in mcid_text:
                    leaf_text += mcid_text[(page_hint, mcid)]

        # collapse runs of same-role struct children
        i = 0
        while i < len(struct_kids) and budget[0] > 0:
            role_i = (struct_kids[i].get_object().get("/S") or "?")
            j = i
            while (j < len(struct_kids)
                   and (struct_kids[j].get_object().get("/S") or "?") == role_i):
                j += 1
            run = struct_kids[i:j]
            child_html.append(render(run[0], page_hint))
            if len(run) > COLLAPSE_RUN + 1:
                rn = role_i[1:] if isinstance(role_i, str) and role_i.startswith("/") else str(role_i)
                child_html.append(
                    f'<li class="more">＋ {len(run) - 1} more <code>{esc(rn)}</code></li>')
                budget[0] -= 1
            else:
                for n in run[1:]:
                    child_html.append(render(n, page_hint))
            i = j

        if leaf_text.strip() and not extra:
            extra = ' <span class="snip">“' + esc(snippet(leaf_text)) + '”</span>'
        inner = ("<ul>" + "".join(c for c in child_html if c) + "</ul>") if child_html else ""
        return f'<li><code>{esc(role)}</code>{extra}{inner}</li>'

    roots = st["/K"]
    roots = roots if isinstance(roots, list) else [roots]
    body = "".join(render(n, 0) for n in roots)
    if budget[0] <= 0:
        body += '<li class="more">… (tree truncated)</li>'
    return f'<ul class="tagtree">{body}</ul>'


# ---------------------------------------------------------------------------
# Scenario description (leading comment block of template.tex)
# ---------------------------------------------------------------------------
def _describe(sdir: str) -> tuple[str, str]:
    """(title, description) from the template's leading `%` comment block."""
    path = os.path.join(sdir, "template.tex")
    lines = []
    try:
        with open(path, encoding="utf-8") as f:
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
    title = ""
    if lines and lines[0].lower().startswith("scenario:"):
        title = lines.pop(0).split(":", 1)[1].strip()
    desc = " ".join(l for l in lines if l)
    return title, desc


# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------
def _panel_imgs(uris: list[str], err: str, alt: str) -> str:
    if err:
        return f'<div class="err">build failed:<br><code>{html.escape(err)}</code></div>'
    if not uris:
        return '<div class="muted">no render (pdftoppm unavailable)</div>'
    return "".join(f'<img loading="lazy" alt="{html.escape(alt)}" src="{u}">' for u in uris)


def _feature_section(item: dict) -> str:
    esc = html.escape
    slug = item["slug"]
    badge = item["badge"]
    npages = f'{item["npages_norm"]}p / {item["npages_acc"]}p'
    desc = esc(item["desc"]) if item["desc"] else '<span class="muted">(no description)</span>'
    return f"""
<section class="feature" id="{esc(slug)}"
         data-search="{esc((item['title'] + ' ' + item['name'] + ' ' + item['desc'] + ' ' + item['area_label']).lower())}">
  <h3>{esc(item['area_label'])} <span class="sep">›</span> {esc(item['name'])}
      <a class="anchor" href="#{esc(slug)}">#</a></h3>
  <p class="desc">{desc}</p>
  <div class="meta">{badge} <span class="muted">· normal vs accessible pages: {npages}</span></div>
  <div class="panels">
    <div class="panel"><div class="phead">Normal</div><div class="render">{item['img_norm']}</div></div>
    <div class="panel"><div class="phead">Accessible</div><div class="render">{item['img_acc']}</div></div>
    <div class="panel struct"><div class="phead">Accessible structure (tag tree)</div>{item['tree']}</div>
  </div>
</section>"""


def _build_html(items: list[dict], stats: dict) -> str:
    # group TOC by area label
    from collections import OrderedDict
    groups: "OrderedDict[str, list]" = OrderedDict()
    for it in items:
        groups.setdefault(it["area_label"], []).append(it)
    toc = []
    for area, its in groups.items():
        links = "".join(
            f'<li><a href="#{html.escape(i["slug"])}">{html.escape(i["name"])}</a>'
            f' {i["badge_mini"]}</li>' for i in its)
        toc.append(f'<div class="tocgroup"><h4>{html.escape(area)}</h4><ul>{links}</ul></div>')
    sections = "".join(_feature_section(i) for i in items)
    passed = stats["passed"]
    total_acc = stats["total_acc"]
    genline = (f'{stats["n"]} features · accessible PDF/UA-2: '
               f'{passed}/{total_acc} PASS'
               + ("" if S.VERAPDF else " · veraPDF not installed (badges show “n/a”)"))
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TeXLib — normal vs accessible feature gallery</title>
<style>
  :root {{
    --bg:#ffffff; --fg:#1a1a1a; --muted:#6b7280; --card:#f7f7f8; --border:#e2e2e6;
    --accent:#2563eb; --pass:#15803d; --passbg:#dcfce7; --fail:#b91c1c; --failbg:#fee2e2;
    --na:#6b7280; --nabg:#eef0f2; --code:#f2f2f5;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0f1115; --fg:#e6e6e6; --muted:#9aa1ac; --card:#171a21; --border:#2a2e37;
      --accent:#60a5fa; --pass:#4ade80; --passbg:#0c2a17; --fail:#f87171; --failbg:#2a1113;
      --na:#9aa1ac; --nabg:#20242c; --code:#1b1f27; }}
  }}
  :root[data-theme="dark"] {{ --bg:#0f1115; --fg:#e6e6e6; --muted:#9aa1ac; --card:#171a21;
    --border:#2a2e37; --accent:#60a5fa; --pass:#4ade80; --passbg:#0c2a17; --fail:#f87171;
    --failbg:#2a1113; --na:#9aa1ac; --nabg:#20242c; --code:#1b1f27; }}
  :root[data-theme="light"] {{ --bg:#ffffff; --fg:#1a1a1a; --muted:#6b7280; --card:#f7f7f8;
    --border:#e2e2e6; --accent:#2563eb; --pass:#15803d; --passbg:#dcfce7; --fail:#b91c1c;
    --failbg:#fee2e2; --na:#6b7280; --nabg:#eef0f2; --code:#f2f2f5; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  header {{ position:sticky; top:0; z-index:5; background:var(--bg);
    border-bottom:1px solid var(--border); padding:14px 20px; }}
  header h1 {{ margin:0 0 4px; font-size:18px; }}
  .genline {{ color:var(--muted); font-size:13px; }}
  #q {{ width:100%; max-width:420px; margin-top:10px; padding:8px 12px; font-size:14px;
    border:1px solid var(--border); border-radius:8px; background:var(--card); color:var(--fg); }}
  .layout {{ display:grid; grid-template-columns:240px 1fr; gap:0; align-items:start; }}
  nav {{ position:sticky; top:96px; align-self:start; max-height:calc(100vh - 110px);
    overflow:auto; padding:16px; border-right:1px solid var(--border); }}
  nav h4 {{ margin:14px 0 6px; font-size:12px; text-transform:uppercase; letter-spacing:.04em;
    color:var(--muted); }}
  nav ul {{ list-style:none; margin:0; padding:0; }}
  nav li {{ margin:2px 0; }}
  nav a {{ color:var(--fg); text-decoration:none; font-size:13px; }}
  nav a:hover {{ color:var(--accent); text-decoration:underline; }}
  main {{ padding:20px; min-width:0; }}
  .feature {{ border:1px solid var(--border); border-radius:12px; background:var(--card);
    padding:16px; margin:0 0 22px; }}
  .feature h3 {{ margin:0 0 4px; font-size:16px; }}
  .feature h3 .sep {{ color:var(--muted); }}
  .anchor {{ color:var(--muted); text-decoration:none; font-weight:normal; opacity:0; }}
  .feature h3:hover .anchor {{ opacity:1; }}
  .desc {{ margin:.2em 0 .6em; color:var(--fg); }}
  .meta {{ font-size:13px; margin-bottom:12px; }}
  .panels {{ display:grid; grid-template-columns:1fr 1fr minmax(220px,0.9fr); gap:14px; }}
  @media (max-width:1100px) {{ .panels {{ grid-template-columns:1fr; }} }}
  .panel {{ border:1px solid var(--border); border-radius:8px; overflow:hidden; background:var(--bg); }}
  .phead {{ font-size:12px; font-weight:600; padding:6px 10px; border-bottom:1px solid var(--border);
    color:var(--muted); background:var(--card); }}
  .render {{ padding:10px; overflow-x:auto; }}
  .render img {{ display:block; max-width:100%; height:auto; margin:0 auto 8px;
    border:1px solid var(--border); }}
  .struct {{ overflow:auto; }}
  .tagtree, .tagtree ul {{ list-style:none; margin:0; padding-left:14px; }}
  .tagtree {{ padding:10px 12px; font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .tagtree li {{ position:relative; }}
  .tagtree code {{ background:var(--code); padding:0 4px; border-radius:4px; }}
  .snip {{ color:var(--muted); }}
  .more {{ color:var(--muted); font-style:italic; }}
  .muted {{ color:var(--muted); }}
  .err {{ padding:14px; color:var(--fail); font-size:13px; }}
  .err code {{ background:var(--failbg); padding:2px 4px; border-radius:4px; }}
  .badge {{ display:inline-block; font-size:12px; font-weight:600; padding:2px 9px;
    border-radius:999px; }}
  .badge.pass {{ color:var(--pass); background:var(--passbg); }}
  .badge.fail {{ color:var(--fail); background:var(--failbg); }}
  .badge.na {{ color:var(--na); background:var(--nabg); }}
  .mini {{ font-size:10px; padding:1px 6px; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .clauses {{ color:var(--fail); font-size:12px; margin-left:6px; }}
</style>
</head><body>
<header>
  <h1>TeXLib — normal vs accessible feature gallery</h1>
  <div class="genline">{html.escape(genline)}</div>
  <input id="q" type="search" placeholder="Filter features… (feature name, class, keyword)">
</header>
<div class="layout">
  <nav>{"".join(toc)}</nav>
  <main>{sections}</main>
</div>
<script>
  const q = document.getElementById('q');
  const secs = [...document.querySelectorAll('section.feature')];
  q.addEventListener('input', () => {{
    const t = q.value.trim().toLowerCase();
    for (const s of secs) s.style.display =
      (!t || s.dataset.search.includes(t)) ? '' : 'none';
  }});
</script>
</body></html>"""


def _badge(problems, skipped, err):
    """problems/skipped are check_verapdf's return: pass == no problems, not skipped."""
    if err:
        return ('<span class="badge fail">build failed</span>',
                '<span class="badge fail mini">fail</span>')
    if not S.VERAPDF or skipped:
        return ('<span class="badge na">veraPDF n/a</span>',
                '<span class="badge na mini">n/a</span>')
    if not problems:
        return ('<span class="badge pass">PDF/UA-2 ✓</span>',
                '<span class="badge pass mini">✓</span>')
    # problems[0] already reads "PDF/UA-2 non-compliant -- failed clause(s): …"
    detail = html.escape(problems[0].replace("PDF/UA-2 non-compliant", "").strip(" -"))
    cl = f' <span class="clauses">{detail}</span>' if detail else ''
    return (f'<span class="badge fail">PDF/UA-2 ✗</span>{cl}',
            '<span class="badge fail mini">✗</span>')


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the normal-vs-accessible feature gallery.")
    ap.add_argument("areas", nargs="*", help="scenario areas to include (default: all)")
    ap.add_argument("--full", action="store_true", help="include tier=full scenarios")
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="render resolution (default 100)")
    ap.add_argument("--timeout", type=int, default=180, help="per-build timeout seconds")
    ap.add_argument("-o", "--out", default=DEFAULT_OUT, help="output HTML path")
    args = ap.parse_args()

    if not shutil.which("lualatex"):
        print("ERROR: lualatex not found on PATH.", flush=True)
        return 2

    scens = S.discover_scenarios(args.areas, include_full=args.full)
    if not scens:
        print("No scenarios found.", flush=True)
        return 1
    try:
        import pdfminer  # noqa: F401
        have_pdfminer = True
    except Exception:
        have_pdfminer = False
    print(f"Gallery: {len(scens)} scenario(s); "
          f"veraPDF={'yes' if S.VERAPDF else 'no'}, "
          f"pdftoppm={'yes' if S.PDFTOPPM else 'no'}, "
          f"tag-text-snippets={'yes' if have_pdfminer else 'no'}", flush=True)

    work = tempfile.mkdtemp(prefix="texlib_gallery_")
    items, passed, total_acc = [], 0, 0
    try:
        for i, scen in enumerate(sorted(scens, key=lambda s: (s["area"], s["name"])), 1):
            slug = scen["slug"]
            print(f"  [{i}/{len(scens)}] {slug} …", end="", flush=True)
            t0 = time.time()
            pdf_n, err_n = _build(scen, work, accessible=False, timeout=args.timeout)
            pdf_a, err_a = _build(scen, work, accessible=True, timeout=args.timeout)
            img_n = _render(pdf_n, work, S.safe_name(slug) + "_n", args.dpi)
            img_a = _render(pdf_a, work, S.safe_name(slug) + "_a", args.dpi)
            problems, skipped = ([], True)
            if pdf_a:
                problems, skipped = S.check_verapdf(pdf_a)
            ua_ok = bool(pdf_a) and S.VERAPDF and not skipped and not problems
            if pdf_a and S.VERAPDF and not skipped:
                total_acc += 1
                if ua_ok:
                    passed += 1
            badge, badge_mini = _badge(problems, skipped, err_a)
            tree = (_tag_tree_html(pdf_a) if pdf_a
                    else '<p class="err">accessible build failed — no tag tree</p>')
            title, desc = _describe(scen["dir"])
            items.append({
                "slug": slug, "name": scen["name"], "area_label": AREA_LABEL.get(scen["area"], scen["area"]),
                "title": title, "desc": desc,
                "img_norm": _panel_imgs(img_n, err_n, "normal render"),
                "img_acc": _panel_imgs(img_a, err_a, "accessible render"),
                "npages_norm": len(img_n), "npages_acc": len(img_a),
                "tree": tree, "badge": badge, "badge_mini": badge_mini,
            })
            print(f" {time.time() - t0:.0f}s "
                  f"[norm {'ok' if pdf_n else 'FAIL'} / acc {'ok' if pdf_a else 'FAIL'}"
                  f"{' / ua2 ' + ('PASS' if ua_ok else 'fail') if (pdf_a and S.VERAPDF and not skipped) else ''}]",
                  flush=True)
        stats = {"n": len(items), "passed": passed, "total_acc": total_acc}
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(_build_html(items, stats))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    size = os.path.getsize(args.out) / 1024
    print(f"\nWrote {args.out} ({size:.0f} KB) — "
          f"{passed}/{total_acc} accessible builds PASS PDF/UA-2.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
