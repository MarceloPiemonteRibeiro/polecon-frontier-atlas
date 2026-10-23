"""Editorial content for the atlas: branch narratives, VoxDev findings, agenda lens, section intros.

Paper references use (surname, year, title-fragment) and are resolved to atlas ids at build time,
so a reference that is not in the database fails loudly instead of linking to the wrong paper.
"""

FAMS = [
    dict(name="Institutions & regimes", branches=["A", "B"]),
    dict(name="Elections & politicians", branches=["C", "D"]),
    dict(name="Clientelism & corruption", branches=["E", "F"]),
    dict(name="State & bureaucracy", branches=["G"]),
    dict(name="Interests & information", branches=["H", "I"]),
    dict(name="Culture & identity", branches=["K"]),
    dict(name="Policy-making", branches=["L"]),
    dict(name="Conflict & crime", branches=["J"]),
    dict(name="Methods & adjacent", branches=["M"]),
]

SHORT = {"A": "Institutions & history", "B": "Democracy & regimes", "C": "Voters & accountability", "D": "Politicians & representation",
         "E": "Clientelism & patronage", "F": "Corruption & connections", "G": "State capacity & bureaucracy", "H": "Interest groups & money",
         "I": "Media & information", "J": "Conflict & crime", "K": "Culture & identity", "L": "Policy-making institutions", "M": "Methods & adjacent"}

NARRATIVE = {
    "A": "The colonial-origins programme (Acemoglu, Johnson & Robinson 2001; Dell 2010; Nunn 2008) is now the canon every course opens with. The frontier has moved from whether institutions matter to how specific historical arrangements — forced labour, indirect rule, concessions, early state presence — travel into today's state capacity, trust and beliefs. The 2026 syllabi pair these shocks with anthropology on lineage, religion and kinship, and with theory of why inefficient institutions persist.",
    "B": "Acemoglu–Robinson's commitment theory of transitions is the backbone; Acemoglu, Naidu, Restrepo & Robinson (2019) closed much of the cross-country growth debate. The frontier is micro: what democracy actually delivers (access more than quality: Kudamatsu, Harding, Martinez-Bravo et al.), how autocracies govern and censor (China's cadre system, village elections, information control), and why voters turn to populists after trade, austerity and financial shocks.",
    "C": "The empirics of political agency — random audits and re-election incentives in Brazil (Ferraz & Finan 2008, 2011) — are the most-taught papers in the atlas. The frontier asks when information actually moves voters (news relative to priors), why voters punish malfeasance more than they reward quality, how attribution breaks across tiers of government, and how electoral incentives distort the location and visibility of spending, now measured with granular administrative data.",
    "D": "Quota experiments (Chattopadhyay & Duflo 2004; Pande 2003) established that the identity of office-holders changes policy. The frontier is political selection: who runs and why (Dal Bó et al. 2017), quotas and the 'mediocre man', experiments in candidate selection and candidate training, party gatekeeping against women, and new outcomes — environment, health, welfare delivery — through which representation shows up.",
    "E": "A first generation documented vote buying and its enforcement (Wantchekon 2003; Finan & Schechter 2012; Stokes). A second opened up brokers and networks. The current frontier asks what weakens clientelism — reducing voters' material dependence works more reliably than information — and measures patronage inside bureaucracies with personnel records, showing who gets hired and what it costs in service quality.",
    "F": "Measurement papers (Olken 2007; Fisman 2001; Khwaja & Mian 2005; Olken & Barron 2009) built the field. The frontier moves to the long-run effects of anti-corruption policy (audits), procurement microdata, and the general-equilibrium costs of connections for firms and misallocation.",
    "G": "Besley & Persson's state-capacity framework gave the macro logic; a personnel-economics-of-the-state boom supplied the micro evidence on selecting, paying, posting and managing bureaucrats. The frontier reconnects bureaucracy to politics: whether bureaucratic quality mediates electoral accountability, how patronage and autonomy interact, and how low-capacity states raise taxes and deliver services.",
    "H": "Lobbying research moved from Grossman–Helpman theory to firm-level disclosure data on connections versus expertise, hidden channels such as corporate philanthropy, campaign-finance limits, and organisations that trade votes for public funding. The diffuse-benefit, concentrated-cost problem at the heart of reform is still mostly theoretical — an opening for new evidence.",
    "I": "Media economics began with accountability (Besley & Burgess 2002; Strömberg 2004; Snyder & Strömberg 2010) and bias (Gentzkow & Shapiro). The frontier is persuasion and polarisation on cable, social media and messaging apps, misinformation, the decline of local news, and how autocrats manage information without overt repression.",
    "J": "Income shocks and civil conflict (Miguel, Satyanath & Sergenti 2004; Dube & Vargas 2013) and counterinsurgency are the canon. The frontier has turned to crime and criminal governance — gangs, mafias and cartels as rivals to the state — to the legacies of violence, and to protest and collective action under authoritarian rule.",
    "K": "Culture entered political economy through trust and values (Tabellini; Guiso, Sapienza & Zingales; Nunn & Wantchekon). The 2026 syllabi push into kinship, morality and cultural evolution, nation-building and identity, and the political consequences of trade, automation and immigration shocks.",
    "L": "The workhorse theory — median voter, probabilistic voting, legislative bargaining, citizen candidates, constitutions — still anchors every PhD course. The empirical frontier estimates these models with roll calls, text and structural methods, studies polarisation and partisanship in firms and markets, and brings geopolitics and economic coercion into international political economy.",
}

