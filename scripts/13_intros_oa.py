"""Harvest introductions for papers that currently have only an abstract.

Why this exists alongside 08_intros.py: that script only targeted papers with NO abstract,
so ~900 abstract-level papers with an open-access copy were never attempted. It also trusted
the single cached `oa_url`, which for most works points at a publisher landing page that
blocks bots. Here we ask OpenAlex for *every* location of a work and prefer repository
copies (PMC, LSE, Harvard DASH, NBER, arXiv, eScholarship...) which actually serve PDFs.

Downloads are untrusted: each PDF lands in its own folder under data/pdfs/<cid>/ and is
parsed with PyMuPDF. Run with `python -P` (NOT -I, or PyMuPDF won't import).

    python -P scripts/13_intros_oa.py --limit 25     # sample run
    python -P scripts/13_intros_oa.py                # full run
"""
import argparse, json, re, sys, time, urllib.error, urllib.request
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
PDFS, INTROS = DATA / "pdfs", DATA / "intros"
CACHE = DATA / "cache" / "oa_locations"
for d in (PDFS, INTROS, CACHE):
    d.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
# Name matches 06_build.py's intros_log*.txt glob, so its download_list picks up these failures.
LOG = DATA / "intros_log_oa.txt"

# Repository hosts serve PDFs to scripts; publisher hosts almost always 403 a bot.
# ponytail: substring match, not a registry — add a host when a run shows it working.
REPO_HOSTS = (
    "ncbi.nlm.nih.gov", "europepmc.org", "arxiv.org", "nber.org", "escholarship.org",
    "dash.harvard.edu", "nrs.harvard.edu", "researchonline.lse.ac.uk", "eprints.lse.ac.uk",
    "zora.uzh.ch", "hal.science", "dspace.mit.edu", "econstor.eu", "ageconsearch.umn.edu",
    "journals.plos.org", "hdl.handle.net", "figshare.com", "osf.io", "repec.org",
    "iza.org", "cepr.org", "worldbank.org", "ssrn.com", "oecd.org", "diva-portal.org",
    "core.ac.uk", "semanticscholar.org", "openalex.org", "biorxiv.org", "mdpi.com",
    "frontiersin.org", "springeropen.com", "nature.com/articles", "elifesciences.org",
)

# Publisher walls: every probe returns 403 behind Cloudflare, and a doi.org/handle link just
# redirects into one. Skipping them outright is what makes the full run finish in minutes.
# ponytail: a paper reachable ONLY here is a download_list job for the user, not a fetch bug.
DEAD_HOSTS = (
    "doi.org", "hdl.handle.net", "academic.oup.com", "onlinelibrary.wiley.com",
    "doi.wiley.com", "www.cambridge.org", "www.sciencedirect.com", "linkinghub.elsevier.com",
    "www.jstor.org", "www.annualreviews.org", "journals.uchicago.edu", "www.aeaweb.org",
    "muse.jhu.edu", "www.tandfonline.com", "www.degruyter.com", "link.springer.com",
    "www.econometricsociety.org", "citeseerx.ist.psu.edu",
)


def usable(u):
    host = urlparse(u).netloc.lower()
    return not any(d in host for d in DEAD_HOSTS)


def http(url, accept, timeout=45):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(25_000_000), r.headers.get("Content-Type", ""), r.geturl()


def oa_locations(doi, cid):
    """Every OA pdf url OpenAlex knows for this work, repository copies first. Cached on disk."""
    cf = CACHE / f"{cid}.json"
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    urls = []
    if doi:
        api = f"https://api.openalex.org/works/doi:{doi}?select=best_oa_location,locations"
        try:
            raw, _, _ = http(api, "application/json", timeout=30)
            w = json.loads(raw)
            locs = [w.get("best_oa_location")] + (w.get("locations") or [])
            for loc in locs:
                if not loc:
                    continue
                for key in ("pdf_url", "landing_page_url"):
                    u = loc.get(key)
                    if u and u not in urls:
                        urls.append(u)
        except Exception as e:
            print(f"  oa-api fail {cid} {type(e).__name__}", file=sys.stderr)
    urls.sort(key=lambda u: 0 if any(h in u for h in REPO_HOSTS) else 1)
    cf.write_text(json.dumps(urls), encoding="utf-8")
    return urls


