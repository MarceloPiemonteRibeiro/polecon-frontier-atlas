"""First-pass leaf assignment from keyword rules (title x3, abstract x1, syllabus heading x1).

Output: data/rule_class.tsv (reviewed by hand into data/manual_class.tsv)
"""
import re, json, sys
from collections import Counter
from pathlib import Path
from taxonomy import LEAF

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
PATS = {lid: re.compile(d["pat"], re.I) for lid, d in LEAF.items()}


def score(title, abstract="", heads=""):
    s = Counter()
    for lid, p in PATS.items():
        s[lid] += 3 * len(p.findall(title or "")) + len(p.findall(abstract or "")) * 0.5 + len(p.findall(heads or "")) * 1
    return [(l, v) for l, v in s.most_common(3) if v > 0]


def main():
    C = json.load(open(DATA / "clusters.json", encoding="utf-8"))
    R = {}
    if (DATA / "resolved.json").exists():
        R = {r["cid"]: r for r in json.load(open(DATA / "resolved.json", encoding="utf-8"))}
    rows = []
    for c in C:
        r = R.get(c["cid"], {})
        heads = " ".join({o["heading"] for o in c["occ"] if o["heading"]})
        sc = score(c["title"], r.get("abstract", ""), heads)
        nco = len({o["course_id"] for o in c["occ"]})
        rows.append((c["cid"], nco, c["year"] or "", c["surname"], c["title"][:150], sc[0][0] if sc else "?", sc[1][0] if len(sc) > 1 else ""))
    with open(DATA / "rule_class.tsv", "w", encoding="utf-8") as f:
        f.write("cid\tncourses\tyear\tsurname\ttitle\tleaf1\tleaf2\n")
        for row in rows:
            f.write("\t".join(map(str, row)) + "\n")
    print(Counter(r[5][0] for r in rows))
    print("unclassified", sum(1 for r in rows if r[5] == "?"))


if __name__ == "__main__":
    main()
