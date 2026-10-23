"""
Download papers without DOIs via Google search + Selenium.

Mimics the manual approach: search "author year title pdf" on Google,
find PDF links in results, download via Chrome (with VPN/uni auth).

One-time Chrome login (SWITCH/Shibboleth), then unattended.
~15-20s per paper to avoid Google CAPTCHAs.

Resumable: skips CIDs already in pdfs/ or logged as downloaded.

Usage: python google_download_no_doi.py [--batch N]
"""
import csv, os, re, shutil, sys, time
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE = Path(r"C:\Users\Marcelo\Job_market\my profile\3.research_statement\polecon_frontier_map")
CSV_PATH = BASE / "manual_download_no_doi.csv"
PDF_DIR = BASE / "pdfs"
LOG_PATH = BASE / "google_download_log.csv"
TEMP_DL = BASE / "_google_downloads"

PDF_DIR.mkdir(exist_ok=True)
TEMP_DL.mkdir(exist_ok=True)

BATCH_SIZE = None
CUSTOM_CSV = None
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--batch" and i < len(sys.argv) - 1:
        BATCH_SIZE = int(sys.argv[i + 1])
    elif arg == "--csv" and i < len(sys.argv) - 1:
        CUSTOM_CSV = Path(sys.argv[i + 1])

if CUSTOM_CSV:
    CSV_PATH = CUSTOM_CSV if CUSTOM_CSV.is_absolute() else BASE / CUSTOM_CSV


# --- Chrome setup ---

_driver = None


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

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(TEMP_DL),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    })

    print("  [Starting Chrome...]", flush=True)
    _driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts,
    )
    _driver.set_page_load_timeout(25)
    return _driver


def clear_temp():
    for f in TEMP_DL.iterdir():
        try:
            f.unlink()
        except Exception:
            pass


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
                except Exception:
                    continue
            return None
        time.sleep(0.5)
    return None


# --- Google search + download ---

def dismiss_consent(driver):
    """Dismiss Google/Scholar cookie consent dialog if present."""
    from selenium.webdriver.common.by import By
    time.sleep(2)
    for text in ["Reject all", "Alles afwijzen", "Alle ablehnen",
                 "Tout refuser", "Rechazar todo", "I agree", "Accept all",
                 "Alles accepteren", "Alle akzeptieren", "Tout accepter"]:
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
    # Fallback: click any visible button with "reject" or "afwijzen" in aria-label
    try:
        for b in driver.find_elements(By.CSS_SELECTOR, "button"):
            label = (b.get_attribute("aria-label") or b.text or "").lower()
            if any(w in label for w in ["reject", "afwijzen", "ablehnen", "refuser"]):
                if b.is_displayed():
                    b.click()
                    time.sleep(1)
                    return True
    except Exception:
        pass
    return False


def build_query(authors, year, title):
    """Build a Google Scholar search query: 'author year title'."""
    t = re.sub(r'^"|"$', '', title)
    t = t.split(",")[0] if len(t.split(",")[0]) > 20 else t
    t = re.sub(r'\s*(Cambridge|Oxford|Princeton|Yale|Harvard|MIT)\s*(University\s*)?Press.*', '', t)
    t = re.sub(r'\s*\(Ch\.?\s*\d+\).*', '', t)
    t = re.sub(r'\s*Chapter\s+\d+.*', '', t, flags=re.IGNORECASE)
    t = t.strip('.,;: "')

    auth = authors.split(",")[0].split(" et al.")[0].strip()
    auth = re.sub(r'\s+(Jr\.?|Sr\.?|III|IV)$', '', auth)

    parts = [auth, year, t[:120]]
    return " ".join(p for p in parts if p)


def is_captcha(driver):
    """Check if Google is showing a CAPTCHA."""
    try:
        url = driver.current_url
        page = driver.page_source[:2000].lower()
        return ("sorry/index" in url or "captcha" in page
                or "unusual traffic" in page or "not a robot" in page)
    except Exception:
        return False


