"""Assemble the atlas: papers + classification + annotations + citation edges -> site/PolEcon_Frontier_Atlas.html

Inputs (data/): clusters.json, resolved.json, manual_class.txt, annot_*.txt, intros/ (optional)
"""
import json, re, unicodedata, sys
from collections import defaultdict, Counter
from pathlib import Path
from taxonomy import TREE, LEAF, MECHANISMS
from content import FAMS, SHORT, NARRATIVE, VOX_FINDINGS, DESIGNS, MECH_GROUPS, MECH_YEARS, AGENDA, META
from sources import REGISTRY
from leaf_notes import LEAF_NOTES
from model_refs import MODEL_REFS

BASE = Path(__file__).resolve().parents[1]
DATA, SITE = BASE / "data", BASE / "site"
EXCLUDE_FROM_NC = {"USER", "USERGPT", "VOXDEV"}
BR_FAM = {b: i for i, f in enumerate(FAMS) for b in f["branches"]}


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


# Venue categories for the "where it is published" chart (first match wins; fixed order = palette order)
VENUE_CATS = [
    ("Top-5 economics", r"american economic review(?!.{0,12}(insights|papers|proceedings))|quarterly journal of economics|journal of political economy(?! micro)|econometrica|review of economic studies"),
    ("Top-3 political science", r"american political science review|american journal of political science|journal of politics\b(?! institutions)|^the journal of politics"),
    ("Reviews, surveys & handbooks", r"journal of economic literature|journal of economic perspectives|annual review|handbook|research encyclopedia|research observer|brookings papers|macroeconomics annual|economic policy\b"),
    ("Other economics journals", r"econom|ekonom|development|legal studies|journal of finance|financial|journal of development|journal of public|review of economics and statistics|journal of law|rand journal|bell journal|management science|journal of human resources|national tax|industrial and labor|explorations|papers and proceedings|journal of international|public choice"),
    ("Other political science & IR", r"polit|international organization|international studies|journal of peace|conflict resolution|public opinion|electoral studies|legislative|international migration|foreign affairs|public administration|representation|journal of democracy|asian survey|governance"),
    ("Working papers", r"national bureau|nber|ssrn|working paper|mimeo|discussion paper|cepr|unpublished|manuscript|caltechauthors|digital access to scholarship|center for open science|improving systems|imf|world bank|policy brief|work in progress|federal reserve|banco de|\bdp\d|drive.google|dropbox|available at"),
    ("Books & chapters", r"ebooks|university press|press\b|routledge|palgrave|springer|elgar|varieties of capitalism|choice reviews|publishers|sage publications|cambridge|oxford|princeton|gutenberg|columbia global|studies in"),
    ("Science, sociology & other", r"."),
]
_VC = [(i, re.compile(p, re.I)) for i, (_, p) in enumerate(VENUE_CATS)]


def venue_cat(*texts):
    """Index into VENUE_CATS, or 8 (unknown) when no venue text exists."""
    for k, t in enumerate(texts):
        t = (t or "").strip()
        if t:
            hit = next((i for i, rx in _VC if rx.search(t)), 8)
            if k == 0 or hit < 7:                   # syllabus fallback text only counts when it names a known venue type
                return hit
    return 8


def load_labels():
    lab = {}
    for line in open(DATA / "manual_class.txt", encoding="utf-8"):
        a, b = line.split()
        r = range(int(a.split("-")[0]), int(a.split("-")[1]) + 1) if "-" in a and len(a) > 5 else [int(a)]
        for i in r:
            lab[f"C{i:05d}"] = b
    return lab


