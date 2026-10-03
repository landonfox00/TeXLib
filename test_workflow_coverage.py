#!/usr/bin/env python3
r"""Every tracked test file is run by a workflow.

No workflow globs for tests. A file runs in CI only when a workflow names it,
so a test added without a workflow line never runs, and nothing reports that.
On 2026-10-02 that was 16 of the 44 tracked test files. One of them,
Sublime/test_texlib_build.py, had failed on main for four weeks.

Checked against .github/workflows/*.yml:

  * each tracked test_*.py / test_*.lua is run by its path from the repo root:
    an interpreter (python, python3, texlua, lua5.x), then the path, on a line
    that is not a comment;
  * each test path a workflow runs is a tracked file.

A test that must stay out of CI goes in EXEMPT with its reason.

Run:  python test_workflow_coverage.py     (exit 0 ok, 1 fail)
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = os.path.join(HERE, ".github", "workflows")

# Path from the repo root -> why no workflow runs it.
EXEMPT = {}

TEST_RE = re.compile(r"(^|/)test_[^/]*\.(py|lua)$")
INTERPRETER = r"(?:python3?|texlua|lua(?:5\.\d)?)"
# The token after an interpreter: "quoted", 'quoted', or bare.
RUN_RE = re.compile(r"(?<![\w.-])" + INTERPRETER
                    + r"""\s+(?:"([^"]*)"|'([^']*)'|(\S+))""")
# Never descended into by the directory walk that stands in for git.
PRUNED = (".git", ".claude", "node_modules", "__pycache__")


def check(cond, label):
    print("  [%s] %s" % ("OK " if cond else "FAIL", label))
    return cond


def code_lines(text):
    """The lines of a workflow with comments removed and blank lines dropped.

    A `#` at the start of a line or after whitespace opens a comment, in YAML
    and in the shell scripts a `run:` block holds. `${#files[@]}` is not one."""
    out = []
    for raw in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw)
        if line.strip():
            out.append(line)
    return out


def run_tokens(line):
    """What each interpreter on `line` is handed first. A bare token loses the
    shell punctuation that can trail it (`python a.py;`, `(python a.py)`)."""
    return [quoted2 or quoted1 or bare.rstrip(";)&|")
            for quoted2, quoted1, bare in RUN_RE.findall(line)]


def runs(path, line):
    """True when `line` runs the test at `path` (from the repo root)."""
    return path in run_tokens(line)


def run_paths(lines):
    """Every test path the lines run."""
    return {token for line in lines for token in run_tokens(line)
            if TEST_RE.search(token)}


def unrun(tests, lines):
    """The tests no line runs."""
    return [t for t in tests if not any(runs(t, line) for line in lines)]


def tracked_tests(root):
    """(test paths from the root, where the list came from). git's index is the
    authority; a tree with no git (a source archive) is walked instead."""
    try:
        proc = subprocess.run(["git", "-C", root, "ls-files", "-z"],
                              capture_output=True, timeout=60)
        listed = proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        listed = False
    if listed:
        names = proc.stdout.decode("utf-8", errors="replace").split("\0")
        source = "git ls-files"
    else:
        names = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Pruned by name BELOW the root: this checkout may itself sit
            # under .claude/worktrees/.
            dirnames[:] = [d for d in dirnames if d not in PRUNED]
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            for fn in filenames:
                names.append(fn if rel == "." else rel + "/" + fn)
        source = "directory walk (git unavailable)"
    return sorted(n for n in names if TEST_RE.search(n)), source


def main():
    ok = True

    # --- the matcher, on lines whose answer is known -------------------------
    ok &= check(runs("test_x.py", "run: python test_x.py"),
                "matcher: `run: python <path>` runs it")
    ok &= check(runs("Report Cards/test_x.lua",
                     'lua5.3 "Report Cards/test_x.lua"'),
                "matcher: a quoted path with a space runs it")
    ok &= check(not runs("Sublime/test_texlib_build.py",
                         "python Sublime/test_texlib_builder.py"),
                "matcher: test_texlib_build.py is not test_texlib_builder.py")
    ok &= check(not runs("test_x.py", "python3 Sublime/test_x.py"),
                "matcher: a root path is not the same name in a directory")
    ok &= check(not runs("test_x.py", "path: test_x.py"),
                "matcher: a path with no interpreter before it is not a run")
    ok &= check(code_lines("  # python test_x.py\n") == []
                and unrun(["test_x.py"],
                          code_lines("echo hi  # python test_x.py\n"))
                == ["test_x.py"],
                "matcher: a path named only in a comment is not a run")
    ok &= check(unrun(["test_x.py"],
                      code_lines("python test_x.py  # cheap; run first\n"))
                == [],
                "matcher: a trailing comment does not hide the run")

    # --- this repository -----------------------------------------------------
    files = sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml"))
                   + glob.glob(os.path.join(WORKFLOWS, "*.yaml")))
    if not files:
        print("  SKIP  no workflows beside this file (not a repository "
              "checkout); nothing to compare against")
        print("\nALL PASS" if ok else "\nFAILURES ABOVE")
        return 0 if ok else 1

    lines = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            lines.extend(code_lines(fh.read()))
    tests, source = tracked_tests(HERE)
    print("  %d test files from %s; %d workflows, %d lines of code"
          % (len(tests), source, len(files), len(lines)))

    # A scan that read nothing would pass every check below.
    ok &= check("test_workflow_coverage.py" in tests
                and "Sublime/test_texlib_builder.py" in tests,
                "the file list reached this file and the builder suite")
    ok &= check(any(runs("Sublime/test_texlib_builder.py", line)
                    for line in lines),
                "the workflow scan found the builder suite's run line")

    missing = set(unrun(tests, lines))
    for test in tests:
        if test in EXEMPT:
            ok &= check(test in missing,
                        "exempt, and no workflow runs it: %s (%s)"
                        % (test, EXEMPT[test]))
        else:
            ok &= check(test not in missing, "run by a workflow: %s" % test)
    stale = sorted(set(EXEMPT) - set(tests))
    ok &= check(not stale, "every EXEMPT entry is a tracked test file"
                + ("".join("\n         " + s for s in stale)))

    dangling = sorted(run_paths(lines) - set(tests))
    ok &= check(not dangling, "every test a workflow runs is a tracked file"
                + ("".join("\n         " + d for d in dangling)))

    if missing - set(EXEMPT):
        print("\nA test file runs in CI only when a workflow names it. Add a "
              "line such as\n    python %s\nto a job in "
              ".github/workflows/tests.yml (builder-logic if it needs no TeX,\n"
              "biber-integration if it does), by its path from the repo root, "
              "or list it\nin EXEMPT with the reason."
              % sorted(missing - set(EXEMPT))[0])

    print("\nALL PASS" if ok else "\nFAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
