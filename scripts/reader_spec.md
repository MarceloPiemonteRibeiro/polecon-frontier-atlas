# Evidence-card reading spec

You are reading political-economy papers to build a comparable evidence base. One JSON object per
paper, one per line, appended to the output file you were given. No prose, no markdown, no commentary
in the output file.

## Input

Each paper is a JSON file at `data/fulltext/<cid>.json`, sliced from the PDF. Fields:

| field | what it is |
|---|---|
| `abstract` | the abstract, or the first page when no abstract heading was found |
| `intro` | the introduction (first ~9k chars after the heading) |
| `conclusion` | the conclusion / concluding remarks |
| `data` | the data or setting section, when the paper has one |
| `results` | blocks under results headings; when the paper has no such heading, the paragraphs with the most quantified claims |
| `captions` | table and figure captions |
| `claims` | sentences matching "we find / we estimate / increases by ..." and carrying a number |
| `gaps` | sentences matching "future research / remains an open question / little is known ..." |
| `lit` | sentences about the prior literature ("a large literature", "contrary to previous work", "mixed evidence") |
| `models` | canonical model names detected verbatim in the body |
| `pages`, `chars` | size of the original PDF |

Slices can be empty or garbled (two-column extraction, scanned pages, publisher front matter). Work
with what is there. If a file has `"no_text": true` or the slices carry no substantive content, emit a
card with `"confidence": "none"` and `"skip_reason"` set, and move on.

**Check that the slices are the paper the batch file names.** Some PDFs were downloaded from search
results and hold something else entirely — an editor's annual report, a publisher's catalogue, an
unrelated article, or only a paper's online appendix. If the slices plainly do not match the title and
authors in your batch line, do **not** code whatever paper is actually there and do not fall back on
what you remember about the named paper. Emit `"confidence": "none"` with
`"skip_reason": "wrong PDF: slices are <what they actually are>"`, and list those cids in your final
report. A card coded against the wrong paper is far worse than a missing card.

The paper's title, authors, year, venue and current one-line finding are in the batch file.

## Hard rules

1. **Never invent.** Every number, country, sample size and claim must be present in the slices. If a
   field is not determinable, use `null` (or `[]`), not a guess. A thin card is worth more than a
   plausible-sounding wrong one.
2. **No outside knowledge.** You may well know this paper. Code only what these slices say. If the
   slices contradict what you remember, follow the slices.
3. Quote magnitudes in the paper's own units. Do not convert, rescale or annualise.
4. `claim` is the paper's own headline result, not your assessment of it.
5. Theory papers, reviews and books: most empirical fields are `null`. Code `mechanisms`,
   `settled`, `contested`, `gaps` and `claim` — they are often the richest source of those.
6. Keep every text field short. `claim` ≤ 240 chars; each list item ≤ 200 chars.

## Output schema

```json
{
  "cid": "C00001",
  "claim": "Districts subject to the colonial mining mita have ~25% lower household consumption and 6pp more child stunting today.",
  "treatment": "colonial_historical",
  "treatment_desc": "assignment to the Peruvian mining mita, 1573-1812",
  "outcome": "economic_development",
  "outcome_desc": "household consumption; child stunting",
  "direction": "neg",
  "magnitudes": [
    {"outcome": "household consumption", "value": -25, "unit": "pct"},
    {"outcome": "child stunting", "value": 6, "unit": "pp"}
  ],
  "setting": {
    "countries": ["Peru", "Bolivia"],
    "level": "district",
    "period": [1573, 2001],
    "n_units": 1478,
    "unit_desc": "districts along the mita boundary"
  },
  "identification": {
    "design": "RD",
    "variation": "the historical mita boundary, with elevation and ethnicity balanced across it",
    "threat": "other institutions may have changed discontinuously at the same boundary"
  },
  "mechanisms": [
    {"id": "M_commit", "verdict": "supports", "note": "de facto power of landowners carried the effect forward"},
    {"id": "M_statecap", "verdict": "refines", "note": "public-goods channel, not fiscal capacity as such"}
  ],
  "settled": ["Historical institutions affect current income (Acemoglu Johnson Robinson; Nunn)"],
  "contested": ["Whether land inequality helps or hurts long-run growth"],
  "gaps": ["General models of institutional evolution", "How constraints respond to forces promoting change"],
  "data_asset": "digitised Spanish Empire and Peruvian Republic records matched to modern household surveys",
  "data_novel": true,
  "scope": "identified only locally, at the mita boundary",
  "confidence": "high"
}
```