VOX_FINDINGS = {
    "F1": dict(short="Visible goods beat quality", claim="Politicians favour visible, attributable benefits over quality",
               detail="Cash transfers, roads and electrification are politically legible; learning, clinical quality and maintenance are not, so incumbents over-invest in the first."),
    "F2": dict(short="Punish more than reward", claim="Voters punish malfeasance more reliably than they reward delivery",
               detail="Audits revealing corruption cost votes; better schools or clinics are rewarded inconsistently, so reforms rarely become self-sustaining."),
    "F3": dict(short="Who governs matters", claim="Who governs matters as much as the rules",
               detail="Reserved seats for women, castes and tribes shift provision toward their priorities; pay, recruitment and training reshape politician quality."),
    "F4": dict(short="Dependence fuels clientelism", claim="Reducing material dependence weakens clientelism more than information",
               detail="Cisterns and cash transfers free voters to act on preferences; informed but vulnerable voters can be bought back."),
    "F5": dict(short="Organised losers block reform", claim="Organised frontline providers block reform",
               detail="Unions, patronage networks and local elites are concentrated and mobilised; future beneficiaries are diffuse. Good reforms get weakened, delayed or reversed."),
    "F6": dict(short="Bureaucracy mediates", claim="Bureaucratic quality mediates whether political will becomes delivery",
               detail="Personnel rules, credentials and oversight bodies can stop managers from directing frontline workers; political will and capacity are complements."),
}

DESIGNS = {
    "RCT": "Field experiment (RCT)", "NatExp": "Natural experiment / lottery", "RD": "Regression discontinuity",
    "DiD": "Difference-in-differences / event study", "IV": "Instrumental variables", "Panel": "Panel / fixed effects",
    "XC": "Cross-country", "Struct": "Structural estimation", "Survey": "Survey / list experiment", "Lab": "Lab or lab-in-the-field",
    "Hist": "Historical / archival", "Text": "Text as data", "Desc": "Descriptive / measurement", "Theory": "Theory",
    "Review": "Review / survey article", "Book": "Book",
}

MECH_GROUPS = {
    "M_median": "Competing for voters", "M_probvote": "Competing for voters", "M_citizencand": "Who runs and who governs",
    "M_moralhazard": "Voters controlling politicians", "M_selection": "Voters controlling politicians", "M_career": "Voters controlling politicians",
    "M_visibility": "Voters controlling politicians", "M_fear": "Who runs and who governs", "M_commit": "Power, commitment and institutions",
    "M_coord": "Power, commitment and institutions", "M_legbargain": "Bargaining and policy-making", "M_contest": "Bargaining and policy-making",
    "M_lobby": "Organised interests and information", "M_collective": "Organised interests and information", "M_cheaptalk": "Organised interests and information",
    "M_media": "Organised interests and information", "M_clientelism": "Clientelism and corruption", "M_corruption": "Clientelism and corruption",
    "M_statecap": "The state and its agents", "M_bureau": "The state and its agents", "M_capture": "The state and its agents",
    "M_war": "Conflict", "M_culture": "Culture and identity", "M_diversity": "Culture and identity",
}

MECH_YEARS = {
    "M_median": [1981], "M_probvote": [1987, 1996], "M_moralhazard": [1973, 1986], "M_selection": [1999, 2006], "M_career": [1990, 2001, 2004],
    "M_visibility": [2005, 2007], "M_citizencand": [1996, 1997], "M_commit": [2000, 2001, 2006], "M_legbargain": [1978, 1989],
    "M_contest": [1980], "M_lobby": [1983, 1994], "M_collective": [1965, 1971], "M_clientelism": [2005, 2013], "M_fear": [2007],
    "M_coord": [1997, 2011], "M_cheaptalk": [1982], "M_media": [2004, 2005, 2006], "M_statecap": [2009, 2010], "M_bureau": [1991, 2005, 2013],
    "M_capture": [1956, 1972, 2000], "M_corruption": [1974, 1993, 1997], "M_war": [1995, 2004], "M_culture": [2001, 2008], "M_diversity": [1999],
}

