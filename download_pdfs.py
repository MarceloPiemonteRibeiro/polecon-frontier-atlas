"""
PolEcon PDF downloader — Semantic Scholar + Unpaywall
Run: python download_pdfs.py

Strategy (per DOI):
  1. Semantic Scholar API → openAccessPdf URL
  2. Unpaywall API fallback
  3. Resolve NBER doi links to direct .pdf URLs
  4. Skip SSRN (needs login) — logged separately for Zotero

Resumable: rerunning skips DOIs already in download_log.csv.
Rate: ~1 req/s combined (polite crawl).
"""

import csv, json, time, sys
sys.stdout.reconfigure(encoding='utf-8', line_buffering=False)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=False)
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Config ───────────────────────────────────────────────────────────────────
EMAIL       = "marcelo.piemonte.ribeiro@gmail.com"
BASE_DIR    = Path(r"C:\Users\Marcelo\Job_market\my profile\3.research_statement\polecon_frontier_map")
CSV_PATH    = BASE_DIR / "paper_coverage.csv"
PDF_DIR     = BASE_DIR / "pdfs"
LOG_PATH    = BASE_DIR / "download_log.csv"
SS_DELAY    = 0.15   # Semantic Scholar: generous limits
UP_DELAY    = 0.35   # Unpaywall: polite crawl
PDF_TIMEOUT = 30
MAX_PDF_MB  = 50
# ─────────────────────────────────────────────────────────────────────────────

PDF_DIR.mkdir(exist_ok=True)
HEADERS = {"User-Agent": f"PolEcon research downloader; mailto:{EMAIL}"}


def fetch_json(url, timeout=15):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return json.loads(r.read())


def semantic_scholar(doi):
    try:
        return fetch_json(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            f"?fields=isOpenAccess,openAccessPdf"
        )
    except Exception:
        return None


def unpaywall(doi):
    try:
        return fetch_json(f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}")
    except Exception:
        return None


def resolve_url(raw: str) -> str:
    """Convert NBER DOI links to direct PDF URLs."""
    if raw and "doi.org/10.3386/" in raw:
        nber_id = raw.split("10.3386/")[-1].strip("/")
        return f"https://www.nber.org/papers/{nber_id}.pdf"
    return raw


def find_pdf(doi: str) -> tuple[str | None, str]:
    """Return (pdf_url, source) or (None, reason)."""

    # 1. Semantic Scholar
    ss = semantic_scholar(doi)
    time.sleep(SS_DELAY)
    if ss and ss.get("isOpenAccess"):
        raw = (ss.get("openAccessPdf") or {}).get("url")
        if raw:
            resolved = resolve_url(raw)
            if "ssrn.com" in resolved:
                return resolved, "ssrn_needs_login"  # skip download, log for Zotero
            return resolved, "semantic_scholar"

    # 2. Unpaywall
    up = unpaywall(doi)
    time.sleep(UP_DELAY)
    if up and up.get("is_oa"):
        locs = [l for l in (up.get("oa_locations") or []) if l.get("url_for_pdf")]
        if locs:
            locs.sort(key=lambda l: l.get("host_type") != "publisher")
            raw = locs[0]["url_for_pdf"]
            resolved = resolve_url(raw)
            if "ssrn.com" in resolved:
                return resolved, "ssrn_needs_login"
            return resolved, "unpaywall"

    return None, "no_oa"


def download_pdf(pdf_url: str, dest: Path) -> str:
    try:
        req = Request(pdf_url, headers=HEADERS)
        with urlopen(req, timeout=PDF_TIMEOUT) as r:
            data = r.read()
        if len(data) < 5_000:
            return "too_small"
        if len(data) > MAX_PDF_MB * 1024 * 1024:
            return "too_large"
        dest.write_bytes(data)
        return "ok"
    except HTTPError as e:
        return f"http_{e.code}"
    except Exception as e:
        return f"err_{type(e).__name__}"


def load_log() -> set:
    if not LOG_PATH.exists():
        return set()
    with open(LOG_PATH, encoding="utf-8") as f:
        return {r["cid"] for r in csv.DictReader(f)}


def append_log(row: dict):
    write_header = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "doi", "status", "source", "pdf_url"])
        if write_header:
            w.writeheader()
        w.writerow(row)


def main():
    with open(CSV_PATH, encoding="utf-8") as f:
        papers = [r for r in csv.DictReader(f)
                  if r["needs_download"].strip() == "True" and r["doi"].strip()]

    done = load_log()
    todo = [p for p in papers if p["cid"] not in done]

    print(f"Papers to attempt : {len(todo)}")
    print(f"Already logged    : {len(done)}")
    print(f"PDFs → {PDF_DIR}\n")

    stats = {"downloaded": 0, "no_oa": 0, "ssrn": 0, "fail": 0, "skip": 0}

    for i, paper in enumerate(todo):
        cid  = paper["cid"]
        doi  = paper["doi"].strip()
        dest = PDF_DIR / f"{cid}.pdf"

        print(f"[{i+1}/{len(todo)}] {cid}  {doi[:45]}", end="  ", flush=True)

        # Already on disk
        if dest.exists() and dest.stat().st_size > 5_000:
            print("→ already on disk")
            append_log({"cid": cid, "doi": doi, "status": "already_exists", "source": "", "pdf_url": ""})
            stats["skip"] += 1
            continue

        pdf_url, source = find_pdf(doi)

        if source == "no_oa":
            print("→ no OA copy")
            append_log({"cid": cid, "doi": doi, "status": "no_oa", "source": source, "pdf_url": ""})
            stats["no_oa"] += 1

        elif source == "ssrn_needs_login":
            print(f"→ SSRN (needs login) {pdf_url[:50]}")
            append_log({"cid": cid, "doi": doi, "status": "ssrn_needs_login", "source": source, "pdf_url": pdf_url})
            stats["ssrn"] += 1

        else:
            result = download_pdf(pdf_url, dest)
            if result == "ok":
                kb = dest.stat().st_size // 1024
                print(f"→ {kb} KB  [{source}]")
                append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": source, "pdf_url": pdf_url})
                stats["downloaded"] += 1
            else:
                print(f"→ failed: {result}  [{source}]")
                append_log({"cid": cid, "doi": doi, "status": f"dl_fail_{result}", "source": source, "pdf_url": pdf_url})
                stats["fail"] += 1

    # Summary
    total = sum(stats.values())
    print(f"\n{'='*55}")
    print(f"Downloaded   : {stats['downloaded']:4d}  ({100*stats['downloaded']//max(total,1)}%)")
    print(f"No OA copy   : {stats['no_oa']:4d}")
    print(f"SSRN (login) : {stats['ssrn']:4d}  → import these into Zotero")
    print(f"DL failures  : {stats['fail']:4d}")
    print(f"Already had  : {stats['skip']:4d}")
    print(f"\nLog  : {LOG_PATH}")
    print(f"PDFs : {PDF_DIR}")
    print("\nNext step for remaining papers:")
    print("  1. Open Zotero → File → Import → select download_log.csv (no_oa rows)")
    print("  2. Add your library proxy in Zotero Prefs → Proxies")
    print("  3. Select all → right-click → Find Available PDF")


if __name__ == "__main__":
    main()
