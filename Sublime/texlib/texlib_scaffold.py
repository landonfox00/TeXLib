# texlib_scaffold.py
# ============================================================================
# TeXLib -- new-document scaffolding.
#
# TeXLib: New Document lists the library's <class>-template.tex files, then
# drops the chosen one into the active folder under a name you pick and opens
# it. The template carries no course identity of its own -- it resolves title /
# course / term from the coursemeta.tex in scope (the metadata engine), so this
# warns if there's no coursemeta above the target.
#
# Own top-level file (hot-reloads alone). Self-contained by design.
# ============================================================================

import os

import sublime
import sublime_plugin

TEMPLATE_SUFFIX = "-template.tex"
EXCLUDE_DIRS = {".git", ".claude", "Sublime", "tests", "__pycache__"}


def discover_templates(source_root):
    """Sorted [{class, path}] for every <class>-template.tex under source_root,
    excluding infrastructure dirs. Class name = filename minus -template.tex
    (so report-card-template.tex -> report-card)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(source_root):
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(TEMPLATE_SUFFIX):
                out.append({
                    "class": fn[:-len(TEMPLATE_SUFFIX)],
                    "path": os.path.join(dirpath, fn),
                })
    out.sort(key=lambda t: t["class"])
    return out


def _source_root(settings, plugin_dir):
    """Where the templates live: the class_source setting (the TeXLib repo root)
    if set, else the repo root two dirs above the package."""
    override = settings.get("class_source")
    if override:
        return override
    return os.path.dirname(os.path.dirname(plugin_dir))


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _target_dir(window):
    view = window.active_view()
    if view and view.file_name():
        return os.path.dirname(view.file_name())
    folders = window.folders()
    return folders[0] if folders else None


def _has_coursemeta(start_dir):
    """True if a coursemeta.tex sits at start_dir or up to 4 parents above it
    (matching course-metadata.sty's discovery walk)."""
    d = start_dir
    for _ in range(5):
        if os.path.isfile(os.path.join(d, "coursemeta.tex")):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return False


class TexlibNewDocumentCommand(sublime_plugin.WindowCommand):
    """Scaffold a new TeXLib document from a class template."""

    def run(self):
        settings = sublime.load_settings("TeXLib.sublime-settings")
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        root = _source_root(settings, plugin_dir)
        templates = discover_templates(root)
        if not templates:
            sublime.error_message(
                "TeXLib: no <class>-template.tex found under\n%s\n\n"
                "Set \"class_source\" in TeXLib.sublime-settings to your TeXLib "
                "repo." % root)
            return
        items = [[t["class"], os.path.relpath(t["path"], root)] for t in templates]

        def on_class(i):
            if i >= 0:
                # Defer so the quick panel closes before the input panel opens.
                sublime.set_timeout(lambda: self._ask_name(templates[i]), 0)

        self.window.show_quick_panel(items, on_class)

    def _ask_name(self, template):
        target_dir = _target_dir(self.window)
        if not target_dir:
            sublime.error_message(
                "TeXLib: open a folder or a file first so I know where to put "
                "the new document.")
            return
        default_name = template["class"] + ".tex"
        self.window.show_input_panel(
            "New %s document — file name:" % template["class"],
            default_name,
            lambda name: self._create(template, target_dir, name),
            None, None)

    def _create(self, template, target_dir, name):
        name = name.strip()
        if not name:
            return
        if not name.lower().endswith(".tex"):
            name += ".tex"
        dest = os.path.join(target_dir, name)
        if os.path.exists(dest) and not sublime.ok_cancel_dialog(
                "%s already exists in\n%s\n\nOverwrite?" % (name, target_dir),
                "Overwrite"):
            return
        content = _read(template["path"])
        if content is None:
            sublime.error_message(
                "TeXLib: could not read template %s" % template["path"])
            return
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            sublime.error_message("TeXLib: could not write %s: %s" % (name, exc))
            return
        self.window.open_file(dest)
        if not _has_coursemeta(target_dir):
            sublime.status_message(
                "TeXLib: no coursemeta.tex above %s — metadata won't resolve "
                "until you add one." % name)


def plugin_loaded():
    print("TeXLib scaffolding loaded.")
