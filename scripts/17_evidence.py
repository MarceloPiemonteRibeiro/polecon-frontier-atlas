"""Turn the evidence cards into the structures the dashboard draws.

Reads data/cards/*.jsonl (one card per line, schema in reader_spec.md), validates them against the
controlled vocabularies, and writes data/evidence.json:

  cells        every (treatment x outcome) pair that has evidence: how many papers, how they split on
               sign, which designs and countries, how much is post-2015
  contested    cells where the sign genuinely splits, with the papers on each side and what differs
  thin         structural holes: a treatment and an outcome each well studied, their intersection not
  travelled    claims resting on a single country despite several papers
  mechScore    per canonical mechanism: supports / contradicts / refines / inconclusive
  effects      comparable magnitude strips, where 4+ papers report the same unit for the same pair
  cards        the per-paper card, keyed by atlas paper id, for the drawer

    python scripts/17_evidence.py
    python scripts/17_evidence.py --validate     # report problems, write nothing
"""
import argparse, collections, json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
CARDS = DATA / "cards"

TREAT = {
    "info_voters": "Information to voters", "info_politicians": "Information to politicians & bureaucrats",
    "audit_monitoring": "Audits & monitoring", "electoral_rules": "Electoral rules & re-election incentives",
    "franchise_democracy": "Franchise & democratisation", "quotas_reservation": "Quotas & reserved seats",
    "politician_pay_selection": "Politician pay & selection", "bureaucrat_personnel": "Bureaucratic personnel rules",
    "decentralization": "Decentralisation", "transfers_cash": "Cash transfers & social programmes",
    "public_goods_infra": "Public goods & infrastructure", "media_access": "Media & internet access",
    "media_content": "Media content, slant & propaganda", "campaign_money_lobbying": "Campaign money & lobbying",
    "clientelism_vote_buying": "Vote buying & brokers", "anti_corruption_policy": "Anti-corruption policy",
    "taxation_fiscal_capacity": "Tax enforcement & fiscal capacity", "conflict_violence": "Conflict, violence & repression",
    "economic_shock": "Economic shocks", "migration_immigration": "Migration & immigration",
    "colonial_historical": "Colonial & historical institutions", "culture_identity": "Culture, diversity & identity",
    "institutional_constraints": "Constitutions, courts & checks", "protest_collective_action": "Protest & collective action",
    "education": "Education", "elite_capture": "Elites & capture", "political_competition": "Political competition",
    "land_property_rights": "Land reform & property rights", "foreign_aid": "Foreign aid & intervention",
    "other": "Other",
}
OUTC = {
    "voting_behaviour": "Voting behaviour", "politician_selection": "Who gets selected",
    "politician_behaviour": "Politician behaviour", "corruption_rents": "Corruption & rents",
    "public_goods_access": "Access to public goods", "public_services_quality": "Quality of services",
    "fiscal_spending": "Spending levels & targeting", "taxation_revenue": "Revenue & compliance",
    "state_capacity": "State capacity", "economic_development": "Income & development",
    "firm_outcomes": "Firm outcomes", "inequality_redistribution": "Inequality & redistribution",
    "beliefs_attitudes": "Beliefs & attitudes", "information_knowledge": "What citizens know",
    "polarisation": "Polarisation", "conflict_violence_out": "Conflict, crime & protest",
    "regime_democracy": "Regime & democratisation", "policy_adoption": "Policy adoption",
    "clientelism_out": "Clientelism", "human_capital_health": "Human capital & health",
    "migration_mobility": "Migration & mobility", "media_supply": "Media supply & censorship",
    "civic_participation": "Civic participation & social capital", "institutions_rules": "Institutions & rules adopted",
    "theory_only": "Theory only", "other": "Other",
}
DIRS = ("pos", "neg", "null", "mixed", "na", "unknown")
# Directions that carry no sign, so the paper cannot join an evidence cell: a theory paper, and a
# paper whose slices never stated which way its estimate went.
NOSIGN = ("na", "unknown")
VERDICTS = ("supports", "contradicts", "refines", "tests_inconclusive")
UNITS = ("pct", "pp", "sd", "log", "ratio", "level", "pctile")
LEVELS = ("cross_country", "country", "region", "state", "district", "municipality", "village", "precinct",
          "school_clinic", "firm", "individual", "politician", "bureaucrat", "legislature", "household", "na")