# Your research brief (Sept 2026): causal chain and four failure types.
AGENDA = dict(
    title="Your agenda: socially beneficial reform",
    intro="Your research brief asks why democracies that can produce evidence about problems fail to turn it into policy, especially policies with diffuse, delayed, hard-to-attribute benefits. This view lays the atlas along the causal chain in the brief and along its four failure types, so you can see which links the literature has covered with credible evidence and where the frontier is thin.",
    thin=12,
    links=[
        dict(name="Evidence → public knowledge", leaves=["I1", "C4"], mechs=["M_media", "M_cheaptalk"],
             text="Does evidence reach citizens? Media coverage, report cards and disclosures move what voters know; coverage follows audiences and owners."),
        dict(name="Knowledge → perceived problem", leaves=["I3", "I4", "I2"], mechs=[],
             text="Information is framed, slanted and filtered. Persuasion, propaganda and social media decide whether knowledge becomes a perceived problem."),
        dict(name="Perceived problem → policy preference", leaves=["K3", "K1", "K5"], mechs=["M_culture"],
             text="Beliefs about fairness, mobility, identity and economic insecurity shape whether a recognised problem becomes support for a policy."),
        dict(name="Preference → collective organisation", leaves=["H3", "J6"], mechs=["M_collective", "M_coord"],
             text="The Olson problem: diffuse beneficiaries rarely organise, while concentrated losers do. Protest and movements are the main counter-technology."),
        dict(name="Organisation → political salience", leaves=["J6", "I1", "H1"], mechs=["M_coord"],
             text="Movements, lobbies and news cycles decide what politicians attend to; salience is crowded out by other events."),
        dict(name="Salience → electoral accountability", leaves=["C3", "C4", "C5"], mechs=["M_selection", "M_moralhazard", "M_visibility"],
             text="Accountability needs observability, attribution, salience and a short feedback loop; the evidence shows punishment works better than reward."),
        dict(name="Accountability → legislative adoption", leaves=["L2", "L3", "H1", "H2"], mechs=["M_legbargain", "M_lobby"],
             text="Bargaining, agenda power, parties and money decide which salient demands become law."),
        dict(name="Adoption → bureaucratic implementation", leaves=["G3", "G6"], mechs=["M_bureau"],
             text="Laws pass through bureaucracies whose selection, incentives, autonomy and oversight decide whether they are implemented."),
        dict(name="Implementation → observable outcome", leaves=["G4", "G5", "F1"], mechs=["M_corruption", "M_capture"],
             text="Frontline effort, leakage and local capture separate implemented policy from realised outcomes."),
        dict(name="Outcome → electoral feedback", leaves=["C5"], mechs=["M_visibility"],
             text="Whether visible results are credited to the right politician closes the loop — or doesn't, for diffuse and delayed benefits."),
        dict(name="Feedback → reform survival", leaves=["A4", "H3"], mechs=["M_commit", "M_collective"],
             text="Reforms that leave organised losers intact are reversed; surviving reforms change the political equilibrium."),
    ],
    failures=[
        dict(code="A", name="Preference failure", text="People do not want the policy, because of values or its distributional effects.",
             papers=[("Bursztyn", 2016, "public education spending"), ("Alesina", 2018, "Intergenerational Mobility"), ("Kuziemko", 2015, "How Elastic"), ("Enke", 2020, "Moral Values"), ("Boas", 2021, "Competence versus priorities"), ("Fernandez", 1991, "Resistance to Reform")],
             open="Which features of a diffuse-benefit policy (framing, who pays, identity cues) move preferences durably rather than for one survey round?"),
        dict(code="B", name="Information failure", text="People want it but do not know it is beneficial or who delivered it.",
             papers=[("Ferraz", 2008, "Exposing Corrupt"), ("Snyder", 2010, "Press Coverage"), ("Banerjee", 2024, "Public information is an incentive"), ("Cox", 2024, "Punishing mayors"), ("Dias", 2026, "Information and the politics of school quality"), ("Boomhower", 2023, "Environmental Externalities"), ("Allcott", 2017, "Social Media and Fake News")],
             open="How does attribution fail when several tiers share a service, and what replaces local news as it declines?"),
        dict(code="C", name="Political-aggregation failure", text="People want it, but small organised groups block it.",
             papers=[("Olson", 1965, "Logic of Collective Action"), ("Lizzeri", 2001, "Provision of Public Goods"), ("Grossman", 1994, "Protection for Sale"), ("Bertrand", 2014, "Whom You Know"), ("Sandholtz", 2024, "politics of public service reform"), ("Urvoy", 2025, "Organized Voters"), ("Bombardini", 2012, "Competition and Political Organization"), ("Kaplan", 2018, "Moral Hazard and Special Interests"), ("Matter", 2019, "public attention")],
             open="What lets diffuse beneficiaries become a political actor — organisations, outsiders, or policy design that creates its own constituency?"),
        dict(code="D", name="Implementation failure", text="It is legislated but not implemented, because of bureaucracy, capacity or vested interests.",
             papers=[("Dhaliwal", 2017, "devil is in the details"), ("Bandiera", 2021, "Allocation of Authority"), ("Slough", 2024, "Bureaucratic Quality"), ("Toral", 2024, "How patronage delivers"), ("Rasul", 2014, "Management of Bureaucrats"), ("Gulzar", 2017, "Politicians, bureaucrats")],
             open="Which bureaucratic reforms are politically feasible, and how do oversight bodies avoid becoming their own bottleneck?"),
    ],
)

