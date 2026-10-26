"""Split the sliced papers into reading batches and write the compact slices the standard tier reads.

Two tiers, because a full slice is ~5k tokens and there are ~1,900 political-economy papers with a PDF:

  deep     the papers that anchor the literature (taught in 3+ courses, VoxDevLit evidence, or
           heavily cited) get every slice, so magnitudes and mechanism verdicts come through.
  standard everything else gets data/fulltext_lite/<cid>.json: abstract, the "this paper" opening,
           quantified claims, conclusion, captions, stated gaps and claims about the literature.
           About 2k tokens, enough for claim / direction / setting / mechanisms / gaps.

    python scripts/16_read_batches.py
"""
import argparse, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
FULL, LITE = DATA / "fulltext", DATA / "fulltext_lite"
BATCH, CARDS = DATA / "read_batches", DATA / "cards"
# Papers per reader agent. Bigger batches amortise the spec read; the ceiling is the agent's own
# context (a deep batch is ~5k tokens of slices per paper, a standard one ~2k).
DEEP_N, STD_N = 25, 60


def lite_of(d):
    """The slices that carry the finding, trimmed. Order matters: a reader stops when it has enough."""
    o = dict(cid=d["cid"], pages=d.get("pages"))
    if d.get("abstract"):
        o["abstract"] = d["abstract"][:1300]
    if d.get("intro"):
        # The "In this paper we..." paragraph is almost always in the first 1,400 chars.
        o["intro_open"] = d["intro"][:1400]
    if d.get("claims"):
        o["claims"] = [c[:260] for c in d["claims"][:10]]
    if d.get("conclusion"):
        o["conclusion"] = d["conclusion"][:2000]
    if d.get("captions"):
        o["captions"] = [c[:130] for c in d["captions"][:8]]
    if d.get("gaps"):
        o["gaps"] = [c[:260] for c in d["gaps"][:6]]
    if d.get("lit"):
        o["lit"] = [c[:260] for c in d["lit"][:6]]
    if d.get("models"):
        o["models"] = d["models"]
    if d.get("no_text"):
        o["no_text"] = True
    return o


def already_carded():
    """cids that already have a card, so a re-run only batches what is left."""
    done = set()
    for f in CARDS.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.search(r'"cid"\s*:\s*"([^"]+)"', line)
            if m:
                done.add(m.group(1).upper())
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-done", action="store_true", help="leave out papers that already have a card")
    a = ap.parse_args()
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    LITE.mkdir(parents=True, exist_ok=True)
    BATCH.mkdir(parents=True, exist_ok=True)
    CARDS.mkdir(parents=True, exist_ok=True)
    skip = already_carded() if a.skip_done else set()
    if skip:
        print(f"skipping {len(skip)} papers that already have a card")
    for f in BATCH.glob("*.txt"):
        f.unlink()

    leaf = {l["id"]: l["name"] for l in D["leaves"]}
    ci = lambda p: p.get("ci") or 0
    rows = []
    for p in D["papers"]:
        if p["f"] >= 8:                           # methods & adjacent: not political economy
            continue
        cid = cid_of.get(str(p["id"]))
        if not cid or cid in skip or not (FULL / f"{cid}.json").exists():
            continue
        # Deep tier kept narrow: the papers that anchor the field. Everything else reads well enough
        # from the compact slices, and the session rate limit is the binding constraint, not quality.
        deep = p["nc"] >= 4 or p.get("vox")
        rows.append(dict(cid=cid, p=p, deep=bool(deep)))

    # Deep first, most-taught first, so an interrupted run still covers what matters.
    rows.sort(key=lambda r: (not r["deep"], -r["p"]["nc"], -ci(r["p"])))
    deep = [r for r in rows if r["deep"]]
    std = [r for r in rows if not r["deep"]]

    for r in std:
        d = json.load(open(FULL / f"{r['cid']}.json", encoding="utf-8"))
        (LITE / f"{r['cid']}.json").write_text(json.dumps(lite_of(d), ensure_ascii=False), encoding="utf-8")

    def line(r):
        p = r["p"]
        fd = re.sub(r"\s+", " ", p.get("fd") or "").strip()
        return (f"{r['cid']} | {p.get('au','')} | {p.get('y','')} | {p['t'][:150]} | {p.get('v','')[:60]} | "
                f"{p['lf']} {leaf.get(p['lf'],'')} | taught in {p['nc']} courses"
                + (f" | prior one-liner: {fd}" if fd else " | prior one-liner: none (title only so far)"))

    n = 0
    for tier, items, size, src in (("deep", deep, DEEP_N, "data/fulltext"), ("std", std, STD_N, "data/fulltext_lite")):
        for i in range(0, len(items), size):
            chunk = items[i:i + size]
            name = f"{tier}_{i // size:03d}"
            (BATCH / f"{name}.txt").write_text(
                f"# batch {name} | tier {tier} | {len(chunk)} papers | slices in {src}/<cid>.json\n"
                f"# cid | authors | year | title | venue | leaf | courses | prior one-liner\n"
                + "\n".join(line(r) for r in chunk) + "\n", encoding="utf-8")
            n += 1

    est = len(deep) * 5.2 + len(std) * 2.0
    print(f"deep {len(deep)} papers in {-(-len(deep)//DEEP_N)} batches; standard {len(std)} in {-(-len(std)//STD_N)} batches; {n} batches total")
    print(f"lite slices written: {len(std)}; estimated reading input ~{est/1000:.1f}M tokens")


if __name__ == "__main__":
    main()
