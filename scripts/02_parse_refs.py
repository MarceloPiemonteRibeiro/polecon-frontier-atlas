"""Parse every source text into (a) full reference entries and (b) in-text author-year mentions.

Output: data/raw_entries.jsonl, data/raw_mentions.jsonl
"""
import re, json, unicodedata
from pathlib import Path
from sources import lookup

BASE = Path(__file__).resolve().parents[1]
TXT = BASE / "text"
OUT = BASE / "data"

LIG = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "“": '"', "”": '"', "„": '"', "‟": '"',
       "‘": "'", "’": "'", "´": "'", "`": "'", "–": "-", "—": "-", "‐": "-", " ": " ", " ": " ",
       "˜": "~", "": "•", "": "•", "": "•", "▶": "•", "►": "•"}
LIG = {k: v for k, v in LIG.items() if k}
LIG_RE = re.compile("|".join(map(re.escape, LIG)))

YEAR_RE = re.compile(r"(?<![\d/.\-])((?:18[5-9]|19\d|20[0-2])\d)[a-e]?(?![\d])")
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣∙·o\-\*>]|\(\*\)|\*+|\d{1,3}[\.\)](?!\d)|\[\d{1,3}\]|\(\d{1,3}\)|[a-h]\))\s+")
NAME = r"[A-ZÀ-Þ][A-Za-zÀ-ſ'\-]+"
PARTICLE = r"(?:(?:van|von|der|de|del|della|da|dos|das|di|du|la|le|i|y|den|ten|St\.)\s)"
# "Surname, First" / "Surname, F." / "De La O, Ana" / "Padró i Miquel, Gerard"
AUTH_COMMA = re.compile(rf"^\*?\s*(?:{PARTICLE}*{NAME}(?:\s{PARTICLE}*{NAME}){{0,2}}),\s*(?:[A-Z][a-zÀ-ſ]+|[A-Z]\.?(?:\s?[A-Z]\.?)*)(?=[\s,.\)])")
# "First Last," / "First M. Last and" / "Last (2001)" / "Last and Last (2001)"
AUTH_PLAIN = re.compile(rf"^\*?\s*(?:{NAME}\s(?:[A-Z]\.\s)?{PARTICLE}*{NAME}\s?(?:,|\band\b|&|\(|\[|\d{{4}})|{NAME}(?:\s(?:and|&)\s{NAME})?\s?[\(\[]?(?:19|20)\d\d)")
HEADING_RE = re.compile(r"^\s*(?:(?:week|lecture|class|session|topic|part|module|aula|semana|tema|unit|section)\b|\d{1,2}(?:\.\d{1,2})*\.?\s+[A-Z]|[IVX]{1,5}\.\s+[A-Z]|[A-Z][A-Za-z ,&:\-/']{3,80}$)", re.I)
INTEXT_RE = re.compile(
    rf"({NAME}(?:\s{PARTICLE}?{NAME})?)"                          # surname 1 (allow 2-token like 'Dal Bo')
    rf"(?:\s*(?:,\s*{NAME}\s*,?)*\s*(?:and|&)\s+({NAME}(?:\s{NAME})?)|\s+et\.?\s+al\.?)?"   # and / et al
    r",?\s*[\(\[]?((?:19[5-9]|20[0-2])\d)[a-e]?[\)\]]?")
STOP_SURNAMES = set("""The A An In On Of For And To From With By At As Is Are Was Were This That These Those Table Figure Fig Panel
Section Chapter Vol Volume No Number Page Pages Journal Review Economic Economics Political Quarterly American European
Working Paper Papers Press University Census Survey World Bank Source Data Notes Note Elections Election January February
March April May June July August September October November December Spring Fall Winter Summer Since Until Before After
During Between Around Over Under About Fall Lecture Week Brazil India China Mexico Colombia Kenya Indonesia Pakistan Africa
America Europe US USA UK Act Law Congress Senate House Reform Program Programme Policy Model Theorem Proposition Lemma
Year Years Total Average Mean Note Notes Today Then When Where How Why What Which Who See Also Cf Eg Ie Dec Jan Feb Mar Apr
Jun Jul Aug Sep Sept Oct Nov Revolution War Crisis Great Civil Cold Constitution Federal State States National""".split())


