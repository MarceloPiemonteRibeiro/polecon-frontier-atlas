"""Extract text from every syllabus/slide file in input/ into text/<slug>.txt."""
import fitz, docx, zipfile, re, json, html, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "input"
OUT = Path(__file__).resolve().parents[1] / "text"
OUT.mkdir(exist_ok=True)

def slug(p):
    s = str(p.relative_to(ROOT)).replace("\\", "/")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:150]

def pdf_text(p):
    d = fitz.open(p)
    return "\n".join(f"\n<<PAGE {i+1}>>\n" + pg.get_text() for i, pg in enumerate(d)), d.page_count

def docx_text(p):
    d = docx.Document(p)
    parts = [para.text for para in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            parts.append(" | ".join(c.text for c in r.cells))
    return "\n".join(parts), None

def html_strip(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</tr>|</h\d>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", html.unescape(s))

manifest = []
for p in sorted(ROOT.rglob("*")):
    if p.is_dir():
        continue
    ext = p.suffix.lower()
    try:
        if ext == ".pdf":
            txt, n = pdf_text(p)
        elif ext == ".docx":
            txt, n = docx_text(p)
        elif ext in (".txt", ".md"):
            txt, n = p.read_text(encoding="utf-8", errors="ignore"), None
        elif ext == ".zip":
            z = zipfile.ZipFile(p)
            parts = []
            for name in z.namelist():
                if re.search(r"pages/(syllabus|readings|calendar|lecture-notes)/index\.html$|resources/readings/index\.html$", name):
                    parts.append(f"\n<<{name}>>\n" + html_strip(z.read(name).decode("utf-8", "ignore")))
            txt, n = "\n".join(parts), None
        else:
            continue
    except Exception as e:
        print("FAIL", p, e, file=sys.stderr)
        continue
    out = OUT / (slug(p) + ".txt")
    out.write_text(txt, encoding="utf-8")
    manifest.append({"file": str(p.relative_to(ROOT)), "txt": out.name, "pages": n, "chars": len(txt)})

(OUT.parent / "data").mkdir(exist_ok=True)
(OUT.parent / "data" / "source_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
for m in manifest:
    print(f"{m['chars']:>8}  {m['pages'] or '':>4}  {m['file']}")
