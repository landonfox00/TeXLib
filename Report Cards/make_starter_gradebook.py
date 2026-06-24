#!/usr/bin/env python3
"""make_starter_gradebook.py — generate the Math 181 starter gradebook.xlsx.

Produces a two-tab workbook that demonstrates the whole report-card workflow:

  * "Roster"      — one column per assignment (the instructor's workspace).
  * "Report View" — formula columns that reference Roster and compute exactly
                    the values the report-card class reads. This is the only
                    tab gradebook_to_csv.py extracts.

The Report View cells carry BOTH the formula (so the sheet stays live when you
edit Roster) AND a cached value (so a fresh download / this file convert
correctly before any spreadsheet app recomputes). Import it into Google Sheets
(File -> Import -> Upload) to get a starting point you can edit, or just read
its layout to mirror in your own gradebook.

Dependency-free: writes the .xlsx (a zip of XML) with the standard library.
"""

import zipfile
from xml.sax.saxutils import escape

# --- scheme ----------------------------------------------------------------
FINAL_WEIGHT = 25
REG_BASE = 75                     # sum of regular (non-EC) weights
WEIGHT_SUMMARY = "75% (+15% E.C.)"
CUTOFFS = [("D", 60), ("C", 70), ("B", 80), ("A", 90)]

# Raw per-assignment scores. Homework/Quiz averages are computed from these;
# exams and extra credit are single scores.
roster = {
    "John Doe":  {"HW": [80, 85, 90], "Q": [75, 80, 85],
                  "Exam": [78, 75, 80, 76, 78], "EC": [50, 33, 0, 33, 50]},
    "Jane Doe":  {"HW": [88, 92, 96], "Q": [85, 88, 91],
                  "Exam": [90, 85, 91, 88, 93], "EC": [100, 100, 67, 100, 100]},
    "Jamie Doe": {"HW": [70, 74, 78], "Q": [65, 67.5, 70],
                  "Exam": [60, 58, 71, 65, 62], "EC": [50, 0, 33, 0, 50]},
}
names = list(roster)


def col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def num(x):
    return f"{x:g}"


# --- minimal xlsx writer ---------------------------------------------------
def cell(ref, value=None, formula=None, text=False):
    """One <c> element. value is the cached result; formula is optional."""
    if formula is not None:
        if text:
            return (f'<c r="{ref}" t="str"><f>{escape(formula)}</f>'
                    f'<v>{escape(str(value))}</v></c>')
        return f'<c r="{ref}"><f>{escape(formula)}</f><v>{value}</v></c>'
    if value is None or value == "":
        return f'<c r="{ref}"/>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{num(value)}</v></c>'
    return (f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(str(value))}</t></is></c>')


def sheet_xml(rows):
    body = []
    for ri, cells in enumerate(rows, start=1):
        body.append(f'<row r="{ri}">' + "".join(cells) + "</row>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><sheetData>'
            + "".join(body) + "</sheetData></worksheet>")


def write_xlsx(path, sheets):
    """sheets: list of (name, rows) where rows is list of list-of-cell-xml."""
    ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
              'content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxml'
              'formats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/xl/workbook.xml" ContentType="application/'
              'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
              + "".join(
                  f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.'
                  'spreadsheetml.worksheet+xml"/>'
                  for i in range(1, len(sheets) + 1))
              + "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/'
                 'package/2006/relationships"><Relationship Id="rId1" '
                 'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                 'relationships/officeDocument" Target="xl/workbook.xml"/>'
                 '</Relationships>')
    wb_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(sheets, start=1))
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/'
                'spreadsheetml/2006/main" xmlns:r="http://schemas.openxml'
                'formats.org/officeDocument/2006/relationships"><sheets>'
                + wb_sheets + "</sheets></workbook>")
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/'
               'package/2006/relationships">'
               + "".join(
                   f'<Relationship Id="rId{i}" Type="http://schemas.openxml'
                   'formats.org/officeDocument/2006/relationships/worksheet" '
                   f'Target="worksheets/sheet{i}.xml"/>'
                   for i in range(1, len(sheets) + 1))
               + "</Relationships>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        for i, (_name, rows) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(rows))


# --- build the Roster tab --------------------------------------------------
# A Name | B-D HW1-3 | E-G Q1-3 | H-L Exam1-5 | M-Q EC1-5
ROSTER_HDR = (["Name"] + [f"HW{i}" for i in (1, 2, 3)]
              + [f"Quiz{i}" for i in (1, 2, 3)]
              + [f"Exam {i}" for i in range(1, 6)]
              + [f"Exam {i} E.C." for i in range(1, 6)])


def roster_rows():
    rows = [[cell(col(c + 1) + "1", h) for c, h in enumerate(ROSTER_HDR)]]
    for ri, name in enumerate(names, start=2):
        d = roster[name]
        vals = [name] + d["HW"] + d["Q"] + d["Exam"] + d["EC"]
        rows.append([cell(col(c + 1) + str(ri), v) for c, v in enumerate(vals)])
    return rows