JOURNAL_WORDS = set("""Economics Economic Economy Review Journal Quarterly Political Politics Science Sciences Studies Press
University Proceedings Volume Vol American European Development Public Law Policy Annual Research Letters Papers Paper Working
Handbook Oxford Cambridge Princeton Harvard Chicago Yale Stanford Berkeley London New Econometrica Explorations History
Historical Comparative International World Social Society Sociological Psychology Psychological Behavior Behavioral Theory
Finance Financial Management Organization Organizations Business Applied Macroeconomics Microeconomics Monetary Labor
Population Health Environmental Urban Regional Agricultural Institute Institutions Institutional National Bureau Center
Centre Department Chapter Chapters Pages Available Forthcoming Mimeo Unpublished Conditionally Accepted Revise Resubmit
Section Week Lecture Class Topic Part Readings Reading Required Optional Background Recommended Supplementary Further
Additional Also Note Notes See In The A An Of On And For To From With By At As Is MIT NBER CEPR SSRN IZA JSTOR""".split())


def clean(s):
    s = LIG_RE.sub(lambda m: LIG[m.group(0)], s)
    s = unicodedata.normalize("NFC", s)
    return s


def norm_name(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def is_noise(line):
    l = line.strip()
    return (not l or re.fullmatch(r"\d{1,3}|\d+\s*/\s*\d+|page \d+.*|<<.*>>", l, re.I) is not None
            or re.search(r"https?://\S+$", l) and len(l) < 25)


def segment(text):
    """Yield (entry_text, heading_context). Line-based with entry-start detection."""
    lines = [clean(l).rstrip() for l in text.splitlines()]
    entries, cur, heads = [], [], []
    blank_run = 0

    def flush():
        if cur:
            e = re.sub(r"\s+", " ", " ".join(cur)).strip()
            e = re.sub(r"(\w)- (\w)", r"\1\2", e)  # de-hyphenate line breaks
            entries.append((e, " > ".join(heads[-2:])))
        cur.clear()

    for raw in lines:
        if raw.startswith("<<PAGE") or raw.startswith("<<"):
            continue
        if is_noise(raw):
            blank_run += 1
            if blank_run >= 1 and cur and YEAR_RE.search(" ".join(cur)):
                flush()
            continue
        blank_run = 0
        line = raw.strip()
        has_bullet = bool(BULLET_RE.match(line))
        body = BULLET_RE.sub("", line, count=1) if has_bullet else line
        cur_txt = " ".join(cur)
        cur_has_year = bool(YEAR_RE.search(cur_txt))
        first_tok = re.match(r"\W*([A-Za-zÀ-ſ]+)", body)
        looks_author = bool((AUTH_COMMA.match(body) or AUTH_PLAIN.match(body))
                            and not (first_tok and first_tok.group(1) in JOURNAL_WORDS))
        # heading: short, no year, not an author line, current entry complete
        cur_complete = (not cur) or (cur_has_year and re.search(r'[.)"\]\d]\s*$', cur_txt) is not None)
        strong_head = re.match(r"^\s*(?:reading list|readings|week|lecture|class|session|topic|part|module|aula|semana|tema|unit|section)", line, re.I)
        if (not has_bullet and not YEAR_RE.search(line) and cur_complete and not looks_author
                and ((strong_head and len(line) < 170) or (len(line) < 80 and "," not in line and HEADING_RE.match(line)))):
            flush()
            heads.append(line)
            heads[:] = heads[-3:]
            continue
        if has_bullet:
            flush(); cur.append(body); continue
        if looks_author and (not cur or (cur_has_year and (cur_txt.rstrip().endswith((".", ")", '"', "]")) or len(cur_txt) > 60))):
            flush(); cur.append(body); continue
        # a yearless fragment (instructor line, stray heading) followed by a new author line: drop the fragment
        if looks_author and cur and not cur_has_year and not re.search(r"(,|\band|&|[A-Z]\.)\s*$", cur_txt):
            flush(); cur.append(body); continue
        if cur and len(cur_txt) > 700:
            flush()
        cur.append(line)
    flush()
    return entries


TITLE_Q = re.compile(r'"\s*([^"]{6,330}?)\s*[,.]?\s*"')
TITLE_I = re.compile(r"(?<![A-Za-z])'([^']{12,250}?)[,.]?'(?![A-Za-z])")


def parse_entry(e):
    """Return dict(authors, year, title, venue, surname) or None if not a reference."""
    ys = [(m.start(), m.group(1)) for m in YEAR_RE.finditer(e)]
    if not ys:
        if not re.search(r"forthcoming|working paper|mimeo|unpublished|in press|manuscript", e, re.I):
            return None
    q = TITLE_Q.search(e) or TITLE_I.search(e)
    title = venue = None
    year = None
    if q:
        title = q.group(1)
        authors = e[:q.start()]
        pre_years = [y for p, y in ys if p < q.start()]
        post_years = [y for p, y in ys if p > q.end()]
        year = pre_years[-1] if pre_years else (post_years[0] if post_years else None)
        venue = e[q.end():].strip(" ,.;:")[:160]
    else:
        if not ys:
            return None
        p, year = ys[0]
        authors = e[:p]
        rest = e[p + 4:].lstrip("abcde").lstrip(" )].,:;-")
        # unquoted title: up to first ". " followed by capital (journal) or end
        m = re.match(r"(.{6,250}?)(?:\.\s+(?=[A-Z(])|,\s+(?=(?:in|In)\s)|$|\.$)", rest)
        title = (m.group(1) if m else rest[:200]).strip(" ,.;:")
        venue = rest[len(title):].strip(" ,.;:")[:160]
    authors = re.sub(r"[\(\[]\s*$", "", authors).strip(" ,.;:-([*")
    authors = re.sub(r"^\(\*\)\s*|^\*+\s*", "", authors)
    if not authors or len(authors) > 300 or not re.search(r"[A-Z]", authors):
        return None
    if re.search(r"\b(?:pp?\.|vol\.|chapter|see also|homework|problem set|due|exam|grade|office hours)\b", authors, re.I) and len(authors) > 120:
        return None
    sur = first_surname(authors)
    if not sur or sur in STOP_SURNAMES:
        return None
    if title:
        title = re.sub(r"\s+", " ", title).strip(" .,")
        if len(title) < 6:
            return None
    return dict(authors=authors, year=int(year) if year else None, title=title, venue=venue, surname=sur)


def first_surname(authors):
    a = authors.strip()
    a = re.sub(r"^(?:\d+[\.\)]\s*|[•\-\*]\s*)", "", a)
    m = re.match(rf"({PARTICLE}*{NAME}(?:\s{PARTICLE}*{NAME}){{0,2}}),", a)
    if m:
        cand = m.group(1)
        # "First Last, and Other" -> take last token as surname
        if re.match(rf"^[A-Z][a-z]+\s{NAME}$", cand) and not re.match(r"^(?:De|Del|Da|Van|Von|Di|La|Le|Dal)\s", cand):
            # ambiguous: 'Daron Acemoglu,' vs 'Dal Bo,'. If followed by initials/first name -> it's Surname, First
            after = a[m.end():].strip()
            if re.match(r"^[A-Z][a-z]+\b|^[A-Z]\.", after) and not re.match(r"^(?:and|&)\b", after):
                return cand
            return cand.split()[-1]
        return cand
    first = re.split(r",|\band\b|&|;", a)[0].strip()
    toks = [t for t in first.split() if re.match(r"[A-ZÀ-Þ]", t) and not re.fullmatch(r"[A-Z]\.?", t)]
    if not toks:
        return None
    # handle particles: 'Gerard Padro i Miquel' -> keep 'Padro i Miquel'
    m2 = re.search(rf"\b((?:[A-Z][\wÀ-ſ'\-]+\s)?(?:i|de|da|del|van|von|dal)\s{NAME})\s*$", first)
    if m2 and len(first.split()) >= 3:
        return m2.group(1)
    return toks[-1]


def mentions(text):
    t = clean(text)
    for m in INTEXT_RE.finditer(t):
        s1, s2, y = m.group(1), m.group(2), m.group(3)
        if s1.split()[-1] in STOP_SURNAMES or s1 in STOP_SURNAMES:
            continue
        if len(s1) < 3:
            continue
        etal = "et al" in m.group(0)
        ctx = t[max(0, m.start() - 120): m.end() + 160].replace("\n", " ")
        yield dict(s1=s1, s2=s2, etal=etal, year=int(y), ctx=re.sub(r"\s+", " ", ctx))


def main():
    OUT.mkdir(exist_ok=True)
    n_e = n_m = 0
    with open(OUT / "raw_entries.jsonl", "w", encoding="utf-8") as fe, open(OUT / "raw_mentions.jsonl", "w", encoding="utf-8") as fm:
        for f in sorted(TXT.glob("*.txt")):
            src = lookup(f.name)
            if src["kind"] == "skip":
                continue
            text = f.read_text(encoding="utf-8")
            base = dict(file=f.name, course_id=src["course_id"], src_label=src["label"], src_year=src["year"], src_kind=src["kind"])
            k = 0
            for e, head in segment(text):
                p = parse_entry(e)
                if p:
                    fe.write(json.dumps({**base, **p, "raw": e[:700], "heading": head}, ensure_ascii=False) + "\n")
                    k += 1
            n_e += k
            km = 0
            for mm in mentions(text):
                fm.write(json.dumps({**base, **mm}, ensure_ascii=False) + "\n")
                km += 1
            n_m += km
            print(f"{k:5d} entries {km:5d} mentions  {f.name[:90]}")
    print("TOTAL entries", n_e, "mentions", n_m)


if __name__ == "__main__":
    main()