def load_annotations():
    """annot_*.txt lines: cid|country|design|finding|mechs|vox  (later files override earlier ones)."""
    ann = {}
    for f in sorted(DATA.glob("annot_*.txt")):
        src = {"annot_voxdev.txt": "review"}.get(f.name, "intro" if "intro" in f.name else "abstract")
        for line in open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 6:
                print("bad annotation line", f.name, line[:80], file=sys.stderr)
                continue
            cid, country, design, finding, mechs, vox = parts[:6]
            cid = cid.strip()
            cid = cid if cid.startswith("W") else "C" + cid.lstrip("C")   # W… = work expanded from reference lists
            me = []
            for m in filter(None, (x.strip() for x in mechs.split(","))):
                v = m[-1] if m[-1] in "+~-" else "+"
                mid = m.rstrip("+~-")
                if mid not in MECH_IDS:
                    print("unknown mechanism", mid, cid, file=sys.stderr)
                    continue
                me.append([mid, v])
            if design and design not in DESIGNS:
                print("unknown design", design, cid, file=sys.stderr)
            ann[cid] = dict(ct=[c.strip() for c in country.split(";") if c.strip() and c.strip() not in ("Theory",)],
                            de=design.strip(), fd=finding.strip(), me=me, vx=[v for v in vox.split(",") if v.strip()], rs=src)
    return ann


MECH_IDS = {m["id"] for m in MECHANISMS}

COUNTRIES = """Afghanistan Albania Algeria Angola Argentina Armenia Australia Austria Azerbaijan Bangladesh Belarus Belgium Benin Bolivia
Bosnia Botswana Brazil Bulgaria Burkina Burundi Cambodia Cameroon Canada Chad Chile China Colombia Congo Croatia Cuba Cyprus Czech
Denmark Ecuador Egypt Estonia Ethiopia Finland France Gabon Gambia Georgia Germany Ghana Greece Guatemala Guinea Haiti Honduras Hungary
India Indonesia Iran Iraq Ireland Israel Italy Jamaica Japan Jordan Kazakhstan Kenya Korea Kosovo Kyrgyzstan Laos Latvia Lebanon Lesotho Liberia
Libya Lithuania Madagascar Malawi Malaysia Mali Mauritania Mexico Moldova Mongolia Morocco Mozambique Myanmar Namibia Nepal Netherlands
Nicaragua Niger Nigeria Norway Pakistan Palestine Panama Paraguay Peru Philippines Poland Portugal Romania Russia Rwanda Senegal Serbia
Slovakia Slovenia Somalia Spain Sudan Sweden Switzerland Syria Taiwan Tajikistan Tanzania Thailand Togo Tunisia Turkey Uganda Ukraine
Uruguay Uzbekistan Venezuela Vietnam Yemen Zambia Zimbabwe""".split()
DEMONYM = {"Brazilian": "Brazil", "Indian": "India", "Chinese": "China", "Mexican": "Mexico", "Kenyan": "Kenya", "Indonesian": "Indonesia",
           "Colombian": "Colombia", "Pakistani": "Pakistan", "Ugandan": "Uganda", "Nigerian": "Nigeria", "Ghanaian": "Ghana", "Peruvian": "Peru",
           "Argentine": "Argentina", "Argentinian": "Argentina", "Chilean": "Chile", "Russian": "Russia", "Italian": "Italy", "Swedish": "Sweden",
           "German": "Germany", "French": "France", "British": "United Kingdom", "Spanish": "Spain", "Afghan": "Afghanistan", "Iraqi": "Iraq",
           "Rwandan": "Rwanda", "Vietnamese": "Vietnam", "Filipino": "Philippines", "Ugandan's": "Uganda", "Sierra Leonean": "Sierra Leone",
           "Venezuelan": "Venezuela", "Turkish": "Turkey", "Swiss": "Switzerland", "Danish": "Denmark", "Norwegian": "Norway", "Dutch": "Netherlands",
           "Ethiopian": "Ethiopia", "Malawian": "Malawi", "Senegalese": "Senegal", "Liberian": "Liberia", "Congolese": "DR Congo", "Burundian": "Burundi",
           "Tanzanian": "Tanzania", "Ecuadorian": "Ecuador", "Bolivian": "Bolivia", "Salvadoran": "El Salvador", "Japanese": "Japan", "Korean": "South Korea"}
