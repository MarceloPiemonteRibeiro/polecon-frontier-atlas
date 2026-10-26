"""Section-slice the downloaded PDFs so a reader can see findings, not just abstracts.

Three sources of PDFs: pdfs/<cid>.pdf (named by the download scripts), data/pdfs/<cid>/*.pdf
(fetched by 13_intros_oa.py) and manual_download/ + pdfs_rejected/ (hand-saved, publisher
filenames -> matched to a cid by the title on the first pages, as 12_ingest_pdfs.py does).

Output: data/fulltext/<cid>.json with the slices that carry findings (abstract, introduction,
results headings, conclusion, table captions, data section) plus sentence harvests (quantified
claims, stated gaps, claims about the prior literature). Full text is never kept: 2,500 papers
at ~97k chars is 250 MB of mostly references and proofs.

PDFs are untrusted input, so run with `python -P` (NOT -I, or PyMuPDF won't import):

    python -P scripts/15_fulltext.py --limit 20     # sample
    python -P scripts/15_fulltext.py                # full run
"""
import argparse, csv, json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
OUT = DATA / "fulltext"

# How much of each slice to keep. Tuned so a standard-tier card fits ~2k tokens and a deep one ~7k.
LIM = dict(abstract=2500, intro=9000, concl=6000, data=2000, results=6000, captions=3500)

HEAD = r"(?:\n|^)[ \t]*(?:\d+\.?\d*|[IVXL]+\.?|[A-H]\.?)?[ \t]*"


COMMON = set("the of and to in a is that for are with as by on this be an it from or we which not have "
             "has their they but all can more been would was were there when such other than into its".split())


def english(s):
    """Share of words that are common English. Near zero means the extraction is garbled."""
    w = re.findall(r"[a-z]{2,}", s.lower())
    return sum(1 for x in w if x in COMMON) / len(w) if len(w) > 40 else 1.0


def unshift(s):
    """Some PDFs carry a font CMap offset by a constant, so every character extracts N codepoints up
    ('Frpsdudwlyh Srolwlfv' for 'Comparative Politics'). Undo it when a small shift reads as English."""
    if english(s[:6000]) >= 0.05:
        return s
    best, score = s, english(s[:6000])
    for k in range(1, 6):
        cand = "".join(chr(ord(c) - k) if 32 + k <= ord(c) < 127 + k else c for c in s[:6000])
        if english(cand) > score:
            best, score = k, english(cand)
    if isinstance(best, int):
        return "".join(chr(ord(c) - best) if 32 + best <= ord(c) < 127 + best else c for c in s)
    return s


def norm(s):
    s = s.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    s = re.sub(r"-\n(?=[a-z])", "", s)          # de-hyphenate across line breaks
    s = re.sub(r"\n(?=[a-z,;)])", " ", s)       # re-join wrapped sentences
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s)


def cut_refs(txt):
    """Drop the reference list and appendix: they are half the file and carry no findings."""
    best = None
    for m in re.finditer(HEAD + r"(References|Bibliography|Works Cited)[ \t]*\n", txt, re.I):
        if m.start() > len(txt) * 0.4:
            best = m.start()
            break
    return txt[:best] if best else txt


def after(txt, pattern, n):
    m = None
    for m in re.finditer(HEAD + pattern + r"[ \t]*\n", txt, re.I):
        pass                                     # last match: skip the table of contents
    if not m:
        return ""
    return txt[m.end():m.end() + n].strip()


def first_after(txt, pattern, n):
    m = re.search(HEAD + pattern + r"[ \t]*\n", txt, re.I)
    return txt[m.end():m.end() + n].strip() if m else ""


def sentences(txt):
    txt = re.sub(r"\b(e\.g|i\.e|cf|vs|et al|Fig|Tab|No|pp|approx|Dr|Prof|St)\.", r"\1<D>", txt)
    out = []
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", txt):
        s = s.replace("<D>", ".").strip()
        if 40 <= len(s) <= 700:
            out.append(re.sub(r"\s+", " ", s))
    return out


