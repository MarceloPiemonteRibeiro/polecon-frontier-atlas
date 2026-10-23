"""What text do we actually hold for each paper? Writes paper_coverage.csv + a colour-coded .xlsx.

green  = introduction read (full text harvested)
yellow = abstract only, an open-access copy may still exist
red    = you need to download this one by hand (publisher-walled, no OA copy)

Run with `python -P` (not -I, or openpyxl in user site-packages won't import).

    python -P scripts/14_coverage_report.py
"""
import csv, glob, json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

GREEN, YELLOW, RED = "FFC6EFCE", "FFFFEB9C", "FFFFC7CE"


def load():
    atlas = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    papers = atlas["papers"] if isinstance(atlas, dict) else atlas
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    resolved = {r["cid"]: r for r in json.load(open(DATA / "resolved.json", encoding="utf-8"))}
    s2 = json.load(open(DATA / "s2_abstracts.json", encoding="utf-8"))
    intros = {p.stem for p in (DATA / "intros").glob("*.txt")}

    coded = set()
    for f in glob.glob(str(DATA / "annot_*.txt")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                coded.add(line.split("|")[0].strip())

    tiers = {}
    dl = BASE / "download_list.csv"
    if dl.exists():
        for row in csv.DictReader(open(dl, encoding="utf-8")):
            tiers[row.get("save_pdf_as", "").replace(".pdf", "")] = row.get("tier", "")
    return papers, cid_of, resolved, s2, intros, coded, tiers


def build():
    papers, cid_of, resolved, s2, intros, coded, tiers = load()
    s2_text = {k for k, v in s2.items() if v}
    rows = []
    for p in papers:
        cid = cid_of.get(str(p.get("id", "")), "")
        if not cid:
            continue
        r = resolved.get(cid, {})
        has_intro = cid in intros
        has_abs = bool(p.get("ab") or r.get("abstract") or cid in s2_text)
        level = "introduction" if has_intro else ("abstract" if has_abs else "title_only")
        # Red = no full text and no OA copy left to try: a human has to fetch it.
        oa = bool(r.get("oa_url") or r.get("pdf_url"))
        rows.append({
            "cid": cid,
            "authors": p.get("au", ""),
            "year": p.get("y", ""),
            "title": p.get("t", ""),
            "venue": p.get("v", ""),
            "doi": p.get("doi", ""),
            "n_courses": p.get("nc", 0),
            "text_available": level,
            "needs_download": not has_intro and not oa,
            # 1,973 rows need a human; only the most-taught are worth your time first.
            "download_priority": "" if (has_intro or oa) else (
                "high" if p.get("nc", 0) >= 3 else "medium" if p.get("nc", 0) >= 1 else "low"),
            "has_oa_copy": oa,
            "manually_coded": cid in coded,
            "download_tier": tiers.get(cid, ""),
        })
    order = {"introduction": 0, "abstract": 1, "title_only": 2}
    rows.sort(key=lambda r: (order[r["text_available"]], -r["n_courses"]))
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_xlsx(rows, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "coverage"
    cols = list(rows[0].keys())
    ws.append([c.replace("_", " ").title() for c in cols])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFFFF")
        c.fill = PatternFill("solid", fgColor="FF44546A")
        c.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"

    for r in rows:
        ws.append([r[c] for c in cols])
        fill = GREEN if r["text_available"] == "introduction" else (RED if r["needs_download"] else YELLOW)
        for c in ws[ws.max_row]:
            c.fill = PatternFill("solid", fgColor=fill)

    widths = {"cid": 9, "authors": 34, "year": 6, "title": 70, "venue": 30,
              "doi": 30, "n_courses": 10, "text_available": 15, "needs_download": 15,
              "download_priority": 17, "has_oa_copy": 12, "manually_coded": 15, "download_tier": 13}
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(c, 14)
    ws.auto_filter.ref = ws.dimensions

    legend = wb.create_sheet("legend")
    for i, (txt, fill) in enumerate([
        ("GREEN - introduction read (full text harvested)", GREEN),
        ("YELLOW - abstract only; an open-access copy exists to retry", YELLOW),
        ("RED - download by hand: publisher-walled, no OA copy found", RED),
        ("", "FFFFFFFF"),
        ("Filter Download Priority = high for the 149 most-taught reds first.", "FFFFFFFF"),
    ], 1):
        legend.cell(i, 1, txt).fill = PatternFill("solid", fgColor=fill)
    legend.column_dimensions["A"].width = 64
    wb.save(path)


def main():
    rows = build()
    write_csv(rows, BASE / "paper_coverage.csv")
    write_xlsx(rows, BASE / "paper_coverage.xlsx")
    lv = Counter(r["text_available"] for r in rows)
    print(f"papers: {len(rows)}")
    print(f"  introduction : {lv['introduction']}")
    print(f"  abstract     : {lv['abstract']}")
    print(f"  title only   : {lv['title_only']}")
    print(f"  RED need download : {sum(r['needs_download'] for r in rows)}")
    assert sum(lv.values()) == len(rows)


if __name__ == "__main__":
    main()
