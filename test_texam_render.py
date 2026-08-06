"""test_texam_render.py -- real-engine render integration for TeXaM (tool-gated).

Unlike the stubbed render tests in test_texam.py, this drives the ACTUAL
pipeline -- lualatex compiles the preview harness and pdftocairo/dvisvgm makes
the SVG -- against the committed demo course.  It SOFT-SKIPS (exit 0) when the
toolchain is absent, mirroring the other integration suites, so it is safe on a
host without TeX Live.

    python test_texam_render.py
"""

import os
import unittest

import bank_parser
import bank_render

DEMO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "examples", "TeXam-Demo", "exam-01.tex")


@unittest.skipUnless(bank_render.available(),
                     "needs lualatex + pdftocairo/dvisvgm on PATH")
class RealRenderTests(unittest.TestCase):
    """Exercises the genuine render path end to end on the demo bank."""

    @classmethod
    def setUpClass(cls):
        _sources, probs = bank_parser.discover(DEMO)
        cls.by_id = {p.id: p for p in probs}
        cls.count = len(probs)

    def test_demo_bank_discovered(self):
        self.assertGreaterEqual(self.count, 18)
        for pid in ("lim-factor", "der-quotient-mc", "int-poly"):
            self.assertIn(pid, self.by_id)

    def test_free_response_renders_valid_svg(self):
        svg = bank_render.render_svg(self.by_id["lim-factor"], use_cache=False)
        self.assertTrue(bank_render._is_complete_svg(svg))
        self.assertIn("<svg", svg)

    def test_multiple_choice_renders_valid_svg(self):
        svg = bank_render.render_svg(self.by_id["der-quotient-mc"], use_cache=False)
        self.assertTrue(bank_render._is_complete_svg(svg))

    def test_cache_written_and_consistent(self):
        p = self.by_id["int-poly"]
        a = bank_render.render_svg(p, show_solution=False, use_cache=True)
        cache = bank_render._cache_path(p.source_file, p.id, False)
        self.assertTrue(os.path.isfile(cache) and os.path.getsize(cache) > 0)
        b = bank_render.render_svg(p, show_solution=False, use_cache=True)  # cache hit
        self.assertEqual(a, b)
        self.assertTrue(bank_render._is_complete_svg(a))

    def test_solution_variant_differs(self):
        p = self.by_id["lim-factor"]
        with_sol = bank_render.render_svg(p, show_solution=True, use_cache=False)
        without = bank_render.render_svg(p, show_solution=False, use_cache=False)
        self.assertTrue(bank_render._is_complete_svg(with_sol))
        self.assertNotEqual(with_sol, without)          # the worked solution shows

    def test_parallel_prewarm_real_toolchain(self):
        sample = [self.by_id[i] for i in ("lim-squeeze", "int-exp", "der-power")]
        for t in bank_render.prewarm(sample, workers=3):
            t.join(timeout=180)
        for p in sample:                                # each now a valid cached render
            self.assertTrue(bank_render._is_complete_svg(
                bank_render.render_svg(p, use_cache=True)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
