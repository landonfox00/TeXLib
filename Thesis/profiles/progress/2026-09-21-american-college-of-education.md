# 2026-09-21 — american-college-of-education

**blocked** — alphabetical queue. PR #259.

ACE is a large online Ed.D./Ed.S. institution with a genuine dissertation
sequence (RES6512 concept paper → RES6521/6531/6541/6551/6561 chapter courses →
RES6302 defence) and an assigned two-person dissertation committee. Its public
catalog at `catalog.ace.edu` (catoid=92) describes all of that and **no
formatting at all**. The format lives in a dissertation template distributed
through the Canvas Writing Center / Dissertation Toolbox in the Student Commons,
which needs a student login — so the figures exist but are not publishable
sources.

What a later pass must not rediscover, and one trap:

* `catalog.ace.edu` returns **HTTP 202 with a zero-byte body** to `curl` and
  WebFetch alike (bot protection). It renders fine in the Browser pane after a
  ~3 s wait; that is the only way in. Don't read a 202 as "page gone".
* The catalog's own search for the whole word "dissertation" was run: it matches
  programs and the policy pages *Program Specific Doctoral*, *Conferral and
  Commencement*, *Grading*, *Glossary* — none of which names a margin, spacing,
  typeface, title page, approval page or accessibility rule. Re-running that
  search is wasted effort.
* `etdadmin.com/main/resources?siteId=1160` is ACE's ProQuest submission page and
  carries only ProQuest's generic boilerplate ("Follow your university's
  formatting guidance"). Under RESEARCHING.md that is not a source.
* There is no catalog PDF; `ace.edu/student-success/catalog/` only links the
  Modern Campus portal, and the ACE blog posts on dissertations are marketing,
  not filing requirements.