DESIGNS = ("RCT", "NatExp", "RD", "DiD", "IV", "Panel", "XC", "Struct", "Survey", "Lab", "Hist", "Text",
           "Desc", "Theory", "Review", "Book")
CREDIBLE = {"RCT", "RD", "DiD", "IV", "NatExp", "Struct"}
MECHS = {"M_median", "M_probvote", "M_moralhazard", "M_selection", "M_career", "M_visibility", "M_citizencand",
         "M_commit", "M_legbargain", "M_contest", "M_lobby", "M_collective", "M_clientelism", "M_fear",
         "M_coord", "M_cheaptalk", "M_media", "M_statecap", "M_bureau", "M_capture", "M_corruption",
         "M_war", "M_culture", "M_diversity"}


def load_cards(problems):
    out = {}
    for f in sorted(CARDS.glob("*.jsonl")):
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                c = json.loads(line)
            except Exception as e:
                problems.append(f"{f.name}:{ln} unparseable ({e})")
                continue
            cid = (c.get("cid") or "").upper()
            if not re.fullmatch(r"(C\d{5}|W\d+)", cid):
                problems.append(f"{f.name}:{ln} bad cid {cid!r}")
                continue
            if cid in out and out[cid].get("confidence") != "none":
                continue                          # first good card wins; re-runs append
            c["cid"] = cid
            out[cid] = c
    return out


def clean(c, problems):
    """Drop values outside the controlled vocabularies rather than letting them into the charts."""
    cid = c["cid"]
    def chk(key, allowed, default=None, path=""):
        v = c.get(key)
        if v in allowed:
            return v
        if v not in (None, "", []):
            problems.append(f"{cid}{path}: {key}={v!r} not in vocabulary")
        return default
    c["treatment"] = chk("treatment", TREAT, "other")
    c["outcome"] = chk("outcome", OUTC, "other")
    c["direction"] = chk("direction", DIRS, "na")
    c["confidence"] = chk("confidence", ("high", "medium", "low", "none"), "low")
    ident = c.get("identification") or {}
    if ident.get("design") not in DESIGNS:
        if ident.get("design"):
            problems.append(f"{cid}: design={ident.get('design')!r} not in vocabulary")
        ident["design"] = None
    c["identification"] = ident
    st = c.get("setting") or {}
    if st.get("level") not in LEVELS:
        st["level"] = None
    cs = [x for x in (st.get("countries") or []) if isinstance(x, str) and 2 <= len(x) <= 40]
    st["countries"] = sorted(dict.fromkeys(cs))
    per = st.get("period")
    st["period"] = per if (isinstance(per, list) and len(per) == 2 and all(isinstance(y, int) for y in per)
                           and 1000 <= per[0] <= per[1] <= 2030) else None
    c["setting"] = st
    ms = []
    for m in (c.get("mechanisms") or []):
        if isinstance(m, dict) and m.get("id") in MECHS and m.get("verdict") in VERDICTS:
            ms.append(dict(id=m["id"], verdict=m["verdict"], note=(m.get("note") or "")[:200]))
        elif isinstance(m, dict) and m.get("id"):
            problems.append(f"{cid}: mechanism {m.get('id')}/{m.get('verdict')} invalid")
    c["mechanisms"] = ms[:4]
    mg = []
    for m in (c.get("magnitudes") or []):
        if isinstance(m, dict) and m.get("unit") in UNITS and isinstance(m.get("value"), (int, float)):
            mg.append(dict(outcome=(m.get("outcome") or "")[:80], value=round(float(m["value"]), 4), unit=m["unit"]))
    c["magnitudes"] = mg[:4]
    for k in ("settled", "contested", "gaps"):
        c[k] = [re.sub(r"\s+", " ", x).strip()[:200] for x in (c.get(k) or []) if isinstance(x, str) and len(x) > 15][:5]
    for k in ("claim", "scope", "treatment_desc", "outcome_desc", "data_asset"):
        v = c.get(k)
        c[k] = re.sub(r"\s+", " ", v).strip()[:260] if isinstance(v, str) and v.strip() else None
    c["data_novel"] = bool(c.get("data_novel"))
    return c


def slice_text(cid):
    for p in (DATA / "fulltext" / f"{cid}.json", DATA / "fulltext_lite" / f"{cid}.json"):
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            parts = []
            for v in d.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, list):
                    parts += [x for x in v if isinstance(x, str)]
            return " ".join(parts)
    return ""


