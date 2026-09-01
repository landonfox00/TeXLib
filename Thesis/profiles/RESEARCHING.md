# Researching an institution profile

A thesis profile encodes what a graduate school requires of a filed
dissertation. Getting a figure wrong does not produce a bad commit — it
produces a **rejected filing** for someone who trusted the profile, usually
after they have already scheduled a defence. This file is the standard a
profile has to meet before it is merged.

It is written for a person and for the scheduled routine
(`texlib-thesis-profile-round`), which follows it verbatim.

## What a profile may contain

Only what a named, dated source actually says:

| Field | Source |
|---|---|
| `\thesisinstitution` | the institution's own name, as IPEDS records it |
| `\thesissetgeometry` | the margin rule, quoted from the filing requirements |
| `\thesissetspacing` | the line-spacing rule |
| `\thesistitlepage` | the required title-page layout and wording |
| `\thesisapprovalpage` | the required committee/approval page |

Nothing else. A profile is not the place for a department's preferences, a
style guide's advice, or anything an advisor told you once.

## The rule that matters

**Every value must come from a URL you actually opened, and the URL and access
date go in the file header.** Not "the university's site presumably says", not
a figure carried over from a similar institution, not a plausible default.

If the requirements are not findable — behind a login, only in a scanned image,
a dead link, or simply not published — that is a **result**, not a failure. Record
it and stop:

```bash
python thesis_institutions.py block <slug> "requirements behind a student login"
```

That keeps the queue moving; without it `next` returns the same institution
forever. Blocking is not a verdict on the institution, just a note that this
attempt could not complete.

**Partial findings are allowed and expected.** If you find the margin rule but
not the approval-page wording, set the geometry and leave
`\thesisapprovalpage` alone — the class's institution-neutral page renders
instead, the header records which parts are unverified, and a later pass can
finish it. A half-verified profile that says so is useful; a whole one that
guessed is not.

## Sources, in order of preference

1. The graduate school's own **thesis/dissertation filing requirements** page
   or PDF — usually `<domain>/graduate/…/format`, `…/thesis-dissertation`,
   `…/etd`. This is the only authoritative source.
2. The graduate school's **official LaTeX or Word template**, if it publishes
   one. A template is evidence of layout; prefer the prose requirements where
   they disagree, and say so in the header.
3. Nothing else. A department page, a library guide, a student wiki, or another
   university's template are **not** sources for this. Neither is a language
   model's recollection, including yours.

ProQuest/ETD boilerplate describes ProQuest's requirements, not the
institution's. Do not mistake one for the other.

## Verification pass

After drafting, re-open each source and check the drafted values against it
with a skeptical eye. Specifically:

- Are the margins stated for **all four sides**, and do any exceptions apply
  (first pages, landscape tables, appendices)? A profile cannot express
  "except on chapter openings" — if the rule has exceptions, note them in the
  header rather than silently picking one.
- Is the spacing rule about the **body**, or the whole document? Front matter is
  often single-spaced.
- Is the requirements page **current**? Many carry a revision date or an
  academic year. If it is more than a couple of years stale, say so in the
  header.
- Does the approval page prescribe **signature lines**, and does the institution
  still collect physical signatures? Many moved to electronic approval and the
  page changed accordingly.

Record the outcome in the header, including anything you could not confirm.

## Before opening a PR

The profile must build. From a checkout:

```bash
python texlib_cli.py build <a test thesis>.tex --mode accessible
```

A profile that errors is worse than no profile, because the neutral pages at
least produce a conformant document. Check that the tagged twin still passes
veraPDF — a profile can break conformance by, for example, putting an
un-alt-texted logo on the approval page.

## What the PR must say

Open it as a **draft**, and put in the body:

- the source URL and the date you read it,
- which fields are verified and which are still the neutral fallback,
- anything ambiguous in the requirements, quoted,
- whether the institution still requires physical signatures.

A reviewer has to be able to check your work without repeating it.

**No profile is merged by the routine.** A person merges it, after reading the
source themselves or deciding the citation is good enough. That is deliberate:
the cost of a wrong margin falls on a student, not on us.
