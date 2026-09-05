r"""texlib_freshness.py — decide whether a build would change anything at all.

WHY THIS FILE EXISTS

The fastest build is the one that does not run. Pressing Ctrl+B after changing
nothing -- to bring the PDF forward, to forward-sync the viewer, out of habit --
costs a full engine pass, and for a TeXLib document that is seconds. Nothing
about the output differs afterwards.

Deciding is nearly free if the question is asked correctly. The engine, run with
-recorder, writes a `.fls` listing every file it actually read: 317 unique
inputs for a six-page Notes document, including the .bbl and every texlib
.sty/.cls, all as absolute paths. That is a complete and *observed* dependency
list -- better than anything a source scan could infer, because it is what the
engine did rather than what a parser thinks it would do.

Measured on that document:

    stat fingerprint (path + mtime + size)     6.8 ms
    content fingerprint (17.5 MB hashed)     107.4 ms
    one engine pass                         ~4000    ms

So the check costs 0.2%-3% of the pass it avoids.

WHY BOTH FINGERPRINTS

The stat fingerprint is the fast path and is what runs first. It is also wrong
in one environment that matters here: OneDrive rewrites mtimes when it syncs, so
a teaching tree stored there produces stat mismatches on files whose bytes never
changed. That is only a missed optimisation, never a wrong answer -- but it
would miss constantly, which is the same as not existing.

So a stat mismatch does not mean stale. It means "look properly": the content
fingerprint is computed, and if the bytes match, the build is still skipped and
the stamp's stat fingerprint is refreshed so the next check takes the fast path
again. Only a content mismatch is stale.

THE CONSERVATIVE DIRECTION

Skipping a build that was needed produces a stale PDF and a confused author, and
that is much worse than running a build that was not needed. Every uncertainty
therefore resolves toward building:

  * no stamp, no .fls, no PDF, an unreadable file -> build;
  * a PDF whose size or mtime is not what the stamp recorded (someone deleted
    or replaced it) -> build;
  * a different engine, mode, or deferral prefix -> build;
  * anything raising at all -> build.

A stamp is written only after a CLEAN build. A run that emitted errors may have
failed to read a file it would otherwise depend on -- the classic case is an
\includegraphics whose target does not exist yet, which never reaches the .fls
-- so its input list is not trustworthy as a dependency set.
"""

import hashlib
import io
import json
import os

STAMP_SUFFIX = ".texlibstamp"

# Files whose content is a build artifact rather than an input. The engine reads
# its own .aux/.out on the next pass, so they legitimately appear in the .fls;
# they are excluded because their content is derived from the very inputs
# already being hashed, and including them makes the fingerprint depend on which
# pass of a multi-pass build happened to write them last.
_DERIVED_SUFFIXES = (".aux", ".out", ".toc", ".lof", ".lot", ".synctex",
                     ".synctex.gz", ".fls", ".fdb_latexmk", ".log", ".nav",
                     ".snm", ".vrb", ".bcf", ".run.xml", ".buildmeta")


def fls_path_for(pdf_path):
    """The .fls beside a PDF, whatever directory the build routed output to."""
    return os.path.splitext(pdf_path)[0] + ".fls"


def stamp_path_for(pdf_path):
    return os.path.splitext(pdf_path)[0] + STAMP_SUFFIX


