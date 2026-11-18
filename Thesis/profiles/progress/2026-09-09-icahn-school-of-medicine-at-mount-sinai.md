# 2026-09-09 — icahn-school-of-medicine-at-mount-sinai

**profile** — HERD rank 34. PR #162.

Set from the Graduate School of Biomedical Sciences deposit guides: geometry
(1in all four sides, flat, no binding allowance), spacing (double), the title
page and the approval page. Both pages branch on `\doctype`, because GSBS
publishes a separate guide per degree level and the two differ in the wording of
exactly those two pages. Left to the neutral fallback: nothing except
`\thesissetchapteropening`, which GSBS does not prescribe.

Things a later pass should not have to rediscover:

- **The doctoral guide does not date itself.** Its page footer is the literal
  string `Updated 0` — truncated in the source PDF, not in extraction; the
  footer region was rendered at 150dpi to confirm. Only the asset name (`_2021`)
  and the master's twin's `Updated 4/21` place it.
- **A superseded master's edition is still served**, at
  `…/Student Resources/DepositingMasterThesis.pdf`, footer `Updated 07/13`. It
  was read in full and agrees with the 2021 edition on every figure this profile
  encodes. Do not treat it as governing.
- **`icahn.mssm.edu` returns 403 to plain curl** (any User-Agent tried), but
  WebFetch retrieves the PDFs fine. The bytes then need `pdftotext -layout`;
  WebFetch's own extractor returns nothing usable for these files.
- **Signatures are physical and the filed page is a scan.** The typeset approval
  page is the sheet to print and sign; the deposited PDF must carry the scanned
  signed leaf merged in as page iii.
- **Accessibility: nothing published.** Both guides were read end to end and
  contain no accessibility rule at all. The only adjacent statement is font
  embedding, which GSBS attributes to ProQuest's ETD Administrator. The
  `ISO 19005-1 Compliant` checkbox mentioned in the Word 2010 font-embedding
  instructions is deliberately NOT encoded as a PDF/A requirement — see the
  profile header for why.
