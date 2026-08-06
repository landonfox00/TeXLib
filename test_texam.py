"""test_texam.py -- dependency-free tests for TeXam.

Covers the bank parser (region split, MC detection, meta, points, comment
handling) and the exam writer (add / remove / reorder, environment creation).
No TeX toolchain required.  Server routing and the real-engine renderer are
tested in later, tool-gated additions.

    python test_texam.py
"""

import os
import tempfile
import unittest

import bank_parser
import bank_render
import texam
import exam_writer
import usage_scan


BANK = r"""
\begin{problem}{frac-lim}[topic=limit, section=2.3, source=test]
	Evaluate \[ \lim_{x\to3}\frac{x^2-9}{x-3}. \]
	\begin{parts}
		\part[4] Compute it.
		\part[2] Explain.
	\end{parts}
	\begin{solution} The limit is $6$. \end{solution}
\end{problem}

\begin{problem}{deriv-mc}[topic=derivative, section=3.1]
	Compute \[ \frac{d}{dx} x^4. \]
	\begin{choices}
		\cchoice $4x^3$
		\choice $x^3$
		\choice $3x^4$
	\end{choices}
	\begin{solution} Power rule. \end{solution}
\end{problem}

\begin{problem}{cmt-test}[topic=misc]
	A stem. % \begin{solution} not the real one \end{solution}
	\begin{solution} real sol \end{solution}
\end{problem}
"""

EXAM = r"""\documentclass[exam-number=1]{autoexam}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem{topic=limit}
	\problem{topic=continuity}
\end{problems}
\end{document}
"""

EXAM_BARE = r"""\documentclass{autoexam}
\begin{document}
\maketitle
\end{document}
"""


class ParserTests(unittest.TestCase):
    def setUp(self):
        # Parse the fixture string directly (scan_problems reads files).
        self.by_id = {}
        for m in bank_parser.PROBLEM_RE.finditer(BANK):
            end = bank_parser.PROBLEM_END_RE.search(BANK, m.end())
            pid = m.group(1).strip()
            attrs = (m.group(2) or "").strip()
            raw = BANK[m.start():end.end()]
            body = BANK[m.end():end.start()]
            self.by_id[pid] = bank_parser.Problem(pid, attrs, "bank.tex", 0, raw, body)

    def test_all_three_parsed(self):
        self.assertEqual(set(self.by_id), {"frac-lim", "deriv-mc", "cmt-test"})

    def test_free_response_with_parts(self):
        p = self.by_id["frac-lim"]
        self.assertFalse(p.is_mc)
        self.assertEqual(p.topic, "limit")
        self.assertEqual(p.section, "2.3")
        self.assertEqual(p.source, "test")
        self.assertEqual(p.part_points, [4, 2])
        self.assertEqual(p.points, 6)
        self.assertEqual(p.choices, [])
        self.assertIn("6", p.solution)
        # solution excised from the stem
        self.assertNotIn("The limit is", p.stem)
        self.assertIn("Evaluate", p.stem)

    def test_multiple_choice(self):
        p = self.by_id["deriv-mc"]
        self.assertTrue(p.is_mc)
        self.assertEqual(p.choices_env, "choices")
        self.assertEqual(len(p.choices), 3)
        self.assertTrue(p.choices[0]["correct"])
        self.assertIn("4x^3", p.choices[0]["text"])
        self.assertFalse(p.choices[1]["correct"])
        self.assertFalse(p.choices[2]["correct"])
        # choices removed from the stem, solution present
        self.assertNotIn("cchoice", p.stem)
        self.assertIn("Power rule", p.solution)

    def test_meta_and_id_injected(self):
        p = self.by_id["deriv-mc"]
        self.assertEqual(p.meta["id"], "deriv-mc")
        self.assertEqual(p.meta["topic"], "derivative")
        self.assertIsNone(p.points)

    def test_comment_env_ignored(self):
        p = self.by_id["cmt-test"]
        self.assertFalse(p.is_mc)
        self.assertEqual(p.solution, "real sol")


class ScanFileTests(unittest.TestCase):
    def test_scan_and_discover_via_tmp(self):
        import os
        import tempfile
        d = tempfile.mkdtemp(prefix="texam-test-")
        bank = os.path.join(d, "bank.tex")
        exam = os.path.join(d, "exam.tex")
        with open(bank, "w", encoding="utf-8") as fh:
            fh.write(BANK)
        with open(exam, "w", encoding="utf-8") as fh:
            fh.write(EXAM)
        sources, probs = bank_parser.discover(exam)
        self.assertIn(bank, sources)          # sibling bank.tex discovered
        self.assertEqual({p.id for p in probs},
                         {"frac-lim", "deriv-mc", "cmt-test"})


