r"""texlib_format_cache.py — precompiled preambles for the edit-recompile loop.

WHY THIS FILE EXISTS

A TeXLib engine pass spends almost all of its time loading the class. Measured on
a six-page notes document (TeX Live 2026, pdflatex):

    engine floor (near-empty article)          1.09s
    + the TeXLib class bundle                  3.55s   <- this
    + the document's own 25 KB of content      0.25s

Nothing an author writes moves that middle number, and it is paid again on every
pass. `mylatexformat` removes it: the preamble is executed once and dumped to a
`.fmt`, and later passes start from that image. The same document measured
end-to-end:

    lualatex, as the hand-written build script ran it        6.02s
    pdflatex (this class never needed lualatex)              4.60s
    + scanner-chosen deferrals                               3.82s
    + a cached format                                        0.97s

WHAT MAKES IT SAFE

A precompiled preamble is a cache, and a cache that misses a change is worse
than no cache: the build silently uses a stale preamble and the author debugs a
document that is already correct. So the key covers everything that can change
what the preamble does:

  * the engine, and the injected prefix (deferral flags, accessible metadata) --
    two different prefixes are two different preambles;
  * the PREAMBLE and its input tree, gathered by
    texlib_preamble_scan.gather_preamble, so a change to an \input'd preamble.tex
    or coursemeta.tex invalidates it;
  * every texlib .sty/.cls in the library -- editing the class must not leave a
    stale format behind, which is the failure mode that would waste the most
    time in this repo specifically;
  * the document's own path, so two documents never share an image (a preamble
    may capture \jobname).

Any mismatch produces a different key, which is a cache miss, which re-dumps.
There is no invalidation logic to get wrong -- a stale entry is simply never
addressed again, and `prune()` reclaims it later.

WHY THE BODY IS NOT IN THE KEY

mylatexformat dumps everything up to \begin{document} and nothing after it, so
the body cannot change the image. Keying on it only produced misses -- and misses
on precisely the edit the cache exists to serve, changing a problem and pressing
Ctrl+B. On the Math 126 Exam 1 that is every write-loop build.

The body still reaches the key by the one route through which it can genuinely
change the preamble: the deferral prefix is computed from the FULL source, so a
body that starts using plots or units changes `prefix`, and the key with it.

WHAT IT DOES NOT DO

The format is dumped WITH the prefix already applied, so the compile step must
NOT repeat it -- re-executing the flags on top of a format that already has them
raises errors. `compile_argv` returns the bare document for that reason.

This is wired to the quick/preview build only. A final build runs the ordinary
path: the loop is where 3.8s -> 1.0s is worth having, and a full build should not
depend on a cache at all.
"""

import hashlib
import io
import os
import shutil
import subprocess
import time

try:
    from TeXLib import texlib_preamble_scan as _scan
except ImportError:  # plain import outside the Sublime package (tests, CLI)
    import texlib_preamble_scan as _scan

# The -ini program that dumps a format for each engine, and the format it
# preloads. luahbtex/pdftex are the binaries; lualatex/pdflatex are the formats.
# pdflatex ONLY, and that is not an oversight.
#
# A dumped format restores TeX's state, not Lua's. Every TeXLib lua class builds
# its engine at preamble time -- problem_engine.lua publishes itself as the
# global `texlib`, schedule.lua and bingo.lua likewise -- and none of that
# survives into a -fmt run. The format loads, \begin{document} reaches the first
# \directlua, and the document dies with "attempt to index a nil value (global
# 'texlib')" and no PDF.
#
# lualatex was listed here from the start and never worked: the dump exits 1 on
# luahbtex ("no pages of output"), the old returncode check read that as failure,
# and the cache silently declined every lualatex document. Fixing that check
# without this restriction converts a cache that does nothing into a build that
# produces a broken PDF quickly, which is strictly worse.
#
# Reaching autoexam would mean re-initialising the Lua side after format load --
# a library change in texlib-problembank.sty and each class-local engine, not a
# builder one.
INITEX = {
    "pdflatex": ("pdftex", "pdflatex"),
}

# A dumped format is ~8-10 MB, so the cache needs a ceiling. Both are generous:
# a working set of a dozen documents fits, and anything untouched for a fortnight
# is almost certainly a document that has moved on.
MAX_CACHE_BYTES = 2 * 1024 * 1024 * 1024      # 2 GB
MAX_CACHE_AGE_SECONDS = 14 * 24 * 60 * 60     # 14 days

# Bumped whenever what the key COVERS changes, so entries dumped under an older
# rule are never addressed again rather than being trusted under the new one.
# v2: the key reads the preamble only, not the whole source tree.
KEY_VERSION = "v2"


def cache_dir():
    """Where dumped formats live. TEXLIB_FORMAT_CACHE overrides."""
    override = os.environ.get("TEXLIB_FORMAT_CACHE")
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "TeXLib", "formats")
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    return os.path.join(base, "texlib", "formats")


