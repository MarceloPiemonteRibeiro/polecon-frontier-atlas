"""Resolve clusters to DOIs (Crossref, free) and enrich with OpenAlex single-record lookups (free).

Caches every HTTP response in data/cache/ so reruns are cheap.
Output: data/resolved.json
"""
import json, re, time, hashlib, difflib, unicodedata, urllib.request, urllib.parse, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
CACHE = DATA / "cache"
CACHE.mkdir(exist_ok=True)
UA = "polecon-frontier-map/1.0 (academic literature mapping script)"
TYPE_RANK = {"journal-article": 0, "book": 1, "monograph": 1, "edited-book": 1, "book-chapter": 2, "proceedings-article": 2,
             "report": 3, "posted-content": 3, "dissertation": 4, "other": 5}


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


def nt(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", fold(t).lower())).strip()


import threading
_CR_LOCK = threading.Lock()
_CR_LAST = [0.0]


def get(url, tries=6):
    key = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".json")
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    for k in range(tries):
        if "crossref.org" in url:  # public pool: 1 req/s, concurrency 1
            with _CR_LOCK:
                wait = _CR_LAST[0] + 1.1 - time.time()
                if wait > 0:
                    time.sleep(wait)
                _CR_LAST[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode("utf-8"))
            key.write_text(json.dumps(data), encoding="utf-8")
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                key.write_text(json.dumps({"_404": True}), encoding="utf-8")
                return {"_404": True}
            time.sleep(2 ** k + 1)
        except Exception:
            time.sleep(2 ** k + 1)
    return None


def tsim(a, b):
    a, b = nt(a), nt(b)
    if not a or not b:
        return 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    # title prefix (subtitle dropped on one side)
    short = min(len(a), len(b))
    if short >= 20 and (a.startswith(b[:short]) or b.startswith(a[:short])):
        r = max(r, 0.9)
    return r


def crossref(c, journal_only=False):
    q = f'{c["authors"][:120]} {c["year"] or ""} {c["title"]}'
    params = {"query.bibliographic": q[:400], "rows": 6,
              "select": "DOI,title,author,issued,container-title,type,score,subtitle,publisher,is-referenced-by-count"}
    if journal_only:
        params["filter"] = "type:journal-article"
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    d = get(url)
    if not d or "message" not in d:
        return None
    best = None
    sur = re.sub(r"[^a-z]", "", fold(c["surname"].split()[-1]).lower())
    for it in d["message"]["items"]:
        title = (it.get("title") or [""])[0]
        if it.get("subtitle"):
            title_full = title + ": " + it["subtitle"][0]
        else:
            title_full = title
        s = max(tsim(c["title"], title), tsim(c["title"], title_full))
        fams = [re.sub(r"[^a-z]", "", fold(a.get("family", "")).lower()) for a in it.get("author", [])]
        auth_ok = any(sur and len(f) > 1 and (sur in f or f in sur or difflib.SequenceMatcher(None, sur, f).ratio() >= 0.8)
                      for f in fams) or not fams
        y = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        y_ok = (not c["year"] or not y or abs(y - c["year"]) <= 8)
        if s >= 0.78 and auth_ok and y_ok:
            wp_doi = it["DOI"].lower().startswith(("10.2139/", "10.3386/", "10.1596/", "10.2307/j.ctt"))
            rank = (TYPE_RANK.get(it.get("type"), 5) + (3 if wp_doi else 0), -s)
            # prefer journal article over WP/posted version when both match
            if best is None or rank < best[0]:
                best = (rank, dict(doi=it["DOI"].lower(), cr_title=title_full, cr_year=y, cr_type=it.get("type"),
                                   cr_venue=(it.get("container-title") or [""])[0] or it.get("publisher", ""),
                                   cr_authors=[(a.get("given", "") + " " + a.get("family", "")).strip() for a in it.get("author", [])],
                                   cr_sim=round(s, 3), cr_cites=it.get("is-referenced-by-count")))
    res = best[1] if best else None
    if res and not journal_only and (res["cr_type"] in ("report", "posted-content") or res["doi"].startswith(("10.2139/", "10.3386/"))):
        alt = crossref(c, journal_only=True)
        if alt and not alt["doi"].startswith(("10.2139/", "10.3386/")):
            alt["wp_doi"] = res["doi"]
            return alt
    return res


def oa_raw(doi=None, wid=None):
    """Raw OpenAlex work record (cached), by DOI or by OpenAlex id."""
    url = ("https://api.openalex.org/works/" + wid) if wid else \
        "https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/:.()-_;<>")
    d = get(url)
    return d if d and not d.get("_404") and "id" in d else None


def openalex(doi):
    d = oa_raw(doi)
    return oa_parse(d) if d else None


def oa_parse(d):
    inv = d.get("abstract_inverted_index") or {}
    abstract = None
    if inv:
        pos = {}
        for w, ps in inv.items():
            for p in ps:
                pos[p] = w
        abstract = " ".join(pos[i] for i in sorted(pos))
    loc = d.get("primary_location") or {}
    src = (loc.get("source") or {})
    boa = d.get("best_oa_location") or {}
    return dict(
        oa_id=d["id"].rsplit("/", 1)[-1], oa_title=d.get("title"), oa_year=d.get("publication_year"),
        oa_type=d.get("type"), venue=src.get("display_name"), cited_by=d.get("cited_by_count"),
        abstract=abstract, refs=[r.rsplit("/", 1)[-1] for r in d.get("referenced_works") or []],
        related=[r.rsplit("/", 1)[-1] for r in (d.get("related_works") or [])[:10]],
        oa_url=(d.get("open_access") or {}).get("oa_url"), pdf_url=boa.get("pdf_url") or loc.get("pdf_url"),
        landing=boa.get("landing_page_url") or loc.get("landing_page_url"),
        authors=[(a.get("author") or {}).get("display_name") for a in d.get("authorships", [])],
        inst_countries=sorted({c for a in d.get("authorships", []) for c in (a.get("countries") or [])}),
        topics=[(t.get("display_name"), (t.get("subfield") or {}).get("display_name"), (t.get("field") or {}).get("display_name"))
                for t in (d.get("topics") or [])[:3]],
        keywords=[k.get("display_name") for k in (d.get("keywords") or [])[:8]],
        counts_by_year=d.get("counts_by_year"),
    )


def work_cr(c):
    r = dict(cid=c["cid"])
    cr = crossref(c)
    if cr:
        r.update(cr)
    return r


def work_oa(r):
    if r.get("doi"):
        oa = openalex(r["doi"])
        if oa:
            r.update(oa)
    return r


def main():
    C = json.load(open(DATA / "clusters.json", encoding="utf-8"))
    if len(sys.argv) > 1:
        C = C[: int(sys.argv[1])]
    out, t0 = [], time.time()
    for i, c in enumerate(C):  # Crossref strictly sequential
        out.append(work_cr(c))
        if i % 100 == 0:
            print("crossref", i, round(time.time() - t0), "s", sum(1 for x in out if x.get("doi")), "dois", flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        out = list(ex.map(work_oa, out))
    json.dump(out, open(DATA / "resolved.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("done", len(out), "doi", sum(1 for x in out if x.get("doi")), "openalex", sum(1 for x in out if x.get("oa_id")),
          "abstract", sum(1 for x in out if x.get("abstract")))


if __name__ == "__main__":
    main()
