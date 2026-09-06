r"""texlib_preamble_scan.py — decide which deferrable components a document can skip.

WHY THIS FILE EXISTS

Package loading, not typesetting, is what a TeXLib build spends its time on. On a
six-page notes document the class costs ~3.5s of a ~5.5s engine pass and the
document's own content costs ~0.25s, so the only lever that moves a build is
loading less. `texlib-corepkg.sty` exposes that lever as \TeXLibDefer: define
\TeXLibNo<Name> before \documentclass and the component never loads.

Asking authors to maintain those flags by hand would be a bad trade -- the flag
is invisible until the day someone adds a citation and gets an error that names
biblatex rather than the flag. So the flags are DERIVED: this module reads a
document and its whole \input tree and defers only what provably never appears.

THE SAFETY RULE

Loading is always correct; deferring is an optimisation. So every ambiguity
resolves toward loading:

  * A component is deferred only when NOTHING in the source tree matches any of
    its evidence patterns.
  * If any part of the tree cannot be read -- a missing \input, an unreadable
    file, a path built from a macro we cannot resolve -- NOTHING is deferred for
    that document. A partial scan is worthless, because the evidence could be in
    the part we failed to read.
  * The patterns are deliberately loose. A false positive costs a package load
    (the status quo); a false negative costs a broken build.

WHY ONLY texlib-thesis IS ON TIKZ_CLASSES

Because it is the only class where deferring tikz actually removes tikz.

The test that settles this is not "can the class build with \TeXLibNoTikz" --
all of them can -- but "is tikz still LOADED afterwards". Probed with
\@ifpackageloaded on a bare stub of every class, in a clean directory:

    class          tikz eager   tikz with \TeXLibNoTikz   tcolorbox
    texlib-thesis      N                 N                    N
    didactic           Y                 Y                    Y
    pset               Y                 Y                    Y
    report-card        Y                 Y                    N
    quiz               Y                 Y                    N
    autoexam           Y                 Y                    Y
    bank               Y                 Y                    N

Every teaching class reaches tcolorbox (directly, or through texlib-thmenv ->
texlib-theorems), and tcolorbox loads tikz itself, AFTER this bundle's deferral
has correctly skipped its own \RequirePackage{tikz}. So the flag is honoured and
changes nothing: the same packages end up in memory either way, and there is no
work to save.

didactic and pset were briefly added to this list on the strength of a 0.12s
measurement. That measurement was noise -- with identical packages loaded there
is nothing for it to have measured -- and they were removed again once the
package probe replaced the stopwatch. Do not re-add a class here on a timing
difference alone; probe what is loaded.

texlib-thesis is the exception because it loads no tcolorbox at all. Nothing in
that class draws: the only tikz in the whole Thesis tree is the decorative
committee-page frame in profiles/unr.tex, one profile of twenty-one, which asks
for tikz itself with \TeXLibLoadTikz.

The scan-visibility rule below still applies and is still necessary -- it is
just no longer sufficient. A class must ALSO shed tikz for inclusion to mean
anything.
"""

import io
import os
import re

# Components this module is willing to defer, and the evidence that forbids it.
#
# Each pattern is matched against the comment-stripped concatenation of the
# document and everything it inputs. One match anywhere keeps the component.
# Classes for which Tikz may be auto-deferred as well. See the module docstring:
# the test is whether a source scan can see every use of tikz, which is true for
# texlib-thesis and false for the tcolorbox-based teaching classes.
TIKZ_CLASSES = ("thesis", "texlib-thesis")

# Evidence that a document draws. Kept separate from DEFERRABLE because it
# applies only to the classes above.
TIKZ_PATTERNS = (
    r"\\begin\{tikzpicture\}",
    r"\\tikz\b",
    r"\\tikzset\b",
    r"\\usetikzlibrary\b",
    r"\\begin\{tikzcd\}",
    r"\\encircle\b",
    r"quiver",
    r"pgf",
    r"\\TeXLibLoadTikz\b",
)

_DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}")

DEFERRABLE = {
    # biblatex, +1.21s -- the most expensive load in the bundle.
    "Bib": (
        r"\\[a-zA-Z]*cite[a-zA-Z]*\b",      # \cite \autocite \textcite \nocite ...
        r"\\addbibresource\b",
        r"\\bibliography\b",
        r"\\printbibliography\b",
        r"\\printreferences\b",
        r"\\bibliographystyle\b",
        r"\\DeclareFieldFormat\b",
        r"\\TeXLibLoadBib\b",
    ),
    # pgfplots, +0.88s on top of tikz.
    "Plots": (
        r"\\begin\{(semilog[xy]|loglog|polar|ternary|group)?axis\}",
        r"\\addplot",
        r"\\pgfplots",
        r"pgfplots",
        r"\\begin\{groupplot\}",
        r"\\TeXLibLoadPlots\b",
    ),
    # siunitx, +0.18s.
    "Units": (
        r"\\SI\b", r"\\SIrange\b", r"\\SIlist\b",
        r"\\si\{", r"\\num\b", r"\\numlist\b", r"\\numrange\b",
        r"\\qty\b", r"\\qtyrange\b", r"\\qtylist\b",
        r"\\unit\{", r"\\ang\b", r"\\tablenum\b", r"\\complexnum\b",
        r"\\sisetup\b",
        r"siunitx",
        r"[^A-Za-z]S\[",                     # an S[...] tabular column spec
        r"\\TeXLibLoadUnits\b",
    ),
    # tasks, +0.32s.
    "Tasks": (
        r"\\begin\{tasks\}",
        r"\\task\b",
        r"\\settasks\b",
        r"\\TeXLibLoadTasks\b",
    ),
    # caption, +0.20s. \caption itself is a kernel command and would still
    # "work" without the package -- but it would be formatted differently, which
    # is a silent visual regression rather than an error, so any \caption at all
    # keeps the package. \fig (texlib-utilities) emits \caption internally.
    "Caption": (
        r"\\caption",
        r"\\captionsetup\b",
        r"\\captionof\b",
        r"\\subcaption",
        r"\\DeclareCaption",
        r"\\fig\b",
        r"\\TeXLibLoadCaption\b",
    ),
}