def num_forms(v):
    """How a paper might print this number: as written, or rescaled by a factor of 100 or 1,000."""
    out = set()
    for x in (v, v / 100.0, v * 100.0, v / 1000.0):
        out.update({"%g" % x, "%.1f" % x, "%.2f" % x, "%.3f" % x})
        if abs(x - round(x)) < 1e-9:
            out.add(str(int(round(x))))
    return {s for s in out if s.strip("0.")}


def trace_magnitudes(cards):
    """Mark each magnitude that can actually be found in the paper's own text.

    A reader is told to quote the paper's numbers, never to compute them, but some arrive anyway:
    spot-checking found figures that appear nowhere in the PDF. Untraceable numbers stay on the card,
    flagged, and are kept out of the effect-size strips, which invite readers to compare them.
    """
    n = t = 0
    for cid, c in cards.items():
        if not c["magnitudes"]:
            continue
        txt = slice_text(cid)
        for m in c["magnitudes"]:
            n += 1
            v = abs(float(m["value"]))
            hit = bool(txt) and any(re.search(r"(?<![\d.])" + re.escape(p) + r"(?![\d])", txt)
                                    for p in num_forms(v))
            m["t"] = hit
            t += hit
    return n, t


def agreement(d):
    """Share of the signed papers that sit on the modal side; nulls count as signed-against."""
    n = d["pos"] + d["neg"] + d["null"]
    return round(max(d["pos"], d["neg"]) / n, 2) if n else None


STOPW = set("the of and to in a is that for are with as by on this be an it from or we which not have has "
            "their they but all can more been would was were there when such other than into its also may "
            "some these effect effects on per change level rate share total measure measures index".split())


def outw(c):
    """Content words naming what a paper actually measured."""
    return {w for w in re.findall(r"[a-z]{4,}", (c.get("outcome_desc") or "").lower()) if w not in STOPW}