MULTI = {"United States": "United States", "U.S.": "United States", "US ": "United States", "America's": "United States", "American": "United States",
         "United Kingdom": "United Kingdom", "Britain": "United Kingdom", "England": "United Kingdom", "Sierra Leone": "Sierra Leone",
         "South Africa": "South Africa", "Sri Lanka": "Sri Lanka", "El Salvador": "El Salvador", "Costa Rica": "Costa Rica", "New Zealand": "New Zealand",
         "Dominican Republic": "Dominican Republic", "Puerto Rico": "Puerto Rico", "Hong Kong": "China", "South Korea": "South Korea",
         "Democratic Republic of the Congo": "DR Congo", "DRC": "DR Congo", "Eastern Congo": "DR Congo", "Burkina Faso": "Burkina Faso",
         "Cote d'Ivoire": "Côte d'Ivoire", "Côte d'Ivoire": "Côte d'Ivoire", "Ivory Coast": "Côte d'Ivoire", "Sao Tome": "Sao Tome and Principe",
         "Soviet Union": "Russia", "USSR": "Russia", "Prussia": "Germany", "Nazi": "Germany", "Weimar": "Germany", "Punjab": "Pakistan",
         "West Bengal": "India", "Rajasthan": "India", "Uttar Pradesh": "India", "Bihar": "India", "Maharashtra": "India", "Delhi": "India",
         "Sicily": "Italy", "Sicilian": "Italy", "Aceh": "Indonesia", "Java": "Indonesia", "Bali": "Indonesia", "Rio de Janeiro": "Brazil",
         "Amazon": "Brazil", "Bolsa Fam": "Brazil", "Progresa": "Mexico", "NREGS": "India", "panchayat": "India", "Scheduled Caste": "India",
         "Scheduled Tribe": "India", "Suharto": "Indonesia", "Soeharto": "Indonesia", "Pinochet": "Chile", "Montesinos": "Peru",
         "Tea Party": "United States", "Congress": None, "Brexit": "United Kingdom", "Fox News": "United States", "Berlusconi": "Italy",
         "Chavez": "Venezuela", "Rio Grande": None, "Ottoman": "Turkey", "Mughal": "India", "Qing": "China", "Mamluk": "Egypt", "Kuba": "DR Congo",
         "Native American": "United States", "Jim Crow": "United States", "Antebellum": "United States", "Great Migration": "United States",
         "Voting Rights Act": "United States", "Swedish": "Sweden", "Canton": "Switzerland"}
ATLAS_NAME = {"United States of America": "United States", "Dem. Rep. Congo": "DR Congo", "Central African Rep.": "Central African Republic",
              "S. Sudan": "South Sudan", "Bosnia and Herz.": "Bosnia", "Dominican Rep.": "Dominican Republic", "Eq. Guinea": "Equatorial Guinea",
              "Solomon Is.": "Solomon Islands", "eSwatini": "Eswatini", "W. Sahara": "Western Sahara", "N. Cyprus": "Cyprus", "Côte d'Ivoire": "Côte d'Ivoire",
              "Czechia": "Czech", "Congo": "Congo", "Macedonia": "North Macedonia", "Timor-Leste": "Timor-Leste"}
CTRY_FIX = {"South Korea": "South Korea", "Korea": "South Korea", "Bosnia": "Bosnia", "Czech": "Czech", "Burkina": "Burkina Faso",
            "Congo": "DR Congo", "Guinea": "Guinea", "Georgia": None}


def detect_countries(text):
    found = []
    t = " " + (text or "") + " "
    for k, v in MULTI.items():
        if v and re.search(r"(?<![A-Za-z])" + re.escape(k), t):
            found.append(v)
    for c in COUNTRIES:
        if re.search(r"(?<![A-Za-z])" + c + r"(?![a-z])", t):
            c2 = CTRY_FIX.get(c, c)
            if c2:
                found.append(c2)
    for k, v in DEMONYM.items():
        if re.search(r"(?<![A-Za-z])" + re.escape(k) + r"(?![a-z])", t):
            found.append(v)
    out = []
    for f in found:
        if f not in out:
            out.append(f)
    return out[:4]