# Commands that pull another source file into the document. Group 1 is the path.
_INPUT_RE = re.compile(
    r"\\(?:input|include|subfile|subfileinclude|loadbank|import|includefrom)"
    r"\s*\{([^}]*)\}"
)

# A \input whose argument is not a plain path -- it contains a macro, so the
# real filename is only known to the engine. Any of these forces a bail-out.
_DYNAMIC_ARG_RE = re.compile(r"\\|#")

# Files a TeXLib document picks up without naming them (course metadata and the
# shared preamble). Looked for beside the document and one level up.
_IMPLICIT = ("coursemeta.tex", "preamble.tex")


def strip_comments(text):
    """Drop TeX line comments, keeping escaped \\%.

    A commented-out \\cite is not evidence. The scan runs on the stripped text so
    a citation the author has already commented out does not pin biblatex in
    place forever.
    """
    out = []
    for line in text.splitlines():
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\":
                i += 2          # skip the escaped char, \% included
                continue
            if ch == "%":
                break
            i += 1
        out.append(line[:i])
    return "\n".join(out)


def _resolve(path, base_dir):
    """Absolute path for one \\input argument, or None if it does not exist."""
    candidate = os.path.normpath(os.path.join(base_dir, path))
    for attempt in (candidate, candidate + ".tex"):
        if os.path.isfile(attempt):
            return attempt
    return None


def gather_source(tex_path, _seen=None):
    """Concatenated, comment-stripped text of a document and its input tree.

    Returns (text, complete). `complete` is False when any input could not be
    resolved or read, or when a path is built from a macro -- in which case the
    caller must defer nothing.
    """
    if _seen is None:
        _seen = set()
    tex_path = os.path.abspath(tex_path)
    if tex_path in _seen:
        return "", True             # already folded in; cycles are not an error
    _seen.add(tex_path)

    try:
        with io.open(tex_path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return "", False

    text = strip_comments(raw)
    complete = True
    base_dir = os.path.dirname(tex_path)

    for match in _INPUT_RE.finditer(text):
        arg = match.group(1).strip()
        if not arg or _DYNAMIC_ARG_RE.search(arg):
            complete = False        # macro-built path: we cannot follow it
            continue
        resolved = _resolve(arg, base_dir)
        if resolved is None:
            complete = False
            continue
        sub_text, sub_complete = gather_source(resolved, _seen)
        text += "\n" + sub_text
        complete = complete and sub_complete

    # Implicit companions, when they exist. Their absence is not incompleteness:
    # most documents legitimately have neither.
    for name in _IMPLICIT:
        for directory in (base_dir, os.path.dirname(base_dir)):
            if not directory:
                continue
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate) and os.path.abspath(candidate) not in _seen:
                sub_text, sub_complete = gather_source(candidate, _seen)
                text += "\n" + sub_text
                complete = complete and sub_complete

    return text, complete


def deferrable_for(tex_path):
    """Names of the components this document can safely skip loading.

    Empty when the source tree could not be read in full -- see the safety rule
    in the module docstring.
    """
    text, complete = gather_source(tex_path)
    if not complete:
        return []
    deferrable = []
    for name in sorted(DEFERRABLE):
        patterns = DEFERRABLE[name]
        if not any(re.search(p, text) for p in patterns):
            deferrable.append(name)

    match = _DOCCLASS_RE.search(text)
    if match and match.group(1).strip() in TIKZ_CLASSES:
        if not any(re.search(p, text) for p in TIKZ_PATTERNS):
            deferrable.append("Tikz")
            deferrable.sort()
    return deferrable


def defer_macros(names):
    r"""The \def prefix that turns a list of component names into engine input.

    Injected ahead of \documentclass exactly like the accessible build's
    \DocumentMetadata prefix, and for the same reason: the class loads the
    bundle, so the flag has to exist before the class does.
    """
    return "".join("\\def\\TeXLibNo%s{}" % n for n in names)


def defer_prefix_for(tex_path):
    r"""Convenience: the \def prefix for one document, possibly empty."""
    return defer_macros(deferrable_for(tex_path))


def main(argv=None):
    """Report what would be deferred for each named document."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: texlib_preamble_scan.py <document.tex> [...]")
        return 2
    for path in args:
        text, complete = gather_source(path)
        names = deferrable_for(path)
        status = "complete" if complete else "INCOMPLETE (deferring nothing)"
        print("%s  [%s]" % (path, status))
        print("    defer: %s" % (", ".join(names) if names else "(nothing)"))
        kept = sorted(set(DEFERRABLE) - set(names))
        print("    load : %s" % (", ".join(kept) if kept else "(nothing)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
