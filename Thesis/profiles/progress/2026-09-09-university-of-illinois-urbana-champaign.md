# 2026-09-09 — university-of-illinois-urbana-champaign

**profile** — HERD rank 40. PR #168.

Set: geometry (1in minimum), spacing (double, one of two permitted), the title
page from the Graduate College's specimen, `\thesisnoapprovalpage`, and six
quoted accessibility entries. Left to the neutral fallback: chapter openings and
every checkable accessibility declaration.

Things a later pass should not have to rediscover:

- **These are the REVISED requirements**, in force "beginning in the Spring 2026
  semester". The revision removed Roman-numeral pagination entirely, banned the
  List of Figures and List of Tables, banned full justification, and changed the
  title page's spacing and capitalization. Any older description of an Illinois
  thesis is superseded.
- **The class violates one hard requirement by default**: "The body text must be
  left-aligned. Body text that is fully justified will not be accepted." LaTeX
  justifies by default. Left to the filer (`\AtBeginDocument{\raggedright}`) and
  recorded loudly in the header, on the same line held at Arizona State over its
  typeface list. This is the *least* ambiguous case in the directory — if a
  justification field is ever added to the class, Illinois is the reason.
- **No Roman numerals at all.** The abstract is Arabic 2 (3 with a copyright
  page) and numbering runs in sequence throughout. A document filed here must
  not call `\frontmatter`.
- **List of Figures / List of Tables are banned**, explicitly on accessibility
  grounds.
- **"Urbana, Illinois" is on the title page and in none of the prose.** It
  appears in all three specimens and nowhere in the requirements text block. It
  would have been missed by reading the prose alone.
- **Two internal inconsistencies in Illinois's own material**, both left for a
  reviewer rather than silently resolved: the prose spells the master's heading
  "Adviser:" while the Master's Title Page Example prints "Advisor:"; and the
  Format Requirements page states alt text with "must" while the Thesis Updates
  page says the Graduate College "strongly encourage[s]" it. Both quoted.
- **No WCAG level, PDF standard, tagging rule or document-language rule** is
  named anywhere, despite accessibility being the stated motivation for the
  whole 2026 revision. So none of the checkable declarations is set.
- **Fetching**: the requirements live inside `<ilw-accordion-panel>` custom
  elements whose bodies are a second unnamed slot — `get_page_text` returns only
  the headings. Read `h.parentElement.parentElement.textContent` for each
  section's anchor id.