CLAIM = re.compile(r"\b(we find|we show|we estimate|we document|we provide evidence|I find|I show|I estimate|"
                   r"our (?:results|estimates|findings)|the (?:results|estimates|evidence) (?:show|indicate|suggest|imply)|"
                   r"results (?:show|indicate|suggest)|point estimate|increases? by|decreases? by|reduces? (?:by|the)|"
                   r"raises? (?:by|the)|lowers? (?:by|the)|associated with a|effect (?:of|on) )", re.I)
NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent|percentage point|pp\b|s\.?d\.?|standard deviation|log point|σ)"
                 r"|\b\d+\.\d+\b|\b\d{2,}\b")
GAP = re.compile(r"\b(future (?:research|work|studies)|further (?:research|work)|remains? an open|open question|"
                 r"we leave|left for future|little is known|not (?:yet )?been (?:studied|examined|explored|documented)|"
                 r"no (?:direct )?evidence on|we know (?:little|very little)|an? important (?:open|unanswered)|"
                 r"more (?:research|work|evidence) is needed|promising (?:avenue|direction)|beyond the scope)", re.I)
LIT = re.compile(r"\b(a (?:large|growing|substantial|vast|small|thin) literature|the literature (?:on|has|is|suggests|finds)|"
                 r"prior (?:work|studies|literature)|previous (?:work|studies|research|findings)|earlier (?:work|studies)|"
                 r"is well (?:established|documented|known)|(?:remains?|is) (?:still )?(?:contested|debated|unresolved|an? (?:matter|subject) of debate)|"
                 r"at odds with|contrary to (?:the|prior|previous|existing)|mixed (?:evidence|results|findings)|"
                 r"conflicting (?:evidence|results|findings)|we depart from|in contrast (?:to|with) (?:the|prior|previous|existing)|"
                 r"unlike (?:prior|previous|existing|most)|standard (?:models?|theory|accounts?) (?:predicts?|implies|suggests?)|"
                 r"(?:challenges?|qualifies|overturns|revises) the (?:view|claim|finding|consensus))", re.I)
MODEL = re.compile(r"\b(median voter|probabilistic voting|citizen[- ]candidate|moral hazard|adverse selection|"
                   r"political agency|Downsian|Grossman[- ]Helpman|Meltzer[- ]Richard|legislative bargaining|"
                   r"Baron[- ]Ferejohn|commitment (?:problem|device)|time[- ]inconsistency|rent[- ]seeking|"
                   r"common[- ]agency|selection (?:model|effect)|career concerns|yardstick competition)", re.I)


def tabular(s):
    """Table rows survive extraction as pseudo-sentences; they are noise in a harvest."""
    digits = sum(c.isdigit() for c in s)
    return digits > len(s) * 0.22 or len(re.findall(r"\(\s*\d+\.\d+\s*\)", s)) >= 2


def harvest(txt, rx, extra=None, cap=14):
    out, seen = [], set()
    for s in sentences(txt):
        if not rx.search(s) or (extra is not None and not extra.search(s)) or tabular(s):
            continue
        k = re.sub(r"[^a-z]", "", s.lower())[:90]
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= cap:
            break
    return out


