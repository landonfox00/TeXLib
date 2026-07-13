# texlib_topic.py
# ============================================================================
# TeXLib -- insert a bank problem by topic (D1).
#
# The bank stores per-problem [attrs] like [topic=limit, section=2.3]. This
# command scans the bank (reusing texlib_bank), lets you pick a topic, then a
# problem within that topic, and inserts \getproblem{id} at the cursor. There is
# no engine-level "\problem{topic=X}" filter macro, so we filter the scanned
# definitions ourselves -- honest and immediate.
#
# Own top-level file (hot-reloads alone). Pure helpers (parse_attrs / topics_of /
# problems_with) are unit-tested headlessly.
# ============================================================================

import re

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_bank
except ImportError:
    import texlib_bank

# key=value inside an [attrs] blob; value runs to the next comma.
ATTR_RE = re.compile(r"([A-Za-z][\w-]*)\s*=\s*([^,]+)")


def parse_attrs(attrs):
    """'topic=limit, section=2.3' -> {'topic': 'limit', 'section': '2.3'}."""
    out = {}
    for m in ATTR_RE.finditer(attrs or ""):
        out[m.group(1).strip().lower()] = m.group(2).strip()
    return out


def topics_of(problems, key="topic"):
    """Sorted distinct values of `key` across problems, each with its count, plus
    a trailing '(no <key>)' bucket if any problem lacks it. Returns a list of
    (label, value) where value is None for the missing bucket."""
    counts = {}
    missing = 0
    for p in problems:
        v = parse_attrs(p.get("attrs", "")).get(key)
        if v:
            counts[v] = counts.get(v, 0) + 1
        else:
            missing += 1
    rows = [("%s  (%d)" % (v, n), v) for v, n in sorted(counts.items())]
    if missing:
        rows.append(("(no %s)  (%d)" % (key, missing), None))
    return rows


def problems_with(problems, key, value):
    """Problems whose attribute `key` equals `value` (value None -> lacking it)."""
    out = []
    for p in problems:
        v = parse_attrs(p.get("attrs", "")).get(key)
        if (value is None and not v) or (value is not None and v == value):
            out.append(p)
    return out


class TexlibInsertByTopicCommand(sublime_plugin.WindowCommand):
    r"""Pick a topic, then a problem within it; insert \getproblem{id}."""

    def run(self):
        view = self.window.active_view()
        doc_path, doc_text = texlib_bank._resolve_doc(view)
        if not doc_path:
            sublime.status_message("TeXLib: save the document first.")
            return
        problems = texlib_bank.scan_problems(
            texlib_bank.problem_sources(doc_path, doc_text))
        if not problems:
            sublime.status_message(
                "TeXLib: no \\begin{problem}{...} in this document or its bank(s).")
            return
        topics = topics_of(problems)
        if len(topics) == 1 and topics[0][1] is None:
            sublime.status_message(
                "TeXLib: bank problems carry no topic= attribute.")
            return

        def pick_topic(i):
            if i < 0:
                return
            value = topics[i][1]
            subset = problems_with(problems, "topic", value)
            rows = [[p["id"], p["attrs"] or "(no attrs)"] for p in subset]

            def pick_problem(j):
                if j < 0:
                    return
                self.window.active_view().run_command(
                    "insert", {"characters": "\\getproblem{%s}" % subset[j]["id"]})

            # Re-entering a quick panel from its own callback needs a tick.
            sublime.set_timeout(
                lambda: self.window.show_quick_panel(rows, pick_problem), 10)

        self.window.show_quick_panel(
            [[lbl, "topic"] for (lbl, _v) in topics], pick_topic)

    def is_enabled(self):
        return texlib_bank._is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib insert-by-topic loaded.")
