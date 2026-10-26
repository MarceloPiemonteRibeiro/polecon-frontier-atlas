"""
Interactive download for failed papers — you stay nearby to handle CAPTCHAs/logins.

Strategy per paper:
  1. requests → direct publisher PDF URL + Semantic Scholar + Unpaywall
  2. Chrome → DOI navigation + publisher PDF patterns + page scraping
  3. Chrome → Google Scholar search (author year title)
  4. Chrome → Google web search (author year title pdf)

Between strategies, pauses so you can intervene (solve CAPTCHA, login).

Usage: python interactive_download.py [--batch N]
"""
import base64, csv, json, os, random, re, shutil, sys, time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE = Path(r"D:\GitHub\polecon-frontier-atlas")
MASTER = BASE / "papers_master.csv"
PDF_DIR = BASE / "pdfs"
LOG_PATH = BASE / "logs" / "interactive_download_log.csv"
TEMP_DL = BASE / "_downloads"

PDF_DIR.mkdir(exist_ok=True)
TEMP_DL.mkdir(exist_ok=True)

EMAIL = "marcelo.piemonte.ribeiro@gmail.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "application/pdf,*/*"}

BATCH_SIZE = None
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--batch" and i < len(sys.argv) - 1:
        BATCH_SIZE = int(sys.argv[i + 1])

# --- Rate limiting ---
_last_domain = defaultdict(float)

def rate_limit(url, delay=5.0):
    domain = urlparse(url).netloc.replace("www.", "")
    elapsed = time.time() - _last_domain[domain]
    if elapsed < delay:
        time.sleep(delay - elapsed + random.uniform(0.5, 2.0))
    _last_domain[domain] = time.time()


# --- Publisher PDF URLs ---

def pdf_url_from_doi(doi, final_url=""):
    urls = []
    fu = final_url.lower()
    if "aeaweb.org" in fu or "10.1257" in doi:
        urls.append(f"https://pubs.aeaweb.org/doi/pdf/{doi}")
    if "academic.oup.com" in fu:
        if "/article/" in fu:
            urls.append(final_url.replace("/article/", "/article-pdf/").split("?")[0] + "?redirect=false")
        elif "/edited-volume/" in fu or "/book/" in fu:
            urls.append(final_url.rstrip("/") + "/pdf")
    if "10.1093" in doi and not any("oup.com" in u for u in urls):
        urls.append(f"https://academic.oup.com/restud/article-pdf/doi/{doi}")
    if "journals.uchicago.edu" in fu or ("10.1086" in doi and "jstor.org" not in fu):
        urls.append(f"https://www.journals.uchicago.edu/doi/pdf/{doi}")
    if "10.3982" in doi:
        urls.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
    if "wiley.com" in fu or ("10.1111" in doi and "10.3982" not in doi):
        urls.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
    if "direct.mit.edu" in fu or "10.1162" in doi:
        urls.append(f"https://direct.mit.edu/rest/article-pdf/doi/{doi}")
    if "jstor.org" in fu and "/stable/" in fu:
        stable_id = final_url.split("/stable/")[-1].split("?")[0].split("#")[0]
        if stable_id:
            urls.append(f"https://www.jstor.org/stable/pdf/{stable_id}.pdf")
    if "10.2307" in doi:
        jstor_id = doi.replace("10.2307/", "")
        urls.append(f"https://www.jstor.org/stable/pdf/{jstor_id}.pdf")
    if "10.1086" in doi and "jstor.org" in fu and "/stable/" in fu:
        stable_id = final_url.split("/stable/")[-1].split("?")[0].split("#")[0]
        if stable_id:
            urls.append(f"https://www.jstor.org/stable/pdf/{stable_id}.pdf")
    if "cambridge.org" in fu:
        if "/article/" in fu and "/pdf/" not in fu:
            urls.append(final_url.replace("/article/", "/article/pdf/"))
    if "sciencedirect.com" in fu and "/article/pii/" in fu:
        pii = final_url.split("/article/pii/")[-1].split("?")[0].split("/")[0]
        urls.append(f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true")
    if "10.1016" in doi and not any("sciencedirect" in u for u in urls):
        urls.append(f"https://doi.org/{doi}")
    if "link.springer.com" in fu or "10.1007" in doi:
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    if "annualreviews.org" in fu or "10.1146" in doi:
        urls.append(f"https://www.annualreviews.org/content/journals/{doi}")
    if "sagepub.com" in fu or "10.1177" in doi:
        urls.append(f"https://journals.sagepub.com/doi/pdf/{doi}")
    if "tandfonline.com" in fu or "10.1080" in doi:
        urls.append(f"https://www.tandfonline.com/doi/pdf/{doi}?needAccess=true")
    if "science.org" in fu or "10.1126" in doi:
        urls.append(f"https://www.science.org/doi/pdf/{doi}")
    if "10.1561" in doi:
        urls.append(f"https://www.nowpublishers.com/article/Download/{doi}")
    if "degruyter" in fu or "10.1515" in doi:
        urls.append(f"https://www.degruyterbrill.com/document/doi/{doi}/pdf")
    if "emerald.com" in fu or "10.1108" in doi:
        urls.append(f"https://www.emerald.com/insight/content/doi/{doi}/full/pdf")
    if "nature.com" in fu or "10.1038" in doi:
        urls.append(f"https://www.nature.com/articles/{doi.split('/')[-1]}.pdf")
    if "informs.org" in fu or "10.1287" in doi:
        urls.append(f"https://pubsonline.informs.org/doi/pdf/{doi}")
    if "ssrn.com" in fu or "10.2139" in doi:
        ssrn_id = doi.replace("10.2139/ssrn.", "")
        urls.append(f"https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID{ssrn_id}_code.pdf?abstractid={ssrn_id}&type=2")
    # Princeton UP, other book DOIs — try doi.org directly
    if "princeton" in doi or "23943" in doi or "9780" in doi:
        urls.append(f"https://doi.org/{doi}")
    return urls


# --- Requests download ---

def download_with_requests(url, dest, timeout=25):
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("Content-Type", "")
            if "html" in ct.lower() and "pdf" not in ct.lower():
                return False, "html_response"
            data = r.read()
        if len(data) < 5000:
            return False, "too_small"
        if not data[:5] == b"%PDF-":
            return False, "not_pdf"
        dest.write_bytes(data)
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}"


def try_requests(doi, dest):
    for url in pdf_url_from_doi(doi):
        rate_limit(url)
        ok, reason = download_with_requests(url, dest)
        if ok:
            return True, f"req:{url[:50]}"
    # Semantic Scholar
    try:
        ss_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=isOpenAccess,openAccessPdf"
        req = Request(ss_url, headers={"User-Agent": f"PolEcon; mailto:{EMAIL}"})
        with urlopen(req, timeout=10) as r:
            ss = json.loads(r.read())
        if ss.get("isOpenAccess"):
            pdf_url = (ss.get("openAccessPdf") or {}).get("url")
            if pdf_url:
                ok, _ = download_with_requests(pdf_url, dest)
                if ok:
                    return True, f"req_ss:{pdf_url[:50]}"
    except Exception:
        pass
    # Unpaywall
    try:
        up_url = f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}"
        req = Request(up_url, headers={"User-Agent": f"PolEcon; mailto:{EMAIL}"})
        with urlopen(req, timeout=10) as r:
            up = json.loads(r.read())
        if up.get("is_oa"):
            for loc in (up.get("oa_locations") or [])[:3]:
                pdf_url = loc.get("url_for_pdf")
                if pdf_url:
                    ok, _ = download_with_requests(pdf_url, dest)
                    if ok:
                        return True, f"req_oa:{pdf_url[:50]}"
    except Exception:
        pass
    return False, "req_exhausted"


# --- Chrome setup ---

_driver = None

def get_driver(fresh=False):
    global _driver
    if not fresh and _driver is not None:
        try:
            _ = _driver.current_url
            return _driver
        except Exception:
            try: _driver.quit()
            except: pass
            _driver = None

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(TEMP_DL),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    })
    print("  [Starting Chrome...]", flush=True)
    _driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    _driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    _driver.set_page_load_timeout(40)
    return _driver


def clear_temp():
    for f in TEMP_DL.iterdir():
        try: f.unlink()
        except: pass


def wait_for_download(timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        files = list(TEMP_DL.iterdir())
        done = [f for f in files if not f.name.endswith((".crdownload", ".tmp"))]
        if done:
            time.sleep(0.5)
            for f in done:
                try:
                    if f.stat().st_size > 5000:
                        return f
                except: continue
            return None
        time.sleep(0.5)
    return None


def try_chrome_dl(driver, url, dest, wait=0):
    clear_temp()
    rate_limit(url)
    try: driver.get(url)
    except: pass
    time.sleep(3 + wait)
    dl = wait_for_download(timeout=15 + wait)
    if dl and dl.stat().st_size > 5000:
        try:
            shutil.move(str(dl), str(dest))
            clear_temp()
            return True
        except: pass
    try:
        ct = driver.execute_script("return document.contentType;")
        if ct and "pdf" in ct.lower():
            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
            data = base64.b64decode(pdf_data["data"])
            if len(data) > 5000:
                dest.write_bytes(data)
                return True
    except: pass
    clear_temp()
    return False


def try_chrome_doi(doi, dest):
    try:
        driver = get_driver()
    except Exception as e:
        return False, f"chrome_fail:{type(e).__name__}"

    rate_limit(f"https://doi.org/{doi}")
    final_url = ""
    try:
        driver.get(f"https://doi.org/{doi}")
        time.sleep(5)
        final_url = driver.current_url
    except Exception as e:
        try: final_url = driver.current_url
        except: return False, f"doi_resolve:{type(e).__name__}"

    # Auth redirect — try direct PDF URLs
    if any(x in final_url.lower() for x in ["adfs.", "shibboleth", "login"]):
        for url in pdf_url_from_doi(doi):
            if try_chrome_dl(driver, url, dest, wait=5):
                return True, f"chrome_bypass:{url[:50]}"
        return False, f"auth:{final_url[:50]}"

    # Try constructed PDF URLs
    extra = 5 if any(d in final_url.lower() for d in ["sciencedirect", "jstor", "emerald"]) else 2
    for url in pdf_url_from_doi(doi, final_url):
        if try_chrome_dl(driver, url, dest, wait=extra):
            return True, f"chrome:{url[:50]}"

    # Scrape page for PDF links
    from selenium.webdriver.common.by import By
    if final_url:
        rate_limit(final_url)
        try: driver.get(final_url)
        except: pass
        time.sleep(4)

        seen = set()
        for sel in ["a[href*='/pdf']", "a[href*='.pdf']", "a[href*='pdfft']",
                     "a[href*='pdfdirect']", "a[href*='download']"]:
            try:
                for link in driver.find_elements(By.CSS_SELECTOR, sel):
                    href = link.get_attribute("href")
                    if href and href not in seen:
                        seen.add(href)
                        if try_chrome_dl(driver, href, dest, wait=extra):
                            return True, f"scrape:{href[:50]}"
            except: continue

        # Click "Download PDF" buttons
        for xpath in [
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download pdf')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view pdf')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download pdf')]",
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xpath)[:2]:
                    href = el.get_attribute("href")
                    if href and href not in seen:
                        seen.add(href)
                        if try_chrome_dl(driver, href, dest, wait=extra):
                            return True, f"btn:{href[:50]}"
                    else:
                        clear_temp()
                        try:
                            el.click()
                            time.sleep(4)
                            dl = wait_for_download(timeout=15)
                            if dl and dl.stat().st_size > 5000:
                                shutil.move(str(dl), str(dest))
                                clear_temp()
                                return True, f"click:{final_url[:50]}"
                        except: pass
            except: continue

    return False, f"chrome_exhausted:{final_url[:50]}"


# --- Google Scholar / Google search ---

_consent_done = False

def dismiss_consent(driver):
    from selenium.webdriver.common.by import By
    time.sleep(2)
    for text in ["Reject all", "Alle ablehnen", "Tout refuser", "I agree", "Accept all"]:
        try:
            for b in driver.find_elements(By.XPATH,
                f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                f"'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"):
                if b.is_displayed():
                    b.click()
                    time.sleep(1)
                    return True
        except: continue
    return False

def is_captcha(driver):
    try:
        url = driver.current_url
        page = driver.page_source[:2000].lower()
        return "sorry/index" in url or "captcha" in page or "unusual traffic" in page
    except: return False

def build_query(paper):
    title = paper.get("title", "")
    title = re.sub(r'<[^>]+>', '', title)  # strip HTML tags
    title = re.sub(r'\s*(Cambridge|Oxford|Princeton).*Press.*', '', title)
    title = title.strip('.,;: "')[:120]
    auth = paper.get("authors", "").split(",")[0].split(" et al.")[0].strip()
    year = paper.get("year", "")
    return " ".join(p for p in [auth, year, title] if p)

def collect_pdf_links(driver):
    from selenium.webdriver.common.by import By
    pdf_links, result_links = [], []
    try:
        for link in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = link.get_attribute("href") or ""
            text = (link.text or "").strip()
            if "/scholar?" in href or "scholar.google" in href:
                continue
            if "google.com/url?" in href:
                parsed = parse_qs(urlparse(href).query)
                href = unquote(parsed.get("q", parsed.get("url", [""]))[0])
            if not href or "google.com" in href:
                continue
            if "[pdf]" in text.lower():
                pdf_links.insert(0, href)
            elif any(x in href.lower() for x in [".pdf", "/pdf/", "/pdf?"]):
                pdf_links.append(href)
            elif "nber.org/papers/" in href.lower():
                pdf_links.append(href.rstrip("/") + ".pdf" if not href.endswith(".pdf") else href)
    except: pass
    try:
        for sel in ["h3.gs_rt a", ".gs_rt a", "h3 a", ".yuRUbf a"]:
            for link in driver.find_elements(By.CSS_SELECTOR, sel):
                href = link.get_attribute("href") or ""
                if "google.com/url?" in href:
                    parsed = parse_qs(urlparse(href).query)
                    href = unquote(parsed.get("q", parsed.get("url", [""]))[0])
                if href and "google.com" not in href and href not in result_links:
                    result_links.append(href)
    except: pass
    return pdf_links, result_links

def try_search_links(driver, pdf_links, result_links, dest):
    from selenium.webdriver.common.by import By
    for href in pdf_links[:5]:
        if try_chrome_dl(driver, href, dest, wait=5):
            return True, f"search_pdf:{href[:50]}"
    for href in result_links[:3]:
        try: driver.get(href)
        except: pass
        time.sleep(4)
        try:
            for pl in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                ph = pl.get_attribute("href") or ""
                pt = (pl.text or "").lower()
                if any(x in ph.lower() for x in [".pdf", "/pdf/"]) or "download" in pt:
                    if "google.com" not in ph:
                        if try_chrome_dl(driver, ph, dest, wait=5):
                            return True, f"landing:{ph[:50]}"
                        break
        except: pass
    return False, "no_pdf"

def try_google_scholar(paper, dest, driver):
    global _consent_done
    query = build_query(paper)
    url = f"https://scholar.google.com/scholar?q={quote_plus(query)}"
    try: driver.get(url)
    except: pass
    time.sleep(4)
    if not _consent_done:
        if dismiss_consent(driver):
            _consent_done = True
            time.sleep(1)
            try: driver.get(url)
            except: pass
            time.sleep(4)
    if is_captcha(driver):
        return False, "scholar_captcha"
    pdf_links, result_links = collect_pdf_links(driver)
    ok, detail = try_search_links(driver, pdf_links, result_links, dest)
    return (True, f"scholar:{detail}") if ok else (False, f"scholar_exhausted({len(pdf_links)})")

def try_google_web(paper, dest, driver):
    query = build_query(paper) + " pdf"
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    try: driver.get(url)
    except: pass
    time.sleep(4)
    if is_captcha(driver):
        return False, "google_captcha"
    pdf_links, result_links = collect_pdf_links(driver)
    ok, detail = try_search_links(driver, pdf_links, result_links, dest)
    return (True, f"google:{detail}") if ok else (False, f"google_exhausted({len(pdf_links)})")


# --- Log ---

def append_log(row):
    write_header = not LOG_PATH.exists() or LOG_PATH.stat().st_size < 10
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "doi", "status", "source", "detail"])
        if write_header:
            w.writeheader()
        w.writerow(row)


# --- Main ---

def main():
    global _driver

    with open(MASTER, encoding="utf-8") as f:
        papers = list(csv.DictReader(f))

    on_disk = {p.stem for p in PDF_DIR.glob("*.pdf")}

    FILTER = "no_doi"
    for j, a in enumerate(sys.argv[1:], 1):
        if a == "--filter" and j < len(sys.argv) - 1:
            FILTER = sys.argv[j + 1]

    todo = [p for p in papers
            if p.get("missing_reason") == FILTER
            and p["cid"] not in on_disk]

    random.shuffle(todo)

    if BATCH_SIZE:
        todo = todo[:BATCH_SIZE]

    if not todo:
        print("Nothing to download!")
        return

    print(f"Papers to attempt : {len(todo)}")
    print(f"PDFs on disk      : {len(on_disk)}")
    print(f"Strategy: requests → Chrome DOI → Google Scholar → Google web")
    print(f"Interactive mode: longer waits, you handle CAPTCHAs/logins")

    print(f"\n{'='*60}")
    print("Chrome will open. Log in to your university if needed,")
    print("then come back here and press ENTER.")
    print(f"{'='*60}")

    driver = get_driver(fresh=True)
    driver.get("https://scholar.google.com/")
    time.sleep(2)
    dismiss_consent(driver)
    input("\nPress ENTER when ready...")
    print("Starting downloads...\n")

    stats = {"req": 0, "chrome": 0, "scholar": 0, "google": 0, "failed": 0, "captcha": 0}
    start = time.time()

    for i, paper in enumerate(todo):
        cid = paper["cid"]
        doi = paper["doi"].strip()
        dest = PDF_DIR / f"{cid}.pdf"

        if dest.exists() and dest.stat().st_size > 5000:
            continue

        title_short = re.sub(r'<[^>]+>', '', paper.get("title", ""))[:45]
        print(f"[{i+1}/{len(todo)}] {cid} {paper.get('authors','')[:20]} ({paper.get('year','')}) {title_short}", end="  ", flush=True)

        detail = ""
        if doi:
            # Strategy 1: requests
            ok, detail = try_requests(doi, dest)
            if ok:
                kb = dest.stat().st_size // 1024
                print(f"-> {kb} KB [req]")
                stats["req"] += 1
                append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "requests", "detail": detail})
                time.sleep(random.uniform(2, 4))
                continue

            # Strategy 2: Chrome DOI
            try:
                ok, detail = try_chrome_doi(doi, dest)
            except Exception as e:
                ok, detail = False, f"crash:{type(e).__name__}"
                try: _driver = None; get_driver(fresh=True)
                except: pass

            if ok:
                kb = dest.stat().st_size // 1024
                print(f"-> {kb} KB [chrome]")
                stats["chrome"] += 1
                append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "chrome", "detail": detail})
                time.sleep(random.uniform(3, 6))
                continue

        # Strategy 3: Google Scholar
        time.sleep(random.uniform(12, 20))
        try:
            driver = get_driver()
            ok2, detail2 = try_google_scholar(paper, dest, driver)
        except Exception as e:
            ok2, detail2 = False, f"crash:{type(e).__name__}"

        if ok2:
            kb = dest.stat().st_size // 1024
            print(f"-> {kb} KB [scholar]")
            stats["scholar"] += 1
            append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "scholar", "detail": detail2})
            time.sleep(random.uniform(5, 10))
            continue

        if "captcha" in detail2:
            stats["captcha"] += 1
            print("-> Scholar CAPTCHA! Solve it in Chrome, waiting 90s...", flush=True)
            time.sleep(90)

        # Strategy 4: Google web search
        time.sleep(random.uniform(12, 20))
        try:
            driver = get_driver()
            ok3, detail3 = try_google_web(paper, dest, driver)
        except Exception as e:
            ok3, detail3 = False, f"crash:{type(e).__name__}"

        if ok3:
            kb = dest.stat().st_size // 1024
            print(f"-> {kb} KB [google]")
            stats["google"] += 1
            append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "google", "detail": detail3})
            time.sleep(random.uniform(5, 10))
            continue

        if "captcha" in detail3:
            stats["captcha"] += 1
            print("-> Google CAPTCHA! Solve it in Chrome, waiting 90s...", flush=True)
            time.sleep(90)
        else:
            print(f"-> FAILED")
            stats["failed"] += 1
            append_log({"cid": cid, "doi": doi, "status": "failed", "source": "all",
                         "detail": f"{detail}|{detail2}|{detail3}"})

        time.sleep(random.uniform(3, 6))

        if (i + 1) % 25 == 0:
            elapsed = time.time() - start
            total_dl = stats["req"] + stats["chrome"] + stats["scholar"] + stats["google"]
            remaining = len(todo) - i - 1
            rate = (i + 1) / elapsed * 3600
            eta_m = remaining / rate * 60 if rate > 0 else 0
            print(f"\n  --- {i+1}/{len(todo)} | DL: {total_dl} (r:{stats['req']} c:{stats['chrome']} "
                  f"s:{stats['scholar']} g:{stats['google']}) | Fail: {stats['failed']} | "
                  f"CAPTCHA: {stats['captcha']} | ~{eta_m:.0f}m left ---\n")

    if _driver:
        try: _driver.quit()
        except: pass
    clear_temp()

    elapsed = time.time() - start
    total_dl = stats["req"] + stats["chrome"] + stats["scholar"] + stats["google"]
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed/60:.1f} min")
    print(f"Downloaded: {total_dl} (req:{stats['req']} chrome:{stats['chrome']} "
          f"scholar:{stats['scholar']} google:{stats['google']})")
    print(f"Failed: {stats['failed']} | CAPTCHAs: {stats['captcha']}")
    print(f"Total PDFs on disk: {len(list(PDF_DIR.glob('*.pdf')))}")


if __name__ == "__main__":
    main()
