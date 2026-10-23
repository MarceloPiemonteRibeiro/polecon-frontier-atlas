"""Fill missing abstracts for core papers from Semantic Scholar (public API, throttled to stay under the shared rate limit).

Papers with a DOI are looked up by DOI; the rest (mostly working papers) by title match, accepted only when the
returned title is near-identical and the year is within 3. Open-access PDF links found on the way go to s2_pdfs.json
for 08_intros.py.

Output: data/s2_abstracts.json {cid: abstract}; 06_build.py uses it when OpenAlex has no abstract.
"""
import difflib, json, re, time, urllib.request, urllib.parse, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
OUT, PDFS = DATA / "s2_abstracts.json", DATA / "s2_pdfs.json"
API = "https://api.semanticscholar.org/graph/v1/paper/"
FIELDS = "title,year,abstract,tldr,openAccessPdf"


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def get(url):
    """JSON from S2, or None on 404; retries with backoff on 429/5xx."""
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "polecon-frontier-map/1.0"}), timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(10 * (attempt + 1))
        except Exception:
            time.sleep(10 * (attempt + 1))
    return None


def lookup(p):
    if p.get("doi"):
        return get(API + "DOI:" + urllib.parse.quote(p["doi"], safe="/") + "?fields=" + FIELDS)
    d = get(API + "search/match?query=" + urllib.parse.quote(p["t"][:250]) + "&fields=" + FIELDS)
    d = (d or {}).get("data", [None])[0] if d else None
    if not d or difflib.SequenceMatcher(None, norm(d.get("title")), norm(p["t"])).ratio() < 0.9:
        return None
    if p.get("y") and d.get("year") and abs(d["year"] - p["y"]) > 3:
        return None
    return d


def main():
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    have = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}
    pdfs = json.load(open(PDFS, encoding="utf-8")) if PDFS.exists() else {}
    targets = [p for p in D["papers"] if p["f"] < 8 and not p.get("ab") and not p.get("fd")
               and (p["nc"] >= 2 or p.get("vox") or "BREAD26" in p["cs"] or (p["fr"] and p["nc"] >= 1))]
    print("targets", len(targets), flush=True)
    for k, p in enumerate(targets):
        cid = cid_of[str(p["id"])]
        if cid in have:
            continue
        d = lookup(p) or {}
        have[cid] = d.get("abstract") or ((d.get("tldr") or {}).get("text") and "TLDR: " + d["tldr"]["text"]) or ""
        if (d.get("openAccessPdf") or {}).get("url"):
            pdfs[cid] = d["openAccessPdf"]["url"]
        time.sleep(3.2)
        if k % 20 == 0:
            json.dump(have, open(OUT, "w", encoding="utf-8"))
            json.dump(pdfs, open(PDFS, "w", encoding="utf-8"))
            print(k, sum(1 for v in have.values() if v), "found", flush=True)
    json.dump(have, open(OUT, "w", encoding="utf-8"))
    json.dump(pdfs, open(PDFS, "w", encoding="utf-8"))
    print("done", sum(1 for v in have.values() if v), "abstracts,", len(pdfs), "pdf links")


if __name__ == "__main__":
    main()
