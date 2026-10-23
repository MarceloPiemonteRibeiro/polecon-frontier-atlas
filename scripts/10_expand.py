"""Snowball the corpus one step through reference lists.

Works that at least MIN_CITES syllabus political-economy papers cite (OpenAlex referenced_works) but that no
syllabus lists are fetched from OpenAlex and placed on the tree by majority vote of the leaves of the atlas papers
citing them. Hand overrides go in data/expanded_class.txt ("W123 C4" or "W123 -" to drop).

Output: data/expanded.json
"""
import importlib.util, json, re, difflib
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
MIN_CITES = 10
spec = importlib.util.spec_from_file_location("r4", Path(__file__).with_name("04_resolve.py"))
R4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(R4)


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower())


def main():
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    syl = [p for p in D["papers"] if not p.get("x")]
    R = {r["cid"]: r for r in json.load(open(DATA / "resolved.json", encoding="utf-8"))}
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    for p in syl:
        p["cid"] = cid_of[str(p["id"])]
    have = {r["oa_id"] for r in R.values() if r.get("oa_id")}
    cites = defaultdict(list)                       # W -> leaves of citing syllabus PE papers
    for p in syl:
        if p["f"] >= 8:
            continue
        for w in set(R.get(cid_of[str(p["id"])], {}).get("refs") or []):
            if w not in have:
                cites[w].append(p["lf"])
    cand = sorted((w for w, ls in cites.items() if len(ls) >= MIN_CITES), key=lambda w: -len(cites[w]))
    print("candidates", len(cand), flush=True)

    titles = {norm(p["t"]): p for p in syl}
    over, fix, alias = {}, {}, {}
    f = DATA / "expanded_class.txt"
    if f.exists():
        for line in open(f, encoding="utf-8"):
            if not line.strip() or line.startswith("#"):
                continue
            head, _, meta = line.partition(" = ")
            w, lab = head.split()[:2]
            if lab == ">":
                alias[w] = head.split()[2]
            else:
                over[w] = lab
            if meta:
                au, yr, ti = meta.strip().split("|")
                fix[w] = dict(authors=[a.strip() for a in au.split(",")], y=int(yr), t=ti.strip())
    out = []
    for k, w in enumerate(cand):
        if w in alias:
            continue
        d = R4.oa_raw(wid=w)
        if k % 50 == 0:
            print(k, flush=True)
        if not d or d.get("type") in ("dataset", "paratext", "erratum", "retraction", "peer-review", "editorial"):
            continue
        o = R4.oa_parse(d)
        t = norm(o["oa_title"])
        twin = titles.get(t) or next((p for tt, p in titles.items() if len(t) > 25 and difflib.SequenceMatcher(None, t, tt).ratio() > 0.93), None)
        if twin:                                    # same work under another OpenAlex id (WP vs journal)
            alias[w] = twin["cid"]
            continue
        votes = Counter(cites[w])
        lab = over.get(w) or votes.most_common(1)[0][0]
        if lab == "-":
            continue
        rec = dict(wid=w, t=o["oa_title"], y=o["oa_year"], v=o["venue"] or "", doi=(d.get("doi") or "").replace("https://doi.org/", "") or None,
                   authors=o["authors"], ab=o["abstract"] or "", refs=o["refs"], ci=o["cited_by"], u=o["pdf_url"] or o["oa_url"] or "",
                   lf=lab, votes=votes.most_common(4), ncite=len(cites[w]), typ=d.get("type"))
        if w in fix:                                # record was a review of the book: keep the book, drop the reviewer's text
            rec.update(fix[w], ab="", v="", doi=None, u="", oa_authors=False)
        out.append(rec)
    json.dump(dict(works=out, alias=alias, min_cites=MIN_CITES), open(DATA / "expanded.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("expanded works", len(out), "aliases", len(alias))


if __name__ == "__main__":
    main()
