"""Ingest PDFs the user downloaded into polecon_frontier_map/inbox/.

Name a file after the `save_pdf_as` column of download_list.csv (e.g. C00123.pdf) for an exact match; any other name is
matched by the paper title found on the first pages. The abstract + introduction go to data/intros/<cid>.txt (07_batches.py
then puts them in a reading batch) and the PDF moves to inbox/done/. Run with `python -P` (PDFs are untrusted input).
"""
import csv, importlib.util, re, shutil, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INBOX, DONE, INTROS = BASE / "inbox", BASE / "inbox" / "done", BASE / "data" / "intros"
spec = importlib.util.spec_from_file_location("intros", Path(__file__).with_name("08_intros.py"))
I8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(I8)


def words(s):
    return set(w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in {"the", "and", "for", "from", "with", "evidence"})


def main():
    INBOX.mkdir(exist_ok=True); DONE.mkdir(exist_ok=True); INTROS.mkdir(exist_ok=True)
    rows = list(csv.DictReader(open(BASE / "download_list.csv", encoding="utf-8-sig")))
    by_cid = {r["save_pdf_as"][:-4]: r for r in rows}
    pdfs = sorted(INBOX.glob("*.pdf"))
    print(len(pdfs), "PDFs in inbox")
    for pdf in pdfs:
        cid = pdf.stem.upper() if pdf.stem.upper() in by_cid else None
        if not cid:                                    # match by title on the first two pages
            import fitz
            doc = fitz.open(pdf)
            head = words(" ".join(doc[i].get_text() for i in range(min(2, doc.page_count))))
            best = max(rows, key=lambda r: len(words(r["title"]) & head) / max(1, len(words(r["title"]))))
            score = len(words(best["title"]) & head) / max(1, len(words(best["title"])))
            if score < 0.7:
                print("  no confident match:", pdf.name, f"(best {best['title'][:60]!r}, {score:.2f})", file=sys.stderr)
                continue
            cid = best["save_pdf_as"][:-4]
        (INTROS / f"{cid}.txt").write_text(I8.intro_text(pdf), encoding="utf-8")
        shutil.move(str(pdf), DONE / f"{cid}.pdf")
        print("  ok", cid, by_cid[cid]["title"][:70])


if __name__ == "__main__":
    main()