def short_authors(names, fallback):
    names = [n for n in (names or []) if n]
    if not names:
        sur, raw = fallback
        raw = re.sub(r"\s*[\(\[]?\d{4}.*$", "", raw or "").strip(" .,)(")
        raw = re.sub(r",\s*and\b", " and", raw)
        if not sur:
            return "Unknown", raw
        parts = re.split(r"\band\b|&", raw)
        head = parts[0].strip(" ,")
        if len(parts) == 1:
            return (sur + " et al." if head.count(",") >= 3 else sur), raw
        if len(parts) == 2 and head.count(",") <= 1:
            tail = parts[1].strip(" .,")
            if "," in tail:
                second = tail.split(",")[0].strip()
            else:
                toks = [t.strip(".,") for t in tail.split() if t[:1].isupper() and not re.fullmatch(r"[A-Z]\.?", t)]
                second = toks[-1] if toks else ""
            return (f"{sur} & {second}" if second and second != sur else sur), raw
        return sur + " et al.", raw
    sur = []
    for n in names:
        parts = n.split()
        s = parts[-1] if parts else n
        if len(parts) >= 2 and parts[-2].lower() in ("de", "da", "dal", "del", "van", "von", "la", "le", "di", "i") :
            s = " ".join(parts[-2:])
            if len(parts) >= 3 and parts[-3].lower() in ("padró", "padro"):
                s = " ".join(parts[-3:])
        sur.append(s)
    if len(sur) == 1:
        short = sur[0]
    elif len(sur) == 2:
        short = f"{sur[0]} & {sur[1]}"
    else:
        short = f"{sur[0]} et al."
    return short, ", ".join(names[:12]) + (" et al." if len(names) > 12 else "")


def find_paper(papers, sur, year, frag, strict=True):
    s0 = fold(sur).lower()
    f0 = frag.lower()
    hits = [p for p in papers if f0 in p["t"].lower() and (s0 in fold(p["af"]).lower() or s0 in fold(p["au"]).lower())]
    if not hits:
        hits = [p for p in papers if f0 in p["t"].lower() and abs((p["y"] or year) - year) <= 3]
    if not hits:
        if strict:
            raise SystemExit(f"content reference not found: {sur} {year} {frag}")
        return None
    return min(hits, key=lambda p: abs((p["y"] or year) - year))["id"]


