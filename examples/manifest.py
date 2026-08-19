"""examples/manifest.py — every TeXLib example, declared exactly once.

WHY THIS FILE EXISTS

The example corpus was spread over four registries with four different
discovery mechanisms: `MODULES` (a hand-kept list), the scenario glob,
`SCENARIO_AREA_MODULE`, and `VISUAL_MODULES` — plus three separate expectation
dicts keyed by module. Adding an example meant remembering which subset of those
to touch, and adding one to the wrong subset failed silently: the example simply
never ran, and a green suite said nothing was wrong.

Everything is declared here now, once, tagged by what it is FOR. `smoke_test.py`
derives its structures from this list; the gallery reads the same list, so what
you can browse and what CI actually builds cannot drift apart.

WHAT LIVES WHERE

    examples/templates/<Module>/    the canonical document a user copies to
                                    start work, plus the data that document
                                    needs (its bank, gradebook, coursemeta,
                                    .bib). The class, its engine .lua and the
                                    library defaults it resolves by name (the
                                    *-instructions.tex files, Syllabi's policy
                                    statements) stay in <Module>/ — those are
                                    library assets, not example data.
    examples/fixtures/<Module>/     regression traps for one specific bug.
                                    Deliberately weird; a bad showcase.
    examples/scenarios/<area>/      one-configuration-each feature matrix.
                                    Deliberately minimal.
    examples/<Course>/              end-to-end course folders sharing one
                                    coursemeta.tex. Realistic, multi-document.

A template builds from outside its module directory the same way a course
folder does: smoke_test's CLASS_HOME_MODULE stages the class's library assets
into the build cwd. That mechanism already existed for examples/<Course>/, which
is why the move needed no new machinery.

Those four are not merged into one corpus on purpose: a good teaching example is
a poor regression fixture (too much going on to localise a failure), and a good
fixture is a terrible showcase. They are unified by DECLARATION, not by file.

TAGS

    smoke       build it in the module suite (smoke.yml, and locally)
    accessible  also build the tagged PDF/UA variant (accessible.yml)
    visual      pixel-diff it against tests/visual_refs/ (visual.yml)
    showcase    render it into the browsable class gallery

`smoke` implies `accessible`: the accessible gate runs the same corpus in a
second mode. `visual` is restricted to DETERMINISTIC output — autoexam and quiz
shuffle versions and pull random bank problems, so pixel-diffing them is noise.
"""


class Example:
    """One example document.

    module    registry key AND the directory the build stages from
    template  filename within that directory
    kind      "template" | "fixture" | "course"
    tags      see the module docstring
    expect    substrings that must appear in the rendered PDF text
    absent    substrings that must NOT appear (the negative mirror of expect)
    artifact  glob patterns for sidecars that must exist and be non-empty
    note      why this example exists at all -- the thing a list of paths loses
    """

    __slots__ = ("module", "template", "kind", "tags", "expect", "absent",
                 "artifact", "note")

    def __init__(self, module, template, kind, tags,
                 expect=(), absent=(), artifact=(), note=""):
        self.module = module
        self.template = template
        self.kind = kind
        self.tags = frozenset(tags)
        self.expect = tuple(expect)
        self.absent = tuple(absent)
        self.artifact = tuple(artifact)
        self.note = note


# Built by CI and shown in the class gallery.
_SMOKE = ("smoke", "accessible", "showcase")
_SMOKE_VISUAL = _SMOKE + ("visual",)

# Built by CI but NOT shown in the gallery. Fixtures are regression traps
# written to be deliberately weird -- a bare \documentclass{article} probing
# a metadata catch-all, a bank whose header wraps lines. They make excellent
# tests and terrible showcases, and putting them in the gallery would file
# them under class headings ("Metadata") that are not classes at all.
_FIXTURE = ("smoke", "accessible")


