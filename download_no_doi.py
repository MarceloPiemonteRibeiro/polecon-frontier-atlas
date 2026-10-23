"""
Download papers without DOIs by title search via OpenAlex.

Two-pass strategy:
  Pass 1 (this script): OpenAlex title search → download OA PDFs directly,
          save discovered DOIs for papers that need VPN/browser auth.
  Pass 2 (vpn_download.py): user runs existing script on newly-discovered DOIs.

For each paper:
  1. OpenAlex search → match by title → collect DOI + OA URLs
  2. Try downloading OA/NBER PDFs directly (no auth needed)
  3. Try DOI-based publisher URLs (works for some publishers via VPN IP)
  4. If DOI found but download failed → save DOI for vpn_download.py

Outputs:
  - PDFs in pdfs/ (directly downloadable ones)
  - no_doi_download_log.csv (per-paper results)
  - no_doi_found_dois.csv (DOIs for vpn_download.py pass)

Resumable. Rate: ~1 req/s (OpenAlex polite pool).
Usage: python download_no_doi.py [--batch N]
"""
import csv, json, re, sys, time
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

EMAIL = "marcelo.piemonte.ribeiro@gmail.com"
BASE = Path(r"C:\Users\Marcelo\Job_market\my profile\3.research_statement\polecon_frontier_map")
CSV_PATH = BASE / "manual_download_no_doi.csv"
PDF_DIR = BASE / "pdfs"
LOG_PATH = BASE / "no_doi_download_log.csv"
DOIS_PATH = BASE / "no_doi_found_dois.csv"

PDF_DIR.mkdir(exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS_DL = {"User-Agent": UA, "Accept": "application/pdf,*/*"}
HEADERS_API = {"User-Agent": f"PolEcon research downloader; mailto:{EMAIL}"}

BATCH_SIZE = None
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--batch" and i < len(sys.argv) - 1:
        BATCH_SIZE = int(sys.argv[i + 1])


def fetch_json(url, timeout=15, retries=2):
    for attempt in range(retries + 1):
        try:
            with urlopen(Request(url, headers=HEADERS_API), timeout=timeout) as r:
                return json.loads(r.read())
        except HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"\n  [429 rate limit, waiting {wait}s...]", end="", flush=True)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("fetch_json: retries exhausted")


def download_pdf(url, dest, timeout=25):
    try:
        req = Request(url, headers=HEADERS_DL)
        with urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("Content-Type", "")
            if "html" in ct.lower() and "pdf" not in ct.lower():
                return False
            data = r.read()
        if len(data) < 5000 or data[:5] != b"%PDF-":
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def clean_title(title):
    t = re.sub(r'^"|"$', '', title)
    t = re.split(r',\s*(American Economic Review|Quarterly Journal|Journal of|NBER|CEPR|RePEc)', t)[0]
    return t.rstrip('.,;: ')


def search_safe(title):
    return re.sub(r'[?*"]+', ' ', title).strip()


def normalize(s):
    return re.sub(r'\W+', ' ', s.lower()).strip()


def titles_match(query, candidate):
    q, c = normalize(query), normalize(candidate)
    if not q or not c:
        return False
    return q[:35] in c or c[:35] in q


def pdf_url_from_doi(doi):
    urls = []
    if "10.1257" in doi: urls.append(f"https://pubs.aeaweb.org/doi/pdf/{doi}")
    if "10.1093" in doi: urls.append(f"https://academic.oup.com/restud/article-pdf/doi/{doi}")
    if "10.1086" in doi: urls.append(f"https://www.journals.uchicago.edu/doi/pdf/{doi}")
    if "10.3982" in doi: urls.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
    if "10.1111" in doi: urls.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
    if "10.1162" in doi: urls.append(f"https://direct.mit.edu/rest/article-pdf/doi/{doi}")
    if "10.2307" in doi:
        jstor_id = doi.replace("10.2307/", "")
        urls.append(f"https://www.jstor.org/stable/pdf/{jstor_id}.pdf")
    if "10.1016" in doi: urls.append(f"https://doi.org/{doi}")
    if "10.1007" in doi: urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    if "10.1146" in doi: urls.append(f"https://www.annualreviews.org/doi/pdf/{doi}")
    if "10.1177" in doi: urls.append(f"https://journals.sagepub.com/doi/pdf/{doi}")
    if "10.1080" in doi: urls.append(f"https://www.tandfonline.com/doi/pdf/{doi}")
    if "10.1126" in doi: urls.append(f"https://www.science.org/doi/pdf/{doi}")
    if "10.3386" in doi:
        nber_id = doi.split("10.3386/")[-1]
        urls.append(f"https://www.nber.org/papers/{nber_id}.pdf")
    if "10.1515" in doi: urls.append(f"https://www.degruyterbrill.com/document/doi/{doi}/pdf")
    if "10.1561" in doi: urls.append(f"https://www.nowpublishers.com/article/Download/{doi}")
    return urls