def main():
    C = {c["cid"]: c for c in json.load(open(DATA / "clusters.json", encoding="utf-8"))}
    R = {r["cid"]: r for r in json.load(open(DATA / "resolved.json", encoding="utf-8"))}
    LAB = load_labels()
    S2 = json.load(open(DATA / "s2_abstracts.json", encoding="utf-8")) if (DATA / "s2_abstracts.json").exists() else {}
    ANN = load_annotations()

    # --- merge clusters that resolved to the same DOI / OpenAlex work
    groups = defaultdict(list)
    for cid, c in C.items():
        r = R.get(cid, {})
        key = r.get("oa_id") or r.get("doi") or cid
        groups[key].append(cid)
    merged = []
    for key, cids in groups.items():
        cids.sort(key=lambda x: (LAB.get(x, "-") == "-", -len(C[x]["occ"])))
        prim = cids[0]
        if LAB.get(prim, "-") == "-":
            continue
        merged.append((prim, cids))
    print("works after DOI merge:", len(merged), "from", len(C))

    papers = []
    for prim, cids in merged:
        c, r = C[prim], R.get(prim, {})
        occ = [o for x in cids for o in C[x]["occ"]]
        lab = LAB[prim].split(",")
        leaf, l2 = lab[0], lab[1:]
        br = leaf[0]
        yr = c["year"]
        ry = r.get("oa_year") or r.get("cr_year")
        if ry and (not yr or abs(ry - yr) <= 8):
            yr = ry if (r.get("cr_type") in ("journal-article", "book-chapter", "proceedings-article") or not yr) else yr
        title = r.get("cr_title") if r.get("cr_title") and r.get("cr_sim", 0) >= 0.9 else c["title"]
        title = re.sub(r"\s+", " ", title or c["title"]).strip()
        au, af = short_authors(r.get("authors") or r.get("cr_authors"), (c["surname"], c["authors"]))
        courses = sorted({o["course_id"] for o in occ})
        a = next((ANN[x] for x in cids if x in ANN), None)
        ab = r.get("abstract") or next((S2[x] for x in cids if S2.get(x)), "")
        if ab and (len(ab) < 80 or ab.lower().startswith(("no abstract", "abstract not"))):
            ab = ""
        p = dict(cid=prim, t=title, au=au, af=af, y=yr, v=r.get("venue") or r.get("cr_venue") or "", doi=r.get("doi"),
                 oa=r.get("oa_id"), br=br, lf=leaf, l2=l2, f=BR_FAM[br], cs=courses,
                 nc=len([x for x in courses if x not in EXCLUDE_FROM_NC]), cy=len({(o["course_id"], o["src_year"]) for o in occ}),
                 vox=int("VOXDEV" in courses), ab=ab[:2400], ci=r.get("cited_by"), u=r.get("pdf_url") or r.get("oa_url") or "",
                 refs=r.get("refs", []),
                 vc=venue_cat(r.get("venue") or r.get("cr_venue"), c.get("venue"), re.sub(r"^.*?\b(19|20)\d\d\b", "", c.get("raw") or "")))
        if a:
            p.update(ct=a["ct"], de=a["de"], fd=a["fd"], me=a["me"], vx=a["vx"], rs=a["rs"])
        else:
            p.update(ct=detect_countries(title + " " + ab) if br != "M" else [], de="", fd="", me=[], vx=[], rs="title")
        p["fr"] = int(bool(p["y"] and p["y"] >= 2015))
        papers.append(p)

    # --- works expanded from reference lists (10_expand.py): x = number of syllabus papers citing it
    X = json.load(open(DATA / "expanded.json", encoding="utf-8")) if (DATA / "expanded.json").exists() else {"works": [], "alias": {}}
    for w in X["works"]:
        br, a = w["lf"][0], ANN.get(w["wid"])
        au, af = short_authors(w["authors"], ("", ""))
        ab = w["ab"] if len(w["ab"] or "") >= 80 else ""
        p = dict(cid=w["wid"], t=re.sub(r"\s+", " ", w["t"] or "").strip(), au=au, af=af, y=w["y"], v=w["v"], doi=w["doi"], oa=w["wid"],
                 br=br, lf=w["lf"], l2=[], f=BR_FAM[br], cs=[], nc=0, cy=0, vox=0, ab=ab[:2400], ci=w["ci"], u=w["u"], refs=w["refs"], x=w["ncite"], vc=venue_cat(w["v"], "Cambridge" if w.get("typ") in ("book", "book-chapter") or w.get("oa_authors") is False else ""))
        if a:
            p.update(ct=a["ct"], de=a["de"], fd=a["fd"], me=a["me"], vx=a["vx"], rs=a["rs"])
        else:
            p.update(ct=[], de="", fd="", me=[], vx=[], rs="abstract-uncoded" if ab else "title")
        p["fr"] = int(bool(p["y"] and p["y"] >= 2015))
        papers.append(p)
    papers.sort(key=lambda p: (bool(p.get("x")), -p["nc"], -(p.get("x") or 0), p["y"] or 0))
    for i, p in enumerate(papers):
        p["id"] = i
    cid2id = {p["cid"]: p["id"] for p in papers}

    # --- citation edges among atlas works
    oa2id = {p["oa"]: p["id"] for p in papers if p["oa"]}
    for w, cid in X["alias"].items():                 # same work under a second OpenAlex id
        if cid in cid2id:
            oa2id.setdefault(w, cid2id[cid])
    edges, out, inn = [], defaultdict(list), defaultdict(list)
    for p in papers:
        for ref in p["refs"]:
            j = oa2id.get(ref)
            if j is not None and j != p["id"]:
                edges.append([p["id"], j]); out[p["id"]].append(j); inn[j].append(p["id"])
    print("citation edges:", len(edges))

    # --- branches, leaves, courses
    branches = [dict(id=b[0], name=b[1], short=SHORT[b[0]], desc=b[2], fam=BR_FAM[b[0]], narrative=NARRATIVE.get(b[0], "")) for b in TREE]
    leaves = []
    for b in TREE:
        for lid, name, _ in b[3]:
            ps = [p for p in papers if p["lf"] == lid and not p.get("x")]
            leaves.append(dict(id=lid, name=name, br=b[0], n=len(ps), nf=sum(p["fr"] for p in ps), settled=LEAF_NOTES[lid][0], open=LEAF_NOTES[lid][1],
                               nx=sum(1 for p in papers if p["lf"] == lid and p.get("x"))))
    reg = {}
    for pat, d in REGISTRY:
        if d.get("kind") != "skip":
            reg.setdefault(d["course_id"], d)
    years = defaultdict(set)
    for c in C.values():
        for o in c["occ"]:
            if o["src_year"]:
                years[o["course_id"]].add(o["src_year"])
    courses = []
    for cid, d in reg.items():
        ps = [p for p in papers if cid in p["cs"] and p["f"] < 8]
        lab = re.sub(r"\s+(19|20)\d\d(\s*$)", "", d["label"])
        lab = re.sub(r"\s+(19|20)\d\d$", "", lab)
        courses.append(dict(id=cid, label=lab, inst=d["inst"], instr=d["instr"], level=d["level"], kind=d["kind"],
                            years=sorted(years[cid]), n=len(ps), br=dict(Counter(p["br"] for p in ps))))

    mechs = []
    for m in MECHANISMS:
        mm = dict(m)
        mm["group"] = MECH_GROUPS[m["id"]]
        mm["modelYears"] = MECH_YEARS[m["id"]]
        ids = []
        for ref in MODEL_REFS.get(m["id"], []):
            j = find_paper(papers, *ref, strict=False)
            if j is None:
                print("  model not in atlas:", m["id"], ref, file=sys.stderr)
            elif j not in ids:
                ids.append(j)
        mm["modelIds"] = ids
        mechs.append(mm)

    # --- agenda references
    ag = json.loads(json.dumps(AGENDA))
    for f in ag["failures"]:
        f["papers"] = [find_paper(papers, *ref) for ref in f["papers"]]

    # --- download list: papers whose introduction I could not read, in four tiers (stop wherever you like)
    def core(p):
        return p["f"] < 8 and (p["nc"] >= 2 or p["vox"] or "BREAD26" in p["cs"] or (p["fr"] and p["nc"] >= 1))
    have_intro = {f.stem for f in (DATA / "intros").glob("*.txt")}
    blocked = {m.group(1) for f in DATA.glob("intros_log*.txt") for m in re.finditer(r"fail (\w+) ", f.read_text(encoding="utf-8"))}
    TIERS = {1: "title only, core syllabus paper", 2: "title only, other syllabus paper", 3: "title only, added from reference lists",
             4: "abstract only, taught in 3+ courses: the introduction would sharpen design and mechanism coding"}

    def tier(p):
        if p["f"] >= 8 or p["cid"] in have_intro or p.get("rs") in ("intro", "review"):
            return 0
        if not p.get("fd"):
            if p.get("rs") == "abstract-uncoded":   # abstract in hand: mine to code, no download needed
                return 0
            return 3 if p.get("x") else 1 if core(p) else 2
        return 4 if p.get("rs") == "abstract" and not p.get("x") and p["nc"] >= 3 else 0
    todo = sorted((p for p in papers if tier(p)), key=lambda p: (tier(p), -p["nc"], -(p.get("x") or 0), -(p["y"] or 0)))
    download = [p["id"] for p in todo]
    dl_tier = {p["id"]: tier(p) for p in todo}
    dl_key = {p["id"]: p["cid"] for p in todo}
    import csv, urllib.parse
    with open(BASE / "download_list.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "tier", "why", "save_pdf_as", "authors", "year", "title", "venue", "open_copy_blocked_for_me", "doi_link", "scholar_search", "n_courses", "sub_literature"])
        for k, p in enumerate(todo, 1):
            q = urllib.parse.quote_plus(f'{p["t"]} {p["au"].split()[0]}')
            clean = p["af"] if p["af"] and len(p["af"]) <= 90 and not re.search(r"[\d/()*:]", p["af"]) else p["au"]
            w.writerow([k, tier(p), TIERS[tier(p)], p["cid"] + ".pdf", clean, p["y"], p["t"], p["v"], p.get("u") or ("tried, blocked" if p["cid"] in blocked else ""),
                        "https://doi.org/" + p["doi"] if p.get("doi") else "", "https://scholar.google.com/scholar?q=" + q, p["nc"], LEAF[p["lf"]]["name"] if p["lf"] in LEAF else p["lf"]])
    print("download list", len(download), "by tier", Counter(dl_tier.values()))

    # --- authors, coauthorship and affiliations (11_authors.py)
    AU = json.load(open(DATA / "authors.json", encoding="utf-8")) if (DATA / "authors.json").exists() else None
    authors, insts, coauth = [], [], []
    if AU:
        iidx = {}

        def inst_index(iid):
            if not iid or iid not in AU["insts"]:
                return -1
            if iid not in iidx:
                inst = AU["insts"][iid]
                iidx[iid] = len(insts)
                insts.append(dict(n=inst["n"], cc=inst["cc"], co=inst["country"], ci=inst["city"], la=inst["lat"], lo=inst["lng"], r=inst["reg"]))
            return iidx[iid]

        # OpenAlex sometimes splits one person into two ids: merge same first+last name at the same current institution
        def name_key(a):
            t = re.findall(r"[a-z]+", fold(a["n"]).lower())
            return (t[0], t[-1], a["inst"]) if len(t) >= 2 else (a["n"], "", a["inst"])
        canon = {}
        for aid, a in AU["authors"].items():
            canon.setdefault(name_key(a), aid)
        alias = {aid: canon[name_key(a)] for aid, a in AU["authors"].items()}

        aidx, wt, yrs = {}, Counter(), defaultdict(list)
        for key, aids in AU["papers"].items():
            pid = cid2id.get(key)
            if pid is None or papers[pid]["f"] >= 8:
                continue
            pins = AU.get("pinst", {}).get(key) or [None] * len(aids)
            row, rins = [], []
            for aid, pin in zip(aids, pins):
                aid = alias.get(aid, aid)
                a = AU["authors"].get(aid)
                if not a or aid in [r[0] for r in rins]:
                    continue
                if aid not in aidx:
                    aidx[aid] = len(authors)
                    authors.append(dict(n=a["n"], i=inst_index(a["inst"]), h=a["h"], p=[]))
                authors[aidx[aid]]["p"].append(pid)
                row.append(aidx[aid])
                rins.append((aid, inst_index(pin)))
            papers[pid]["A"] = row
            papers[pid]["AI"] = [i for _, i in rins]          # institution at the time of this paper
            if len(row) <= 12:                                 # skip hyper-authored papers for the coauthor graph
                for i in range(len(row)):
                    for j in range(i + 1, len(row)):
                        e = tuple(sorted((row[i], row[j])))
                        wt[e] += 1
                        yrs[e].append(papers[pid]["y"] or 0)
        coauth = [[a, b, w, sorted(yrs[(a, b)])] for (a, b), w in wt.items()]
        print("authors", len(authors), "institutions", len(insts), "coauthor links", len(coauth))

    # --- country name mapping for the world map
    world = json.load(open(SITE / "vendor" / "countries-110m.json", encoding="utf-8"))
    cname = {}
    for g in world["objects"]["countries"]["geometries"]:
        nm = g["properties"]["name"]
        cname[nm] = ATLAS_NAME.get(nm, nm)

    meta = dict(META)
    meta.update(nSyllabi=len({o["file"] for c in C.values() for o in c["occ"]}), nEdges=len(edges),
                yearMin=min(p["y"] for p in papers if p["y"] and p["y"] > 1800), yearMax=max(p["y"] for p in papers if p["y"]))
    meta["foot"] = (f"Built {__import__('datetime').date.today().isoformat()} from {meta['nSyllabi']} syllabi, reading lists and lecture decks in "
                    "<span class='mono'>3.research_statement/input</span>. Metadata from Crossref and OpenAlex; citation links from OpenAlex reference lists. "
                    "Classification into the tree is mine, reviewed title by title; findings and mechanism verdicts are my reading of the VoxDevLit review, "
                    "abstracts and introductions, flagged per paper. Treat verdicts as a reader's map, not a meta-analysis. "
                    f"{sum(1 for p in papers if p.get('x') and p['f'] < 8)} political-economy works no syllabus lists were added by following reference lists one step out "
                    "(each cited by at least ten syllabus papers; hollow nodes, marked “ref”). Authors' current institutions come from OpenAlex, "
                    "scored by the institutions on their own recent papers and affiliation history; disambiguation errors remain possible.")

    json.dump({p["id"]: p["cid"] for p in papers}, open(DATA / "cid_index.json", "w"))
    for p in papers:
        for k in ("refs", "cid", "oa"):
            if k != "oa":
                p.pop(k, None)
        if not p["l2"]:
            p.pop("l2")
        for k in ("ct", "me", "vx"):
            if not p.get(k):
                p.pop(k, None)
        for k in ("fd", "de", "u", "v", "ab", "doi"):
            if not p.get(k):
                p.pop(k, None)
        p.pop("oa", None)

    D = dict(papers=papers, edges=edges, out=out, inn=inn, branches=branches, leaves=leaves, courses=courses, mechs=mechs,
             fams=[dict(name=f["name"]) for f in FAMS], voxFindings=VOX_FINDINGS, designs=DESIGNS, agenda=ag, download=download, dlTier=dl_tier, dlKey=dl_key, dlTiers=TIERS, venueCats=[c[0] for c in VENUE_CATS],
             countryName=cname, meta=meta, authors=authors, insts=insts, coauth=coauth,
             regions=["United States", "Canada", "United Kingdom", "Europe", "Latin America", "Asia-Pacific", "Middle East & N. Africa", "Sub-Saharan Africa"])
    data_js = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("�", "")  # ponytail: drop garbled chars from source abstracts
    tpl = (SITE / "atlas_template.html").read_text(encoding="utf-8")
    page = lambda js: tpl.replace("/*__DATA__*/null", js.replace("</", "<\\/")).replace("/*__WORLD__*/null", json.dumps(world, separators=(",", ":")))
    standalone = lambda h: ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + h + "</body></html>")
    html = page(data_js)
    (SITE / "atlas_artifact.html").write_text(html, encoding="utf-8")  # fragment: the Artifact host adds doctype/head
    (SITE / "PolEcon_Frontier_Atlas.html").write_text(standalone(html), encoding="utf-8")
    if "--public" in sys.argv:  # GitHub Pages copy: no publisher abstracts (their copyright); my coded findings stay
        pub = SITE / "public"
        pub.mkdir(exist_ok=True)
        priv = {"USER", "USERGPT"}  # my research brief and agenda draft stay out of the public copy, as does the agenda tab
        pubp = [{k: ([c for c in v if c not in priv] if k == "cs" else v) for k, v in p.items() if k != "ab"} for p in papers]
        js = json.dumps(dict(D, papers=pubp, agenda=None, download=[], dlTier={}, dlKey={}, courses=[c for c in courses if c["id"] not in priv]), ensure_ascii=False, separators=(",", ":")).replace("�", "")
        (pub / "index.html").write_text(standalone(page(js)), encoding="utf-8")
        (pub / ".nojekyll").write_text("")
    json.dump(D, open(DATA / "atlas_data.json", "w", encoding="utf-8"), ensure_ascii=False)
    pe = [p for p in papers if p["f"] < 8]
    print(f"papers {len(papers)} (PE {len(pe)}), annotated {sum(1 for p in pe if p.get('fd'))}, with abstract {sum(1 for p in pe if p.get('ab'))}, "
          f"download list {len(download)}, html {len(html)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
