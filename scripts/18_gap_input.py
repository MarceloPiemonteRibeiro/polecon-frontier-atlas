"""Collect the "what is still open" statements out of the cards, one file per branch.

Each card carries up to five `gaps`: what that paper's own authors wrote down as unknown. Across
~1,900 papers that is several thousand statements, far too many to show raw. A clustering agent reads
one branch at a time and groups them into themes; the themes land in data/gap_themes.json and
17_evidence.py folds them into the Gaps view.

    python scripts/18_gap_input.py
"""
import collections, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
CARDS, OUT = DATA / "cards", DATA / "gap_input"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.txt"):
        f.unlink()
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    P = {cid_of[str(p["id"])]: p for p in D["papers"] if str(p["id"]) in cid_of}
    BR = {b["id"]: b for b in D["branches"]}
    LF = {l["id"]: l["name"] for l in D["leaves"]}

    rows = collections.defaultdict(list)
    seen, n = set(), 0
    for f in sorted(CARDS.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except Exception:
                continue
            cid = (c.get("cid") or "").upper()
            p = P.get(cid)
            if not p or cid in seen:
                continue
            seen.add(cid)
            for g in (c.get("gaps") or []):
                g = re.sub(r"\s+", " ", str(g)).strip()
                if len(g) < 20:
                    continue
                rows[p["br"]].append((cid, p, g))
                n += 1

    for br, items in sorted(rows.items()):
        b = BR.get(br, {})
        lines = [f"# branch {br} — {b.get('name', br)}",
                 f"# {len(items)} open-question statements, from the authors' own conclusions",
                 "# cid | leaf | authors year | the statement", ""]
        for cid, p, g in sorted(items, key=lambda r: (r[1]["lf"], -r[1]["nc"])):
            lines.append(f"{cid} | {p['lf']} {LF.get(p['lf'],'')} | {p.get('au','')} {p.get('y','')} | {g}")
        (OUT / f"{br}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{n} statements from {len(seen)} papers -> {len(rows)} branch files in data/gap_input/")
    for br, items in sorted(rows.items()):
        print(f"  {br} {BR.get(br,{}).get('short',br):<28} {len(items):>5}")


if __name__ == "__main__":
    main()
