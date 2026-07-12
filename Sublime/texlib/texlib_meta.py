# texlib_meta.py
# ============================================================================
# TeXLib -- show resolved course metadata (D4).
#
# course-metadata.sty writes a <jobname>.metadump sidecar at \AtEndDocument (N1)
# listing every field with its RESOLVED value (coursemeta defaults + class-option
# overrides + derived fields like Term all folded in) -- values a build tool can't
# reconstruct by scraping coursemeta.tex. This command reads that sidecar (from
# the build's aux dir, or next to the source for a CLI build) and shows it.
#
# Own top-level file (hot-reloads alone). parse_metadump / render_metadump are
# pure and unit-tested headlessly.
# ============================================================================

import os

import sublime
import sublime_plugin

try:
    from TeXLib import texlib_locate
except ImportError:
    import texlib_locate


def parse_metadump(text):
    """Parse the tab-separated <base>.metadump into an ordered list of
    (key, value) pairs. Blank lines are skipped; a line with no tab is treated
    as key with an empty value."""
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        key, tab, value = line.partition("\t")
        rows.append((key.strip(), value.strip()))
    return rows


def render_metadump(rows, base):
    """Render (key, value) rows as an aligned report; unset fields shown faintly."""
    width = max((len(k) for k, _ in rows), default=0)
    L = ["TeXLib resolved metadata — %s" % base, "=" * 60, ""]
    for k, v in rows:
        L.append("  %-*s  %s" % (width, k, v if v else "(unset)"))
    L.append("")
    return "\n".join(L)


def _metadump_path(root):
    """Where the .metadump for `root` is: the build's aux dir first (routed
    build), else next to the source (a bare CLI build)."""
    base = os.path.splitext(os.path.basename(root))[0]
    cand = os.path.join(texlib_locate.aux_dir_for(root), base + ".metadump")
    if os.path.isfile(cand):
        return cand
    beside = os.path.join(os.path.dirname(root), base + ".metadump")
    return beside if os.path.isfile(beside) else None


class TexlibShowMetadataCommand(sublime_plugin.WindowCommand):
    """Show the resolved course metadata for the active document (needs a build)."""

    def run(self):
        root = texlib_locate._tex_root(self.window.active_view())
        if not root:
            sublime.status_message("TeXLib: save the document first.")
            return
        path = _metadump_path(root)
        if not path:
            sublime.status_message(
                "TeXLib: no metadata dump yet — build the document first.")
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                rows = parse_metadump(fh.read())
        except OSError as exc:
            sublime.error_message("TeXLib: could not read metadata: %s" % exc)
            return
        out = self.window.new_file()
        out.set_name("TeXLib · Resolved Metadata")
        out.set_scratch(True)
        out.run_command("append", {
            "characters": render_metadump(rows, os.path.basename(root))})
        out.set_read_only(True)

    def is_enabled(self):
        return texlib_locate._is_tex(self.window.active_view())


def plugin_loaded():
    print("TeXLib metadata viewer loaded.")