def _library_fingerprint(library_root):
    """Hash of every texlib .sty/.cls, so editing the class busts the cache.

    Content, not mtime: a checkout or a branch switch rewrites mtimes without
    changing what the class does, and re-dumping then costs more than it saves.
    """
    digest = hashlib.sha256()
    if not library_root or not os.path.isdir(library_root):
        return "no-library"
    for dirpath, dirnames, filenames in os.walk(library_root):
        dirnames[:] = [
            d for d in dirnames if d not in (".git", ".claude", "__pycache__")
        ]
        for name in sorted(filenames):
            if not name.endswith((".sty", ".cls")):
                continue
            path = os.path.join(dirpath, name)
            try:
                with io.open(path, "rb") as fh:
                    digest.update(name.encode("utf-8"))
                    digest.update(fh.read())
            except OSError:
                digest.update(b"unreadable:" + name.encode("utf-8"))
    return digest.hexdigest()


def format_key(tex_path, engine, prefix, library_root):
    """Stable cache key for one (document, engine, prefix, library) combination."""
    source, complete = _scan.gather_preamble(tex_path)
    digest = hashlib.sha256()
    for part in (
        KEY_VERSION,
        engine,
        prefix,
        os.path.abspath(tex_path),
        "complete" if complete else "partial",
        source,
        _library_fingerprint(library_root),
    ):
        digest.update(part.encode("utf-8", "replace"))
        digest.update(b"\0")
    return "texlibfmt-" + digest.hexdigest()[:24]


def format_path(key):
    return os.path.join(cache_dir(), key + ".fmt")


def env_with_cache(env=None):
    """A copy of `env` with the cache dir prepended to TEXFORMATS.

    The trailing separator keeps the distribution's own format path searched
    after ours, so a missing entry falls back to the installed formats instead
    of failing to find pdflatex.fmt at all.
    """
    env = dict(os.environ if env is None else env)
    sep = ";" if os.name == "nt" else ":"
    existing = env.get("TEXFORMATS", "")
    env["TEXFORMATS"] = cache_dir() + sep + existing if existing else cache_dir() + sep
    return env


def dump_argv(tex_path, engine, prefix, key):
    r"""argv that dumps a format for one document.

    The prefix is applied here, once, and baked into the image -- which is why
    compile_argv deliberately does not repeat it.
    """
    binary, base_format = INITEX[engine]
    name = os.path.basename(tex_path)
    return [
        binary,
        "-ini",
        "-interaction=nonstopmode",
        "-jobname=" + key,
        "&" + base_format,
        "mylatexformat.ltx",
        prefix + "\\input{" + name + "}",
    ]


def compile_argv(engine, key, tex_name):
    """argv fragment selecting the cached format. No prefix -- see module doc."""
    return [engine, "-fmt=" + key, tex_name]


def ensure(tex_path, engine, prefix, library_root, env=None, timeout=300):
    """Return the cache key for a usable format, dumping one if needed.

    Returns None when a format cannot be produced -- an unsupported engine, a
    missing mylatexformat, or a dump that fails. Every failure is non-fatal by
    design: the caller falls back to an ordinary build, which is merely the
    speed it was before.
    """
    if engine not in INITEX:
        return None
    key = format_key(tex_path, engine, prefix, library_root)
    target = format_path(key)
    if os.path.isfile(target):
        os.utime(target, None)          # touch: prune() evicts by last use
        return key

    os.makedirs(cache_dir(), exist_ok=True)
    tex_dir = os.path.dirname(os.path.abspath(tex_path)) or "."
    produced = os.path.join(tex_dir, key + ".fmt")
    try:
        result = subprocess.run(
            dump_argv(tex_path, engine, prefix, key),
            cwd=tex_dir,
            env=env_with_cache(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    # The ARTIFACT is the verdict, not the exit status. A -ini dump typesets
    # nothing, and luahbtex reports "no pages of output" by exiting 1 -- so
    # every lualatex document failed this check while writing a perfectly good
    # format, which is every exam, quiz and lecture-notes document in the
    # library. (pdftex exits 0 on the same run, which is why the pdflatex
    # numbers in this module's header were real and nobody noticed.)
    if not os.path.isfile(produced) or os.path.getsize(produced) == 0:
        _unlink(produced)
        _unlink(os.path.join(tex_dir, key + ".log"))
        return None

    try:
        shutil.move(produced, target)
    except OSError:
        _unlink(produced)
        return None
    _unlink(os.path.join(tex_dir, key + ".log"))
    return key


def _unlink(path):
    try:
        os.remove(path)
    except OSError:
        pass


def prune(max_bytes=MAX_CACHE_BYTES, max_age=MAX_CACHE_AGE_SECONDS):
    """Evict stale and excess formats, oldest use first. Returns bytes freed."""
    directory = cache_dir()
    if not os.path.isdir(directory):
        return 0
    entries = []
    for name in os.listdir(directory):
        if not name.endswith(".fmt"):
            continue
        path = os.path.join(directory, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        entries.append((stat.st_mtime, stat.st_size, path))

    now = time.time()
    freed = 0
    survivors = []
    for mtime, size, path in entries:
        if now - mtime > max_age:
            _unlink(path)
            freed += size
        else:
            survivors.append((mtime, size, path))

    survivors.sort()                     # oldest use first
    total = sum(size for _, size, _ in survivors)
    while total > max_bytes and survivors:
        _, size, path = survivors.pop(0)
        _unlink(path)
        freed += size
        total -= size
    return freed
