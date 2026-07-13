#!/usr/bin/env python
r"""Headless coverage for the plugin feel/UX cluster (P1–P6 bits that are pure).

Stubs sublime/sublime_plugin, then exercises:
  * texlib._status_line -- the status-bar spinner line (P1) incl. the
    "(+N more building)" parallel tail (P4) and step truncation.
  * texlib_editor.DELEGATIONS + command classes -- each TeXLib editor command
    maps to the intended LaTeXTools command (P2), and Edit Settings exists (P3).

Run:  python Sublime/test_texlib_editor.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

# Minimal sublime / sublime_plugin stubs (WindowCommand is subclassed).
from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("WindowCommand", "EventListener", "ViewEventListener")

import texlib          # noqa: E402
import texlib_editor   # noqa: E402


ok = True

# --- P1: spinner status line ------------------------------------------------
one = texlib._status_line(0, "exam-01.tex", "lualatex run 1", 1)
ok &= check("TeXLib: exam-01.tex" in one, "status: names the document")
ok &= check("lualatex run 1" in one, "status: shows the current step")
ok &= check(one[0] in texlib.SPIN_FRAMES, "status: starts with a spinner frame")
ok &= check("more building" not in one, "status: no parallel tail for a lone build")

# frame index wraps around the spinner
wrapped = texlib._status_line(len(texlib.SPIN_FRAMES), "a", "s", 1)
ok &= check(wrapped[0] == texlib.SPIN_FRAMES[0], "status: frame index wraps")

# --- P4: parallel tail ------------------------------------------------------
multi = texlib._status_line(0, "quiz.tex", "biber", 3)
ok &= check("(+2 more building)" in multi, "status: parallel tail counts peers")

# --- P1: defaults + truncation ----------------------------------------------
none_step = texlib._status_line(0, "d.tex", None, 1)
ok &= check("starting…" in none_step, "status: falls back to 'starting…'")
long_step = texlib._status_line(0, "d.tex", "x" * 200, 1)
ok &= check(len(long_step) < 130, "status: long step is truncated")

# --- P2: editor delegations -------------------------------------------------
ok &= check(texlib_editor.DELEGATIONS.get("texlib_word_count") == "latextools_texcount",
            "delegate: word count -> latextools_texcount")
ok &= check(texlib_editor.DELEGATIONS.get("texlib_toc") == "latextools_toc_quickpanel",
            "delegate: TOC -> latextools_toc_quickpanel")
ok &= check(texlib_editor.DELEGATIONS.get("texlib_jump_to_ref") == "latextools_jumpto_anywhere",
            "delegate: jump-to-ref -> latextools_jumpto_anywhere")
ok &= check(texlib_editor.TexlibWordCountCommand.latextools_command
            == texlib_editor.DELEGATIONS["texlib_word_count"],
            "delegate: command class matches the mapping")

# --- P3: edit settings ------------------------------------------------------
ok &= check(hasattr(texlib_editor, "TexlibEditSettingsCommand"),
            "P3: TexlibEditSettingsCommand present")

report(ok)
