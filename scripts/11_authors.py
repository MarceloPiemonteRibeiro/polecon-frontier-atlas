"""Authors, coauthorship and current affiliations for every atlas work resolved in OpenAlex.

Authorships come from the cached work records; each author's current affiliation is OpenAlex's
last_known_institutions (fallback: the latest institution on an atlas paper); institution coordinates come from
the institution record. Output: data/authors.json keyed by paper key (cid for syllabus works, W-id for expanded).
"""
import importlib.util, json, re, time, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
spec = importlib.util.spec_from_file_location("r4", Path(__file__).with_name("04_resolve.py"))
R4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(R4)
OA = "https://api.openalex.org/"
NETWORK_TYPES = {"nonprofit", "archive", "other"}               # NBER, CEPR, CIFAR, J-PAL… are memberships, not employers
NON_LATIN = re.compile(r"[Ͱ-ϿЀ-ӿ֐-ۿ぀-鿿가-힯]")

EUROPE = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE CH NO IS LI MC SM AD RS BA ME MK AL UA BY MD RU GE AM AZ XK".split())
LATAM = set("MX GT BZ SV HN NI CR PA CU DO HT JM TT BB BS CO VE EC PE BO CL AR UY PY BR GY SR PR".split())
MENA = set("MA DZ TN LY EG SD IL PS JO LB SY IQ IR SA AE QA KW BH OM YE TR".split())
ASIAPAC = set("CN HK MO TW JP KR KP MN IN PK BD LK NP BT MV AF KZ KG TJ TM UZ TH VN LA KH MM MY SG ID PH BN TL AU NZ PG FJ".split())


def region(cc):
    if not cc:
        return "Unknown"
    if cc == "US": return "United States"
    if cc == "CA": return "Canada"
    if cc == "GB": return "United Kingdom"
    if cc in EUROPE: return "Europe"
    if cc in LATAM: return "Latin America"
    if cc in MENA: return "Middle East & N. Africa"
    if cc in ASIAPAC: return "Asia-Pacific"
    return "Sub-Saharan Africa"


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()


def pick_name(display, raws):
    """Name as printed on the author's papers ("Claudio Ferraz") when it is a full-form subset of OpenAlex's display name."""
    if NON_LATIN.search(display or "") and raws:
        display = raws.most_common(1)[0][0]
    toks = set(re.findall(r"[a-z]+", fold(display)))
    for raw, _ in raws.most_common():
        parts = raw.replace(",", " ").split()
        if len(parts) >= 2 and len(parts[0].strip(".")) > 2 and "." not in parts[0] and not raw.isupper()                 and set(re.findall(r"[a-z]+", fold(raw))) <= toks and len(set(re.findall(r"[a-z]+", fold(raw)))) < len(toks):
            display = raw
            break
    return display.title() if display and display.isupper() else display


def short(u):
    return (u or "").rsplit("/", 1)[-1]


def main():
    D = json.load(open(DATA / "atlas_data.json", encoding="utf-8"))
    cid_of = json.load(open(DATA / "cid_index.json", encoding="utf-8"))
    X = json.load(open(DATA / "expanded.json", encoding="utf-8")) if (DATA / "expanded.json").exists() else {"works": []}
    jobs = [(cid_of[str(p["id"])], dict(doi=p["doi"])) for p in D["papers"] if not p.get("x") and p.get("doi") and p["f"] < 8]
    jobs += [(w["wid"], dict(wid=w["wid"])) for w in X["works"] if w.get("oa_authors", True) and w["lf"][0] != "M"]   # skip book reviews' reviewers
    paper_auth, paper_inst, auth_name, raw_names = {}, {}, {}, defaultdict(Counter)
    evid, itype = defaultdict(Counter), {}          # author -> institution -> recency-weighted count on atlas papers
    for key, kw in jobs:
        d = R4.oa_raw(**kw)
        if not d:
            continue
        yr = d.get("publication_year") or 0
        w = 1.0 if yr >= 2021 else 0.4 if yr >= 2015 else 0.12 if yr >= 2005 else 0.04
        ids, pins = [], []
        for a in (d.get("authorships") or [])[:25]:
            aid = short((a.get("author") or {}).get("id"))
            if not aid:
                continue
            ids.append(aid)
            auth_name[aid] = (a.get("author") or {}).get("display_name")
            if a.get("raw_author_name"):
                raw_names[aid][a["raw_author_name"]] += 1
            here = [i for i in a.get("institutions") or [] if i.get("id")]
            for i in here:
                evid[aid][short(i["id"])] += w
                itype[short(i["id"])] = i.get("type")
            real_here = [i for i in here if i.get("type") not in NETWORK_TYPES] or here
            real_here.sort(key=lambda i: i.get("type") != "education")
            pins.append(short(real_here[0]["id"]) if real_here else None)   # where the author was when writing this paper
        paper_auth[key] = ids
        paper_inst[key] = pins
    print("papers with authors", len(paper_auth), "authors", len(auth_name), flush=True)

    authors = {}
    for k, aid in enumerate(auth_name):
        r = R4.get(OA + "authors/" + aid) or {}
        if k % 500 == 0:
            print("authors", k, flush=True)
        score = Counter({i: 3 * v for i, v in evid[aid].items()})        # what the author's own atlas papers say
        for a in r.get("affiliations") or []:                            # recent affiliation years
            i = short((a.get("institution") or {}).get("id"))
            if i:
                itype.setdefault(i, (a.get("institution") or {}).get("type"))
                score[i] += 1.5 * sum(1 for y in a.get("years") or [] if y >= 2022)
        for i in r.get("last_known_institutions") or []:
            if i.get("id"):
                itype.setdefault(short(i["id"]), i.get("type"))
                score[short(i["id"])] += 2
        real = [i for i in score if itype.get(i) not in NETWORK_TYPES]
        pool = real or list(score)
        inst = max(pool, key=lambda i: (score[i], itype.get(i) == "education")) if pool else None
        name = pick_name(r.get("display_name") or auth_name[aid], raw_names[aid])
        authors[aid] = dict(n=name, inst=inst, h=(r.get("summary_stats") or {}).get("h_index"),
                            w=r.get("works_count"), c=r.get("cited_by_count"), orcid=(r.get("orcid") or "").rsplit("/", 1)[-1] or None)
    insts = {}
    for k, iid in enumerate({a["inst"] for a in authors.values() if a["inst"]} | {i for v in paper_inst.values() for i in v if i}):
        r = R4.get(OA + "institutions/" + iid) or {}
        if k % 250 == 0:
            print("institutions", k, flush=True)
        g = r.get("geo") or {}
        cc = r.get("country_code") or g.get("country_code")
        insts[iid] = dict(n=r.get("display_name") or iid, cc=cc, country=g.get("country"), city=g.get("city"), lat=g.get("latitude"), lng=g.get("longitude"),
                          typ=r.get("type"), reg=region(cc))
        time.sleep(0.05)
    json.dump(dict(papers=paper_auth, pinst=paper_inst, authors=authors, insts=insts), open(DATA / "authors.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("done: authors", len(authors), "institutions", len(insts))


if __name__ == "__main__":
    main()
