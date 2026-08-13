"""texam.py -- local web app to browse a TeXLib bank and compose an exam.

    python texam.py path/to/exam.tex        # opens the browser

Resolves the bank behind the exam, serves a small single-page app, and writes
``\\problem{...}`` lines back into the exam file as you add problems.  Stdlib
only (http.server); problems render with the real engine via bank_render (SVG,
cached + pre-warmed).  Launched from the shell or, later, a Sublime command.

Endpoints (JSON unless noted):
  GET  /                     the app
  GET  /<asset>              static files from texam_web/
  GET  /api/bank             {problems: [...], render_available: bool, sources}
  GET  /api/exam             {name, path, entries: [...], exists}
  POST /api/exam/add         {id, mode: 'id'|'filter'} -> updated exam
  POST /api/exam/remove      {index}                   -> updated exam
  POST /api/exam/reorder     {index, dir: -1|1}        -> updated exam
  POST /api/exam/undo        -> restore prior exam state (+ {undone: label})
  POST /api/exam/redo        -> reapply undone state   (+ {redone: label})
  POST /api/reveal           {id}  -> open the problem's source in Sublime
  GET  /api/render/<id>?sol= image/svg+xml (503 if the toolchain is missing)
  GET  /api/ping             {ok}  -- keep-alive heartbeat (resets idle timer)
  POST /api/quit             {ok}  -- stop the server

CLI: `--export [dir]` renders every problem once and writes the SVGs to dir
(default <exam-dir>/texam-render/), then exits without serving.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import bank_parser
import bank_render
import exam_writer
import usage_scan

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "texam_web")
_MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

CTX = {"exam": None, "by_id": {}, "sources": []}
_write_lock = threading.Lock()

# Server lifecycle: the running server, the last-request time, and the idle
# window after which a hidden (console-less) server auto-quits so it can't
# linger. The page pings every 30s while open, so this only fires once the tab
# is really gone.
_httpd = None
_last_activity = 0.0
_IDLE_TIMEOUT = 300.0


def _touch():
    global _last_activity
    _last_activity = time.monotonic()


def _shutdown():
    """Stop serve_forever from a separate (non-handler) thread -- no deadlock."""
    if _httpd is not None:
        _httpd.shutdown()


def _idle_watch():
    """Auto-quit after _IDLE_TIMEOUT with no browser request, so a hidden
    (console-less) server cleans itself up once the tab is closed."""
    while True:
        time.sleep(15)
        if time.monotonic() - _last_activity > _IDLE_TIMEOUT:
            _shutdown()
            return


def export_bank(problems, outdir=None, show_solution=False):
    """Render every problem ONCE and save the SVGs to a persistent directory --
    a portable, reusable image set for a bank, with no server and no
    re-rendering later. Renders in parallel; prints a per-problem failure line."""
    if not bank_render.available():
        sys.exit("texam: renderer unavailable (need lualatex + pdftocairo/dvisvgm)")
    if not outdir:
        outdir = os.path.join(os.path.dirname(CTX["exam"]), "texam-render")
    os.makedirs(outdir, exist_ok=True)
    print(f"TeXaM export: rendering {len(problems)} problem(s) in parallel...")
    for t in bank_render.prewarm(problems, show_solution=show_solution):
        t.join()                                        # populate the cache in parallel
    ok = fail = 0
    for p in problems:
        try:
            svg = bank_render.render_svg(p, show_solution=show_solution)  # cache hit
            if not bank_render._is_complete_svg(svg):
                raise RuntimeError("empty render")
            with open(os.path.join(outdir, p.id + ".svg"), "w", encoding="utf-8") as fh:
                fh.write(svg)
            ok += 1
        except Exception as exc:
            fail += 1
            first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            print(f"  ! {p.id}: {first}")
    print(f"TeXaM export: wrote {ok} SVG(s) to {outdir}"
          + (f"  ({fail} failed)" if fail else ""))

# Undo/redo: snapshots of the whole exam-file text taken before each edit, so a
# restore is exact regardless of index churn. Each entry is (text, nl, label).
_undo = []
_redo = []
_HISTORY_MAX = 100


def _record(pre_text, pre_nl, label):
    """Push the pre-edit exam state onto the undo stack; a fresh edit voids redo."""
    _undo.append((pre_text, pre_nl, label))
    del _undo[:-_HISTORY_MAX]
    _redo.clear()


def history_step(redo):
    """Swap the current exam text with the top of the undo (or redo) stack,
    pushing the current state onto the other stack. Returns the action label, or
    None if the stack is empty. The file rewrite is the whole exam text, so it is
    exact regardless of index churn."""
    src, dst = (_redo, _undo) if redo else (_undo, _redo)
    with _write_lock:
        if not src:
            return None
        cur, curnl = read_exam(CTX["exam"])
        text, nl, label = src.pop()
        dst.append((cur, curnl, label))
        del dst[:-_HISTORY_MAX]
        write_exam(CTX["exam"], text, nl)
    return label


# --------------------------------------------------------------------------
# exam file I/O (preserve the file's newline style; the memory notes a CRLF
# hazard on this tree)
# --------------------------------------------------------------------------
def read_exam(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    return text, nl


def write_exam(path, text, nl):
    data = text if nl == "\n" else text.replace("\n", nl)
    with open(path, "wb") as fh:
        fh.write(data.encode("utf-8"))


def refresh_bank():
    """Re-scan the bank; keep an id->Problem map for render/add lookups."""
    sources, problems = bank_parser.discover(CTX["exam"])
    CTX["sources"] = sources
    CTX["by_id"] = {p.id: p for p in problems}
    return problems


def exam_state():
    path = CTX["exam"]
    if not os.path.isfile(path):
        return {"name": os.path.basename(path), "path": path,
                "entries": [], "exists": False}
    text, _ = read_exam(path)
    return {"name": os.path.basename(path), "path": path,
            "entries": exam_writer.public_entries(text), "exists": True}


def _arg_for(problem, mode):
    if mode == "filter" and problem.topic:
        return "topic=" + problem.topic
    return problem.id


_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
# Common Windows install spots when `subl` is not on PATH (macOS/Linux ship the
# `subl` symlink, so which() covers them).
_SUBL_FALLBACKS = (
    r"C:\Program Files\Sublime Text\subl.exe",
    r"C:\Program Files\Sublime Text 3\subl.exe",
    r"C:\Program Files (x86)\Sublime Text 3\subl.exe",
)


def _find_subl():
    return (shutil.which("subl") or shutil.which("subl.exe")
            or next((c for c in _SUBL_FALLBACKS if os.path.isfile(c)), None))


def reveal_in_editor(source_file, line):
    """Open ``source_file`` at ``line`` (0-based) in Sublime via the ``subl``
    CLI -- inverse search from a preview to the bank definition. Returns the
    launched ``file:line`` target; raises RuntimeError if ``subl`` is missing."""
    subl = _find_subl()
    if not subl:
        raise RuntimeError("Sublime 'subl' CLI not found on PATH")
    target = "%s:%d" % (source_file, (line or 0) + 1)
    subprocess.Popen([subl, target], creationflags=_NO_WINDOW)
    return target


# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "TeXaM"

    def log_message(self, *a):
        pass  # quiet

    # -- helpers -----------------------------------------------------------
    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj), _MIME[".json"])

    def _body_json(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        _touch()
        try:
            u = urlparse(self.path)
            path, qs = u.path, parse_qs(u.query)
            if path == "/" or path == "/index.html":
                return self._static("index.html")
            if path == "/api/ping":                     # keep-alive heartbeat
                return self._json({"ok": True})
            if path == "/api/bank":
                return self._api_bank()
            if path == "/api/exam":
                return self._json(exam_state())
            if path.startswith("/api/render/"):
                return self._api_render(unquote(path[len("/api/render/"):]), qs)
            if path.startswith("/api/"):
                return self._json({"error": "not found"}, 404)
            return self._static(path.lstrip("/"))
        except Exception as exc:                       # noqa: BLE001 - report to client
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        _touch()
        try:
            u = urlparse(self.path)
            if u.path == "/api/quit":                   # stop the server (Quit button)
                self._json({"ok": True})
                threading.Thread(target=_shutdown, daemon=True).start()
                return
            if u.path == "/api/exam/add":
                return self._api_add(self._body_json())
            if u.path == "/api/exam/remove":
                return self._api_mutate("remove", self._body_json())
            if u.path == "/api/exam/reorder":
                return self._api_mutate("reorder", self._body_json())
            if u.path == "/api/exam/undo":
                return self._api_history(redo=False)
            if u.path == "/api/exam/redo":
                return self._api_history(redo=True)
            if u.path == "/api/reveal":
                return self._api_reveal(self._body_json())
            return self._json({"error": "not found"}, 404)
        except Exception as exc:                       # noqa: BLE001
            self._json({"error": str(exc)}, 500)

    # -- endpoints ---------------------------------------------------------
    def _static(self, rel):
        rel = rel or "index.html"
        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            return self._json({"error": "not found: " + rel}, 404)
        with open(full, "rb") as fh:
            data = fh.read()
        ctype = _MIME.get(os.path.splitext(full)[1].lower(),
                          "application/octet-stream")
        self._send(200, data, ctype)

    def _api_bank(self):
        problems = refresh_bank()
        usage = usage_scan.scan(os.path.dirname(CTX["exam"]), problems,
                                set(CTX["sources"]))
        dicts = []
        for p in problems:
            d = p.to_dict()
            d["used_in"] = usage.get(p.id, [])
            dicts.append(d)
        self._json({
            "problems": dicts,
            "render_available": bank_render.available(),
            "sources": CTX["sources"],
            "exam": exam_state(),
        })

    def _api_render(self, pid, qs):
        problem = CTX["by_id"].get(pid) or {p.id: p for p in refresh_bank()}.get(pid)
        if not problem:
            return self._json({"error": "unknown problem: " + pid}, 404)
        if not bank_render.available():
            return self._json({"error": "renderer unavailable "
                               "(need lualatex + pdftocairo/dvisvgm)"}, 503)
        show_sol = qs.get("sol", ["1"])[0] != "0"
        try:
            svg = bank_render.render_svg(problem, show_solution=show_sol)
        except bank_render.RenderUnavailable as exc:
            return self._json({"error": str(exc)}, 503)
        except bank_render.RenderError as exc:
            return self._json({"error": str(exc)}, 500)
        self._send(200, svg, _MIME[".svg"])

    def _api_add(self, body):
        pid = (body or {}).get("id", "")
        mode = (body or {}).get("mode", "id")
        problem = CTX["by_id"].get(pid) or {p.id: p for p in refresh_bank()}.get(pid)
        if not problem:
            return self._json({"error": "unknown problem: " + pid}, 404)
        after = (body or {}).get("after", None)
        after = int(after) if after is not None else None
        with _write_lock:
            text, nl = read_exam(CTX["exam"])
            _record(text, nl, "add " + _arg_for(problem, mode))
            text = exam_writer.add_problem(text, _arg_for(problem, mode),
                                           problem.is_mc, after_index=after)
            write_exam(CTX["exam"], text, nl)
        self._json(exam_state())

    def _api_reveal(self, body):
        pid = (body or {}).get("id", "")
        problem = CTX["by_id"].get(pid) or {p.id: p for p in refresh_bank()}.get(pid)
        if not problem:
            return self._json({"error": "unknown problem: " + pid}, 404)
        try:
            reveal_in_editor(problem.source_file, problem.line)
        except RuntimeError as exc:                     # subl not found
            return self._json({"error": str(exc)}, 503)
        except OSError as exc:
            return self._json({"error": str(exc)}, 500)
        self._json({"ok": True, "file": problem.source_file,
                    "line": (problem.line or 0) + 1})

    def _api_mutate(self, op, body):
        idx = int((body or {}).get("index", -1))
        with _write_lock:
            text, nl = read_exam(CTX["exam"])
            if op == "remove":
                ents = exam_writer.public_entries(text)
                arg = ents[idx]["arg"] if 0 <= idx < len(ents) else ""
                _record(text, nl, "remove " + arg)
                text = exam_writer.remove_problem(text, idx)
            else:
                _record(text, nl, "reorder")
                text = exam_writer.move_problem(text, idx,
                                                int((body or {}).get("dir", 0)))
            write_exam(CTX["exam"], text, nl)
        self._json(exam_state())

    def _api_history(self, redo):
        """Undo (redo=False) / redo (redo=True) the exam, returning the exam
        state plus `undone`/`redone` = the action label (None if nothing)."""
        label = history_step(redo)
        st = exam_state()
        st["redone" if redo else "undone"] = label
        self._json(st)


def main(argv):
    if len(argv) < 2:
        sys.exit("usage: python texam.py <exam.tex> [--port N] [--no-open] "
                 "[--export [dir]]")
    exam = os.path.abspath(argv[1])
    if not os.path.isfile(exam):
        sys.exit(f"texam: no such exam file: {exam}")
    CTX["exam"] = exam
    port = 8765
    do_open = "--no-open" not in argv
    if "--port" in argv:
        try:
            port = int(argv[argv.index("--port") + 1])
        except (IndexError, ValueError):
            sys.exit("texam: --port needs a number, e.g. --port 8790")

    try:
        problems = refresh_bank()
    except Exception as exc:            # a parse error must not crash the launcher
        sys.exit(f"texam: could not read the exam or its bank: {exc}")

    if "--export" in argv:             # render all + save SVGs, then exit (no server)
        i = argv.index("--export")
        outdir = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else None
        return export_bank(problems, outdir)

    print(f"TeXaM -- exam: {CTX['exam']}")
    print(f"  bank sources: {len(CTX['sources'])}, problems: {len(problems)}")
    if not problems:
        print("  note: no bank problems found -- check the coursemeta bank-path "
              "or the \\loadbank targets.")
    if bank_render.available():
        print("  renderer: lualatex ready; pre-warming previews in background...")
        bank_render.prewarm(problems)
    else:
        print("  renderer: unavailable (source view only)")

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        sys.exit(f"texam: cannot serve on port {port} ({exc}).\n"
                 "  TeXaM may already be running -- close its window, or "
                 "pass --port <n> to use a different port.")
    global _httpd
    _httpd = httpd
    _touch()
    threading.Thread(target=_idle_watch, daemon=True).start()   # hidden-server cleanup
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"  serving {url}  (Ctrl+C to stop)")
    if do_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main(sys.argv)
