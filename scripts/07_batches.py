"""Write reading batches of abstracts (and fetched introductions) for papers not yet annotated.

Uses data/atlas_data.json from the last build plus data/intros/*.txt.
Output: data/batches/batch_XXX.txt  (one block per paper; I read these and write data/annot_abs_XXX.txt)
"""
import json, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
OUT = DATA / "batches"
OUT.mkdir(exist_ok=True)
SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 40


def main():
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))  # atlas id -> primary cluster id
    done = set()
    for f in DATA.glob("annot_*.txt"):
        for line in open(f, encoding="utf-8"):
            if line[:1].isdigit() or line[:1] == "W":
                key = line.split("|")[0].strip()
                done.add(key if key.startswith("W") else "C" + key)
    intros = {p.stem: p.read_text(encoding="utf-8") for p in (DATA / "intros").glob("*.txt")} if (DATA / "intros").exists() else {}
    todo = []
    for p in D["papers"]:
        cid = cid_of[str(p["id"])]
        if p["f"] >= 8 or cid in done:
            continue
        txt = p.get("ab") or ""
        src = "abstract"
        if not txt and cid in intros:
            txt, src = intros[cid], "intro"
        if not txt:
            continue
        todo.append((p["br"], p["lf"], -(p["nc"]), cid, p, txt, src))
    todo.sort(key=lambda r: (r[0], r[1], r[2]))
    for old in OUT.glob("batch_*.txt"):
        old.unlink()
    for k in range(0, len(todo), SIZE):
        with open(OUT / f"batch_{k // SIZE:03d}.txt", "w", encoding="utf-8") as f:
            for br, lf, _, cid, p, txt, src in todo[k:k + SIZE]:
                key = cid if cid.startswith("W") else cid[1:]
                tag = f" | cited by {p['x']} syllabus papers" if p.get("x") else ""
                f.write(f"## {key} | {p['y']} | {p['au']} | {lf} | {p.get('v','')}{tag}\n{p['t']}\n[{src}] {txt[:2200]}\n\n")
    print("papers to read:", len(todo), "batches:", (len(todo) + SIZE - 1) // SIZE)


if __name__ == "__main__":
    main()
