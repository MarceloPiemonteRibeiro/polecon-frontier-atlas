"""Filter raw entries and cluster them into unique works.

Output: data/clusters.json  (one record per unique work, with every occurrence)
"""
import re, json, unicodedata, difflib
from collections import defaultdict, Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

BAD_SUR = set("""Polity Comparison December Development Services Ideological Selection Telecommunications Source Notes Table
Figure Data Evidence Theory Model Results Introduction Conclusion Background Motivation Question Questions Answer Readings
Reading Required Optional Summary Overview Example Examples Literature Review Papers Paper Topics Topic Lecture Week""".split())


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


def norm_title(t):
    t = fold(t).lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_sur(s):
    return re.sub(r"[^a-z]", "", fold(s).lower())


def good(e):
    s, t = e["surname"], e["title"] or ""
    if not s or s.isupper() and len(s) > 3 or re.search(r"[\d?%�]", s) or s in BAD_SUR:
        return False
    if len(s.split()) > 3:
        return False
    if e["year"] and not (1850 <= e["year"] <= 2027):
        return False
    if not t or len(t.split()) < 2 or not re.match(r"[A-Z0-9\"'¿¡(À-Þ]", t):
        return False
    if re.search(r"%2|verify citation|https?:|www\.|\.pdf|homework|problem set", t, re.I):
        return False
    if sum(ch.isdigit() for ch in t) > len(t) * 0.25:
        return False
    if e["src_kind"] == "slides" and '"' not in e["raw"] and not re.search(
            r"\b(journal|review|econometrica|quarterly|economics|economy|science|working paper|press|proceedings)\b", e["raw"], re.I):
        return False
    return True


def main():
    E = [json.loads(l) for l in open(DATA / "raw_entries.jsonl", encoding="utf-8")]
    G = [e for e in E if good(e)]
    print("raw", len(E), "kept", len(G))
    for e in G:
        e["nt"] = norm_title(e["title"])
        e["ns"] = norm_sur(e["surname"].split()[-1] if " " in e["surname"] and not re.match(r"(?i)(de|del|da|van|von|dal|la|le)\s", e["surname"]) else e["surname"])

    # union-find
    parent = list(range(len(G)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    by_key = defaultdict(list)
    for i, e in enumerate(G):
        by_key[" ".join(e["nt"].split()[:9])].append(i)
    for idx in by_key.values():
        for j in idx[1:]:
            union(idx[0], j)
    # fuzzy within surname bucket
    by_sur = defaultdict(list)
    for i, e in enumerate(G):
        by_sur[e["ns"][:5]].append(i)
    reps_done = 0
    for bucket in by_sur.values():
        roots = {}
        for i in bucket:
            roots.setdefault(find(i), i)
        items = list(roots.values())
        for a in range(len(items)):
            ta = G[items[a]]["nt"]
            for b in range(a + 1, len(items)):
                tb = G[items[b]]["nt"]
                if abs(len(ta) - len(tb)) > max(len(ta), len(tb)) * 0.6 and not (ta.startswith(tb[:30]) or tb.startswith(ta[:30])):
                    continue
                short = min(len(ta), len(tb))
                if short >= 25 and (ta.startswith(tb[:short]) or tb.startswith(ta[:short])):
                    union(items[a], items[b]); reps_done += 1; continue
                if difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.86:
                    union(items[a], items[b]); reps_done += 1
    groups = defaultdict(list)
    for i in range(len(G)):
        groups[find(i)].append(G[i])
    print("clusters", len(groups), "fuzzy merges", reps_done)

    out = []
    for k, (root, occ) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        titles = Counter(o["title"] for o in occ)
        title = max(titles, key=lambda t: (titles[t], '"' in t or True, len(t)))
        years = Counter(o["year"] for o in occ if o["year"])
        best_raw = max(occ, key=lambda o: ('"' in o["raw"], o["src_kind"] == "reading_list", -abs(len(o["raw"]) - 220)))["raw"]
        out.append(dict(
            cid=f"C{k:05d}", title=title, surname=Counter(o["surname"] for o in occ).most_common(1)[0][0],
            ns=occ[0]["ns"], year=years.most_common(1)[0][0] if years else None, years=sorted(years),
            authors=max((o["authors"] for o in occ), key=len)[:300], venue=Counter(o["venue"] for o in occ).most_common(1)[0][0],
            raw=best_raw[:500],
            occ=[dict(file=o["file"], course_id=o["course_id"], src_label=o["src_label"], src_year=o["src_year"],
                      src_kind=o["src_kind"], heading=o["heading"], starred=o["raw"].lstrip().startswith(("*", "(*)"))) for o in occ]))
    json.dump(out, open(DATA / "clusters.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    n_courses = Counter(len({o["course_id"] for o in c["occ"]}) for c in out)
    print("clusters by #distinct courses:", sorted(n_courses.items())[:12])


if __name__ == "__main__":
    main()
