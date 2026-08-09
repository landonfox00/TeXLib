"""test_texam_server.py -- HTTP-level tests for the TeXaM server.

Starts a real ThreadingHTTPServer against a temp course and exercises every
endpoint over HTTP: index, bank/exam reads, add/remove/reorder, undo/redo,
reveal (subl stubbed), render (stubbed / 503 / 404), static files, path
traversal, and unknown routes.  No TeX toolchain and no editor are launched.

    python test_texam_server.py
"""

import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

import bank_render
import texam


COURSEMETA = "\\metasetup{ course-number = 1, bank-path = Bank/bank.tex }\n"
MASTER = "\\loadbank{\\GetCourseMetaDir Bank/ch.tex}\n"
CHAPTER = (
    "\\begin{problem}{fr-one}[topic=alpha, section=1.1]\n"
    "Compute $1+1$.\n\\begin{solution} $2$ \\end{solution}\n\\end{problem}\n"
    "\\begin{problem}{fr-two}[topic=alpha, section=1.2]\n"
    "Compute $2+2$.\n\\end{problem}\n"
    "\\begin{problem}{mc-one}[topic=beta, section=2.1]\n"
    "Pick.\n\\begin{choices}\\cchoice a\\choice b\\end{choices}\n\\end{problem}\n"
)
EXAM = (
    "\\documentclass[exam-number=1]{autoexam}\n\\begin{document}\n\\maketitle\n"
    "\\begin{problems}\\problem{fr-one}\\end{problems}\n\\end{document}\n"
)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="texam-srv-")
        _write(os.path.join(self.dir, "coursemeta.tex"), COURSEMETA)
        _write(os.path.join(self.dir, "Bank", "bank.tex"), MASTER)
        _write(os.path.join(self.dir, "Bank", "ch.tex"), CHAPTER)
        self.exam = os.path.join(self.dir, "Exams", "exam.tex")
        _write(self.exam, EXAM)
        texam.CTX["exam"] = self.exam
        texam.CTX["by_id"] = {}
        texam.CTX["sources"] = []
        texam._undo.clear()
        texam._redo.clear()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), texam.Handler)
        self.port = self.httpd.server_address[1]
        # small poll interval so tearDown's shutdown() returns quickly
        self.t = threading.Thread(
            target=lambda: self.httpd.serve_forever(poll_interval=0.02), daemon=True)
        self.t.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # -- request helpers --
    def _req(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        data, hdrs = None, {}
        if body is not None:
            data = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        c.request(method, path, data, hdrs)
        r = c.getresponse()
        raw = r.read()
        ct = r.getheader("Content-Type", "")
        c.close()
        return r.status, ct, raw

    def _json(self, method, path, body=None):
        st, _ct, raw = self._req(method, path, body)
        return st, (json.loads(raw.decode()) if raw else {})

    def _args(self):
        _st, d = self._json("GET", "/api/exam")
        return [e["arg"] for e in d["entries"]]

    # -- index + reads --
    def test_index_serves_app(self):
        st, ct, raw = self._req("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("text/html", ct)
        self.assertIn(b"TeXaM", raw)

    def test_bank_lists_full_chain(self):
        st, d = self._json("GET", "/api/bank")
        self.assertEqual(st, 200)
        self.assertEqual({p["id"] for p in d["problems"]},
                         {"fr-one", "fr-two", "mc-one"})
        self.assertIn("render_available", d)
        self.assertIn("exam", d)
        self.assertTrue(any(s.endswith("ch.tex") for s in d["sources"]))

    def test_exam_entries(self):
        st, d = self._json("GET", "/api/exam")
        self.assertEqual(st, 200)
        self.assertTrue(d["exists"])
        self.assertEqual([e["arg"] for e in d["entries"]], ["fr-one"])

    # -- mutations --
    def test_add_by_id(self):
        st, d = self._json("POST", "/api/exam/add", {"id": "mc-one", "mode": "id"})
        self.assertEqual(st, 200)
        self.assertIn("mc-one", [e["arg"] for e in d["entries"]])

    def test_add_by_filter(self):
        st, d = self._json("POST", "/api/exam/add", {"id": "mc-one", "mode": "filter"})
        self.assertIn("topic=beta", [e["arg"] for e in d["entries"]])

    def test_add_unknown_id_404(self):
        st, d = self._json("POST", "/api/exam/add", {"id": "nope", "mode": "id"})
        self.assertEqual(st, 404)

    def test_remove(self):
        self._json("POST", "/api/exam/add", {"id": "fr-two", "mode": "id"})
        _st, d = self._json("GET", "/api/exam")
        idx = [e["index"] for e in d["entries"] if e["arg"] == "fr-two"][0]
        self._json("POST", "/api/exam/remove", {"index": idx})
        self.assertNotIn("fr-two", self._args())

    def test_reorder(self):
        self._json("POST", "/api/exam/add", {"id": "fr-two", "mode": "id"})
        self.assertEqual(self._args(), ["fr-one", "fr-two"])
        _st, d = self._json("GET", "/api/exam")
        idx = [e["index"] for e in d["entries"] if e["arg"] == "fr-two"][0]
        self._json("POST", "/api/exam/reorder", {"index": idx, "dir": -1})
        self.assertEqual(self._args(), ["fr-two", "fr-one"])

    # -- undo / redo --
    def test_undo_then_redo(self):
        self._json("POST", "/api/exam/add", {"id": "mc-one", "mode": "id"})
        st, d = self._json("POST", "/api/exam/undo")
        self.assertEqual(st, 200)
        self.assertEqual(d["undone"], "add mc-one")
        self.assertEqual([e["arg"] for e in d["entries"]], ["fr-one"])
        _st, d = self._json("POST", "/api/exam/redo")
        self.assertEqual(d["redone"], "add mc-one")
        self.assertIn("mc-one", [e["arg"] for e in d["entries"]])

    def test_undo_empty_is_null(self):
        _st, d = self._json("POST", "/api/exam/undo")
        self.assertIsNone(d["undone"])

    # -- reveal --
    def test_reveal_launches(self):
        calls = []
        of, op = texam._find_subl, texam.subprocess.Popen
        texam._find_subl = lambda: "subl"
        texam.subprocess.Popen = lambda a, **k: calls.append(a)
        try:
            st, d = self._json("POST", "/api/reveal", {"id": "fr-one"})
        finally:
            texam._find_subl, texam.subprocess.Popen = of, op
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])
        self.assertTrue(d["file"].endswith("ch.tex"))
        self.assertEqual(len(calls), 1)

    def test_reveal_unknown_404(self):
        st, _d = self._json("POST", "/api/reveal", {"id": "nope"})
        self.assertEqual(st, 404)

    def test_reveal_no_subl_503(self):
        of = texam._find_subl
        texam._find_subl = lambda: None
        try:
            st, _d = self._json("POST", "/api/reveal", {"id": "fr-one"})
        finally:
            texam._find_subl = of
        self.assertEqual(st, 503)

    # -- render --
    def test_render_ok_stubbed(self):
        oa, orr = bank_render.available, bank_render.render_svg
        bank_render.available = lambda: True
        bank_render.render_svg = lambda p, show_solution=True: "<svg>ok</svg>"
        try:
            st, ct, raw = self._req("GET", "/api/render/fr-one")
        finally:
            bank_render.available, bank_render.render_svg = oa, orr
        self.assertEqual(st, 200)
        self.assertIn("image/svg", ct)
        self.assertIn(b"<svg>", raw)

    def test_render_unavailable_503(self):
        oa = bank_render.available
        bank_render.available = lambda: False
        try:
            st, _d = self._json("GET", "/api/render/fr-one")
        finally:
            bank_render.available = oa
        self.assertEqual(st, 503)

    def test_render_unknown_404(self):
        st, _d = self._json("GET", "/api/render/nope")
        self.assertEqual(st, 404)

    # -- routing / static --
    def test_unknown_api_404(self):
        st, _d = self._json("GET", "/api/bogus")
        self.assertEqual(st, 404)

    def test_static_asset(self):
        st, ct, _raw = self._req("GET", "/app.js")
        self.assertEqual(st, 200)
        self.assertIn("javascript", ct)

    def test_static_missing_404(self):
        st, _ct, _raw = self._req("GET", "/nope.js")
        self.assertEqual(st, 404)

    def test_path_traversal_blocked(self):
        st, _ct, _raw = self._req("GET", "/../texam.py")
        self.assertEqual(st, 404)

    def test_ping_ok(self):
        st, d = self._json("GET", "/api/ping")
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])

    def test_quit_responds_ok(self):
        # texam._httpd is None under test, so _shutdown() is a no-op -- the quit
        # endpoint still acknowledges without killing this test's server.
        st, d = self._json("POST", "/api/quit")
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])

    def test_static_css_content_type(self):
        st, ct, _raw = self._req("GET", "/app.css")
        self.assertEqual(st, 200)
        self.assertIn("text/css", ct)

    def test_add_appends_then_reorders(self):
        self._json("POST", "/api/exam/add", {"id": "fr-two", "mode": "id"})
        self.assertEqual(self._args(), ["fr-one", "fr-two"])       # append semantics
        _st, d = self._json("GET", "/api/exam")
        idx = [e["index"] for e in d["entries"] if e["arg"] == "fr-two"][0]
        self._json("POST", "/api/exam/reorder", {"index": idx, "dir": -1})
        self.assertEqual(self._args(), ["fr-two", "fr-one"])

    def test_malformed_body_is_graceful(self):
        # a non-JSON body decodes to {} -> add of "" -> unknown id -> 404, no 500
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("POST", "/api/exam/add", b"not json at all",
                  {"Content-Type": "application/json"})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 404)               # graceful, not a 500 crash

    def test_crlf_exam_preserved_on_edit(self):
        with open(self.exam, "wb") as fh:
            fh.write(EXAM.replace("\n", "\r\n").encode())
        self._json("POST", "/api/exam/add", {"id": "fr-two", "mode": "id"})
        with open(self.exam, "rb") as fh:
            raw = fh.read()
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\r\r", raw)                # not doubled

    def test_render_error_is_500(self):
        oa, orr = bank_render.available, bank_render.render_svg
        def boom(p, show_solution=True):
            raise bank_render.RenderError("compile failed")
        bank_render.available = lambda: True
        bank_render.render_svg = boom
        try:
            st, _d = self._json("GET", "/api/render/fr-one")
        finally:
            bank_render.available, bank_render.render_svg = oa, orr
        self.assertEqual(st, 500)

    def test_reveal_launch_oserror_is_500(self):
        of, op = texam._find_subl, texam.subprocess.Popen
        texam._find_subl = lambda: "subl"
        def boom(*a, **k):
            raise OSError("cannot exec")
        texam.subprocess.Popen = boom
        try:
            st, _d = self._json("POST", "/api/reveal", {"id": "fr-one"})
        finally:
            texam._find_subl, texam.subprocess.Popen = of, op
        self.assertEqual(st, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
