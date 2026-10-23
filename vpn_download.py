"""
Overnight PDF downloader — multi-strategy, one login then unattended.
VPN must be ON. You log in once via SWITCH/Shibboleth, then sleep.

Strategies per paper (tries in order, stops on first success):
  1. requests with browser UA → direct publisher PDF URL (fast)
  2. requests → Semantic Scholar / Unpaywall OA URL
  3. Chrome navigation → direct publisher PDF URL
  4. Chrome → scrape PDF links from article page
  5. Google Scholar search → download PDF links found
  6. Google web search → download PDF links found

Resilient: auto-restarts Chrome on crash (restores cookies),
           skips individual failures, resumes from log on restart,
           updates coverage every 25 papers.

Usage: python vpn_download.py [--batch N] [--retry-all]
"""
import base64
import csv
import json
import os
import pickle
import random
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE = Path(r"C:\Users\Marcelo\Job_market\my profile\3.research_statement\polecon_frontier_map")
PDF_DIR = BASE / "pdfs"
CSV_PATH = BASE / "paper_coverage.csv"
LOG_PATH = BASE / "vpn_download_log.csv"
TEMP_DL = BASE / "_downloads"
COOKIE_PATH = BASE / "_cookies.pkl"

PDF_DIR.mkdir(exist_ok=True)
TEMP_DL.mkdir(exist_ok=True)