META = dict(
    lede="A map of the political-economy literature as top PhD programmes teach it in 2026: every paper on ~90 syllabi and lecture decks, deduplicated, placed on one tree, linked by citations, and read against the canonical models it tests. The VoxDevLit review on public service delivery is the anchor.",
    thesis="Across the syllabi, the field has moved from cross-country correlations about institutions to micro-evidence on the agents inside them: voters with limited information, politicians selected and disciplined by elections, brokers and bureaucrats who sit between policy and delivery. The 2015-onward readings concentrate on four fronts: <b>accountability with imperfect information</b> (punishment works better than reward; visibility beats quality), <b>who governs</b> (selection and representation), <b>the state's own agents</b> (bureaucratic selection, incentives and autonomy) and <b>information ecosystems</b> (social media, polarisation, autocratic control). Older canon on institutions, conflict and redistribution theory remains, but its share of new readings is falling. Read against the canonical models, the median-voter account of redistribution is the most contested: over two in five of its tests qualify or contradict it, while models of bureaucratic incentives, media influence and lobbying are almost uniformly supported.",
    mechIntro="Patrick Francois's BREAD lecture lists the recurring strategic architectures of political economy — voters disciplining politicians, citizens deciding to run, promises that cannot be made credible, groups spending resources to win. Each mechanism below starts from its canonical model and its predictions, then lists every coded paper that tests it, with my reading of whether the evidence supports the prediction, qualifies it (the effect depends on conditions the model treats as fixed), or contradicts it.",
    netIntro="Edges come from the reference lists of papers resolved in OpenAlex: a link means the newer paper cites the older one and both are in the atlas. Filled dots are syllabus papers; hollow rings are works no syllabus lists but that at least ten syllabus papers cite, added by following the reference lists one step out. Colour is the branch family; size grows with the number of courses assigning the paper and how often other atlas papers build on it.",
    mtreeIntro="The canonical mechanisms of political economy as a tree. Each architecture branches into its mechanisms; each mechanism into the models that state it and the empirical papers that test it, split by verdict — supports, qualifies (the effect depends on conditions the model treats as fixed) or contradicts. Open a mechanism to see who tested it, when, where and with what design.",
    authIntro="Every author of an atlas paper resolved in OpenAlex, placed at their current institution (OpenAlex's last known affiliation, which can lag recent moves). The left chart shows whether the field's centre of gravity is shifting; the map and ranking show where the centres are; the network shows who writes with whom. Authors of papers OpenAlex could not resolve (mostly books and working papers) are missing.",
    mapIntro="Country of study for empirical papers, coded from my reading of the review, abstracts and titles. The United States accounts for about a third of single-country studies; among developing countries India, Brazil, China and Indonesia lead because of audit lotteries, close elections, reservations and administrative data. Whole regions with weak data remain nearly blank. Cross-country and theory papers are not on the map.",
    revIntro="Pick what you care about and the atlas assembles a structured review from its own codings: the scope of the evidence, an answer section for each of your questions, the foundations and frontier of each topic, the mechanisms tested and how often the evidence supports them, gaps, and references. It does not write prose. For a narrative review, copy the prompt: it bundles this outline with every selected paper's coded record, so Claude or ChatGPT writes from the evidence rather than from memory. Your choices are remembered in this browser.",
    timeIntro="Three views of time. The first shows when the assigned papers were published, so you can see which waves of work the syllabi lean on. The map below it shows where that evidence was produced, year by year. The last follows each canonical mechanism from its model to the empirical tests that came later.",
    courseIntro="Each course is a different cut of the same field. MIT's 14.773 leans on institutions, conflict and history; the BREAD-IGC and PUC-Rio courses on accountability, selection and bureaucracy; Stockholm and Harvard on elections, legislatures and media; Chicago's 2026 courses on culture and context. The matrix makes those choices comparable.",
    dlNote="Papers whose introduction I could not read, in four tiers. Tiers 1–3 I could place only from the title and syllabus context; tier 4 I coded from the abstract alone, and the introduction would sharpen the design and mechanism verdicts. Open copies were blocked for my scripts (publisher and SSRN pages refuse automated downloads) but usually open in your browser or through your library login. The same list, with every link, is in download_list.csv",
)