def try_download_all_urls(pdf_urls, doi, dest):
    """Try OA URLs first, then DOI-based publisher patterns."""
    for url in pdf_urls:
        if "ssrn.com" in url:
            continue
        if download_pdf(url, dest):
            return True, f"oa_direct:{url[:60]}"
        time.sleep(0.3)

    if doi:
        for url in pdf_url_from_doi(doi):
            if download_pdf(url, dest):
                return True, f"doi_direct:{doi[:40]}"
            time.sleep(0.3)

        # Unpaywall as last resort
        try:
            up = fetch_json(f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}")
            if up.get("is_oa"):
                for loc in (up.get("oa_locations") or []):
                    pdf_url = loc.get("url_for_pdf")
                    if pdf_url and "ssrn.com" not in pdf_url:
                        if download_pdf(pdf_url, dest):
                            return True, f"unpaywall:{doi[:40]}"
        except Exception:
            pass

    return False, ""


def _extract_from_work(w):
    """Extract doi + pdf_urls from an OpenAlex work record."""
    pdf_urls = []
    for loc_key in ("best_oa_location", "primary_location"):
        loc = w.get(loc_key) or {}
        if loc.get("pdf_url"):
            pdf_urls.append(loc["pdf_url"])
    oa = w.get("open_access") or {}
    if oa.get("oa_url"):
        pdf_urls.append(oa["oa_url"])
    doi_url = w.get("doi")
    doi = doi_url.replace("https://doi.org/", "") if doi_url else None
    return doi, pdf_urls


def _match_results(results, title, year):
    """Find best matching work from OpenAlex results."""
    clean = clean_title(title)
    for w in (results or []):
        wtitle = w.get("title") or ""
        if not titles_match(clean, wtitle):
            continue
        wyear = w.get("publication_year")
        if year and wyear and abs(int(year) - wyear) > 3:
            continue
        doi, pdf_urls = _extract_from_work(w)
        return doi, pdf_urls, wtitle
    return None, [], None


SELECT = "title,publication_year,doi,open_access,primary_location,best_oa_location"


def lookup_openalex_id(work_id):
    """Direct lookup for W-prefixed OpenAlex IDs."""
    try:
        data = fetch_json(
            f"https://api.openalex.org/works/{work_id}"
            f"?select={SELECT}&mailto={EMAIL}"
        )
        doi, pdf_urls = _extract_from_work(data)
        return doi, pdf_urls, data.get("title")
    except Exception:
        return None, [], None


def search_openalex(title, year, cid=""):
    """Search OpenAlex with ID lookup / text search / filter fallback."""
    from urllib.parse import quote

    # Strategy 0: direct ID lookup for W-prefixed CIDs
    if cid.startswith("W") and cid[1:].isdigit():
        result = lookup_openalex_id(cid)
        if result[2]:
            return result

    clean = search_safe(clean_title(title))
    # Use only first ~80 chars of title for search (avoids publisher/venue noise)
    short_clean = clean.split(",")[0].strip()[:100]

    # Strategy A: text search (broader, better for fuzzy matching)
    query = quote_plus(short_clean)
    try:
        data = fetch_json(
            f"https://api.openalex.org/works?search={query}&per_page=5"
            f"&select={SELECT}&mailto={EMAIL}"
        )
        doi, pdf_urls, matched = _match_results(data.get("results"), title, year)
        if matched:
            return doi, pdf_urls, matched
    except Exception:
        pass

    time.sleep(2)

    # Strategy B: filter by display_name with year
    filt = f"display_name.search:{short_clean}"
    if year:
        filt += f",publication_year:{year}"
    try:
        data = fetch_json(
            f"https://api.openalex.org/works?filter={quote(filt)}&per_page=5"
            f"&select={SELECT}&mailto={EMAIL}"
        )
        doi, pdf_urls, matched = _match_results(data.get("results"), title, year)
        if matched:
            return doi, pdf_urls, matched
    except Exception:
        pass

    # Strategy C: filter without year
    if year:
        time.sleep(2)
        try:
            data = fetch_json(
                f"https://api.openalex.org/works?filter={quote(f'display_name.search:{short_clean}')}"
                f"&per_page=5&select={SELECT}&mailto={EMAIL}"
            )
            doi, pdf_urls, matched = _match_results(data.get("results"), title, "")
            if matched:
                return doi, pdf_urls, matched
        except Exception:
            pass

    return None, [], None