# --- build the Report View tab ---------------------------------------------
# Column letters are fixed (see header list); formulas reference Roster.
RV_HDR = (
    ["Name",
     "Homework Avg. Weight", "Homework Avg. Score", "Homework Avg. Points",
     "Quiz Avg. Weight", "Quiz Avg. Score", "Quiz Avg. Points", "---"]
    + sum(([f"Exam {i} Weight", f"Exam {i} Score", f"Exam {i} Points"]
           for i in range(1, 6)), [])
    + ["---"]
    + sum(([f"Exam {i} E.C. Weight", f"Exam {i} E.C. Score",
            f"Exam {i} E.C. Points"] for i in range(1, 6)), [])
    + ["Current Points", "Current Total", "Weight Summary"]
    + [f"Need {L}" for (L, _) in CUTOFFS])

# Roster source columns for each score (1-based): HW=B:D, Q=E:G, Exam i=H..L,
# EC i = M..Q.
EXAM_SRC = ["H", "I", "J", "K", "L"]
EC_SRC = ["M", "N", "O", "P", "Q"]
# Report-view point-column letters, in order, for the Current Points sum.
PT_COLS = ["D", "G", "K", "N", "Q", "T", "W", "AA", "AD", "AG", "AJ", "AM"]
# Score/weight column letters per category triplet (weight, score, points).
TRIPLETS = [("B", "C", "D"), ("E", "F", "G"),
            ("I", "J", "K"), ("L", "M", "N"), ("O", "P", "Q"),
            ("R", "S", "T"), ("U", "V", "W"),
            ("Y", "Z", "AA"), ("AB", "AC", "AD"), ("AE", "AF", "AG"),
            ("AH", "AI", "AJ"), ("AK", "AL", "AM")]
CAT_WEIGHTS = [15, 10, 10, 10, 10, 10, 10, 3, 3, 3, 3, 3]
CUR_PTS = "AN"


def _score_formula(cat_index, r):
    if cat_index == 0:
        return f"AVERAGE(Roster!B{r}:D{r})"
    if cat_index == 1:
        return f"AVERAGE(Roster!E{r}:G{r})"
    if 2 <= cat_index <= 6:
        return f"Roster!{EXAM_SRC[cat_index - 2]}{r}"
    return f"Roster!{EC_SRC[cat_index - 7]}{r}"


def _score_value(name, cat_index):
    d = roster[name]
    if cat_index == 0:
        return sum(d["HW"]) / len(d["HW"])
    if cat_index == 1:
        return sum(d["Q"]) / len(d["Q"])
    if 2 <= cat_index <= 6:
        return d["Exam"][cat_index - 2]
    return d["EC"][cat_index - 7]


def report_view_rows():
    rows = [[cell(col(c + 1) + "1", h) for c, h in enumerate(RV_HDR)]]
    for r, name in enumerate(names, start=2):
        cells = [cell(f"A{r}", name, formula=f"Roster!A{r}", text=True)]
        points_vals = []
        for ci, (wc, sc, pc) in enumerate(TRIPLETS):
            w = CAT_WEIGHTS[ci]
            score = _score_value(name, ci)
            pts = round(w * score / 100.0, 1)
            points_vals.append(pts)
            cells.append(cell(f"{wc}{r}", w))
            cells.append(cell(f"{sc}{r}", score, formula=_score_formula(ci, r)))
            cells.append(cell(f"{pc}{r}", pts,
                              formula=f"ROUND({wc}{r}*{sc}{r}/100,1)"))
        # rule markers H (after Quiz) and X (after Exam 5)
        cells.append(cell(f"H{r}", "---"))
        cells.append(cell(f"X{r}", "---"))
        cur_pts = round(sum(points_vals), 1)
        cur_tot = round(cur_pts / REG_BASE * 100.0, 1)
        sum_f = "ROUND(" + "+".join(f"{c}{r}" for c in PT_COLS) + ",1)"
        cells.append(cell(f"{CUR_PTS}{r}", cur_pts, formula=sum_f))
        cells.append(cell(f"AO{r}", cur_tot,
                          formula=f"ROUND({CUR_PTS}{r}/{REG_BASE}*100,1)"))
        cells.append(cell(f"AP{r}", WEIGHT_SUMMARY))
        need_cols = ["AQ", "AR", "AS", "AT"]
        for (L, cut), nc in zip(CUTOFFS, need_cols):
            need = (cut - cur_pts) / (FINAL_WEIGHT / 100.0)
            if need <= 0:
                val = "Already secured"
            elif need > 100:
                val = f"{need:.1f}% (just out of reach)"
            else:
                val = f"{need:.1f}%"
            base = f"({cut}-{CUR_PTS}{r})/({FINAL_WEIGHT}/100)"
            f = (f'IF({base}<=0,"Already secured",'
                 f'IF({base}>100,TEXT({base},"0.0")&"% (just out of reach)",'
                 f'TEXT({base},"0.0")&"%"))')
            cells.append(cell(f"{nc}{r}", val, formula=f, text=True))
        # Cells must be in column order within the row for strict readers.
        rows.append(_order_cells(cells, r))
    return rows


def _order_cells(cells, r):
    def key(c):
        ref = c.split('r="', 1)[1].split('"', 1)[0]
        letters = "".join(ch for ch in ref if ch.isalpha())
        n = 0
        for ch in letters:
            n = n * 26 + (ord(ch) - 64)
        return n
    return sorted(cells, key=key)


def main():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "gradebook.xlsx")
    write_xlsx(out, [("Roster", roster_rows()),
                     ("Report View", report_view_rows())])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
