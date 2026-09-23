# 2026-09-09 — university-of-texas-southwestern-medical-center

**profile** — HERD rank 43. PR #171.

Set: geometry (1in), spacing (double), the title-fly (signature page) and the
title page, plus six quoted accessibility entries. Left to the neutral fallback:
chapter openings and every checkable accessibility declaration.

Things a later pass should not have to rediscover:

- **Two editions, both used on purpose.** The current *Instructions for the
  Preparation of Electronic Theses and Dissertations at UT Southwestern Medical
  Center* (`etdUniversalInstructions.pdf`, "Revised 12/30/2025") carries every
  figure but prints **no sample pages**. The superseded *INSTRUCTIONS For
  Preparation Of MASTERS THESES and DOCTORAL DISSERTATIONS*
  (`etdGradInstructions.pdf`, "Revised, Fall 2016") is the **only** source of the
  page specimens. Figures from 2025, layout from 2016, 2025 wins where they
  disagree. They disagree twice, both recorded in the profile:
  the conferral-date format (2016 "June, 2002"; 2025 "MONTH YEAR (e.g., May
  2020)") and the institution's name.
- **The institution's name changed.** The 2016 specimen prints "The University
  of Texas Southwestern Medical Center **at Dallas**" three times; the 2025
  document titles itself "at UT Southwestern Medical Center" and IPEDS records
  no "at Dallas". The profile uses the current form via `\utswname{}`.
- **The title-fly comes FIRST, before the title page.** The 2025 arrangement
  table lists it as row one, Required for every school. The class emits
  `\thesistitlepage` then `\thesisapprovalpage`, so a UTSW document must call
  `\thesisapprovalpage` **first**. Said in the profile header.
- **The signature rules carry no names** — the only approval page in this
  directory that doesn't. "All signatures must be original and in ink."
- **Accessibility sits between Purdue and ASU in force.** UTSW names WCAG 2.1
  Levels A and AA and the date **April 24, 2026**, but frames the obligation as
  one on the institution ("State institutions are required to comply..."), asks
  for the student's "assistance", introduces the element list as "the major
  elements *recommended*", and attaches no consequence. So no checkable
  declaration is set, and the tagging sentence — which sits inside the
  recommended list — is quoted rather than acted on.
- **April 24 2026 here, April 2026 at UC Davis, Spring 2027 at Purdue.** All
  three are right; the ADA Title II dates differ by entity size.
- **The typeface rule is a recommendation**, so the class passes — unlike Baylor
  College of Medicine (#170) and Arizona State (#165).
- **The library issues the instructions**, and that is fine: they are the
  institution's filing requirements, not a library research guide. Same
  arrangement as Mount Sinai's Levy Library (#162).
- **The specimen's line counts overrun the page if taken literally plus extra
  gaps.** A first pass added a blank line under DISSERTATION and a four-line gap
  under the degree, which pushed the closing university/city/date block onto a
  second sheet on a build that exited clean. Only the counts the specimen states
  are fixed now; the rest is elastic.
