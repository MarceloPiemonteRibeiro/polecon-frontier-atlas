"""Warm the OpenAlex cache for clusters whose Crossref lookups are already cached (no new Crossref traffic)."""
import json, importlib.util, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("resolve", HERE / "04_resolve.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
real_get = R.get


def cached_only(url, tries=6):
    if "crossref.org" in url:
        key = R.CACHE / (R.hashlib.md5(url.encode()).hexdigest() + ".json")
        return json.loads(key.read_text(encoding="utf-8")) if key.exists() else None
    return real_get(url, tries)


R.get = cached_only
C = json.load(open(R.DATA / "clusters.json", encoding="utf-8"))
dois = [cr["doi"] for c in C if (cr := R.crossref(c))]
print("cached crossref matches:", len(dois), flush=True)
with ThreadPoolExecutor(max_workers=6) as ex:
    n = sum(1 for x in ex.map(R.openalex, dois) if x)
print("openalex records warmed:", n)

# provisional resolved.json from cache (the full run overwrites it)
out = []
for c in C:
    r = R.work_cr(c)
    out.append(R.work_oa(r))
json.dump(out, open(R.DATA / "resolved.json", "w", encoding="utf-8"), ensure_ascii=False)
print("provisional resolved:", sum(1 for x in out if x.get("doi")), "with abstract", sum(1 for x in out if x.get("abstract")))
