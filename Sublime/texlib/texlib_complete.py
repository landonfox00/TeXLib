# texlib_complete.py
# ============================================================================
# TeXLib -- completions LaTeXTools can't provide (it doesn't know our macros).
#
#   * After a backslash, offer the TeXLib bank/variable macros (\getproblem,
#     \setvar, \picklist, \loadbank, ...) as snippet completions.
#   * Inside \getproblem{...} / \useproblem{...} / \reqproblem{...}, offer the
#     actual problem IDS available to the document, reusing the bank scanner.
#
# Own top-level file (hot-reloads alone). Reuses texlib_bank's scan.
# ============================================================================

import os
import re

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_bank
except ImportError:
    import texlib_bank

# TeXLib macros: (trigger, snippet-without-leading-backslash, annotation). The
# backslash is already typed, so the completion inserts only the rest -- no
# double backslash.
MACROS = [
    ("getproblem", "getproblem{$1}", "retrieve a bank problem by id/filter"),
    ("useproblem", "useproblem{$1}", "alias of \\getproblem"),
    ("loadbank", "loadbank{$1}", "load a problem-bank file"),
    ("importproblem", "importproblem{$1}{$2}", "import a standalone problem"),
    ("setvar", "setvar{$1}{$2}", "set a variable"),
    ("setrng", "setrng{$1}{$2}{$3}", "set a random-range variable"),
    ("calcvar", "calcvar{$1}{$2}", "compute a variable"),
    ("get", "get{$1}", "expand a variable"),
    ("picklist", "picklist{$1}", "pick from a list"),
    ("pickrange", "pickrange{$1}{$2}", "pick from a range"),
    ("setexamseed", "setexamseed{$1}", "seed the version RNG"),
]

# Cursor sits inside the braces of a by-id retrieval command.
PROBLEM_CMD_RE = re.compile(r"\\(?:getproblem|useproblem|reqproblem)\{[^}]*$")


def completion_context(left_full, char_before_prefix):
    """Pure classifier. left_full = line text up to the cursor (incl. the prefix
    being typed); char_before_prefix = the char just before that prefix.
    Returns 'ids' (inside \\getproblem{...}), 'macros' (right after a \\), or
    None."""
    if PROBLEM_CMD_RE.search(left_full):
        return "ids"
    if char_before_prefix == "\\":
        return "macros"
    return None


class TexlibCompletions(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        pt = locations[0]
        if not view.match_selector(pt, "text.tex.latex"):
            return None
        line_begin = view.line(pt).begin()
        left_full = view.substr(sublime.Region(line_begin, pt))
        bp = pt - len(prefix) - 1
        char_before = view.substr(bp) if bp >= line_begin else ""

        ctx = completion_context(left_full, char_before)
        if ctx == "ids":
            return self._problem_ids(view)
        if ctx == "macros":
            return [
                sublime.CompletionItem.snippet_completion(
                    trig, snip, annotation="TeXLib · " + ann)
                for (trig, snip, ann) in MACROS
            ]
        return None

    def _problem_ids(self, view):
        doc_path, doc_text = texlib_bank._resolve_doc(view)
        if not doc_path:
            return None
        problems = texlib_bank.scan_problems(
            texlib_bank.problem_sources(doc_path, doc_text))
        if not problems:
            return None
        items = [
            sublime.CompletionItem.snippet_completion(
                p["id"], p["id"],
                annotation="problem · " + (p["attrs"] or os.path.basename(p["file"])))
            for p in problems
        ]
        return (items, sublime.INHIBIT_WORD_COMPLETIONS)


def plugin_loaded():
    print("TeXLib completions loaded.")