def pdf_from_landing(html, page_url):
    """Repository landing pages advertise the PDF in a citation_pdf_url meta tag."""
    m = re.search(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']', html, re.I)
    if not m:
        return None
    u = m.group(1)
    if u.startswith("/"):
        p = urlparse(page_url)
        u = f"{p.scheme}://{p.netloc}{u}"
    return u


def fetch_pdf(url, dest):
    """True once dest holds a real PDF. Follows one landing-page hop."""
    data, ctype, final = http(url, "application/pdf,text/html;q=0.9")
    if not data.startswith(b"%PDF") and ("html" in ctype.lower() or data[:200].lstrip().startswith(b"<")):
        nxt = pdf_from_landing(data.decode("utf-8", "replace"), final)
        if not nxt or nxt == url:
            return False
        time.sleep(0.5)
        data, ctype, final = http(nxt, "application/pdf")
    if not data.startswith(b"%PDF"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def intro_text(pdf):
    import fitz
    doc = fitz.open(pdf)
    txt = "\n".join(doc[i].get_text() for i in range(min(10, doc.page_count)))
    doc.close()
    txt = re.sub(r"[ \t]+", " ", txt)
    m = re.search(r"\n\s*(?:1\.?|I\.?)?\s*Introduction\s*\n", txt, re.I) or re.search(r"Introduction", txt)
    body = txt[m.end():m.end() + 6000] if m else txt[:6000]
    return re.sub(r"\n(?=[a-z])", " ", body).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after N new intros attempted (sampling)")
    args = ap.parse_args()

    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    R = {r["cid"]: r for r in json.load(open(DATA / "resolved.json", encoding="utf-8"))}

    # Papers that already have an abstract but no intro yet, most-taught first.
    targets = []
    for p in D["papers"]:
        cid = cid_of.get(str(p["id"]))
        if not cid or (INTROS / f"{cid}.txt").exists():
            continue
        r = R.get(cid, {})
        if not (p.get("ab") or r.get("abstract")):
            continue
        if not (r.get("oa_url") or r.get("pdf_url") or r.get("doi")):
            continue
        targets.append((p.get("nc", 0), cid, r))
    targets.sort(key=lambda t: -t[0])
    if args.limit:
        targets = targets[:args.limit]
    print(f"candidates: {len(targets)}", flush=True)

    got = fails = 0
    log = LOG.open("a", encoding="utf-8")
    for i, (nc, cid, r) in enumerate(targets, 1):
        urls = []
        for u in (r.get("pdf_url"), r.get("oa_url")):
            if u and any(h in u for h in REPO_HOSTS):
                urls.append(u)
        for u in oa_locations(r.get("doi"), cid):
            if u not in urls:
                urls.append(u)
        for u in (r.get("pdf_url"), r.get("oa_url")):
            if u and u not in urls:
                urls.append(u)
        m = re.match(r"10\.3386/w(\d+)", r.get("doi") or "")
        if m:
            n = m.group(1)
            urls.append(f"https://www.nber.org/system/files/working_papers/w{n}/w{n}.pdf")

        ok = False
        for u in [u for u in urls if usable(u)][:6]:
            try:
                if fetch_pdf(u, PDFS / cid / "paper.pdf"):
                    (INTROS / f"{cid}.txt").write_text(intro_text(PDFS / cid / "paper.pdf"), encoding="utf-8")
                    log.write(f"ok {cid} {u}\n")
                    ok = True
                    break
                log.write(f"notpdf {cid} {u}\n")
            except Exception as e:
                log.write(f"fail {cid} {u[:100]} {type(e).__name__}\n")
            time.sleep(0.6)
        got += ok
        fails += not ok
        if i % 25 == 0:
            log.flush()
            print(f"  {i}/{len(targets)}  got={got} fail={fails}", flush=True)
    log.close()
    print(f"new introductions: {got} / {len(targets)} attempted")


if __name__ == "__main__":
    main()