_consent_dismissed = False
_captcha_consecutive = 0
_google_cooldown_until = 0


def try_google_download(query, dest, driver):
    """Search Google Scholar for query, find PDF links, download first one."""
    global _consent_dismissed, _captcha_consecutive, _google_cooldown_until
    from selenium.webdriver.common.by import By

    # If in cooldown from repeated CAPTCHAs, skip Scholar entirely
    if time.time() < _google_cooldown_until:
        return False, "google_cooldown"

    clear_temp()

    search_url = f"https://scholar.google.com/scholar?q={quote_plus(query)}"
    try:
        driver.get(search_url)
    except Exception:
        pass
    time.sleep(3)

    # Dismiss cookie consent on first visit
    if not _consent_dismissed:
        if dismiss_consent(driver):
            _consent_dismissed = True
            time.sleep(2)
            try:
                driver.get(search_url)
            except Exception:
                pass
            time.sleep(3)

    if is_captcha(driver):
        return False, "captcha"

    # Collect PDF links from Scholar results
    pdf_links = []
    try:
        links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
        for link in links:
            href = link.get_attribute("href") or ""
            text = (link.text or "").strip()

            # Unwrap Google redirect URLs
            if "/scholar?" in href or "scholar.google" in href:
                continue
            if "google.com/url?" in href:
                parsed = parse_qs(urlparse(href).query)
                href = unquote(parsed.get("q", parsed.get("url", [""]))[0])
            if not href or "google.com" in href:
                continue

            href_lower = href.lower()

            # Scholar marks PDF links with [PDF] text
            if "[pdf]" in text.lower():
                pdf_links.insert(0, href)  # prioritize
            elif any(x in href_lower for x in [".pdf", "/pdf/", "/pdf?"]):
                pdf_links.append(href)
            elif "nber.org/papers/" in href_lower:
                nber_url = href.rstrip("/")
                if not nber_url.endswith(".pdf"):
                    nber_url += ".pdf"
                pdf_links.append(nber_url)
    except Exception:
        pass

    # Also try: first few result links (journal landing pages) — may redirect to PDF via VPN
    result_links = []
    try:
        for link in driver.find_elements(By.CSS_SELECTOR, "h3.gs_rt a, .gs_rt a"):
            href = link.get_attribute("href") or ""
            if "google.com/url?" in href:
                parsed = parse_qs(urlparse(href).query)
                href = unquote(parsed.get("q", parsed.get("url", [""]))[0])
            if href and "google.com" not in href and href not in pdf_links:
                result_links.append(href)
    except Exception:
        pass

    # Try downloading each PDF link
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
                return True, f"scholar_pdf:{href[:60]}"
            except Exception:
                pass

        # Check if Chrome rendered a PDF inline
        try:
            ct = driver.execute_script("return document.contentType;")
            if ct and "pdf" in ct.lower():
                import base64
                pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
                data = base64.b64decode(pdf_data["data"])
                if len(data) > 5000:
                    dest.write_bytes(data)
                    clear_temp()
                    return True, f"scholar_print:{href[:60]}"
        except Exception:
            pass

    # Fallback: try first 3 result links (may be journal pages with PDF access via VPN)
    for href in result_links[:3]:
        clear_temp()
        try:
            driver.get(href)
        except Exception:
            pass
        time.sleep(3)

        # Look for PDF link on the landing page
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
    return False, f"no_pdf_found({len(pdf_links)}_links_tried)"


# --- Log ---

def load_log():
    done = {}
    if LOG_PATH.exists():
        with open(LOG_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done[r["cid"]] = r["status"]
    return done


def append_log(row):
    write_header = not LOG_PATH.exists() or LOG_PATH.stat().st_size < 10
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "title", "status", "source"])
        if write_header:
            w.writeheader()
        w.writerow(row)


# --- Main ---

