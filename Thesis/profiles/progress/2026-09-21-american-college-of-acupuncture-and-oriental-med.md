# 2026-09-21 — american-college-of-acupuncture-and-oriental-med

**blocked** — alphabetical queue. PR #258.

ACAOM (Houston, TX) publishes a full *Catalog 2025-2026* and a *Student Handbook
2024-2025*, both as plain PDFs, and the catalog does prescribe the doctoral
capstone in detail — PD-824 is broken into four graded parts that map onto the
document's sections (Title and Introduction; Literature Review; Methodology and
Results; Discussion/Conclusion and Reference/Bibliography). That is a
**structure** requirement, which a profile cannot express and which the class
does not own. No margin, spacing, typeface, title-page, approval-page or
accessibility rule appears in either document.

What a later pass must not rediscover: both PDFs download with a plain `curl`
from `acaom.edu/attachments/` and extract cleanly, and the registrar page's
full document list (17 PDFs) was read — it holds no capstone manual, format
guide or style guide. Searching both extracted texts for "margin", "double
spac", "title page", "font", "APA" and "accessib" returns nothing relevant.
The absence is real, not a fetch failure.