def clash(cids, cards):
    """The papers in a cell that genuinely contradict each other.

    A sign only means something against a specific measure. Inside 'voting behaviour' a paper on
    turnout and a paper on incumbent vote share are not answering the same question, so counting their
    signs against each other would invent disagreement. A pair counts as a clash only when the two
    papers took opposite signs AND their outcome descriptions share at least two content words; the
    returned papers are those taking part in at least one such pair.
    """
    pos = [c for c in cids if cards[c]["direction"] == "pos"]
    neg = [c for c in cids if cards[c]["direction"] == "neg"]
    nul = [c for c in cids if cards[c]["direction"] == "null"]
    shared = collections.Counter()
    hit = set()
    for a in pos:
        for b in neg + nul:
            common = outw(cards[a]) & outw(cards[b])
            if len(common) >= 2:
                hit.add(a); hit.add(b)
                shared.update(common)
    if not hit:
        return None
    return dict(cids=sorted(hit), label=", ".join(w for w, _ in shared.most_common(4)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--min-cell", type=int, default=3)
    a = ap.parse_args()

    # Everything here is keyed by cid, never by the atlas paper id: 06_build.py assigns ids by sort
    # order, so a pid-keyed card file would silently misalign after any rebuild.
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    P = {cid_of[str(p["id"])]: p for p in D["papers"] if str(p["id"]) in cid_of}

    # 15_fulltext.py --verify checks that each cid's PDF really holds the paper that cid names; some
    # were downloaded from search results and hold an editor's report, a catalogue or another article.
    # A card read off the wrong paper is worse than a missing one, so flagged papers are marked and
    # kept out of the aggregates, while staying visible (with the warning) in the paper drawer.
    mf = DATA / "pdf_mismatch.json"
    doubt = {x["cid"]: x["why"] for x in json.loads(mf.read_text(encoding="utf-8"))} if mf.exists() else {}

    problems = []
    raw = load_cards(problems)
    cards = {}
    for cid, c in raw.items():
        if cid not in P:
            problems.append(f"{cid}: no such paper in the atlas")
            continue
        cards[cid] = clean(c, problems)
        if cid in doubt:
            cards[cid]["doubt"] = doubt[cid]

    print(f"cards {len(cards)} / {len(raw)} lines; {len(problems)} problems")
    conf = collections.Counter(c["confidence"] for c in cards.values())
    print("confidence:", dict(conf))

    # Papers the readers could not code: wrong PDF, appendix only, book front matter, scanned image.
    # These are download failures masquerading as successes, so they get their own list to re-fetch.
    unread = [(cid, (c.get("skip_reason") or "no reason given"), P[cid].get("au", ""), P[cid].get("y", ""),
               P[cid]["t"][:70]) for cid, c in sorted(cards.items()) if c["confidence"] == "none"]
    if unread:
        (DATA / "bad_sources.txt").write_text(
            "# PDFs that are not the paper their cid names, or carry no readable text.\n"
            "# cid | reason the reader gave | authors | year | title\n"
            + "\n".join(f"{c} | {r} | {au} | {y} | {t}" for c, r, au, y, t in unread) + "\n", encoding="utf-8")
        print(f"{len(unread)} papers unreadable from their PDF -> data/bad_sources.txt (re-download these)")
    if a.validate:
        for p in problems[:60]:
            print("  !", p)
        if len(problems) > 60:
            print(f"  ... {len(problems)-60} more")
        return

    nm, nt = trace_magnitudes(cards)
    print(f"magnitudes: {nm}, of which {nt} ({100*nt/max(1,nm):.0f}%) traceable to the paper's own text")

    usable = {cid: c for cid, c in cards.items()
              if c["confidence"] != "none" and c["direction"] not in NOSIGN and not c.get("doubt")}
    nd = sum(1 for c in cards.values() if c.get("doubt") and c["confidence"] != "none")
    print(f"{nd} coded cards held out of the aggregates: their PDF may not be the paper the cid names")
    rank = lambda cid: (-(P[cid]["nc"]), -(P[cid].get("y") or 0))
    # ---- cells ----
    cell = collections.defaultdict(lambda: dict(cids=[], dir=dict.fromkeys(DIRS, 0), de=collections.Counter(),
                                                ct=collections.Counter(), yrs=[], fr=0))
    for cid, c in usable.items():
        e = cell[(c["treatment"], c["outcome"])]
        e["cids"].append(cid)
        e["dir"][c["direction"]] += 1
        if c["identification"].get("design"):
            e["de"][c["identification"]["design"]] += 1
        for ct in c["setting"]["countries"]:
            e["ct"][ct] += 1
        if c["setting"]["period"]:
            e["yrs"].append(c["setting"]["period"][1])
        if P[cid].get("fr"):
            e["fr"] += 1

    cells = []
    for (tr, ou), e in sorted(cell.items(), key=lambda kv: -len(kv[1]["cids"])):
        cids = sorted(e["cids"], key=rank)
        cells.append(dict(tr=tr, ou=ou, n=len(cids), cids=cids, dir=e["dir"],
                          de=dict(e["de"].most_common()), nCred=sum(v for k, v in e["de"].items() if k in CREDIBLE),
                          ct=[c for c, _ in e["ct"].most_common(12)], nCt=len(e["ct"]),
                          yMax=(max(e["yrs"]) if e["yrs"] else None), fr=e["fr"], ag=agreement(e["dir"])))

    # ---- contested: papers measuring the SAME thing that disagree on its sign ----
    # Judged inside a sub-question, never across a whole outcome family, so turnout studies are not
    # counted as contradicting vote-share studies.
    contested = []
    for c in cells:
        if c["n"] < 3:
            continue
        g = clash(c["cids"], usable)
        if not g or len(g["cids"]) < 3:
            continue
        gc = g["cids"]
        d = dict.fromkeys(DIRS, 0)
        for cid in gc:
            d[usable[cid]["direction"]] += 1
        side = lambda w: [cid for cid in gc if usable[cid]["direction"] == w]
        contested.append(dict(tr=c["tr"], ou=c["ou"], n=len(gc), ag=agreement(d), dir=d, label=g["label"],
                              pos=side("pos"), neg=side("neg"), nul=side("null"), mix=side("mixed")))
    contested.sort(key=lambda c: (-(c["n"]), c["ag"] or 1))

    # ---- structural holes: both margins busy, the intersection is not ----
    trN, ouN = collections.Counter(), collections.Counter()
    for c in cells:
        trN[c["tr"]] += c["n"]
        ouN[c["ou"]] += c["n"]
    got = {(c["tr"], c["ou"]): c["n"] for c in cells}
    # "other" and "theory_only" are catch-alls, so a hole involving them says nothing about the field.
    VAGUE = {"other", "theory_only"}
    thin = []
    for tr, tn in trN.items():
        for ou, on in ouN.items():
            if tr in VAGUE or ou in VAGUE:
                continue
            n = got.get((tr, ou), 0)
            if tn >= 12 and on >= 12 and n <= 2:
                # expected count under independence, as a crude benchmark for "should exist"
                exp = tn * on / max(1, sum(trN.values()))
                if exp >= 2.5:
                    here = cell[(tr, ou)]["cids"] if (tr, ou) in cell else []
                    thin.append(dict(tr=tr, ou=ou, n=n, exp=round(exp, 1), trN=tn, ouN=on, cids=sorted(here)))
    thin.sort(key=lambda t: -(t["exp"] - t["n"]))

    # ---- claims that have not travelled: several papers, all in ONE named country ----
    # nCt == 0 means no setting was recorded, which is ignorance rather than a single setting.
    travelled = [dict(tr=c["tr"], ou=c["ou"], n=c["n"], nCt=c["nCt"], ct=c["ct"], cids=c["cids"][:8])
                 for c in cells if c["n"] >= 4 and c["nCt"] == 1
                 and c["tr"] not in {"other", "theory_only"} and c["ou"] not in {"other", "theory_only"}]
    travelled.sort(key=lambda t: -t["n"])

    # ---- mechanism scoreboard ----
    mech = collections.defaultdict(lambda: {v: [] for v in VERDICTS})
    for cid, c in cards.items():
        if c.get("doubt") or c["confidence"] == "none":
            continue
        for m in c["mechanisms"]:
            mech[m["id"]][m["verdict"]].append(cid)
    mechScore = {m: {v: sorted(cs, key=rank) for v, cs in d.items()} for m, d in mech.items()}

    # ---- comparable magnitude strips ----
    # Only traceable numbers go in a strip: a strip invites a reader to compare values, so one the
    # paper never printed does not belong there.
    bag = collections.defaultdict(list)
    for cid, c in usable.items():
        for m in c["magnitudes"]:
            if m.get("t"):
                bag[(c["treatment"], c["outcome"], m["unit"])].append(dict(cid=cid, v=m["value"], o=m["outcome"]))
    effects = [dict(tr=t, ou=o, unit=u, n=len(vs), vals=sorted(vs, key=lambda x: x["v"]))
               for (t, o, u), vs in bag.items() if len(vs) >= 4]
    effects.sort(key=lambda e: -e["n"])

    themes = []
    tf = DATA / "gap_themes.json"
    if tf.exists():
        raw_t = json.loads(tf.read_text(encoding="utf-8"))
        for t in (raw_t.get("themes") if isinstance(raw_t, dict) else raw_t) or []:
            cs = [c.upper() for c in (t.get("cids") or []) if c.upper() in P]
            if not t.get("title") or not cs:
                continue
            themes.append(dict(branch=t.get("branch") or P[cs[0]]["br"], title=t["title"][:120],
                               text=(t.get("text") or "")[:400], why=(t.get("why") or "")[:300],
                               maturity=t.get("maturity"), n=len(cs), cids=sorted(cs, key=rank)[:40]))
        themes.sort(key=lambda t: -t["n"])

    contested_keys = {(c["tr"], c["ou"]) for c in contested}
    nSettled = sum(1 for c in cells if c["n"] >= 4 and (c["tr"], c["ou"]) not in contested_keys and (c["ag"] or 0) >= 0.8)
    out = dict(treatLabels=TREAT, outLabels=OUTC, cells=cells, contested=contested, thin=thin[:40],
               travelled=travelled[:40], mechScore=mechScore, effects=effects, gapThemes=themes,
               cards=cards,
               stats=dict(nCards=len(cards), nUsable=len(usable), conf=dict(conf), nSettled=nSettled,
                          nCells=len(cells), nContested=len(contested), nProblems=len(problems)))
    (DATA / "evidence.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"cells {len(cells)} (>= {a.min_cell} papers: {sum(1 for c in cells if c['n']>=a.min_cell)}), "
          f"contested {len(contested)}, holes {len(thin)}, single-country {len(travelled)}, "
          f"effect strips {len(effects)}, mechanisms scored {len(mechScore)}")
    if problems:
        (DATA / "evidence_problems.txt").write_text("\n".join(problems), encoding="utf-8")
        print(f"problems written to data/evidence_problems.txt")


if __name__ == "__main__":
    main()
