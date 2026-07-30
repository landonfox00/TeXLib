# texlib_complete.py
# ============================================================================
# TeXLib -- completions LaTeXTools can't provide (it doesn't know our macros).
#
#   * After a backslash, offer the TeXLib bank/variable macros (\getproblem,
#     \setvar, \picklist, \loadbank, ...) plus the exam environments
#     (problem/parts/questions/solution/versions) as snippet completions --
#     the popup's only content once LaTeXTools' completions + snippets are
#     suppressed (see LaTeXTools/LaTeX .sublime-settings).
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
# double backslash (guarded by test_texlib_complete.py). The trailing block
# mirrors the environment snippets in Sublime/texlib/snippets/: those still
# tab-expand, but auto_complete_include_snippets=false hides them (and all of
# LaTeXTools') from the popup, so we re-offer them here as plugin completions.
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
    ("problem",
     "begin{problem}{${1:id}}[${2:topic=}]\n\t${0:problem statement}\n\\end{problem}",
     "problem environment"),
    ("parts",
     "begin{parts}\n\t\\part[${1:pts}] ${2:first part}\n"
     "\t\\part[${3:pts}] ${0:second part}\n\\end{parts}",
     "parts environment"),
    ("questions",
     "begin{questions}\n\t\\question ${0:question text}\n\\end{questions}",
     "questions environment"),
    ("solution",
     "begin{solution}\n\t${0:answer}\n\\end{solution}",
     "solution environment"),
    ("versions", "versions{${1:A, B, C}}", "declare exam versions"),
]

# Cursor sits inside the braces of a by-id retrieval command.
PROBLEM_CMD_RE = re.compile(r"\\(?:getproblem|useproblem|reqproblem)\{[^}]*$")

# --- coursemeta key completions (D5) ----------------------------------------
# Inside a \metasetup{ ... } block, at a key position, offer the course-metadata
# field keys (course-number, lecture-days, exam1-date, ...).
META_KEY_RE = re.compile(r"\\meta_create_var:nn\s*\{\s*([A-Za-z][\w-]*)\s*\}")
META_ALIAS_RE = re.compile(r"(?m)^\s*([A-Za-z][\w-]*)\s+\.tl_gset:c")
# A key position: line start (own-line key) or just after a '{' / ',' separator,
# with the partial key being typed at the end.
KEYPOS_RE = re.compile(r"(?:^|[,{])\s*[A-Za-z][\w-]*$")
_META_KEYS_CACHE = [None]


def coursemeta_keys(sty_text):
    """Field keys declared in course-metadata.sty: the \\meta_create_var canonical
    keys plus the .tl_gset:c alias keys. Sorted, unique."""
    keys = set(META_KEY_RE.findall(sty_text))
    keys |= set(META_ALIAS_RE.findall(sty_text))
    return sorted(keys)


def in_metasetup(text_before):
    r"""True if the last \metasetup{ before the cursor is still open (its brace
    depth has not returned to zero)."""
    i = text_before.rfind("\\metasetup{")
    if i == -1:
        return False
    depth = 1
    for ch in text_before[i + len("\\metasetup{"):]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return False
    return True


def _key_position(left_full):
    return bool(KEYPOS_RE.search(left_full))


def _repo_root():
    settings = sublime.load_settings("TeXLib.sublime-settings")
    override = settings.get("class_source")
    if override:
        return override
    plugin_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.dirname(os.path.dirname(plugin_dir))


def _meta_keys():
    if _META_KEYS_CACHE[0] is None:
        path = os.path.join(_repo_root(), "course-metadata.sty")
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                _META_KEYS_CACHE[0] = coursemeta_keys(fh.read())
        except OSError:
            _META_KEYS_CACHE[0] = []
    return _META_KEYS_CACHE[0]


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

        # D5: coursemeta field keys inside a \metasetup{ ... } block.
        if _key_position(left_full):
            before = view.substr(sublime.Region(max(0, pt - 4000), pt))
            if in_metasetup(before):
                keys = _meta_keys()
                if keys:
                    return ([sublime.CompletionItem.snippet_completion(
                                k, k + " = ${1}",
                                annotation="TeXLib · coursemeta key")
                             for k in keys], sublime.INHIBIT_WORD_COMPLETIONS)

        ctx = completion_context(left_full, char_before)
        if ctx == "ids":
            return self._problem_ids(view)
        if ctx == "macros":
            # INHIBIT_WORD_COMPLETIONS keeps Sublime's buffer-word guesses out of
            # the \-popup; ranking within our list stays Sublime's default fuzzy
            # score (no INHIBIT_REORDER).
            return ([
                sublime.CompletionItem.snippet_completion(
                    trig, snip, annotation="TeXLib · " + ann)
                for (trig, snip, ann) in MACROS
            ], sublime.INHIBIT_WORD_COMPLETIONS)
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
