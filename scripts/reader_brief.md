# Reader agent brief

You are a reader agent building an evidence base from political-economy papers, working in
`D:\GitHub\polecon-frontier-atlas`. Your launch message gives you a **batch name** such as
`r5_std_003` or `r5_deep_001`. Everything else you need is here.

## What to do

1. Read `scripts/reader_spec.md` in full. It is the coding manual — the schema, the controlled
   vocabularies and the rules. Follow it exactly.
2. Read your batch file: `data/read_batches/<batch>.txt`. Each line is one paper: cid, authors, year,
   title, venue, tree leaf, how many courses teach it, and the one-line finding coded earlier from
   its abstract (a prior to confirm or correct, not truth).
3. For each cid in order, read its slices:
   - a **`_deep_`** batch reads `data/fulltext/<cid>.json` — every field, the fullest read
   - a **`_std_`** batch reads `data/fulltext_lite/<cid>.json` — the compact slices
4. Append one JSON object per paper, one per line, to `data/cards/<batch>.jsonl`.

## Rules that have cost us before

- **Write each card the moment you finish that paper.** Never accumulate and write at the end. Three
  separate runs have been killed mid-batch by usage limits, and only the already-written cards
  survived. This is the single most important instruction here.
- **Append with a small Python snippet**, not by hand, so the JSON stays valid. Set
  `PYTHONIOENCODING=utf-8` or write bytes — the Windows console default mangles non-ASCII and has
  already broken one run.
- **Only ever write to your own `data/cards/<batch>.jsonl`.** Other agents are working in this repo at
  the same time.
- **Put any helper script in its own new subdirectory of your scratchpad**, with your batch name in
  the filename. Agents sharing a scratchpad filename have overwritten each other's helpers and sent a
  card into the wrong file.
- **Do not parallelise your own reads.** Work steadily through the batch in order.
- **Never invent.** Not a number, not a country, not a sample size, not a direction. `null` and
  `"unknown"` are correct answers and are worth more than a plausible guess. Do not infer a direction
  from the title, the topic, the prior one-liner, or what you remember about the paper.
- **Check the slices are the paper your batch line names.** Roughly one PDF in eight holds something
  else — an editor's annual report, a publisher's catalogue, an online appendix, an unrelated article.
  When that happens, emit `"confidence": "none"` with
  `"skip_reason": "wrong PDF: slices are <what they actually are>"`. Never code the paper that is
  actually there, and never fall back on memory for the paper that should have been.
- **If a slice reads as gibberish**, it may be a font table offset by a constant. Try subtracting 1 to
  5 from each character code; if it decodes to English, use that and say so. If not, code it
  `"confidence": "none"` with a `skip_reason`.
- **Make `outcome_desc` precise.** It names exactly what was measured, and it is what decides whether
  two papers count as answering the same question downstream. "Turnout at the polling station" is
  useful; "voting" is not.
- **Spend real care on `settled`, `contested` and `gaps`.** Those three fields drive the research-gap
  analysis, which is the point of the whole exercise.

## Reporting back

Three lines at most: how many cards you wrote, the confidence breakdown, and which cids you could not
code with the reason. Add a fourth line only for something the next agent or the maintainer genuinely
needs to know — a spec vocabulary that did not fit, a systematic extraction problem, a cid whose PDF
should be replaced.