def fls_inputs(fls_path):
    """Absolute, de-duplicated INPUT paths from a .fls, minus build artifacts.

    Paths in a .fls may be relative to the directory the engine ran in, which
    the file's own PWD line names.
    """
    inputs, seen = [], set()
    base = os.path.dirname(os.path.abspath(fls_path))
    try:
        with io.open(fls_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("PWD "):
                    base = line[4:].strip() or base
                elif line.startswith("INPUT "):
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    path = raw if os.path.isabs(raw) else os.path.normpath(
                        os.path.join(base, raw))
                    if path.lower().endswith(_DERIVED_SUFFIXES):
                        continue
                    key = os.path.normcase(path)
                    if key not in seen:
                        seen.add(key)
                        inputs.append(path)
    except OSError:
        return []
    return inputs


def stat_fingerprint(paths):
    """Cheap fingerprint: path + mtime + size. ~7 ms for 317 files."""
    digest = hashlib.sha256()
    for path in paths:
        digest.update(os.path.normcase(path).encode("utf-8", "replace"))
        try:
            info = os.stat(path)
            digest.update(b"|%d|%d\0" % (info.st_mtime_ns, info.st_size))
        except OSError:
            digest.update(b"|missing\0")
    return digest.hexdigest()


def content_fingerprint(paths):
    """Authoritative fingerprint: the bytes. ~107 ms for 17.5 MB."""
    digest = hashlib.sha256()
    for path in paths:
        digest.update(os.path.normcase(path).encode("utf-8", "replace"))
        try:
            with io.open(path, "rb") as fh:
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            digest.update(b"|missing\0")
        digest.update(b"\0")
    return digest.hexdigest()


def _pdf_identity(pdf_path):
    try:
        info = os.stat(pdf_path)
    except OSError:
        return None
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns}


def read_stamp(pdf_path):
    try:
        with io.open(stamp_path_for(pdf_path), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write_stamp(pdf_path, build_key):
    """Record what this PDF was built from. Call ONLY after a clean build.

    Returns True if a stamp was written. A missing .fls or PDF is not an error:
    it just means the next build cannot be skipped, which is the safe default.
    """
    fls = fls_path_for(pdf_path)
    identity = _pdf_identity(pdf_path)
    if identity is None or not os.path.isfile(fls):
        return False
    paths = fls_inputs(fls)
    if not paths:
        return False
    payload = {
        "version": 1,
        "build_key": build_key,
        "inputs": len(paths),
        "stat": stat_fingerprint(paths),
        "content": content_fingerprint(paths),
        "pdf": identity,
    }
    try:
        with io.open(stamp_path_for(pdf_path), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True)
            fh.write("\n")
    except OSError:
        return False
    return True


def is_fresh(pdf_path, build_key):
    """True when rebuilding `pdf_path` would produce the same file.

    Takes the fast path when mtimes are untouched, and falls back to comparing
    bytes when they are not -- see the module docstring on OneDrive. A byte
    match refreshes the stamp's stat fingerprint so the next check is fast
    again; that refresh is best-effort and its failure only costs speed.
    """
    try:
        stamp = read_stamp(pdf_path)
        if not stamp or stamp.get("version") != 1:
            return False
        if stamp.get("build_key") != build_key:
            return False
        if stamp.get("pdf") != _pdf_identity(pdf_path):
            return False        # PDF deleted, replaced, or rewritten elsewhere

        fls = fls_path_for(pdf_path)
        if not os.path.isfile(fls):
            return False
        paths = fls_inputs(fls)
        if not paths or len(paths) != stamp.get("inputs"):
            return False

        if stat_fingerprint(paths) == stamp.get("stat"):
            return True
        if content_fingerprint(paths) != stamp.get("content"):
            return False

        stamp["stat"] = stat_fingerprint(paths)
        try:
            with io.open(stamp_path_for(pdf_path), "w", encoding="utf-8") as fh:
                json.dump(stamp, fh, indent=1, sort_keys=True)
                fh.write("\n")
        except OSError:
            pass
        return True
    except Exception:           # noqa: BLE001 -- never let this fail a build
        return False


def build_key(engine, mode, prefix, options=()):
    """Identity of the build that produced a PDF.

    Two builds of the same source with different engines, modes or deferral
    prefixes are different outputs, and a stamp from one must never license
    skipping the other.
    """
    parts = [engine or "", mode or "", prefix or ""] + [str(o) for o in options]
    return hashlib.sha256("\0".join(parts).encode("utf-8", "replace")).hexdigest()[:16]