EXAMPLES = [
    # -- Module templates: the canonical copy-me documents --------------------
    Example("examples/templates/Bingo", "bingo-template.tex", "template", _SMOKE,
            expect=["Bingo", "Mark the free space"],
            note="The cells render math symbols, not text labels, so the "
                 "assertions key on the banner and how-to-play boilerplate "
                 "rather than grid coordinates."),
    Example("examples/templates/Exams", "autoexam-template.tex", "template", _SMOKE,
            expect=["Problem 1", "Problem 2"],
            note="Multi-version randomized exam; output is NOT deterministic, "
                 "so it is deliberately not tagged visual."),
    Example("examples/templates/Notes", "didactic-template.tex", "template", _SMOKE_VISUAL,
            expect=["Introduction", "Theorem"]),
    Example("examples/templates/Quizzes", "quiz-template.tex", "template", _SMOKE,
            expect=["Quiz"]),
    Example("examples/templates/Report Cards", "report-card-template.tex", "template", _SMOKE_VISUAL,
            expect=["Report Card"]),
    Example("examples/templates/Schedule", "schedule-template.tex", "template", _SMOKE_VISUAL,
            expect=["MONDAY", "WEEK", "Quiz 1", "Finals Week"],
            artifact=["*_schedule_grid.tex"],
            note="The grid artifact is a dependency-free content signal: it is "
                 "0 bytes exactly when render_grid produced no rows, which is "
                 "the empty-grid bug pdftotext alone would not catch."),
    Example("examples/templates/Syllabi", "syllabus-template.tex", "template", _SMOKE_VISUAL,
            expect=["Course Description", "Office Hours"],
            note="Carries its own metadata rather than the stub, so the "
                 "assertions key on stable section headings."),
    Example("examples/templates/Problem Sets", "pset-template.tex", "template", _SMOKE,
            expect=["Problem 1"]),
    Example("examples/templates/Bank", "bank-template.tex", "template", _SMOKE,
            expect=["Bank coverage", "Solution"],
            note="'Bank coverage' proves the summary rendered; 'Solution' "
                 "proves a cataloged solution rendered (the catalog always "
                 "shows solutions -- it is an instructor tool)."),
    Example("examples/templates/Thesis", "thesis-template.tex", "template", _SMOKE,
            expect=["Abstract", "Introduction", "Theorem 1.1",
                    "List of Tables", "Rudin"],
            note="Front matter in UNR's required order (Abstract i, then "
                 "Contents, List of Tables, List of Figures), a body chapter, "
                 "and a theorem head. 'Rudin' asserts the BIBLIOGRAPHY "
                 "rendered: smoke now runs biber between passes, and without "
                 "it \printbibliography emits an empty list while the build "
                 "still reports success -- exactly the silent failure this "
                 "corpus exists to catch."),

    # -- Fixtures: regression traps, one bug each ------------------------------
    Example("examples/fixtures/Exams", "fix-test.tex", "fixture", _FIXTURE,
            expect=["Problem 1", "MULTILINEHEADEROK"],
            absent=["MLHEADERLEAK"],
            note="Exercises \\problem{id}[a=1,b=2] fix-overrides. The two "
                 "tokens are a pair: MULTILINEHEADEROK proves the wrapped "
                 "\\begin{problem}[meta] header rendered its stem, MLHEADERLEAK "
                 "proves the header continuation lines were skipped rather "
                 "than leaked into it."),
    Example("examples/fixtures/Metadata", "metadata-test.tex", "fixture", _FIXTURE,
            expect=["CMOFFICEHOURSMARK", "CMLECTHALLMARK", "CMTANAMEMARK",
                    "SETCMDMARK", "METAALIASMARK"],
            note="course-metadata.sty's catch-all: one marker per auto-vivified "
                 "getter (coursemeta key, inline-loud, inline-quiet), plus "
                 "\\SetCourseTitle round-tripping and the \\meta->\\metasetup "
                 "alias still minting a key."),
    Example("examples/fixtures/Notes", "theorem-numbering.tex", "fixture", _FIXTURE,
            expect=["Theorem 1.1", "Definition 1.2", "Lemma 1.3",
                    "Theorem 2.1", "Definition 2.2"],
            note="Shared master counter, section-based, resetting per "
                 "\\section. All five must appear IN THIS FORM: per-family "
                 "counters would renumber Definition to 1.1, a flat scheme "
                 "would drop the '.1', and a missing reset would make the "
                 "section-2 boxes 1.4/1.5."),

    # -- Course folders: end-to-end realism ------------------------------------
    # Build-only (no expect): they share one coursemeta.tex across several
    # documents, so there is no single per-module text token to assert.
    Example("examples/Math181-Fall2026", "lecture-01-limits.tex", "course", _SMOKE),
    Example("examples/Math181-Fall2026", "quiz-01.tex", "course", _SMOKE),
    Example("examples/Math181-Fall2026", "exam-01.tex", "course", _SMOKE),
    Example("examples/Math181-Fall2026", "syllabus.tex", "course", _SMOKE),
    Example("examples/Math181-Fall2026", "schedule.tex", "course", _SMOKE),
]


# Scenario <area> -> the module whose .cls/.lua it builds on. Scenarios are
# discovered by glob (examples/scenarios/<area>/<name>/template.tex) rather than
# listed here: they are numerous, uniform, and adding one should not need a
# registry edit. This mapping is the one thing the glob cannot infer.
SCENARIO_AREA_MODULE = {
    "schedule": "Schedule",
    "report-cards": "Report Cards",
    "syllabi": "Syllabi",
    "notes": "Notes",
    "quiz": "Quizzes",
    "exam": "Exams",
    "pset": "Problem Sets",
    "bingo": "Bingo",
    "bank": "Bank",
    "thesis": "Thesis",
}


# ---------------------------------------------------------------------------
# Derived views. smoke_test.py consumes these so its build logic is untouched.
# ---------------------------------------------------------------------------

def modules(tag="smoke"):
    """[(module, template)] for every example carrying `tag`, in declaration order."""
    return [(e.module, e.template) for e in EXAMPLES if tag in e.tags]


def expect_text():
    """{module: [substring]} -- modules with no assertions are omitted."""
    return {e.module: list(e.expect) for e in EXAMPLES if e.expect}


def expect_absent():
    return {e.module: list(e.absent) for e in EXAMPLES if e.absent}


def expect_artifact_nonempty():
    return {e.module: list(e.artifact) for e in EXAMPLES if e.artifact}


def visual_modules():
    """Modules whose output is deterministic enough to pixel-diff."""
    return {e.module for e in EXAMPLES if "visual" in e.tags}


def showcase():
    """Examples the class gallery renders, in declaration order."""
    return [e for e in EXAMPLES if "showcase" in e.tags]
