"""Blocked-institution bookkeeping in thesis_institutions.py.

The queue is the only reason this file exists. `next` returns the first
institution with no profile, so an unresearchable one is served forever unless
it is blocked -- and a block that fails to load silently un-blocks it rather
than erroring, which looks like the routine looping on one school for no
reason. That failure is invisible in a build and cheap to catch here.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import thesis_institutions as ti


class BlockedSlugsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._blocked = ti.BLOCKED
        ti.BLOCKED = os.path.join(self.tmp, "blocked")
        self.addCleanup(setattr, ti, "BLOCKED", self._blocked)

    def write(self, name, body):
        os.makedirs(ti.BLOCKED, exist_ok=True)
        with open(os.path.join(ti.BLOCKED, name), "w", encoding="utf-8",
                  newline="") as f:
            f.write(body)

    def test_absent_directory_is_empty_not_an_error(self):
        # A fresh checkout has blocked nothing; `next` must still run.
        self.assertEqual(ti.blocked_slugs(), {})

    def test_reads_one_file_per_slug(self):
        self.write("alpha-university.csv",
                   "slug,date,reason\nalpha-university,2026-09-08,gone\n")
        self.write("beta-college.csv",
                   "slug,date,reason\nbeta-college,2026-09-08,login\n")
        got = ti.blocked_slugs()
        self.assertEqual(sorted(got), ["alpha-university", "beta-college"])
        self.assertEqual(got["beta-college"]["reason"], "login")

    def test_reason_may_carry_commas_quotes_and_newlines(self):
        # Reasons are prose quoted from a catalog, not identifiers.
        reason = 'says "12-point", double-spaced\nand nothing else'
        self.write("gamma-institute.csv",
                   'slug,date,reason\ngamma-institute,2026-09-08,'
                   '"says ""12-point"", double-spaced\nand nothing else"\n')
        self.assertEqual(ti.blocked_slugs()["gamma-institute"]["reason"],
                         reason)

    def test_non_csv_files_are_ignored(self):
        # A README in the directory is documentation, not a block.
        self.write("alpha-university.csv",
                   "slug,date,reason\nalpha-university,2026-09-08,gone\n")
        self.write("README.md", "# blocked\n")
        self.assertEqual(list(ti.blocked_slugs()), ["alpha-university"])

    def test_filename_disagreeing_with_row_is_fatal(self):
        # Otherwise the block is reachable under a slug `next` never consults,
        # and the institution silently returns to the queue.
        self.write("alpha-university.csv",
                   "slug,date,reason\nmistyped-university,2026-09-08,gone\n")
        with self.assertRaises(SystemExit):
            ti.blocked_slugs()

    def test_header_only_file_is_fatal(self):
        self.write("alpha-university.csv", "slug,date,reason\n")
        with self.assertRaises(SystemExit):
            ti.blocked_slugs()

    def test_blocked_path_is_the_slug(self):
        self.assertEqual(os.path.basename(ti.blocked_path("alpha-university")),
                         "alpha-university.csv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
