"""test_bank_studio.py -- dependency-free tests for Bank Studio.

Covers the bank parser (region split, MC detection, meta, points, comment
handling) and the exam writer (add / remove / reorder, environment creation).
No TeX toolchain required.  Server routing and the real-engine renderer are
tested in later, tool-gated additions.

    python test_bank_studio.py
"""

import os
import tempfile
import unittest

import bank_parser
import bank_studio
import exam_writer


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
        d = tempfile.mkdtemp(prefix="bankstudio-test-")
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
        text, nl = bank_studio.read_exam(p)
        self.assertEqual(nl, "\n")
        bank_studio.write_exam(p, text + "d\n", nl)
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"a\nb\nc\nd\n")

    def test_newline_preserved_crlf(self):
        p = self._tmp(b"a\r\nb\r\n")
        text, nl = bank_studio.read_exam(p)
        self.assertEqual(nl, "\r\n")
        self.assertEqual(text, "a\nb\n")           # normalized in memory
        bank_studio.write_exam(p, text + "c\n", nl)
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"a\r\nb\r\nc\r\n")  # CRLF restored

    def test_arg_for_modes(self):
        prob = bank_parser.Problem("pid", "topic=alg", "b.tex", 0, "", "stem")
        self.assertEqual(bank_studio._arg_for(prob, "id"), "pid")
        self.assertEqual(bank_studio._arg_for(prob, "filter"), "topic=alg")
        notopic = bank_parser.Problem("q", "", "b.tex", 0, "", "stem")
        self.assertEqual(bank_studio._arg_for(notopic, "filter"), "q")  # falls back

    def test_exam_state(self):
        bank_studio.CTX["exam"] = self._tmp(EXAM.encode())
        st = bank_studio.exam_state()
        self.assertTrue(st["exists"])
        self.assertEqual(len(st["entries"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