# --- Log ---

def load_log():
    done = {}
    if LOG_PATH.exists():
        with open(LOG_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done[r["cid"]] = r
    return done


def append_log(row):
    write_header = not LOG_PATH.exists() or LOG_PATH.stat().st_size < 10
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "title", "status", "doi", "source"])
        if write_header:
            w.writeheader()
        w.writerow(row)


def save_found_dois(dois):
    with open(DOIS_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "doi", "title"])
        w.writeheader()
        w.writerows(dois)


# --- Main ---

def main():
    with open(CSV_PATH, encoding="utf-8") as f:
        papers = list(csv.DictReader(f))

    existing_pdfs = {p.stem for p in PDF_DIR.glob("*.pdf")}
    log = load_log()

    todo = [p for p in papers
            if p["cid"] not in existing_pdfs
            and log.get(p["cid"], {}).get("status") != "downloaded"]

    if BATCH_SIZE:
        todo = todo[:BATCH_SIZE]

    if not todo:
        print("Nothing to download!")
        return

    print(f"Papers to attempt: {len(todo)}")
    print(f"Already on disk:   {len(existing_pdfs)}")
    print(f"Strategy: OpenAlex → OA download / DOI → publisher patterns / Unpaywall")
    print()

    stats = {"downloaded": 0, "doi_found_no_dl": 0, "no_match": 0}
    found_dois = []
    start = time.time()

    for i, p in enumerate(todo):
        cid = p["cid"]
        title = p["title"]
        year = p.get("year", "").strip()
        authors = p.get("authors", "")
        dest = PDF_DIR / f"{cid}.pdf"

        if dest.exists() and dest.stat().st_size > 5000:
            continue

        short = f"{authors} ({year}) {title[:50]}"
        print(f"[{i+1}/{len(todo)}] {cid} {short}", end="  ", flush=True)

        # Search OpenAlex
        doi, pdf_urls, matched = search_openalex(title, year, cid)
        time.sleep(2)

        if matched:
            # Try downloading
            ok, detail = try_download_all_urls(pdf_urls, doi, dest)
            if ok:
                kb = dest.stat().st_size // 1024
                print(f"-> {kb} KB [{detail.split(':')[0]}]")
                stats["downloaded"] += 1
                append_log({"cid": cid, "title": title[:80], "status": "downloaded", "doi": doi or "", "source": detail})
            elif doi:
                print(f"-> DOI found ({doi[:40]}) but can't download directly")
                stats["doi_found_no_dl"] += 1
                found_dois.append({"cid": cid, "doi": doi, "title": title[:100]})
                append_log({"cid": cid, "title": title[:80], "status": "doi_only", "doi": doi, "source": "needs_vpn_browser"})
            else:
                print(f"-> matched but no DOI, no OA PDF")
                stats["no_match"] += 1
                append_log({"cid": cid, "title": title[:80], "status": "no_pdf", "doi": "", "source": "matched_no_url"})
        else:
            print(f"-> not found in OpenAlex")
            stats["no_match"] += 1
            append_log({"cid": cid, "title": title[:80], "status": "not_found", "doi": "", "source": "no_openalex_match"})

        if (i + 1) % 25 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed * 3600
            remaining = len(todo) - i - 1
            eta_m = remaining / rate * 60 if rate > 0 else 0
            print(f"\n  --- {i+1}/{len(todo)} | DL: {stats['downloaded']} | "
                  f"DOI-only: {stats['doi_found_no_dl']} | "
                  f"Missing: {stats['no_match']} | ~{eta_m:.0f}m left ---\n")

    # Save DOIs for vpn_download.py
    if found_dois:
        save_found_dois(found_dois)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed/60:.1f} min")
    print(f"Downloaded directly : {stats['downloaded']}")
    print(f"DOI found, need VPN : {stats['doi_found_no_dl']}")
    print(f"Not found / no PDF  : {stats['no_match']}")
    print(f"Total PDFs on disk  : {len(list(PDF_DIR.glob('*.pdf')))}")
    if found_dois:
        print(f"\nSaved {len(found_dois)} DOIs to {DOIS_PATH.name}")
        print(f"Feed these into vpn_download.py for browser-based download.")


if __name__ == "__main__":
    main()