class ExamWriterTests(unittest.TestCase):
    def test_parse_existing(self):
        entries = exam_writer.public_entries(EXAM)
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(e["env"] == "fr" for e in entries))
        self.assertEqual(entries[0]["arg"], "topic=limit")
        self.assertTrue(entries[0]["is_filter"])

    def test_add_fr_appends_in_problems(self):
        out = exam_writer.add_problem(EXAM, "frac-lim", is_mc=False)
        entries = exam_writer.public_entries(out)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[-1]["arg"], "frac-lim")
        self.assertEqual(entries[-1]["env"], "fr")
        self.assertEqual(out.count(r"\begin{problems}"), 1)

    def test_add_mc_creates_mcproblems_after_fr(self):
        out = exam_writer.add_problem(EXAM, "deriv-mc", is_mc=True)
        self.assertIn(r"\begin{mcproblems}", out)
        # mcproblems comes after the problems block
        self.assertGreater(out.index(r"\begin{mcproblems}"),
                           out.index(r"\end{problems}"))
        mc = [e for e in exam_writer.public_entries(out) if e["env"] == "mc"]
        self.assertEqual(len(mc), 1)
        self.assertEqual(mc[0]["arg"], "deriv-mc")

    def test_add_creates_env_in_bare_exam(self):
        out = exam_writer.add_problem(EXAM_BARE, "frac-lim", is_mc=False)
        self.assertIn(r"\begin{problems}", out)
        self.assertGreater(out.index(r"\begin{problems}"),
                           out.index(r"\maketitle"))
        self.assertLess(out.index(r"\end{problems}"),
                        out.index(r"\end{document}"))

    def test_add_after_index_inserts_at_caret(self):
        out = exam_writer.add_problem(EXAM, "ivt-root", is_mc=False, after_index=0)
        self.assertEqual([e["arg"] for e in exam_writer.public_entries(out)],
                         ["topic=limit", "ivt-root", "topic=continuity"])

    def test_add_after_index_wrong_env_appends(self):
        # caret is on an FR entry but the new problem is MC -> append to MC env
        out = exam_writer.add_problem(EXAM, "deriv-mc", is_mc=True, after_index=0)
        mc = [e for e in exam_writer.public_entries(out) if e["env"] == "mc"]
        self.assertEqual(len(mc), 1)
        self.assertEqual(mc[0]["arg"], "deriv-mc")

    def test_remove(self):
        out = exam_writer.remove_problem(EXAM, 0)
        entries = exam_writer.public_entries(out)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["arg"], "topic=continuity")

    def test_reorder_swaps_siblings(self):
        out = exam_writer.add_problem(EXAM, "ivt-root", is_mc=False)  # 3 FR now
        entries = exam_writer.public_entries(out)
        self.assertEqual([e["arg"] for e in entries],
                         ["topic=limit", "topic=continuity", "ivt-root"])
        out = exam_writer.move_problem(out, 2, -1)                    # move last up
        entries = exam_writer.public_entries(out)
        self.assertEqual([e["arg"] for e in entries],
                         ["topic=limit", "ivt-root", "topic=continuity"])

    def test_reorder_boundary_noop(self):
        out = exam_writer.move_problem(EXAM, 0, -1)
        self.assertEqual(out, EXAM)

    def test_move_does_not_cross_environments(self):
        out = exam_writer.add_problem(EXAM, "deriv-mc", is_mc=True)   # 2 FR + 1 MC
        entries = exam_writer.public_entries(out)
        mc_index = [e["index"] for e in entries if e["env"] == "mc"][0]
        # moving the lone MC problem up is a no-op (no MC sibling above it)
        out2 = exam_writer.move_problem(out, mc_index, -1)
        self.assertEqual(exam_writer.public_entries(out2),
                         exam_writer.public_entries(out))


class UsageScanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="texam-usage-")
        self._w("bank.tex", BANK)
        # frac-lim (topic=limit), deriv-mc (topic=derivative)
        self._w("exam-01.tex", r"\begin{problems}\problem{topic=limit}\end{problems}")
        self._w("quiz-02.tex", r"\begin{questions}\question\getproblem{frac-lim}\end{questions}")
        self._w("review.tex", r"\getproblem{topic=derivative}  % by topic")
        _, self.probs = bank_parser.discover(os.path.join(self.d, "exam-01.tex"))

    def _w(self, name, text):
        with open(os.path.join(self.d, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_scans_id_and_topic_uses(self):
        # exclude the bank + the current exam (mirrors the server)
        exclude = {os.path.join(self.d, "bank.tex"), os.path.join(self.d, "exam-01.tex")}
        usage = usage_scan.scan(self.d, self.probs, exclude)
        # frac-lim referenced by id in quiz-02
        self.assertIn({"file": "quiz-02.tex", "by": "id"}, usage["frac-lim"])
        # deriv-mc referenced by topic in review.tex
        self.assertIn({"file": "review.tex", "by": "topic"}, usage["deriv-mc"])
        # excluded files never appear
        files = [h["file"] for hits in usage.values() for h in hits]
        self.assertNotIn("bank.tex", files)
        self.assertNotIn("exam-01.tex", files)

    def test_definition_is_not_a_use(self):
        # a \begin{problem}{frac-lim} definition must not count as usage
        self._w("otherbank.tex", r"\begin{problem}{frac-lim}[topic=x]stem\end{problem}")
        usage = usage_scan.scan(self.d, self.probs,
                                {os.path.join(self.d, "bank.tex")})
        files = [h["file"] for h in usage["frac-lim"]]
        self.assertNotIn("otherbank.tex", files)


class ServerHelperTests(unittest.TestCase):
    def _tmp(self, data):
        fd, path = tempfile.mkstemp(suffix=".tex")
        os.close(fd)
        with open(path, "wb") as fh:
            fh.write(data)
        self.addCleanup(lambda: os.path.isfile(path) and os.remove(path))
        return path

    def test_newline_preserved_lf(self):
        p = self._tmp(b"a\nb\nc\n")
        text, nl = texam.read_exam(p)
        self.assertEqual(nl, "\n")
        texam.write_exam(p, text + "d\n", nl)
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"a\nb\nc\nd\n")

    def test_newline_preserved_crlf(self):
        p = self._tmp(b"a\r\nb\r\n")
        text, nl = texam.read_exam(p)
        self.assertEqual(nl, "\r\n")
        self.assertEqual(text, "a\nb\n")           # normalized in memory
        texam.write_exam(p, text + "c\n", nl)
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"a\r\nb\r\nc\r\n")  # CRLF restored

    def test_arg_for_modes(self):
        prob = bank_parser.Problem("pid", "topic=alg", "b.tex", 0, "", "stem")
        self.assertEqual(texam._arg_for(prob, "id"), "pid")
        self.assertEqual(texam._arg_for(prob, "filter"), "topic=alg")
        notopic = bank_parser.Problem("q", "", "b.tex", 0, "", "stem")
        self.assertEqual(texam._arg_for(notopic, "filter"), "q")  # falls back

    def test_exam_state(self):
        texam.CTX["exam"] = self._tmp(EXAM.encode())
        st = texam.exam_state()
        self.assertTrue(st["exists"])
        self.assertEqual(len(st["entries"]), 2)