### `treatment` — one of (what varies / the cause)

`info_voters` information to voters (report cards, audits made public, scorecards, canvassing, debates) ·
`info_politicians` information or feedback to politicians and bureaucrats ·
`audit_monitoring` audits, inspections, top-down monitoring, community monitoring ·
`electoral_rules` term limits, re-election eligibility, electoral system, ballot design, compulsory voting, district rules ·
`franchise_democracy` enfranchisement, democratisation, regime change, suffrage extension ·
`quotas_reservation` gender, caste, ethnic quotas and reserved seats ·
`politician_pay_selection` politician wages, recruitment, training, screening, candidate entry rules ·
`bureaucrat_personnel` bureaucrat pay, posting, promotion, rotation, autonomy, hiring and firing rules ·
`decentralization` devolution, local vs central assignment, village councils, federalism as treatment ·
`transfers_cash` cash transfers, CCTs, social programmes, pensions, workfare ·
`public_goods_infra` roads, electrification, water, schools, clinics as the treatment ·
`media_access` entry or exit of radio, TV, newspapers, internet, mobile, social media ·
`media_content` slant, propaganda, persuasion content, misinformation, framing ·
`campaign_money_lobbying` campaign finance, contributions, lobbying, connections, revolving door ·
`clientelism_vote_buying` vote buying, brokers, patronage exchange ·
`anti_corruption_policy` procurement rules, e-governance, transparency laws, prosecution, asset disclosure ·
`taxation_fiscal_capacity` tax enforcement, collection technology, fiscal-capacity investment ·
`conflict_violence` war, insurgency, repression, crime exposure as the cause ·
`economic_shock` trade, commodity prices, rainfall, automation, austerity, financial crisis, unemployment ·
`migration_immigration` migration or refugee exposure ·
`colonial_historical` colonial rule, slave trades, land tenure systems, missions, historical state presence, legal origin ·
`culture_identity` ethnic diversity, kinship, religion, trust, nation-building, norms ·
`institutional_constraints` constitutions, courts, separation of powers, property-rights institutions, checks ·
`protest_collective_action` protest, movements, coordination, revolution ·
`education` schooling or human capital as the cause ·
`elite_capture` landed elites, oligarchs, business groups, incumbent firms ·
`political_competition` entry of parties, closeness of races, party system structure ·
`land_property_rights` land reform, titling, tenure systems, property-rights assignment ·
`foreign_aid` aid, donor programmes, external intervention and state-building ·
`corruption_as_cause` corruption, rents or misgovernance as the cause rather than the outcome ·
`election_proximity` nearness or timing of an election: political budget cycles, pre-election periods ·
`politician_identity` who holds office by gender, caste, ethnicity or religion when it is not a quota
(a close-election margin, a candidate's background) &mdash; use `quotas_reservation` for quotas and reserved seats ·
`other`

### `outcome` — one of (what is measured)

`voting_behaviour` turnout, vote share, incumbent support, candidate choice ·
`politician_selection` who runs, who wins, their quality, competence, background ·
`politician_behaviour` effort, attendance, roll-call votes, positions, rent extraction, policy choices by office-holders ·
`corruption_rents` leakage, bribes, misappropriation, procurement overpricing, rents captured ·
`public_goods_access` coverage and access: electrified villages, roads built, enrolment, connections ·
`public_services_quality` learning, clinical quality, provider presence, maintenance, wait times ·
`fiscal_spending` budget levels, composition, geographic targeting ·
`taxation_revenue` revenue, compliance, tax base, enforcement outcomes ·
`state_capacity` bureaucratic quality, administrative reach, measurement and enforcement capacity ·
`economic_development` income, growth, consumption, poverty, productivity ·
`firm_outcomes` firm value, entry, investment, credit, contracts, stock returns ·
`inequality_redistribution` inequality, redistribution levels, transfer generosity ·
`beliefs_attitudes` trust, policy preferences, perceptions, ideology, norms ·
`information_knowledge` what citizens know, media consumption, learning, beliefs about facts ·
`polarisation` affective or ideological polarisation, partisanship, sorting ·
`conflict_violence_out` conflict onset or intensity, crime, repression, protest incidence ·
`regime_democracy` democratisation, regime survival, coups, authoritarian consolidation ·
`policy_adoption` laws passed, reforms enacted, regulation adopted, tariffs set ·
`clientelism_out` vote-buying incidence, broker activity, patronage appointments ·
`human_capital_health` attainment, test scores as human capital, mortality, morbidity, nutrition ·
`migration_mobility` migration, displacement, residential sorting ·
`media_supply` coverage volume, slant, outlet entry and exit, censorship intensity ·
`civic_participation` social capital, associational membership, civic and community participation, collective action ·
`institutions_rules` institutions or rules as the outcome: constitutions adopted, property rights, legal change, electoral rules chosen ·
`environment_resources` forest cover, deforestation, emissions, pollution, water, resource extraction and conservation ·
`theory_only` no empirical outcome ·
`other`

### `direction`

`pos` the treatment raises the outcome · `neg` lowers it · `null` no detectable effect, and the paper
says so · `mixed` signs differ across outcomes, groups or settings in the paper's own account ·
`na` theory, review, descriptive or book with no estimated effect of its own. A model's comparative
static is not an estimated effect, so a theory paper is `na` even when its proposition carries a sign;
put the prediction in `claim` and the model's verdict in `mechanisms`. A review that summarises other
people's results is `na` too — signing it would count the same evidence twice ·
`unknown` the paper clearly estimates an effect but these slices never say which way it goes.

Code the direction of the paper's **headline** result. Put the rest in `scope`.

**The sign is literal, never a verdict on whether the news is good.** `pos` means the number named in
`outcome_desc` goes up; `neg` means it goes down. A programme that cuts infant mortality is `neg` on
"infant mortality", not `pos` for being beneficial. A reform that cuts corruption is `neg` on
"share of funds misappropriated". An audit that lowers re-election is `neg` on "probability of
re-election". Nothing about desirability enters the direction field — the whole evidence matrix is
built by counting these signs against each other, so one reader using "improvement" and another using
the arithmetic sign makes two papers look like they disagree when they agree.

Two rules follow:
- **Name the outcome so the sign cannot be misread.** `outcome_desc` must be the measured quantity
  ("infant mortality per 1,000", "years of schooling"), not the direction of travel
  ("better health outcomes").
- **One headline outcome per card.** When a paper moves several outcomes in different arithmetic
  directions — schooling up *and* infant mortality down — pick the one its abstract leads with, name
  it in `outcome_desc`, and sign against that one. Put the others in `magnitudes` and `scope`. Use
  `mixed` only when the paper reports conflicting signs *on the same measure* across groups,
  settings or specifications.

`unknown` is the honest answer more often than it looks, and it is always better than a guess. Do not
infer a direction from the title, from the prior one-liner in the batch file, from the topic, or from
what you remember about the paper — only from a statement in the slices. A card with
`"direction": "unknown"` still earns its place: its claim, setting, mechanisms and gaps are all
usable. An invented direction corrupts the evidence matrix, which is built from directions.

### `magnitudes`

Up to 4. `unit` is one of `pct` (percent change), `pp` (percentage points), `sd` (standard
deviations), `log` (log points), `ratio` (multiple or elasticity), `level` (the outcome's own units —
then say which in `outcome`), `pctile`. Sign the `value`. Omit the list entirely if the slices carry
no usable number.

### `setting`

`level` is one of `cross_country`, `country`, `region`, `state`, `district`, `municipality`,
`village`, `precinct`, `school_clinic`, `firm`, `individual`, `politician`, `bureaucrat`,
`legislature`, `household`, `na`. `period` is `[first_year, last_year]` of the data, not of
publication. `n_units` is the main estimation sample's unit count, integer, else `null`.

### `identification.design`

Reuse the atlas vocabulary: `RCT`, `NatExp`, `RD`, `DiD`, `IV`, `Panel`, `XC`, `Obs`, `Struct`,
`Survey`, `Lab`, `Hist`, `Text`, `Desc`, `Theory`, `Review`, `Book`. Pick the one carrying the
headline result.

`XC` means **cross-country** specifically — a regression whose units are countries. A cross-sectional
regression on districts, towns, firms or individuals inside one country is `Obs` (selection on
observables), however many controls or robustness checks it carries. Use `Panel` when the identifying
variation is within-unit over time, and `IV` when an instrument carries the headline result.
`variation` names the actual source of variation in one clause. `threat` is the identification
concern **the authors themselves raise**, not yours; `null` if they raise none.

### `mechanisms`

Zero to four, from this list. `verdict` is `supports`, `contradicts`, `refines` (holds but with a
condition or a different channel than the model says), or `tests_inconclusive`.

`M_median` median voter and redistribution ·
`M_probvote` probabilistic voting, swing-voter targeting ·
`M_moralhazard` electoral discipline, moral hazard ·
`M_selection` electoral selection of types ·
`M_career` career concerns, pandering, signalling ·
`M_visibility` visibility and attribution bias, credit claiming ·
`M_citizencand` citizen-candidates, who governs matters ·
`M_commit` commitment problems, de facto power ·
`M_legbargain` legislative bargaining, agenda power ·
`M_contest` rent-seeking contests, conflict technology ·
`M_lobby` lobbying, common agency, protection for sale ·
`M_collective` collective action, concentrated vs diffuse interests ·
`M_clientelism` clientelism as conditional exchange ·
`M_fear` politics of fear, identity loyalty ·
`M_coord` coordinating punishment, self-enforcing constraints ·
`M_cheaptalk` strategic information transmission ·
`M_media` media markets, bias, capture ·
`M_statecap` state capacity as investment ·
`M_bureau` bureaucratic principal-agent ·
`M_capture` local capture vs local information ·
`M_corruption` corruption, extortion, IO of bribes ·
`M_war` bargaining failure, opportunity cost of conflict ·
`M_culture` cultural transmission, co-evolution with institutions ·
`M_diversity` diversity, preferences and public goods

Only code a mechanism the paper actually speaks to. "The paper is about elections" is not a verdict on
`M_moralhazard`.

### `settled`, `contested`, `gaps`

These three carry most of the value, so read `lit` and `gaps` carefully and also look in the
introduction's opening paragraphs and the conclusion's closing ones.

- `settled`: what this paper treats as **established background** — the claims it builds on without
  re-litigating. Name the authors it credits, in parentheses, when it names them. 0–4 items.
- `contested`: what it says is **disputed, mixed or unresolved**, including where it positions itself
  against prior findings. 0–4 items.
- `gaps`: what it says is **not yet known** — future research, open questions, acknowledged
  limitations that need new data or settings. Paraphrase tightly; one question per item. 0–5 items.

Write each as a standalone claim that still makes sense out of context. Not "this is contested" but
"whether information campaigns change votes when voters are materially dependent".

### `scope`

One clause on when the result does or does not travel: the margin it is identified at,
heterogeneity the paper emphasises, the population it generalises to. `null` if the paper says nothing.

### `confidence`

`high` the slices clearly support every coded field · `medium` the headline claim is clear but
magnitudes, setting or mechanisms were partly inferred from context · `low` the slices were thin or
garbled and the card is a best effort · `none` nothing usable; set `skip_reason` too.

## Procedure

1. Read your batch file. It lists, per paper: cid, authors, year, title, venue, tree leaf and the
   existing one-line finding (coded from the abstract — treat it as a prior to confirm or correct,
   not as truth).
2. For each cid, read `data/fulltext/<cid>.json`.
3. Emit one line of JSON to your output file. Append as you go; do not hold the whole batch in memory
   and write at the end.
4. When you finish, verify the output file has one parseable JSON line per cid in your batch, and
   report counts: cards written, by confidence level.

Read the slices with `cat`/`Read`. Do not run the PDFs through anything. Do not fetch anything from
the network — everything you need is on disk.
