# 2026-09-10 — university-of-iowa

**profile** — HERD rank 40. PR #181. Complete; nothing left to the neutral
fallback. Tenth and last institution of the round.

**The Graduate College's "Formatting Your Thesis" web page was down.**
`grad.uiowa.edu/academics/thesis-and-dissertation/formatting` returned "This
page is unavailable and may be under review" on the access date. Nothing here
depends on it: the *Thesis and Dissertation at Iowa* PDF (Spring 2025) carries
the same requirements in Appendix A (Formatting Requirements) and Appendix B
(Required and Optional Elements). **But if that page comes back it may be newer
than the PDF**, and should be checked before this profile is trusted for a
filing. The header says so too.

Set from Appendix A: margins (a *minimum* of 1 inch, not a fixed figure — a
wider consistent margin is in spec), spacing (a choice of 1.5 or double; profile
takes double). No chapter opening: Iowa's heading rules are about consistency
and name no figure.

**The title page's content is in Appendix A; its layout is only in the Word
template.** The alignment was read from the template's paragraph properties
rather than guessed — every paragraph down to the date carries `w:jc="center"`
and the five committee paragraphs carry none, so the committee block is the one
left-aligned element on the page, with the label on the supervisor's line.

**Only the supervisor gets a role.** "Only designate your thesis supervisor(s).
Academic titles and/or degrees earned should not be listed", and Appendix A:
supervisor first, "followed by a comma and the phrase 'Thesis Supervisor.'" Pass
an empty role to `\committeemember` for everyone else. The class's default
member line draws a signature rule and leads with a `\vskip`; both are wrong here
and are overridden inside the minipage.

**Iowa asks for almost nothing on accessibility, and what it asks is a
"Consider".** Three hits for "accessib" in twenty pages, two of them about open
*access*. The one PDF-conversion instruction is about bookmarks, not tags:
"make sure 'Convert Word Headings to Bookmarks' is checked." No flags set.

No approval page: Appendix B is a closed table and contains none. Approval
happens in ProQuest after the Graduate College's format check — "a link that
allows your committee members to approve the thesis."

One thing a document must respect and the profile cannot enforce: 12pt is the
**ceiling** for major headings too ("You may use 12-point font for major
headings. Font larger than this may be used sparingly, if at all"), and the
class's body is already 12pt.