class CoursemetaResolutionTests(unittest.TestCase):
    """The exam names no bank inline; the bank is wired through coursemeta
    `bank-path` -> a thin master bank.tex -> per-chapter files (the real
    teaching-course layout). discover must walk the whole chain."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="texam-cm-")
        self._mk("coursemeta.tex",
                 "\\metasetup{\n  course-number = 182,\n"
                 "  bank-path = Bank/bank.tex,\n}\n")
        # master bank is a thin loader using the \GetCourseMetaDir prefix
        self._mk("Bank/bank.tex",
                 "\\loadbank{\\GetCourseMetaDir Bank/ch5.tex}\n"
                 "\\loadbank{\\GetCourseMetaDir Bank/ch6.tex}\n")
        self._mk("Bank/ch5.tex",
                 "\\begin{problem}{ch5_a}[topic=sub]\nStem A.\n\\end{problem}\n")
        self._mk("Bank/ch6.tex",
                 "\\begin{problem}{ch6_b}[topic=parts]\nStem B.\n"
                 "\\begin{choices}\\cchoice x\\choice y\\end{choices}\n"
                 "\\end{problem}\n")
        # exam lives two dirs below coursemeta and names no bank inline
        self._mk("Exams/Exam 1/exam1.tex",
                 "\\documentclass[exam-number=1]{autoexam}\n\\begin{document}\n"
                 "\\begin{problems}\\problem{ch5_a}\\end{problems}\n"
                 "\\begin{mcproblems}\\problem{ch6_b}\\end{mcproblems}\n"
                 "\\end{document}\n")
        self.exam = os.path.join(self.root, "Exams", "Exam 1", "exam1.tex")

    def _mk(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_find_coursemeta_walks_up(self):
        start = os.path.join(self.root, "Exams", "Exam 1")
        self.assertEqual(bank_parser.find_coursemeta(start),
                         os.path.join(self.root, "coursemeta.tex"))

    def test_bank_path_resolves(self):
        cm = os.path.join(self.root, "coursemeta.tex")
        self.assertEqual(bank_parser.coursemeta_bank_path(cm),
                         os.path.join(self.root, "Bank", "bank.tex"))

    def test_discover_finds_chapter_problems(self):
        sources, probs = bank_parser.discover(self.exam)
        # reached via bank-path -> master bank.tex -> per-chapter files
        self.assertEqual({p.id for p in probs}, {"ch5_a", "ch6_b"})
        # the chapter files themselves (not just the master) are sources
        self.assertTrue(any(s.endswith("ch5.tex") for s in sources))
        self.assertTrue(any(s.endswith("ch6.tex") for s in sources))
        # MC detection survived the resolution chain
        self.assertTrue(next(p for p in probs if p.id == "ch6_b").is_mc)

    def test_expand_metadir(self):
        self.assertEqual(
            bank_parser._expand_metadir("\\GetCourseMetaDir Bank/ch5.tex",
                                        "C:/course/Summer 26"),
            "C:/course/Summer 26/Bank/ch5.tex")
        # no coursemeta -> the macro drops out, path stays relative
        self.assertEqual(
            bank_parser._expand_metadir("\\GetCourseMetaDir Bank/ch5.tex", None),
            "Bank/ch5.tex")

    def test_meta_command_spelling(self):
        alt = self._mk("alt/coursemeta.tex", "\\meta{bank-path}{Bank/bank.tex}\n")
        self._mk("alt/Bank/bank.tex",
                 "\\begin{problem}{alt_a}[topic=x]s\\end{problem}\n")
        self.assertEqual(bank_parser.coursemeta_bank_path(alt),
                         os.path.join(self.root, "alt", "Bank", "bank.tex"))

    def test_no_bank_path_key_is_none(self):
        cm = self._mk("nobank/coursemeta.tex",
                      "\\metasetup{ course-number = 1 }\n")
        self.assertIsNone(bank_parser.coursemeta_bank_path(cm))


class StartupTests(unittest.TestCase):
    """main() turns launch-time failures into a clean message + exit instead of
    an uncaught traceback (mistyped path, bad --port, port already in use)."""

    def _exam(self):
        fd, path = tempfile.mkstemp(suffix=".tex")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(EXAM_BARE)
        self.addCleanup(lambda: os.path.isfile(path) and os.remove(path))
        return path

    def test_missing_file_exits_cleanly(self):
        d = tempfile.mkdtemp(prefix="texam-missing-")
        missing = os.path.join(d, "nope.tex")
        with self.assertRaises(SystemExit):
            texam.main(["texam.py", missing])

    def test_bad_port_arg_exits_cleanly(self):
        exam = self._exam()
        with self.assertRaises(SystemExit):
            texam.main(["texam.py", exam, "--no-open",
                              "--port", "notaport"])

    def test_port_in_use_exits_cleanly(self):
        exam = self._exam()
        orig_avail = bank_render.available
        orig_server = texam.ThreadingHTTPServer
        bank_render.available = lambda: False        # keep the renderer out of it
        texam.ThreadingHTTPServer = _bind_fails
        try:
            with self.assertRaises(SystemExit):
                texam.main(["texam.py", exam, "--no-open"])
        finally:
            bank_render.available = orig_avail
            texam.ThreadingHTTPServer = orig_server


def _bind_fails(*_a, **_k):
    raise OSError("address already in use (simulated)")


class ParallelPrewarmTests(unittest.TestCase):
    """prewarm renders the whole bank across a pool of threads, not one at a
    time; every problem is rendered once and on_done fires for each."""

    def test_pool_renders_all_across_threads(self):
        import threading
        import time
        probs = [bank_parser.Problem("p%d" % i, "", "b.tex", 0, "", "stem")
                 for i in range(6)]
        lock = threading.Lock()
        rendered, threads_seen = [], set()

        def stub(p, show_solution=True, use_cache=True):
            time.sleep(0.05)                 # hold the slot so workers overlap
            with lock:
                rendered.append(p.id)
                threads_seen.add(threading.current_thread().name)
            return "<svg></svg>"

        done = []
        orig = bank_render.render_svg
        bank_render.render_svg = stub
        try:
            ts = bank_render.prewarm(probs, on_done=done.append, workers=3)
            for t in ts:
                t.join(timeout=5)
        finally:
            bank_render.render_svg = orig

        self.assertEqual(sorted(rendered), sorted(p.id for p in probs))
        self.assertEqual(sorted(done), sorted(p.id for p in probs))
        self.assertGreaterEqual(len(threads_seen), 2)   # genuinely parallel

    def test_empty_bank_is_noop(self):
        self.assertEqual(bank_render.prewarm([]), [])


class RevealTests(unittest.TestCase):
    """reveal_in_editor turns a 0-based bank line into subl's 1-based
    file:line target and launches it."""

    def test_builds_target_and_launches(self):
        calls = []
        orig_find, orig_popen = texam._find_subl, texam.subprocess.Popen
        texam._find_subl = lambda: "subl"
        texam.subprocess.Popen = lambda argv, **k: calls.append(argv)
        try:
            target = texam.reveal_in_editor("C:/x/Bank/ch5.tex", 456)
        finally:
            texam._find_subl, texam.subprocess.Popen = orig_find, orig_popen
        self.assertEqual(target, "C:/x/Bank/ch5.tex:457")     # 0-based -> 1-based
        self.assertEqual(calls, [["subl", "C:/x/Bank/ch5.tex:457"]])

    def test_without_subl_raises(self):
        orig = texam._find_subl
        texam._find_subl = lambda: None
        try:
            with self.assertRaises(RuntimeError):
                texam.reveal_in_editor("x.tex", 0)
        finally:
            texam._find_subl = orig


class UndoRedoTests(unittest.TestCase):
    """Whole-file snapshot undo/redo restores the exam exactly and reports the
    action label."""

    def setUp(self):
        texam._undo.clear(); texam._redo.clear()
        fd, self.path = tempfile.mkstemp(suffix=".tex"); os.close(fd)
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(EXAM)                       # 2 FR entries
        texam.CTX["exam"] = self.path
        self.addCleanup(lambda: os.path.isfile(self.path) and os.remove(self.path))

    def _args(self):
        return [e["arg"] for e in exam_writer.public_entries(
            texam.read_exam(self.path)[0])]

    def test_roundtrip(self):
        before = self._args()
        text, nl = texam.read_exam(self.path)     # mimic _api_add's record+mutate
        texam._record(text, nl, "add frac-lim")
        texam.write_exam(self.path, exam_writer.add_problem(text, "frac-lim", False), nl)
        self.assertEqual(len(self._args()), 3)

        self.assertEqual(texam.history_step(redo=False), "add frac-lim")
        self.assertEqual(self._args(), before)    # exact restore
        self.assertEqual(texam.history_step(redo=True), "add frac-lim")
        self.assertEqual(len(self._args()), 3)
        self.assertIsNone(texam.history_step(redo=True))   # nothing left to redo

    def test_empty_stack_returns_none(self):
        self.assertIsNone(texam.history_step(redo=False))

    def test_new_edit_voids_redo(self):
        text, nl = texam.read_exam(self.path)
        texam._record(text, nl, "add a")
        texam.history_step(redo=False)            # now redo has one entry
        self.assertEqual(len(texam._redo), 1)
        texam._record(*texam.read_exam(self.path), "add b")   # a fresh edit
        self.assertEqual(len(texam._redo), 0)     # redo voided


class RenderUnitTests(unittest.TestCase):
    """bank_render helpers that need no TeX toolchain."""

    def _bank(self):
        fd, p = tempfile.mkstemp(suffix=".tex"); os.close(fd)
        self.addCleanup(lambda: os.path.isfile(p) and os.remove(p))
        return p

    def test_is_complete_svg(self):
        self.assertTrue(bank_render._is_complete_svg("<svg x><g/></svg>"))
        self.assertFalse(bank_render._is_complete_svg(""))
        self.assertFalse(bank_render._is_complete_svg("<svg x>truncated"))   # no </svg>
        self.assertFalse(bank_render._is_complete_svg("plain text"))

    def test_cache_path_deterministic_tagged_sanitized(self):
        b = self._bank()
        a1 = bank_render._cache_path(b, "p1", True)
        a2 = bank_render._cache_path(b, "p1", True)
        nos = bank_render._cache_path(b, "p1", False)
        self.assertEqual(a1, a2)                       # deterministic
        self.assertNotEqual(a1, nos)                   # solution flag matters
        self.assertTrue(a1.endswith(".sol.svg"))
        self.assertTrue(nos.endswith(".nosol.svg"))
        weird = os.path.basename(bank_render._cache_path(b, "a/b c:d", True))
        for ch in ("/", " ", ":"):
            self.assertNotIn(ch, weird)                # id sanitized into the name

    def test_harness_env_and_body(self):
        fr = bank_render._harness("bank.tex", "pid-x", False)
        self.assertIn("\\begin{problems}*", fr)
        self.assertIn("\\problem{pid-x}", fr)
        self.assertIn("\\loadbank{bank.tex}", fr)
        self.assertIn("\\begin{mcproblems}*", bank_render._harness("b.tex", "y", True))

    def test_available_mocked(self):
        orig = bank_render._which
        try:
            bank_render._which = lambda n: "x" if n in ("lualatex", "pdftocairo") else None
            self.assertTrue(bank_render.available())
            bank_render._which = lambda n: "x" if n == "lualatex" else None  # no converter
            self.assertFalse(bank_render.available())
        finally:
            bank_render._which = orig

    def test_render_lock_keyed(self):
        lk = bank_render._render_lock("k1")
        self.assertIs(lk, bank_render._render_lock("k1"))       # same key -> same lock
        self.assertIsNot(lk, bank_render._render_lock("k2"))    # different key -> new lock

    def test_texinputs_junction_vs_fallback(self):
        orig = os.path.isdir
        try:
            os.path.isdir = lambda p: p == bank_render.JUNCTION or orig(p)
            self.assertEqual(bank_render._texinputs("/some/bank"),
                             bank_render.TEXINPUTS_JUNCTION)
            os.path.isdir = lambda p: False if p == bank_render.JUNCTION else orig(p)
            self.assertIn("..", bank_render._texinputs("/some/bank"))   # relative fallback
        finally:
            os.path.isdir = orig

    def test_quiet_remove_missing_is_silent(self):
        bank_render._quiet_remove(os.path.join(tempfile.gettempdir(), "no_such_xyz.tmp"))


class ParserEdgeTests(unittest.TestCase):
    """bank_parser corner cases beyond the happy path."""

    def _dir(self):
        return tempfile.mkdtemp(prefix="texam-parse-")

    def _w(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_duplicate_id_first_wins_and_flags(self):
        d = self._dir(); bank = os.path.join(d, "bank.tex")
        self._w(bank, "\\begin{problem}{dup}[topic=a]FIRST\\end{problem}\n"
                      "\\begin{problem}{dup}[topic=b]SECOND\\end{problem}\n")
        probs = bank_parser.scan_problems([bank])
        self.assertEqual(len(probs), 1)
        self.assertEqual(probs[0].topic, "a")          # first definition wins
        self.assertTrue(probs[0].duplicate)            # collision flagged

    def test_tex_root_directive(self):
        d = self._dir()
        self._w(os.path.join(d, "root.tex"), "root body")
        child = os.path.join(d, "child.tex")
        self._w(child, "% !TeX root = root.tex\nchild body")
        root, text = bank_parser.resolve_root(child, bank_parser._read(child))
        self.assertEqual(os.path.basename(root), "root.tex")
        self.assertEqual(text, "root body")

    def test_choices_flags_and_text(self):
        items = bank_parser.parse_choices("\\cchoice right \\choice wrong \\fchoice forced")
        self.assertEqual([i["correct"] for i in items], [True, False, False])
        self.assertEqual(items[0]["text"], "right")

    def test_oneparchoices_detected(self):
        stem, ch, cenv, sol, is_mc = bank_parser._split_body(
            "stem \\begin{oneparchoices}\\cchoice a\\choice b\\end{oneparchoices}")
        self.assertTrue(is_mc); self.assertEqual(cenv, "oneparchoices")

    def test_solution_excised_before_choices(self):
        stem, ch, cenv, sol, is_mc = bank_parser._split_body(
            "STEM \\begin{choices}\\cchoice a\\choice b\\end{choices}"
            " \\begin{solution} SOLTEXT \\end{solution}")
        self.assertTrue(is_mc); self.assertEqual(sol, "SOLTEXT")
        self.assertNotIn("cchoice", stem); self.assertNotIn("SOLTEXT", stem)

    def test_solution_alone_is_not_mc(self):
        _s, _c, _e, sol, is_mc = bank_parser._split_body(
            "stem \\begin{solution} x \\end{solution}")
        self.assertFalse(is_mc); self.assertEqual(sol, "x")

    def test_parse_meta_trims_and_drops_bare(self):
        m = bank_parser.parse_meta("topic = a, section=1.2 , junk , k=v=w")
        self.assertEqual(m["topic"], "a")
        self.assertEqual(m["section"], "1.2")
        self.assertNotIn("junk", m)
        self.assertEqual(m["k"], "v=w")               # split on first = only

    def test_bank_path_brace_wrapped(self):
        d = self._dir()
        self._w(os.path.join(d, "B", "bank.tex"), "")
        cm = os.path.join(d, "coursemeta.tex")
        self._w(cm, "\\metasetup{ bank-path = {B/bank.tex} }\n")
        self.assertEqual(bank_parser.coursemeta_bank_path(cm),
                         os.path.join(d, "B", "bank.tex"))

    def test_bank_path_missing_file_is_none(self):
        d = self._dir()
        cm = os.path.join(d, "coursemeta.tex")
        self._w(cm, "\\metasetup{ bank-path = nope/bank.tex }\n")
        self.assertIsNone(bank_parser.coursemeta_bank_path(cm))

    def test_bank_path_ignores_commented_key(self):
        d = self._dir()
        self._w(os.path.join(d, "R", "bank.tex"), "")
        cm = os.path.join(d, "coursemeta.tex")
        self._w(cm, "% bank-path = old/bank.tex\n\\metasetup{ bank-path = R/bank.tex }\n")
        self.assertEqual(bank_parser.coursemeta_bank_path(cm),
                         os.path.join(d, "R", "bank.tex"))

    def test_loadbank_cycle_terminates(self):
        d = self._dir()
        self._w(os.path.join(d, "a.tex"), "\\loadbank{b.tex}\n\\begin{problem}{pa}[topic=x]s\\end{problem}\n")
        self._w(os.path.join(d, "b.tex"), "\\loadbank{a.tex}\n\\begin{problem}{pb}[topic=y]s\\end{problem}\n")
        srcs = bank_parser.problem_sources(os.path.join(d, "a.tex"),
                                           bank_parser._read(os.path.join(d, "a.tex")))
        self.assertEqual(sorted(os.path.basename(s) for s in srcs), ["a.tex", "b.tex"])

    def test_expand_metadir_windows_backslashes(self):
        self.assertEqual(
            bank_parser._expand_metadir("\\GetCourseMetaDir Bank/ch.tex", "C:\\c\\Su 26"),
            "C:/c/Su 26/Bank/ch.tex")

    def test_importproblem_and_sibling_bank(self):
        d = self._dir()
        self._w(os.path.join(d, "extra.tex"), "\\begin{problem}{ext}[topic=z]s\\end{problem}\n")
        self._w(os.path.join(d, "bank.tex"), "\\begin{problem}{sib}[topic=w]s\\end{problem}\n")
        doc = os.path.join(d, "exam.tex")
        text = "\\importproblem{extra.tex}{}\n"
        self._w(doc, text)
        names = [os.path.basename(s) for s in bank_parser.problem_sources(doc, text)]
        self.assertIn("extra.tex", names)      # \importproblem target resolved
        self.assertIn("bank.tex", names)       # sibling bank.tex auto-default

    def test_scan_skips_missing_files(self):
        self.assertEqual(bank_parser.scan_problems(["/no/such/file.tex"]), [])

    def test_read_missing_returns_none(self):
        self.assertIsNone(bank_parser._read("/no/such/file.tex"))

    def test_strip_comments_respects_escaped_percent(self):
        out = bank_parser.strip_comments("a \\% keep % drop\nb")
        self.assertIn("\\% keep", out)
        self.assertNotIn("drop", out)
        self.assertEqual(out.count("\n"), 1)   # line count preserved


if __name__ == "__main__":
    unittest.main(verbosity=2)
