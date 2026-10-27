# PolEcon Frontier Atlas

An interactive map of the political-economy literature as top PhD programmes teach it: ~90 syllabi and lecture decks, deduplicated into ~2,100 papers, placed on one literature tree, linked by citations, and read against the canonical models they test.

**Live site:** https://marcelopiemonteribeiro.github.io/polecon-frontier-atlas/

Tabs: overview (journals, canon vs frontier), **what is known** (the evidence matrix), **what is contested**, **how it evolved**, **gaps**, build a review (pick topics, mechanisms, filters and your questions; get a structured review, Markdown, PDF, or a prompt that lets Claude/ChatGPT write it from the coded evidence), literature tree with cross-topic links, mechanism tree, models → evidence, citation network, who writes it (coauthor network, institutions, affiliation map), when & where (publication waves and study settings through time), courses, library.

Metadata from Crossref and OpenAlex; citation links from OpenAlex reference lists. Classification and the one-line findings are the author's own reading; treat verdicts as a reader's map, not a meta-analysis. Publisher abstracts are not included in this public copy.

Single self-contained `index.html` (d3 + data inline). Built by Marcelo Piemonte Ribeiro.

## The full-text read

The findings on the original site were coded from abstracts and first pages. The three evidence tabs
are built from a second pass that reads the **downloaded PDFs** instead, and codes every paper the
same way so papers become comparable: what varies, what is measured, which way the effect goes, how
large, where, with what design, which canonical model it speaks to, and what the paper's own authors
say is settled, contested and still open.

A **causal question** is one cause crossed with one outcome (information to voters against turnout,
quotas against spending). The matrix is the field's answer sheet; the empty cells are the gap map.

The four evidence tabs answer four different questions:

| tab | what it answers |
|---|---|
| **What is known** | For any cause-and-outcome pair: how many papers asked, which way they came out, in how many countries, with what designs, and at what magnitudes. |
| **What is contested** | Where papers *measuring the same thing* disagree, with a computed account of what separates the camps (design, period, setting) and a hand-written note on each. |
| **How it evolved** | How the field learned to identify things (design mix by period), which answers have moved against the older evidence, and how each canonical model stands against the evidence that tests it, including the lag from model to first test. |
| **Gaps** | A ranked board of openings across four kinds — live disagreements, structural holes, untested or contradicted models, and the field's own ~2,500 stated open questions clustered into themes. |

Two of those outputs are vetted by a reading pass rather than left to arithmetic, because arithmetic
gets them wrong in a specific way. Contested entries are checked for **treatment polarity**: a card
signs the effect of the cause *as its paper framed it*, so "mayors eligible for re-election steal
less" and "second-term mayors steal more" are the same finding with opposite signs, and counting them
as disagreement is an artifact. Structural holes are checked for pairings that make no conceptual
sense, or that a neighbouring cell already covers under a different label. Verdicts live in
`data/contested_verdicts.jsonl` and `data/hole_verdicts.jsonl`; the aggregator applies them.

    python -P scripts/15_fulltext.py              # slice every PDF into its findings-bearing sections
    python -P scripts/15_fulltext.py --verify     # check each PDF really holds the paper its cid names
    python    scripts/16_read_batches.py --skip-done   # batch what is still unread, write compact slices
    #          ... a reader agent per batch, following scripts/reader_spec.md, writes data/cards/*.jsonl
    python    scripts/17_evidence.py              # cards -> data/evidence.json (cells, contested, gaps)
    python    scripts/18_gap_input.py             # the authors' own open questions, by branch
    python    scripts/06_build.py --public        # rebuild the site

`scripts/reader_spec.md` is the coding manual: the schema, the controlled vocabularies for causes,
outcomes, designs and mechanisms, and the rules. Cards are keyed by `cid`, never by the atlas paper
id, because ids are assigned by sort order and shift on every rebuild.

### What the pipeline refuses to trust

The PDF collection is noisier than the metadata suggests, so three checks run before anything reaches
a chart:

- **Wrong paper.** Some PDFs were fetched from search results and hold an editor's annual report, a
  publisher's catalogue, an online appendix or an unrelated article. `--verify` tests each file
  against the title and authors its `cid` claims (verbatim title in the first four pages, plus an
  author surname). Validated against the readers' own judgement at 83% sensitivity and ~1.5% false
  alarms. Flagged papers are marked, kept out of the matrix, the contested list, the gap map and the
  mechanism scoreboard, and never overwrite a paper's finding — but stay visible in the paper drawer
  behind a "source not verified" notice. The re-download list lands in `data/bad_sources.txt`.
- **Garbled extraction.** A few PDFs carry a font table offset by a constant, so text extracts as
  `Frpsdudwlyh Srolwlfv` for `Comparative Politics`. The slicer detects low English content and undoes
  the shift. The rest (upside-down scans, broken CMaps) are recorded as unreadable, not guessed at.
- **Numbers that are not in the paper.** Readers are told to quote magnitudes, never compute them.
  `17_evidence.py` searches each figure in the paper's own text, allowing for a factor-of-100
  rescaling. ~95% are traceable; the rest stay on the card marked with an asterisk and are kept out of
  the effect-size strips, which invite comparison.

A direction is only meaningful against a specific measure, so **contestation is never counted across a
whole outcome family**: two papers count as disagreeing only when their descriptions of what they
measured overlap. Otherwise a turnout study would appear to contradict a vote-share study.