def main():
    global _driver

    with open(CSV_PATH, encoding="utf-8") as f:
        papers = list(csv.DictReader(f))

    existing_pdfs = {p.stem for p in PDF_DIR.glob("*.pdf")}
    log = load_log()

    todo = [p for p in papers
            if p["cid"] not in existing_pdfs
            and log.get(p["cid"]) != "downloaded"]

    if BATCH_SIZE:
        todo = todo[:BATCH_SIZE]

    if not todo:
        print("Nothing to download!")
        return

    print(f"Papers to attempt : {len(todo)}")
    print(f"Already on disk   : {len(existing_pdfs)}")
    print(f"Strategy: Google search 'author year title pdf' → download PDF links")
    print(f"Delay: ~15s between searches to avoid CAPTCHAs")

    # --- Start Chrome (no login needed for Scholar) ---
    driver = get_driver(fresh=True)
    driver.get("https://scholar.google.com/")
    time.sleep(2)
    dismiss_consent(driver)
    print("Starting automated downloads...")

    stats = {"downloaded": 0, "failed": 0, "captcha": 0}
    start = time.time()

    for i, p in enumerate(todo):
        cid = p["cid"]
        title = p["title"]
        year = p.get("year", "").strip()
        authors = p.get("authors", "")
        dest = PDF_DIR / f"{cid}.pdf"

        if dest.exists() and dest.stat().st_size > 5000:
            continue

        query = build_query(authors, year, title)
        short = f"{authors} ({year}) {title[:45]}"
        print(f"[{i+1}/{len(todo)}] {cid} {short}", end="  ", flush=True)

        try:
            ok, detail = try_google_download(query, dest, driver)
        except Exception as e:
            ok, detail = False, f"error:{type(e).__name__}"
            # Try to recover Chrome
            try:
                driver = get_driver(fresh=True)
            except Exception:
                pass

        if ok:
            kb = dest.stat().st_size // 1024
            print(f"-> {kb} KB")
            stats["downloaded"] += 1
            _captcha_consecutive = 0
            append_log({"cid": cid, "title": title[:80], "status": "downloaded", "source": detail})
        elif "captcha" in detail:
            _captcha_consecutive += 1
            stats["captcha"] += 1
            if _captcha_consecutive == 1:
                print("-> CAPTCHA! Pausing 3min then retrying...")
                time.sleep(180)
            else:
                cooldown_min = 10
                _google_cooldown_until = time.time() + cooldown_min * 60
                print(f"-> CAPTCHA #{_captcha_consecutive}! Cooldown {cooldown_min}min, skipping Scholar...")
                append_log({"cid": cid, "title": title[:80], "status": "captcha_skip", "source": detail})
        elif "cooldown" in detail:
            print(f"-> cooldown, skipping")
        else:
            print(f"-> SKIP ({detail[:40]})")
            stats["failed"] += 1
            append_log({"cid": cid, "title": title[:80], "status": "failed", "source": detail})

        if (i + 1) % 25 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed * 3600
            remaining = len(todo) - i - 1
            eta_m = remaining / rate * 60 if rate > 0 else 0
            print(f"\n  --- {i+1}/{len(todo)} | DL: {stats['downloaded']} | "
                  f"Fail: {stats['failed']} | CAPTCHAs: {stats['captcha']} | "
                  f"~{eta_m:.0f}m left ---\n")

        # Delay between searches (15-20s to look human)
        delay = 12 + (hash(cid) % 8)  # 12-20s, varies per paper
        time.sleep(delay)

    # Cleanup
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
    clear_temp()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed/60:.1f} min")
    print(f"Downloaded : {stats['downloaded']}")
    print(f"Failed     : {stats['failed']}")
    print(f"CAPTCHAs   : {stats['captcha']}")
    print(f"Total PDFs : {len(list(PDF_DIR.glob('*.pdf')))}")


if __name__ == "__main__":
    main()
