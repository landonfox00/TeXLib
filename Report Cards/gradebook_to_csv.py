#!/usr/bin/env python3
"""gradebook_to_csv.py — extract a worksheet from an .xlsx to CSV.

The report-card class reads a CSV "report-view" (one row per student). The
single source of truth, though, is one gradebook.xlsx per course-semester
(Google Sheets -> Download -> Microsoft Excel keeps every tab in one file).
This converter pulls the report-view tab out of that workbook so the class —
and the TeXLib Sublime builder — can read it.

Dependency-free: standard-library zipfile + ElementTree only (no openpyxl),
so it runs anywhere, including Sublime's bundled Python. It reads each cell's
*cached* value (the <v> element), which Google Sheets and Excel write next to
every formula — so a report-view tab built from formulas converts correctly.

CLI:
    python gradebook_to_csv.py gradebook.xlsx [out.csv] [--sheet "Report View"]

If out.csv is omitted, writes <input>.csv next to the workbook.
If --sheet is omitted, picks "Report View", then "Report Cards", then the
first sheet.
"""

import csv
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

PREFERRED_SHEETS = ("Report View", "Report Cards")


def _local(tag):
    """Strip the XML namespace from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _col_to_index(ref):
    """'B7' -> 2 (1-based column index); ignores the row number."""
    letters = re.match(r"[A-Za-z]+", ref or "")
    if not letters:
        return None
    n = 0
    for ch in letters.group(0).upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def _read_shared_strings(zf):
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    out = []
    for si in root:
        # Each <si> holds either a single <t> or several <r><t> runs.
        out.append("".join(t.text or "" for t in si.iter() if _local(t.tag) == "t"))
    return out


def _sheet_map(zf):
    """Ordered [(name, target_path)] for the workbook's sheets."""
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rels = {}
    for rel in rels_root:
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if not target.startswith("/"):
            target = "xl/" + target.lstrip("/")
        else:
            target = target.lstrip("/")
        rels[rid] = target
    sheets = []
    for el in wb.iter():
        if _local(el.tag) != "sheet":
            continue
        name = el.attrib.get("name", "")
        rid = None
        for k, v in el.attrib.items():
            if _local(k) == "id":   # r:id
                rid = v
        sheets.append((name, rels.get(rid)))
    return sheets


def _pick_sheet(sheets, wanted):
    if wanted:
        for name, target in sheets:
            if name.strip().lower() == wanted.strip().lower():
                return target, name
        raise SystemExit(f"gradebook_to_csv: no sheet named {wanted!r}; "
                         f"have {[s[0] for s in sheets]}")
    for pref in PREFERRED_SHEETS:
        for name, target in sheets:
            if name.strip().lower() == pref.lower():
                return target, name
    if sheets:
        return sheets[0][1], sheets[0][0]
    raise SystemExit("gradebook_to_csv: workbook has no sheets")


def _cell_value(c, shared):
    t = c.attrib.get("t")
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter() if _local(x.tag) == "t")
    v = None
    for child in c:
        if _local(child.tag) == "v":
            v = child.text
            break
    if v is None:
        return ""
    if t == "s":                       # shared-string index
        try:
            return shared[int(v)]
        except (ValueError, IndexError):
            return ""
    return v                            # number, boolean, or cached formula value


def read_sheet(xlsx_path, sheet=None):
    """Return the chosen sheet as a list of row lists (strings)."""
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = _read_shared_strings(zf)
        target, _name = _pick_sheet(_sheet_map(zf), sheet)
        root = ET.fromstring(zf.read(target))
        rows = []
        for row in root.iter():
            if _local(row.tag) != "row":
                continue
            cells = {}
            maxc = 0
            for c in row:
                if _local(c.tag) != "c":
                    continue
                ci = _col_to_index(c.attrib.get("r", ""))
                if ci is None:
                    ci = maxc + 1
                cells[ci] = _cell_value(c, shared)
                maxc = max(maxc, ci)
            rows.append([cells.get(i, "") for i in range(1, maxc + 1)])
    # Drop trailing fully-empty rows.
    while rows and not any(s.strip() for s in rows[-1]):
        rows.pop()
    return rows


def convert(xlsx_path, out_csv=None, sheet=None):
    """Extract `sheet` from `xlsx_path` to `out_csv` (default: <input>.csv)."""
    if out_csv is None:
        out_csv = re.sub(r"\.xlsx$", "", xlsx_path, flags=re.I) + ".csv"
    rows = read_sheet(xlsx_path, sheet)
    width = max((len(r) for r in rows), default=0)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for r in rows:
            w.writerow(r + [""] * (width - len(r)))
    return out_csv


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    sheet = None
    for a in argv:
        if a.startswith("--sheet"):
            sheet = a.split("=", 1)[1] if "=" in a else None
    # Support "--sheet NAME" (space-separated) too.
    if "--sheet" in argv:
        i = argv.index("--sheet")
        if i + 1 < len(argv):
            sheet = argv[i + 1]
            args = [a for a in args if a != sheet]
    if not args:
        print(__doc__)
        return 2
    xlsx = args[0]
    out = args[1] if len(args) > 1 else None
    written = convert(xlsx, out, sheet)
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
