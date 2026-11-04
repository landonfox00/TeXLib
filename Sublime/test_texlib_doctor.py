#!/usr/bin/env python
r"""Coverage for Doctor render (N2), the shadow-install warning (N3), and
TEXINPUTS normalization.

Stubs sublime/sublime_plugin, then exercises texlib_doctor.render_doctor (pure),
texlib._shadow_warning_line (the one-time build-time nudge), and
texlib._resolve_texinputs (the empty-segment guarantee).

Run:  python Sublime/test_texlib_doctor.py
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

from _testkit import stub_sublime, check, report  # noqa: E402
stub_sublime("WindowCommand", "EventListener")

import texlib          # noqa: E402
import texlib_doctor   # noqa: E402
import texlib_texmf    # noqa: E402


ok = True

# --- N2: render_doctor verdict ---------------------------------------------
sections_ok = [("Engines:", [("lualatex", texlib_doctor.OK, "/bin/lualatex")])]
text, worst = texlib_doctor.render_doctor(sections_ok)
ok &= check(worst == texlib_doctor.OK and "All good" in text, "N2: all-OK verdict")
ok &= check("[ OK ]" in text and "lualatex" in text, "N2: renders status + tool")

sections_warn = [("X:", [("a", texlib_doctor.OK, ""), ("b", texlib_doctor.WARN, "!")])]
_t, worst2 = texlib_doctor.render_doctor(sections_warn)
ok &= check(worst2 == texlib_doctor.WARN, "N2: a WARN downgrades verdict to warn")

sections_fail = [("X:", [("b", texlib_doctor.WARN, ""), ("c", texlib_doctor.FAIL, "gone")])]
_t, worst3 = texlib_doctor.render_doctor(sections_fail)
ok &= check(worst3 == texlib_doctor.FAIL, "N2: a FAIL dominates the verdict")

# --- N3: shadow-install warning --------------------------------------------
class _Settings:
    def __init__(self, d):
        self._d = d

    def get(self, k, default=None):
        return self._d.get(k, default)


# Every check sets both inputs of the gate itself. The real ones read the
# machine: _derive_texinputs() walks up from texlib.py, and shadows_checkout()
# asks kpsewhich for TEXMFHOME, then falls back to ~/texmf. With the real pair
# the first check passed wherever no TeXLib copy was installed, whatever the
# gate did, and failed wherever one was.
_texmfhome_calls = []


def _no_texmfhome():
    _texmfhome_calls.append(1)
    return os.path.join(HERE, "no-such-texmf")


texlib_texmf.texmfhome = _no_texmfhome


def _n3(settings, derived, shadowed):
    """The warning line for these settings, with `derived` as the derived
    TEXINPUTS and `shadowed` as whether a copy is installed."""
    texlib._derive_texinputs = lambda: derived
    texlib_texmf.shadows_checkout = lambda: shadowed
    texlib._shadow_warned[0] = False
    return texlib._shadow_warning_line(_Settings(settings))


# No checkout path in play (no setting, nothing derivable) -> never warn, even
# with a copy installed.
ok &= check(_n3({}, "", True) is None, "N3: no texinputs -> no warning")

# A derived path counts as one in play. Gating on the setting alone would
# silence the warning for the users who configure nothing by hand.
derived = _n3({}, "." + os.pathsep + "/repo", True)
ok &= check(derived is not None and "shadow" in derived.lower(),
            "N3: derived texinputs + shadow -> warns")

# texinputs set + a shadow present -> warn once, then stay quiet.
first = _n3({"texinputs": ".;C:/repo//;"}, "", True)
ok &= check(first is not None and "shadow" in first.lower(),
            "N3: texinputs + shadow -> warns")
second = texlib._shadow_warning_line(_Settings({"texinputs": ".;C:/repo//;"}))
ok &= check(second is None, "N3: warns only once per session")

# texinputs set but no shadow -> no warning.
ok &= check(_n3({"texinputs": "x"}, "", False) is None,
            "N3: no shadow -> no warning")

ok &= check(not _texmfhome_calls,
            "N3: no check consulted the machine's TEXMFHOME")

# --- TEXINPUTS normalization -------------------------------------------------
# Without an empty segment kpathsea REPLACES its default path (texmf-dist drops
# out and luaotfload fatals at startup), so _resolve_texinputs must always leave
# one; a blank setting stays blank (inherit the process env).
sep = os.pathsep
ok &= check(texlib._resolve_texinputs([".", "C:/j"]) == "." + sep + "C:/j" + sep,
            "texinputs: list w/o empty segment gains a trailing separator")
ok &= check(texlib._resolve_texinputs([".", "C:/j", ""]) == "." + sep + "C:/j" + sep,
            "texinputs: explicit trailing empty segment not doubled")
ok &= check(texlib._resolve_texinputs("." + sep + sep + "C:/j")
            == "." + sep + sep + "C:/j",
            "texinputs: string with a doubled separator left untouched")
ok &= check(texlib._resolve_texinputs("") == "",
            "texinputs: blank stays blank (inherit process env)")

report(ok)