def dense_blocks(txt, n, cap=6):
    """Fallback when a paper has no 'Results' heading (common in Econometrica/QJE house style):
    the paragraphs in the middle of the body that carry the most quantified claims."""
    paras = [p for p in re.split(r"\n\s*\n", txt[len(txt) // 6: int(len(txt) * 0.92)]) if 300 < len(p) < 2600]
    scored = sorted(paras, key=lambda p: -(len(CLAIM.findall(p)) * 2 + len(NUM.findall(p))))
    out, s = [], 0
    for p in scored[:cap * 3]:
        p = re.sub(r"\s+", " ", p).strip()
        if tabular(p) or len(CLAIM.findall(p)) == 0:
            continue
        if s + len(p) > n or len(out) >= cap:
            break
        out.append(p); s += len(p)
    return out


def results_blocks(txt, n):
    """Headings that announce results, plus the opening lines under each (where the numbers are)."""
    pat = (r"((?:Main |Empirical |Baseline |Reduced[- ]form |Primary |Core )?(?:Results|Findings|Estimates|"
           r"Main results|Empirical results|Effects? of [^\n]{0,60}))")
    blocks = []
    for m in re.finditer(HEAD + pat + r"[ \t]*\n", txt, re.I):
        head = m.group(1).strip()
        body = re.sub(r"\s+", " ", txt[m.end():m.end() + 900]).strip()
        if len(body) > 120:
            blocks.append(f"[{head}] {body}")
    s, keep = 0, []
    for b in blocks:
        if s + len(b) > n:
            break
        keep.append(b); s += len(b)
    return keep


def captions(txt, n):
    out, s = [], 0
    for m in re.finditer(r"(?:\n|^)[ \t]*((?:Table|Figure|TABLE|FIGURE|Panel)[ \t]*(?:[A-Z]?\.?\d+|[IVX]+)[.:—-]?[ \t]*[^\n]{10,200})", txt):
        c = re.sub(r"\s+", " ", m.group(1)).strip()
        if c.lower() not in (x.lower() for x in out):
            out.append(c); s += len(c)
            if s > n:
                break
    return out


def slice_pdf(path):
    import fitz
    doc = fitz.open(path)
    pages = doc.page_count
    raw = "\n".join(doc[i].get_text() for i in range(pages))
    doc.close()
    txt = norm(unshift(raw))
    if len(txt) < 2500:
        return dict(pages=pages, chars=len(txt), no_text=True)
    body = cut_refs(txt)
    head = txt[:12000]
    abstract = first_after(head, r"Abstract", LIM["abstract"]) or head[:LIM["abstract"]]
    intro = first_after(body, r"Introduction", LIM["intro"])
    if not intro:
        intro = body[:LIM["intro"]]
    concl = after(body, r"(?:Conclusions?|Concluding [Rr]emarks?|Discussion and [Cc]onclusion|Summary and [Cc]onclusions?)", LIM["concl"])
    tail = body[-14000:]
    return dict(
        pages=pages, chars=len(txt),
        abstract=abstract, intro=intro, conclusion=concl,
        data=first_after(body, r"(?:Data(?: and (?:[A-Za-z ]+))?|Data sources?|Sample(?: and data)?|Setting and data|Context and data)", LIM["data"]),
        results=results_blocks(body, LIM["results"]) or dense_blocks(body, LIM["results"]),
        captions=captions(body, LIM["captions"]),
        claims=harvest(body, CLAIM, NUM, 16) or harvest(body, CLAIM, None, 10),
        gaps=harvest(concl + "\n" + tail + "\n" + intro, GAP, None, 10),
        lit=harvest(intro + "\n" + concl, LIT, None, 12),
        models=sorted({m.group(1).lower() for m in MODEL.finditer(body)}),
    )


STOP = {"the", "and", "for", "from", "with", "its", "are", "does", "not", "who", "how", "why", "what", "when",
        "new", "case", "role", "study", "effect", "effects", "policy", "evidence", "some"}


def words(s):
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in STOP}


def flat(s):
    """Lowercase alphanumerics only: survives line breaks, hyphenation and markup in a PDF's title page."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", "", s or "").lower())


def surnames(authors):
    a = re.sub(r"\bet al\.?|\band\b|&", " ", authors or "")
    return [flat(w) for w in re.findall(r"[A-Z][A-Za-zÀ-ɏ'‐-]{2,}", a)]


def match_by_title(path, rows, idf):
    """Match a hand-saved file to a cid only on strong evidence: the title verbatim in the title block of
    page one, plus an author surname on that page. 12_ingest_pdfs.py's word-overlap rule scored 1.0 on
    titles like 'Civil War', and a looser verbatim rule matches journal names in running headers
    ('Journal of Development Economics'), so both the region and the surname check are needed.
    Everything else is left for hand review rather than risking a wrong paper's findings on a cid."""
    import fitz
    try:
        doc = fitz.open(path)
        p1 = doc[0].get_text() if doc.page_count else ""
        p12 = " ".join(doc[i].get_text() for i in range(min(2, doc.page_count)))
        doc.close()
    except Exception as e:
        return None, 0.0, f"open_failed:{type(e).__name__}"
    if len(p12) < 400:
        return None, 0.0, "no_text"
    title_block, page1 = flat(p1[:1800]), flat(p1)
    # A 40-character exact string is self-identifying; shorter ones can be a journal name, so they
    # also need an author surname on the page.
    hits = [r for r in rows if len(r["_f"]) >= 25 and r["_f"] in title_block
            and (len(r["_f"]) >= 40 or any(s and s in page1 for s in surnames(r["authors"])))]
    if hits:
        return max(hits, key=lambda r: len(r["_f"])), 1.0, ""
    best, score = None, 0.0
    headw = words(p12)
    for r in rows:
        tw = r["_w"]
        if len(tw) < 5:
            continue                             # too generic to identify a paper by overlap
        tot = sum(idf.get(w, 6.0) for w in tw)
        s = sum(idf.get(w, 6.0) for w in tw & headw) / tot
        if s > score:
            best, score = r, s
    if best and score >= 0.88 and any(s and s in page1 for s in surnames(best["authors"])):
        return best, round(score, 2), ""
    return best, round(score, 2), "weak"


def verify(src, rows, idf, by_cid):
    """Does each cid's PDF actually hold the paper that cid names?

    The download scripts matched some papers by search result rather than by DOI, so a cid can hold a
    different paper entirely — a reader agent caught C00309 holding a 1931 Catalonia bank-failure paper
    under an Arab Spring citation. A card coded from the wrong PDF is worse than no card, so every cid
    is checked against the title on its own first page before the read is trusted.
    """
    import fitz
    out = []
    for i, (cid, path) in enumerate(sorted(src.items()), 1):
        want = by_cid.get(cid)
        if not want:
            continue
        try:
            doc = fitz.open(path)
            # Working-paper series, JSTOR and press PDFs often put a blank or image cover page first,
            # so the real title page can be page 2 or 3. Checking only page one flagged papers that
            # were in fact correct, so the window is the first four pages.
            head = " ".join(doc[j].get_text() for j in range(min(4, doc.page_count)))
            doc.close()
        except Exception as e:
            out.append(dict(cid=cid, file=path.name, expected=want["title"][:80], score=0.0,
                            why=f"open_failed:{type(e).__name__}", best_other=""))
            continue
        if len(head) < 400:
            out.append(dict(cid=cid, file=path.name, expected=want["title"][:80], score=0.0,
                            why="no_text", best_other=""))
            continue
        p1, page1, headw = head, flat(head), words(head)
        tw = want["_w"]
        hit = len(want["_f"]) >= 20 and want["_f"] in flat(p1[:2500])
        share = (sum(idf.get(w, 6.0) for w in tw & headw) / sum(idf.get(w, 6.0) for w in tw)) if tw else 0.0
        sur = any(s and s in page1 for s in surnames(want["authors"]))
        # Verbatim title is conclusive. Otherwise most of the title's rare words plus an author
        # surname is enough; anything weaker gets looked at by hand.
        if hit or (share >= 0.70 and sur) or share >= 0.90:
            continue
        best, bscore, _ = match_by_title(path, rows, idf)
        got = f"{best['authors']} {best['year']} · {best['title'][:60]}" if best and best["cid"] != cid else ""
        out.append(dict(cid=cid, file=path.name, expected=want["title"][:80], score=round(share, 2),
                        why=("surname missing" if share >= 0.70 else "title words absent"), best_other=got))
        if i % 400 == 0:
            print(f"  checked {i}/{len(src)}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="", help="comma-separated cids")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify", action="store_true", help="check each cid's PDF is the paper it claims")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(open(BASE / "papers_master.csv", encoding="utf-8-sig")))
    df = {}
    for r in rows:
        r["_w"], r["_f"] = words(r["title"]), flat(r["title"])
        for w in r["_w"]:
            df[w] = df.get(w, 0) + 1
    import math
    idf = {w: math.log(len(rows) / n) for w, n in df.items()}
    known = {r["cid"] for r in rows}

    # cid -> pdf. Earlier sources win; the cid-named folders are authoritative.
    src = {}
    for p in sorted((BASE / "pdfs").glob("*.pdf")):
        if p.stem.upper() in known:
            src.setdefault(p.stem.upper(), p)
    for d in sorted((DATA / "pdfs").glob("*")):
        if d.is_dir() and d.name.upper() in known:
            pdfs = sorted(d.glob("*.pdf"))
            if pdfs:
                src.setdefault(d.name.upper(), pdfs[0])
    named = len(src)

    matched, unmatched = [], []
    for folder in ("manual_download", "pdfs_rejected"):
        for p in sorted((BASE / folder).glob("*.pdf")):
            best, score, err = match_by_title(p, rows, idf)
            if best and not err and best["cid"] not in src:
                src[best["cid"]] = p
                matched.append((best["cid"], score, folder, p.name, best["title"][:70]))
            else:
                unmatched.append((folder, p.name, round(score, 2), (best or {}).get("title", "")[:60], err))

    (DATA / "fulltext_map.json").write_text(json.dumps(
        dict(named=named, matched=[dict(cid=c, score=round(s, 2), folder=f, file=n, title=t) for c, s, f, n, t in matched],
             unmatched=[dict(folder=f, file=n, best_score=s, best_title=t, error=e) for f, n, s, t, e in unmatched]),
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"cid-named {named} + title-matched {len(matched)} = {len(src)} papers with a PDF; {len(unmatched)} files unmatched")

    if a.verify:
        bad = verify(src, rows, idf, {r["cid"]: r for r in rows})
        (DATA / "pdf_mismatch.json").write_text(json.dumps(bad, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\n{len(bad)} of {len(src)} PDFs do not clearly hold the paper their cid names "
              f"-> data/pdf_mismatch.json")
        for b in bad[:40]:
            print(f"  {b['cid']} {b['score']:<5} {b['why']:<18} want: {b['expected'][:46]:<46} "
                  + (f"got: {b['best_other'][:52]}" if b["best_other"] else ""))
        return

    todo = sorted(src)
    if a.only:
        want = {c.strip().upper() for c in a.only.split(",")}
        todo = [c for c in todo if c in want]
    if not a.force:
        todo = [c for c in todo if not (OUT / f"{c}.json").exists()]
    if a.limit:
        todo = todo[:a.limit]
    print(f"slicing {len(todo)}")

    ok = thin = fail = 0
    for i, cid in enumerate(todo, 1):
        try:
            d = slice_pdf(src[cid])
        except Exception as e:
            print("  FAIL", cid, src[cid].name, type(e).__name__, e, file=sys.stderr)
            fail += 1
            continue
        d["cid"], d["file"] = cid, src[cid].name
        if d.get("no_text"):
            thin += 1
        else:
            ok += 1
        (OUT / f"{cid}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        if i % 250 == 0:
            print(f"  {i}/{len(todo)}")
    print(f"sliced {ok}, no extractable text {thin}, failed {fail}")


if __name__ == "__main__":
    main()
