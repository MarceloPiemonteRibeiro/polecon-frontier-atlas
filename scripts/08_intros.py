"""Fetch introductions for core papers that have no abstract: open-access PDF, else the NBER working-paper PDF.

Downloads are untrusted: each PDF lands in its own folder under data/pdfs/<cid>/ and is parsed with PyMuPDF
(run this script with `python -I`). The extracted introduction (first ~4,500 chars after the heading) goes to data/intros/<cid>.txt.
"""
import json, re, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
PDFS, INTROS = DATA / "pdfs", DATA / "intros"
PDFS.mkdir(exist_ok=True); INTROS.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (academic literature mapping; polecon-frontier-map)"


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(25_000_000)
    if not data.startswith(b"%PDF"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def intro_text(pdf):
    import fitz
    doc = fitz.open(pdf)
    txt = "\n".join(doc[i].get_text() for i in range(min(8, doc.page_count)))
    txt = re.sub(r"[ \t]+", " ", txt)
    m = re.search(r"\n\s*(?:1\.?|I\.?)?\s*Introduction\s*\n", txt, re.I) or re.search(r"Introduction", txt)
    start = m.end() if m else 0
    body = txt[start:start + 4500]
    if not m:  # no heading: keep abstract area + first page
        body = txt[:4500]
    return re.sub(r"\n(?=[a-z])", " ", body).strip()


def main():
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    R = {r["cid"]: r for r in json.load(open(DATA / "resolved.json", encoding="utf-8"))}
    s2 = json.load(open(DATA / "s2_pdfs.json", encoding="utf-8")) if (DATA / "s2_pdfs.json").exists() else {}
    targets = [p for p in D["papers"] if p["f"] < 8 and not p.get("ab") and not p.get("fd")
               and (p["nc"] >= 2 or p.get("vox") or "BREAD26" in p["cs"] or (p["fr"] and p["nc"] >= 1))]
    print("core papers without abstract:", len(targets))
    got = 0
    for p in targets:
        cid = cid_of[str(p["id"])]
        out = INTROS / f"{cid}.txt"
        if out.exists():
            got += 1
            continue
        r = R.get(cid, {})
        urls = []
        for u in (r.get("pdf_url"), s2.get(cid), r.get("oa_url")):
            if u and u not in urls:
                urls.append(u)
        for d in (r.get("wp_doi"), r.get("doi")):
            m = re.match(r"10\.3386/w(\d+)", d or "")
            if m:
                n = m.group(1)
                urls.append(f"https://www.nber.org/system/files/working_papers/w{n}/w{n}.pdf")
        for u in urls:
            dest = PDFS / cid / "paper.pdf"
            try:
                if fetch(u, dest):
                    out.write_text(intro_text(dest), encoding="utf-8")
                    got += 1
                    break
            except Exception as e:
                print("  fail", cid, u[:80], type(e).__name__, file=sys.stderr)
            time.sleep(0.5)
    print("introductions available:", got)


if __name__ == "__main__":
    main()
