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
  POST /api/reveal           {id}  -> open the problem's source in Sublime
  GET  /api/render/<id>?sol= image/svg+xml (503 if the toolchain is missing)
"""

import json
import os
import shutil
import subprocess
import sys
import threading
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
    server_version = "TeXam"

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
        try:
            u = urlparse(self.path)
            path, qs = u.path, parse_qs(u.query)
            if path == "/" or path == "/index.html":
                return self._static("index.html")
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
        try:
            u = urlparse(self.path)
            if u.path == "/api/exam/add":
                return self._api_add(self._body_json())
            if u.path == "/api/exam/remove":
                return self._api_mutate("remove", self._body_json())
            if u.path == "/api/exam/reorder":
                return self._api_mutate("reorder", self._body_json())
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
                text = exam_writer.remove_problem(text, idx)
            else:
                text = exam_writer.move_problem(text, idx,
                                                int((body or {}).get("dir", 0)))
            write_exam(CTX["exam"], text, nl)
        self._json(exam_state())


def main(argv):
    if len(argv) < 2:
        sys.exit("usage: python texam.py <exam.tex> [--port N] [--no-open]")
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
    print(f"TeXam -- exam: {CTX['exam']}")
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
                 "  TeXam may already be running -- close its window, or "
                 "pass --port <n> to use a different port.")
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