EMAIL = "marcelo.piemonte.ribeiro@gmail.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "application/pdf,*/*"}

BATCH_SIZE = None
RETRY_ALL = False
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--batch" and i < len(sys.argv) - 1:
        BATCH_SIZE = int(sys.argv[i + 1])
    if arg == "--retry-all":
        RETRY_ALL = True

# --- Per-domain rate limiting ---
_last_domain_access = defaultdict(float)
DOMAIN_DELAY = 4.0  # min seconds between requests to same publisher

def rate_limit_domain(url):
    domain = urlparse(url).netloc.replace("www.", "")
    now = time.time()
    elapsed = now - _last_domain_access[domain]
    if elapsed < DOMAIN_DELAY:
        wait = DOMAIN_DELAY - elapsed + random.uniform(0.5, 2.0)
        time.sleep(wait)
    _last_domain_access[domain] = time.time()

# --- Publisher PDF URL patterns ---

def pdf_url_from_doi(doi, final_url=""):
    urls = []
    fu = final_url.lower()

    # AEA journals
    if "aeaweb.org" in fu or "10.1257" in doi:
        urls.append(f"https://pubs.aeaweb.org/doi/pdf/{doi}")

    # OUP — articles AND edited volumes / handbooks
    if "academic.oup.com" in fu:
        if "/article/" in fu:
            urls.append(final_url.replace("/article/", "/article-pdf/").split("?")[0] + "?redirect=false")
        elif "/edited-volume/" in fu or "/book/" in fu:
            urls.append(final_url.rstrip("/") + "/pdf")
    if "10.1093" in doi and not any("oup.com" in u for u in urls):
        urls.append(f"https://academic.oup.com/restud/article-pdf/doi/{doi}")

    # UChicago (JPE, JLE etc) — but some 10.1086 DOIs land on JSTOR
    if "journals.uchicago.edu" in fu or ("10.1086" in doi and "jstor.org" not in fu):
        urls.append(f"https://www.journals.uchicago.edu/doi/pdf/{doi}")

    # Econometrica / Wiley
    if "10.3982" in doi:
        urls.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
    if "wiley.com" in fu or ("10.1111" in doi and "10.3982" not in doi):
        urls.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")

    # MIT Press
    if "direct.mit.edu" in fu or "10.1162" in doi:
        urls.append(f"https://direct.mit.edu/rest/article-pdf/doi/{doi}")

    # JSTOR — from final URL or DOI prefix
    if "jstor.org" in fu and "/stable/" in fu:
        stable_id = final_url.split("/stable/")[-1].split("?")[0].split("#")[0]
        if stable_id:
            urls.append(f"https://www.jstor.org/stable/pdf/{stable_id}.pdf")
    if "10.2307" in doi:
        jstor_id = doi.replace("10.2307/", "")
        urls.append(f"https://www.jstor.org/stable/pdf/{jstor_id}.pdf")
    # 10.1086 DOIs that landed on JSTOR
    if "10.1086" in doi and "jstor.org" in fu and "/stable/" in fu:
        stable_id = final_url.split("/stable/")[-1].split("?")[0].split("#")[0]
        if stable_id:
            urls.append(f"https://www.jstor.org/stable/pdf/{stable_id}.pdf")

    # Cambridge
    if "cambridge.org" in fu:
        if "/article/" in fu and "/pdf/" not in fu:
            urls.append(final_url.replace("/article/", "/article/pdf/"))
        elif "/core/books/" in fu:
            urls.append(final_url.rstrip("/") + "/pdf")

    # ScienceDirect (Elsevier) — multiple PDF endpoints
    if "sciencedirect.com" in fu and "/article/pii/" in fu:
        pii = final_url.split("/article/pii/")[-1].split("?")[0].split("/")[0]
        urls.append(f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true")
        urls.append(f"https://www.sciencedirect.com/science/article/pii/{pii}/pdf?md5=&pid=1-s2.0-{pii}-main.pdf")
    if "10.1016" in doi and not any("sciencedirect" in u for u in urls):
        urls.append(f"https://doi.org/{doi}")

    # Springer
    if "link.springer.com" in fu or "10.1007" in doi:
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
        if "/chapter/" in fu:
            urls.append(final_url.replace("/chapter/", "/content/pdf/") + ".pdf")

    # Annual Reviews
    if "annualreviews.org" in fu or "10.1146" in doi:
        urls.append(f"https://www.annualreviews.org/content/journals/{doi}")

    # SAGE
    if "sagepub.com" in fu or "10.1177" in doi:
        urls.append(f"https://journals.sagepub.com/doi/pdf/{doi}")

    # Taylor & Francis
    if "tandfonline.com" in fu or "10.1080" in doi:
        urls.append(f"https://www.tandfonline.com/doi/pdf/{doi}?needAccess=true")

    # Science
    if "science.org" in fu or "10.1126" in doi:
        urls.append(f"https://www.science.org/doi/pdf/{doi}")

    # NOW Publishers
    if "10.1561" in doi:
        urls.append(f"https://www.nowpublishers.com/article/Download/{doi}")

    # De Gruyter
    if "degruyter" in fu or "10.1515" in doi:
        urls.append(f"https://www.degruyterbrill.com/document/doi/{doi}/pdf")

    # Emerald
    if "emerald.com" in fu or "10.1108" in doi:
        urls.append(f"https://www.emerald.com/insight/content/doi/{doi}/full/pdf")

    # Nature
    if "nature.com" in fu or "10.1038" in doi:
        urls.append(f"https://www.nature.com/articles/{doi.split('/')[-1]}.pdf")

    # INFORMS (Management Science, etc)
    if "informs.org" in fu or "10.1287" in doi:
        urls.append(f"https://pubsonline.informs.org/doi/pdf/{doi}")

    # SSRN — try direct PDF link
    if "ssrn.com" in fu or "10.2139" in doi:
        ssrn_id = doi.replace("10.2139/ssrn.", "")
        urls.append(f"https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID{ssrn_id}_code.pdf?abstractid={ssrn_id}&type=2")

    # World Bank
    if "worldbank.org" in fu:
        urls.append(final_url.replace("/handle/", "/bitstreams/").rstrip("/") + "/download")

    return urls


# --- Strategy 1: requests-based download ---

def download_with_requests(url, dest, timeout=20):
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
    except HTTPError as e:
        return False, f"http_{e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}"


def try_requests_strategies(doi, dest):
    for url in pdf_url_from_doi(doi):
        rate_limit_domain(url)
        ok, reason = download_with_requests(url, dest)
        if ok:
            return True, f"requests_direct:{url[:60]}"

    # Semantic Scholar
    try:
        ss_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=isOpenAccess,openAccessPdf"
        req = Request(ss_url, headers={"User-Agent": f"PolEcon downloader; mailto:{EMAIL}"})
        with urlopen(req, timeout=10) as r:
            ss = json.loads(r.read())
        if ss.get("isOpenAccess"):
            pdf_url = (ss.get("openAccessPdf") or {}).get("url")
            if pdf_url and "ssrn.com" not in pdf_url:
                ok, reason = download_with_requests(pdf_url, dest)
                if ok:
                    return True, f"requests_ss:{pdf_url[:60]}"
    except Exception:
        pass
    time.sleep(0.2)

    # Unpaywall
    try:
        up_url = f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}"
        req = Request(up_url, headers={"User-Agent": f"PolEcon downloader; mailto:{EMAIL}"})
        with urlopen(req, timeout=10) as r:
            up = json.loads(r.read())
        if up.get("is_oa"):
            locs = [l for l in (up.get("oa_locations") or []) if l.get("url_for_pdf")]
            for loc in locs[:2]:
                pdf_url = loc["url_for_pdf"]
                if "ssrn.com" not in pdf_url:
                    ok, reason = download_with_requests(pdf_url, dest)
                    if ok:
                        return True, f"requests_oa:{pdf_url[:60]}"
    except Exception:
        pass

    return False, "requests_exhausted"


# --- Strategy 2: Selenium/Chrome-based download ---

_driver = None
_saved_cookies = []


def save_cookies(driver):
    global _saved_cookies
    try:
        _saved_cookies = driver.get_cookies()
        with open(COOKIE_PATH, "wb") as f:
            pickle.dump(_saved_cookies, f)
    except Exception:
        pass


def restore_cookies(driver):
    cookies = _saved_cookies
    if not cookies and COOKIE_PATH.exists():
        try:
            with open(COOKIE_PATH, "rb") as f:
                cookies = pickle.load(f)
        except Exception:
            cookies = []

    # Navigate to each unique domain first, then set cookies
    domains = {c.get("domain", "").lstrip(".") for c in cookies if c.get("domain")}
    for domain in domains:
        try:
            driver.get(f"https://{domain}/")
            time.sleep(0.5)
        except Exception:
            continue
        for c in cookies:
            if c.get("domain", "").lstrip(".") == domain:
                try:
                    driver.add_cookie(c)
                except Exception:
                    continue


def get_driver(fresh=False):
    global _driver
    if not fresh and _driver is not None:
        try:
            _ = _driver.current_url
            return _driver
        except Exception:
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None

    # Try undetected-chromedriver first (bypasses bot detection),
    # fall back to regular selenium with stealth patches
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_experimental_option("prefs", {
            "download.default_directory": str(TEMP_DL),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        })
        print("  [Starting Chrome (stealth)...]", flush=True)
        _driver = uc.Chrome(options=opts)
    except ImportError:
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
        print("  [Starting Chrome (patched)...]", flush=True)
        _driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=opts,
        )
        # Remove navigator.webdriver flag
        _driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

    _driver.set_page_load_timeout(35)

    # Restore cookies from previous session
    if not fresh and _saved_cookies:
        print("  [Restoring cookies...]", flush=True)
        restore_cookies(_driver)

    return _driver


def clear_temp():
    for f in TEMP_DL.iterdir():
        try:
            f.unlink()
        except Exception:
            pass


def wait_for_download(timeout=12):
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
                except Exception:
                    continue
            return None
        time.sleep(0.5)
    return None


def try_chrome_download(driver, url, dest, wait_extra=0):
    clear_temp()
    rate_limit_domain(url)
    try:
        driver.get(url)
    except Exception:
        pass
    time.sleep(2 + wait_extra)

    dl = wait_for_download(timeout=12 + wait_extra)
    if dl:
        try:
            if dl.stat().st_size > 5000:
                shutil.move(str(dl), str(dest))
                clear_temp()
                return True
        except Exception:
            pass

    try:
        ct = driver.execute_script("return document.contentType;")
        if ct and "pdf" in ct.lower():
            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
            data = base64.b64decode(pdf_data["data"])
            if len(data) > 5000:
                dest.write_bytes(data)
                return True
    except Exception:
        pass

    clear_temp()
    return False


def try_chrome_strategies(doi, dest):
    try:
        driver = get_driver()
    except Exception as e:
        return False, f"chrome_start_fail:{type(e).__name__}"

    final_url = ""
    rate_limit_domain(f"https://doi.org/{doi}")
    try:
        driver.get(f"https://doi.org/{doi}")
        time.sleep(4)
        final_url = driver.current_url
    except Exception as e:
        try:
            final_url = driver.current_url
        except Exception:
            return False, f"doi_resolve:{type(e).__name__}"

    # Skip if landed on a login/auth page
    if "adfs." in final_url or "shibboleth" in final_url.lower() or "login" in final_url.lower():
        for url in pdf_url_from_doi(doi):
            if try_chrome_download(driver, url, dest):
                return True, f"chrome_direct_bypass:{url[:60]}"
        return False, f"auth_redirect:{final_url[:60]}"

    # Try constructed PDF URLs first
    fu = final_url.lower()
    extra_wait = 3 if any(d in fu for d in ["sciencedirect", "jstor", "emerald"]) else 0
    for url in pdf_url_from_doi(doi, final_url):
        if try_chrome_download(driver, url, dest, wait_extra=extra_wait):
            return True, f"chrome_direct:{url[:60]}"

    # Scrape PDF links from article page — broad selectors
    try:
        from selenium.webdriver.common.by import By
        if final_url:
            rate_limit_domain(final_url)
            try:
                driver.get(final_url)
                time.sleep(3)
            except Exception:
                pass

            # CSS selectors for PDF links
            selectors = [
                "a[href*='/pdf']", "a[href*='.pdf']",
                "a[href*='pdfft']", "a[href*='pdfdirect']", "a[href*='pdf/']",
                "a[href*='Delivery.cfm']",  # SSRN
                "a[href*='/fulltext/pdf']",  # Emerald
                "a[href*='download']",
            ]
            seen = set()
            for sel in selectors:
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, sel)
                    for link in links:
                        href = link.get_attribute("href")
                        if href and href not in seen and ("pdf" in href.lower() or "download" in href.lower()):
                            seen.add(href)
                            if try_chrome_download(driver, href, dest, wait_extra=extra_wait):
                                return True, f"chrome_scrape:{href[:60]}"
                except Exception:
                    continue

            # Text-based: find buttons/links containing "Download PDF" or "PDF"
            try:
                for xpath in [
                    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download pdf')]",
                    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view pdf')]",
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download pdf')]",
                ]:
                    els = driver.find_elements(By.XPATH, xpath)
                    for el in els[:2]:
                        href = el.get_attribute("href")
                        if href and href not in seen:
                            seen.add(href)
                            if try_chrome_download(driver, href, dest, wait_extra=extra_wait):
                                return True, f"chrome_btn:{href[:60]}"
                        else:
                            # Click the button/link directly
                            clear_temp()
                            try:
                                el.click()
                                time.sleep(2 + extra_wait)
                                dl = wait_for_download(timeout=12)
                                if dl and dl.stat().st_size > 5000:
                                    shutil.move(str(dl), str(dest))
                                    clear_temp()
                                    return True, f"chrome_click:{final_url[:60]}"
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        pass

    return False, f"chrome_exhausted:{final_url[:60]}" if final_url else "chrome_exhausted:no_url"


# --- Strategy 3: Google Scholar / Google web search ---

_consent_dismissed = False
_google_cooldown_until = 0.0  # timestamp: skip Google searches until this time
_consecutive_captchas = 0
CAPTCHA_PAUSE = 180        # 3 min pause on first CAPTCHA
CAPTCHA_COOLDOWN = 600     # 10 min cooldown after 2+ CAPTCHAs in a row


def google_available():
    return time.time() >= _google_cooldown_until


def google_captcha_backoff():
    global _google_cooldown_until, _consecutive_captchas
    _consecutive_captchas += 1
    if _consecutive_captchas >= 2:
        _google_cooldown_until = time.time() + CAPTCHA_COOLDOWN
        print(f"  [Google cooldown {CAPTCHA_COOLDOWN}s after {_consecutive_captchas} CAPTCHAs]", flush=True)
    else:
        time.sleep(CAPTCHA_PAUSE)
        print(f"  [Paused {CAPTCHA_PAUSE}s for CAPTCHA]", flush=True)


def google_captcha_reset():
    global _consecutive_captchas
    _consecutive_captchas = 0


def dismiss_consent(driver):
    from selenium.webdriver.common.by import By
    time.sleep(2)
    for text in ["Reject all", "Alles afwijzen", "Alle ablehnen",
                 "Tout refuser", "Rechazar todo", "I agree", "Accept all"]:
        try:
            buttons = driver.find_elements(By.XPATH,
                f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                f"'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
            for b in buttons:
                if b.is_displayed():
                    b.click()
                    time.sleep(1)
                    return True
        except Exception:
            continue
    return False


def is_captcha(driver):
    try:
        url = driver.current_url
        page = driver.page_source[:2000].lower()
        return ("sorry/index" in url or "captcha" in page
                or "unusual traffic" in page or "not a robot" in page)
    except Exception:
        return False


def build_query(authors, year, title):
    t = re.sub(r'^"|"$', '', title)
    t = t.split(",")[0] if len(t.split(",")[0]) > 20 else t
    t = re.sub(r'\s*(Cambridge|Oxford|Princeton|Yale|Harvard|MIT)\s*(University\s*)?Press.*', '', t)
    t = re.sub(r'\s*Chapter\s+\d+.*', '', t, flags=re.IGNORECASE)
    t = t.strip('.,;: "')
    auth = authors.split(",")[0].split(" et al.")[0].strip()
    auth = re.sub(r'\s+(Jr\.?|Sr\.?|III|IV)$', '', auth)
    return " ".join(p for p in [auth, year, t[:120]] if p)


def _collect_pdf_links(driver):
    from selenium.webdriver.common.by import By
    pdf_links = []
    try:
        links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
        for link in links:
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
                nber_url = href.rstrip("/")
                if not nber_url.endswith(".pdf"):
                    nber_url += ".pdf"
                pdf_links.append(nber_url)
    except Exception:
        pass
    return pdf_links


def _collect_result_links(driver):
    from selenium.webdriver.common.by import By
    result_links = []
    try:
        for sel in ["h3.gs_rt a", ".gs_rt a", "h3 a", ".yuRUbf a"]:
            for link in driver.find_elements(By.CSS_SELECTOR, sel):
                href = link.get_attribute("href") or ""
                if "google.com/url?" in href:
                    parsed = parse_qs(urlparse(href).query)
                    href = unquote(parsed.get("q", parsed.get("url", [""]))[0])
                if href and "google.com" not in href and href not in result_links:
                    result_links.append(href)
    except Exception:
        pass
    return result_links


def _try_download_links(driver, pdf_links, result_links, dest):
    from selenium.webdriver.common.by import By

    for href in pdf_links[:5]:
        clear_temp()
        try:
            driver.get(href)
        except Exception:
            pass
        time.sleep(3)
        dl = wait_for_download(timeout=10)
        if dl and dl.stat().st_size > 5000:
            try:
                shutil.move(str(dl), str(dest))
                clear_temp()
                return True, f"search_pdf:{href[:60]}"
            except Exception:
                pass
        try:
            ct = driver.execute_script("return document.contentType;")
            if ct and "pdf" in ct.lower():
                pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
                data = base64.b64decode(pdf_data["data"])
                if len(data) > 5000:
                    dest.write_bytes(data)
                    clear_temp()
                    return True, f"search_print:{href[:60]}"
        except Exception:
            pass

    for href in result_links[:3]:
        clear_temp()
        try:
            driver.get(href)
        except Exception:
            pass
        time.sleep(3)
        try:
            page_links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
            for pl in page_links:
                ph = pl.get_attribute("href") or ""
                pt = (pl.text or "").lower()
                if any(x in ph.lower() for x in [".pdf", "/pdf/", "/pdf?"]) or "download" in pt:
                    if "google.com" not in ph:
                        clear_temp()
                        try:
                            driver.get(ph)
                        except Exception:
                            pass
                        time.sleep(3)
                        dl = wait_for_download(timeout=10)
                        if dl and dl.stat().st_size > 5000:
                            shutil.move(str(dl), str(dest))
                            clear_temp()
                            return True, f"landing_pdf:{ph[:60]}"
                        break
        except Exception:
            pass

    clear_temp()
    return False, f"no_pdf({len(pdf_links)}_links)"


def try_google_scholar(paper, dest, driver):
    global _consent_dismissed
    query = build_query(paper.get("authors", ""), paper.get("year", ""), paper.get("title", ""))
    search_url = f"https://scholar.google.com/scholar?q={quote_plus(query)}"
    try:
        driver.get(search_url)
    except Exception:
        pass
    time.sleep(3)

    if not _consent_dismissed:
        if dismiss_consent(driver):
            _consent_dismissed = True
            time.sleep(1)
            try:
                driver.get(search_url)
            except Exception:
                pass
            time.sleep(3)

    if is_captcha(driver):
        return False, "scholar_captcha"

    pdf_links = _collect_pdf_links(driver)
    result_links = _collect_result_links(driver)
    ok, detail = _try_download_links(driver, pdf_links, result_links, dest)
    if ok:
        return True, f"scholar:{detail}"
    return False, f"scholar_exhausted({len(pdf_links)})"


def try_google_web(paper, dest, driver):
    query = build_query(paper.get("authors", ""), paper.get("year", ""), paper.get("title", ""))
    query += " pdf"
    search_url = f"https://www.google.com/search?q={quote_plus(query)}"
    try:
        driver.get(search_url)
    except Exception:
        pass
    time.sleep(3)

    if is_captcha(driver):
        return False, "google_captcha"

    pdf_links = _collect_pdf_links(driver)
    result_links = _collect_result_links(driver)
    ok, detail = _try_download_links(driver, pdf_links, result_links, dest)
    if ok:
        return True, f"google:{detail}"
    return False, f"google_exhausted({len(pdf_links)})"


# --- Data helpers ---

def load_papers():
    with open(CSV_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_done():
    return {p.stem for p in PDF_DIR.glob("*.pdf")}


def load_tried():
    tried = set()
    retry = set()
    if LOG_PATH.exists():
        with open(LOG_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["status"] == "downloaded":
                    tried.add(r["cid"])
                elif r["status"] == "failed":
                    detail = r.get("detail", "")
                    if "WebDriverException" in detail or "chrome_start_fail" in detail:
                        retry.add(r["cid"])
                    else:
                        tried.add(r["cid"])
    return tried, retry


def append_log(row):
    write_header = not LOG_PATH.exists() or LOG_PATH.stat().st_size < 10
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "doi", "status", "source", "detail"])
        if write_header:
            w.writeheader()
        w.writerow(row)


def update_coverage():
    papers = load_papers()
    pdf_cids = {p.stem for p in PDF_DIR.glob("*.pdf")}
    updated = 0
    for p in papers:
        if p["cid"] in pdf_cids and p["needs_download"] == "True":
            p["needs_download"] = "False"
            updated += 1
    fieldnames = list(papers[0].keys())
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(papers)
    return updated


# --- Main ---

def main():
    global _driver

    papers = load_papers()
    done = load_done()
    tried, retry = load_tried()

    if RETRY_ALL:
        # Retry everything that failed before (improved patterns)
        skip = done
        print("Mode: --retry-all (retrying all prior failures)")
    else:
        skip = done | tried

    todo = [p for p in papers if p["needs_download"] == "True"
            and p["doi"].strip() and (p["cid"] not in skip or p["cid"] in retry)]

    # Shuffle to spread publisher load and avoid rate-limiting
    random.shuffle(todo)

    if BATCH_SIZE:
        todo = todo[:BATCH_SIZE]

    if not todo:
        print("Nothing to download!")
        return

    total_pdfs = len(list(PDF_DIR.glob("*.pdf")))
    print(f"Papers to attempt : {len(todo)}")
    print(f"Already on disk   : {total_pdfs}")
    print(f"Retrying crashes  : {len([t for t in todo if t['cid'] in retry])}")
    print(f"Strategy: requests first, then Chrome fallback")

    # --- One-time SWITCH login ---
    print(f"\n{'=' * 60}")
    print("Step 1: Authenticate via SWITCH (one time)")
    print("  Chrome will open. Log in to your university,")
    print("  then come back here and press ENTER.")
    print("  After that, the script runs unattended.")
    print(f"{'=' * 60}")

    driver = get_driver(fresh=True)
    driver.get("https://www.jstor.org/")
    input("\nPress ENTER after you've logged in via SWITCH...")

    # Save cookies for potential Chrome restarts
    save_cookies(driver)
    print("Cookies saved. Starting downloads...\n")

    stats = {"dl_requests": 0, "dl_chrome": 0, "dl_scholar": 0, "dl_google": 0,
             "failed": 0, "skipped": 0, "captcha_pauses": 0}
    start_time = time.time()

    for i, paper in enumerate(todo):
        cid = paper["cid"]
        doi = paper["doi"].strip()
        dest = PDF_DIR / f"{cid}.pdf"

        if dest.exists() and dest.stat().st_size > 5000:
            stats["skipped"] += 1
            continue

        print(f"[{i+1}/{len(todo)}] {cid} {doi[:50]}", end="  ", flush=True)

        # --- Strategy 1: requests (fast, no browser) ---
        ok, detail = try_requests_strategies(doi, dest)
        if ok:
            kb = dest.stat().st_size // 1024
            print(f"-> {kb} KB [{detail.split(':')[0]}]")
            stats["dl_requests"] += 1
            append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "requests", "detail": detail})
        else:
            # --- Strategy 2: Chrome DOI navigation ---
            try:
                ok, detail = try_chrome_strategies(doi, dest)
            except Exception as e:
                ok, detail = False, f"crash:{type(e).__name__}"

            if ok:
                kb = dest.stat().st_size // 1024
                print(f"-> {kb} KB [{detail.split(':')[0]}]")
                stats["dl_chrome"] += 1
                append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "chrome", "detail": detail})
                if stats["dl_chrome"] % 10 == 0:
                    try:
                        save_cookies(get_driver())
                    except Exception:
                        pass
            else:
                ok2, detail2 = False, "skipped"
                ok3, detail3 = False, "skipped"

                # --- Strategy 3: Google Scholar search ---
                if google_available():
                    time.sleep(random.uniform(10, 18))
                    try:
                        driver = get_driver()
                        ok2, detail2 = try_google_scholar(paper, dest, driver)
                    except Exception as e:
                        ok2, detail2 = False, f"scholar_crash:{type(e).__name__}"

                    if ok2:
                        google_captcha_reset()
                        kb = dest.stat().st_size // 1024
                        print(f"-> {kb} KB [{detail2.split(':')[0]}]")
                        stats["dl_scholar"] += 1
                        append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "scholar", "detail": detail2})
                    elif "captcha" in detail2:
                        stats["captcha_pauses"] += 1
                        google_captcha_backoff()

                # --- Strategy 4: Google web search ---
                if not ok2 and "captcha" not in detail2 and google_available():
                    time.sleep(random.uniform(10, 18))
                    try:
                        driver = get_driver()
                        ok3, detail3 = try_google_web(paper, dest, driver)
                    except Exception as e:
                        ok3, detail3 = False, f"google_crash:{type(e).__name__}"

                    if ok3:
                        google_captcha_reset()
                        kb = dest.stat().st_size // 1024
                        print(f"-> {kb} KB [{detail3.split(':')[0]}]")
                        stats["dl_google"] += 1
                        append_log({"cid": cid, "doi": doi, "status": "downloaded", "source": "google", "detail": detail3})
                    elif "captcha" in detail3:
                        stats["captcha_pauses"] += 1
                        google_captcha_backoff()

                if not ok2 and not ok3:
                    reason = detail[:30]
                    if detail2 != "skipped":
                        reason += f"|{detail2[:15]}"
                    if detail3 != "skipped":
                        reason += f"|{detail3[:15]}"
                    print(f"-> FAILED ({reason})")
                    stats["failed"] += 1
                    append_log({"cid": cid, "doi": doi, "status": "failed", "source": "all", "detail": f"{detail}|{detail2}|{detail3}"})

        # Progress report + coverage update every 25 papers
        if (i + 1) % 25 == 0:
            updated = update_coverage()
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed * 3600
            total_dl = stats["dl_requests"] + stats["dl_chrome"] + stats["dl_scholar"] + stats["dl_google"]
            remaining = len(todo) - i - 1
            eta_h = remaining / rate if rate > 0 else 0
            print(f"\n  --- {i+1}/{len(todo)} | DL: {total_dl} (req:{stats['dl_requests']} "
                  f"chr:{stats['dl_chrome']} sch:{stats['dl_scholar']} ggl:{stats['dl_google']}) | "
                  f"Fail: {stats['failed']} | CAPTCHA: {stats['captcha_pauses']} | ~{eta_h:.1f}h left ---\n")

        time.sleep(random.uniform(1.5, 3.0))

    # Cleanup
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
    clear_temp()
    if COOKIE_PATH.exists():
        COOKIE_PATH.unlink()

    updated = update_coverage()
    elapsed = time.time() - start_time
    total_dl = stats["dl_requests"] + stats["dl_chrome"] + stats["dl_scholar"] + stats["dl_google"]

    print(f"\n{'=' * 60}")
    print(f"DONE in {elapsed/3600:.1f} hours")
    print(f"Downloaded (requests) : {stats['dl_requests']}")
    print(f"Downloaded (Chrome)   : {stats['dl_chrome']}")
    print(f"Downloaded (Scholar)  : {stats['dl_scholar']}")
    print(f"Downloaded (Google)   : {stats['dl_google']}")
    print(f"Failed                : {stats['failed']}")
    print(f"CAPTCHA pauses        : {stats['captcha_pauses']}")
    print(f"Skipped (had already) : {stats['skipped']}")
    print(f"Coverage updated      : {updated} papers")
    print(f"Total PDFs on disk    : {len(list(PDF_DIR.glob('*.pdf')))}")
    remaining = sum(1 for p in load_papers() if p["needs_download"] == "True")
    print(f"Still needs_download  : {remaining}")


if __name__ == "__main__":
    main()
