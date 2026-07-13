#!/usr/bin/env python
r"""Coverage for the doc-context locators (texlib/texlib_locate.py).

No Sublime, no TeX: stubs sublime/sublime_plugin, then checks find_coursemeta's
upward walk and that aux_dir_for reproduces the build brain's key
(md5(tex_root)[:12] under the temp dir).

Run:  python Sublime/test_texlib_locate.py
"""
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("WindowCommand")

import texlib_locate  # noqa: E402


ok = True

# find_coursemeta: walks up to 4 parents.
with tempfile.TemporaryDirectory() as root:
    deep = os.path.join(root, "a", "b", "c")
    os.makedirs(deep)
    cm = os.path.join(root, "a", "coursemeta.tex")
    open(cm, "w").close()
    ok &= check(texlib_locate.find_coursemeta(deep) == cm,
                "find_coursemeta: found two levels up")
    ok &= check(texlib_locate.find_coursemeta(os.path.join(root, "a")) == cm,
                "find_coursemeta: found in the start dir itself")

with tempfile.TemporaryDirectory() as root:
    ok &= check(texlib_locate.find_coursemeta(root) is None,
                "find_coursemeta: None when absent")

# aux_dir_for: reproduces the brain's key exactly.
sample = "C:/Users/Landon/texlib-sublime-wt/examples/Math181-Fall2026/exam-01.tex"
expect_key = hashlib.md5(sample.encode("utf-8")).hexdigest()[:12]
got = texlib_locate.aux_dir_for(sample)
ok &= check(os.path.basename(got) == expect_key,
            "aux_dir_for: key is md5(tex_root)[:12]")
ok &= check(got == os.path.join(tempfile.gettempdir(), "texlib-aux", expect_key),
            "aux_dir_for: <tempdir>/texlib-aux/<key>")
ok &= check(len(os.path.basename(got)) == 12 and all(
                c in "0123456789abcdef" for c in os.path.basename(got)),
            "aux_dir_for: 12 hex chars")

report(ok)
