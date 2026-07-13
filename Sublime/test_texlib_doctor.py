#!/usr/bin/env python
r"""Coverage for Doctor render (N2) and the shadow-install warning (N3).

Stubs sublime/sublime_plugin, then exercises texlib_doctor.render_doctor (pure)
and texlib._shadow_warning_line (the one-time build-time nudge).

Run:  python Sublime/test_texlib_doctor.py
"""
import os
import sys
import types

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texlib"))

sys.modules["sublime"] = types.ModuleType("sublime")
_p = types.ModuleType("sublime_plugin")
_p.WindowCommand = object
_p.EventListener = object
sys.modules["sublime_plugin"] = _p

import texlib          # noqa: E402
import texlib_doctor   # noqa: E402
import texlib_texmf    # noqa: E402


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


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


texlib._shadow_warned[0] = False
# No texinputs preference -> never warn (the install is the intended path).
ok &= check(texlib._shadow_warning_line(_Settings({})) is None,
            "N3: no texinputs -> no warning")

# texinputs set + a shadow present -> warn once, then stay quiet.
texlib_texmf.shadows_checkout = lambda: True
texlib._shadow_warned[0] = False
first = texlib._shadow_warning_line(_Settings({"texinputs": ".;C:/repo//;"}))
ok &= check(first is not None and "shadow" in first.lower(),
            "N3: texinputs + shadow -> warns")
second = texlib._shadow_warning_line(_Settings({"texinputs": ".;C:/repo//;"}))
ok &= check(second is None, "N3: warns only once per session")

# texinputs set but no shadow -> no warning.
texlib_texmf.shadows_checkout = lambda: False
texlib._shadow_warned[0] = False
ok &= check(texlib._shadow_warning_line(_Settings({"texinputs": "x"})) is None,
            "N3: no shadow -> no warning")

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
