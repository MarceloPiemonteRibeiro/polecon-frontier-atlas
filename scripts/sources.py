"""Registry of input documents: which course/source each text file belongs to.

course_id groups multiple years of the same course (canonicality counts distinct courses,
persistence counts distinct course-years).
kind: reading_list | slides | review | agenda | user | skip
"""
import re

# (regex on text filename, fields)
REGISTRY = [
    (r"VoxDev_PoliticalEconomy_slides", dict(course_id="VOXDEV", label="VoxDevLit slides: PolEcon of Public Service Delivery (Ferraz et al.)", inst="VoxDev", instr="Ferraz, Frey, Fujiwara, Mahadevan, Moreira, Sandholtz", year=2026, level="Review", kind="slides", lead=True)),
    (r"Political_Economy_Public_Service_Delivery_Issue1", dict(course_id="VOXDEV", label="VoxDevLit 26(1): PolEcon of Public Service Delivery", inst="VoxDev", instr="Ferraz et al.", year=2026, level="Review", kind="review", lead=True)),
    (r"Week_1_Citation_List|Reading-list-for-lecture_1|IGC_BREAD_Intro", dict(course_id="BREAD26", label="BREAD-IGC 2026 L1 Intro (Callen, Ferraz, Finan)", inst="BREAD-IGC", instr="Callen, Ferraz, Finan", year=2026, level="PhD", kind="reading_list", lecture="1 Introduction")),
    (r"Bread_IGC_PolEcon_Week_3_reading_list|BREAD_Week_3_lecture", dict(course_id="BREAD26", label="BREAD-IGC 2026 L3 Core models (Francois)", inst="BREAD-IGC", instr="Francois", year=2026, level="PhD", kind="reading_list", lecture="3 Core political economy models")),
    (r"BREAD_Week_4|State_Capacity_Conflict", dict(course_id="BREAD26", label="BREAD-IGC 2026 L4 State capacity (Besley)", inst="BREAD-IGC", instr="Besley", year=2026, level="PhD", kind="reading_list", lecture="4 State capacity")),
    (r"Week_5_reading|Politicians_and_Political_Agency", dict(course_id="BREAD26", label="BREAD-IGC 2026 L5 Politicians & agency (Ferraz, Finan)", inst="BREAD-IGC", instr="Ferraz, Finan", year=2026, level="PhD", kind="reading_list", lecture="5 Politicians and political agency")),
    (r"Week_6_reading|Bureaucracy_and_Implementation", dict(course_id="BREAD26", label="BREAD-IGC 2026 L6 Bureaucracy (Khan, Khwaja)", inst="BREAD-IGC", instr="Khan, Khwaja", year=2026, level="PhD", kind="reading_list", lecture="6 Bureaucracy and implementation")),
    (r"Lecture_7_Reading", dict(course_id="BREAD26", label="BREAD-IGC 2026 L7 Selection & representation (Pande, Casey)", inst="BREAD-IGC", instr="Pande, Casey", year=2026, level="PhD", kind="reading_list", lecture="7 Political selection, voice, representation")),
    (r"^Week_3_reading_list", dict(kind="skip")),  # duplicate of BREAD week 3
    (r"syllabus_PolEcon_IGC_BREAD_Intro", dict(kind="skip")),  # duplicate of BREAD intro
    (r"MIT_14773_Acemoglu_Moscona_2026", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Moscona) 2026", inst="MIT", instr="Acemoglu, Moscona", year=2026, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Olken_Spring2024", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Olken) 2024", inst="MIT", instr="Acemoglu, Olken", year=2024, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Fergusson_Spring2021", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Fergusson) 2021", inst="MIT", instr="Acemoglu, Fergusson", year=2021, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Banerjee_Spring2019", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Banerjee) 2019", inst="MIT", instr="Acemoglu, Banerjee", year=2019, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Fergusson_Spring2018", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Fergusson) 2018", inst="MIT", instr="Acemoglu, Fergusson", year=2018, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_GarciaJimeno_Spring2017", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Garcia-Jimeno) 2017", inst="MIT", instr="Acemoglu, Garcia-Jimeno", year=2017, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Banerjee_Duflo_Olken_Spring2015", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Banerjee, Duflo, Olken) 2015", inst="MIT", instr="Acemoglu, Banerjee, Duflo, Olken", year=2015, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Banerjee_Spring2014", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Banerjee) 2014", inst="MIT", instr="Acemoglu, Banerjee", year=2014, level="PhD", kind="reading_list")),
    (r"MIT_14773_Acemoglu_Olken_Spring2012", dict(course_id="MIT14773", label="MIT 14.773 (Acemoglu, Olken) 2012", inst="MIT", instr="Acemoglu, Olken", year=2012, level="PhD", kind="reading_list")),
    (r"MIT_14770_Introduction_PolEcon_Fall2017|14\.770-fall-2017", dict(course_id="MIT14770", label="MIT 14.770 Intro PolEcon (Acemoglu, Olken) 2017", inst="MIT", instr="Acemoglu, Olken", year=2017, level="PhD", kind="reading_list")),
    (r"acemoglu_olken_17", dict(course_id="MIT14770", label="MIT 14.770 lecture slides (Acemoglu, Olken) 2017", inst="MIT", instr="Acemoglu, Olken", year=2017, level="PhD", kind="slides")),
    (r"14\.75-fall-2012|olken_2012", dict(course_id="MIT1475", label="MIT 14.75 PolEcon & Econ Dev (Olken) 2012", inst="MIT", instr="Olken", year=2012, level="UG", kind="slides")),
    (r"14\.771-fall-2021|olken_21", dict(course_id="MIT14771", label="MIT 14.771 Development Econ (Duflo, Olken) 2021", inst="MIT", instr="Duflo, Olken", year=2021, level="PhD", kind="slides")),
    (r"191216_Failures", dict(kind="skip")),
    (r"Chicago_PPHA41150_Robinson", dict(course_id="CHI41150", label="Chicago PPHA 41150 (Robinson, Moscona, Nunn) 2026", inst="Chicago", instr="Robinson, Moscona, Nunn", year=2026, level="PhD", kind="reading_list")),
    (r"Chicago_PPHA41120_Montero", dict(course_id="CHI41120", label="Chicago PPHA 41120 PolEcon of Dev (Montero) 2026", inst="Chicago", instr="Montero, Sanchez de la Sierra", year=2026, level="PhD", kind="reading_list")),
    (r"Berkeley_Miguel_Finan", dict(course_id="BERK270B", label="Berkeley 270B Grad PolEcon (Miguel, Finan) 2012", inst="Berkeley", instr="Miguel, Finan", year=2012, level="PhD", kind="reading_list")),
    (r"Berkeley_Roland_215A_f10", dict(course_id="BERK215A", label="Berkeley 215A Political Economics (Roland) 2010", inst="Berkeley", instr="Roland", year=2010, level="PhD", kind="reading_list")),
    (r"Berkeley_Persson_215a_f08", dict(course_id="BERK215A", label="Berkeley 215A Political Economics (Roland) 2008", inst="Berkeley", instr="Roland", year=2008, level="PhD", kind="reading_list")),
    (r"syllabus_econ215b_spring2022", dict(course_id="BERK215B", label="Berkeley 215B Political Economics (Trebbi) 2022", inst="Berkeley", instr="Trebbi", year=2022, level="PhD", kind="reading_list")),
    (r"Slides_(Congress|elections|Lobbying)_2025", dict(course_id="BERK215B", label="Berkeley PolEcon lecture slides (Trebbi) 2025", inst="Berkeley", instr="Trebbi", year=2025, level="PhD", kind="slides")),
    (r"PHDBA279A", dict(course_id="BERK279A", label="Berkeley PHDBA 279A Pol Institutions & Business (Dal Bó, de Figueiredo) 2009", inst="Berkeley", instr="Dal Bó, de Figueiredo", year=2009, level="PhD", kind="reading_list")),
    (r"ECON224", dict(course_id="BERK224", label="Berkeley ECON 224 Economics of Institutions (Tadelis, Yuchtman) 2011", inst="Berkeley", instr="Tadelis, Yuchtman", year=2011, level="PhD", kind="reading_list")),
    (r"LSE_EC557", dict(course_id="LSE557", label="LSE EC557 PolEcon PhD I (Levy, Persson) 2026", inst="LSE", instr="Levy, Persson", year=2026, level="PhD", kind="reading_list")),
    (r"LSE_EC558", dict(course_id="LSE558", label="LSE EC558 PolEcon PhD II (Ilzetzki, Yuchtman) 2026", inst="LSE", instr="Ilzetzki, Yuchtman", year=2026, level="PhD", kind="reading_list")),
    (r"LSE_EC453", dict(course_id="LSE453", label="LSE EC453 PolEcon MSc (Wolton, Callen) 2026", inst="LSE", instr="Wolton, Callen", year=2026, level="MSc", kind="reading_list")),
    (r"EC453_Political_Economy_-_Syllabus_2020", dict(course_id="LSE453", label="LSE EC453 PolEcon MSc (Wolton) 2020", inst="LSE", instr="Wolton", year=2020, level="MSc", kind="reading_list")),
    (r"GV481", dict(course_id="LSEGV481", label="LSE GV481 PolSci & PolEcon (Matakos, Wolton) 2014", inst="LSE", instr="Matakos, Wolton", year=2014, level="MSc", kind="reading_list")),
    (r"GV482", dict(course_id="LSEGV482", label="LSE GV482 Political Economy (Wolton) 2020", inst="LSE", instr="Wolton", year=2020, level="MSc", kind="reading_list")),
    (r"EC38011", dict(course_id="SU38011", label="Stockholm EC38011 Political Economics II (Persson, Strömberg) 2025", inst="Stockholm/IIES", instr="Persson, Strömberg", year=2025, level="PhD", kind="reading_list")),
    (r"Syllabus-Readings200129", dict(course_id="SU38011", label="Stockholm Political Economics II (Persson, Strömberg) 2020", inst="Stockholm/IIES", instr="Persson, Strömberg", year=2020, level="PhD", kind="reading_list")),
    (r"EC38016", dict(course_id="SU38016", label="Stockholm EC38016 Political Economics III 2025", inst="Stockholm/IIES", instr="Strömberg, Persson, Rickne et al.", year=2025, level="PhD", kind="reading_list")),
    (r"Outline_September_2023_Columbia", dict(course_id="COL6308", label="Columbia GR6308 Political Economy I (Prat) 2023", inst="Columbia", instr="Prat", year=2023, level="PhD", kind="reading_list")),
    (r"syllabus_2017_wlinks", dict(course_id="COLNAIDU", label="Columbia PolEcon of Long-Run Growth (Naidu) 2017", inst="Columbia", instr="Naidu", year=2017, level="PhD", kind="reading_list")),
    (r"syllabus_pons", dict(course_id="HARVPONS", label="Harvard Political Economy (Pons, Shapiro) 2025", inst="Harvard", instr="Pons, Shapiro", year=2025, level="PhD", kind="reading_list")),
    (r"POLITICAL_ECONOMY_SYLLABUS_2021", dict(course_id="HARVRODRIK", label="Harvard Political Economy and its Future (Rodrik, Unger) 2021", inst="Harvard", instr="Rodrik, Unger", year=2021, level="MSc", kind="reading_list")),
    (r"gov_2755", dict(course_id="HARV2755", label="Harvard Gov 2755 Intl Political Economy (Frieden) 2020", inst="Harvard", instr="Frieden", year=2020, level="PhD", kind="reading_list")),
    (r"frieden_gov2158", dict(course_id="HARV2158", label="Harvard Gov 2158 Pol Institutions & Econ Policy (Frieden, Shepsle) 2017", inst="Harvard", instr="Frieden, Shepsle", year=2017, level="PhD", kind="reading_list")),
    (r"frieden_gov94jf", dict(course_id="HARV94JF", label="Harvard Gov 94jf PolEcon of Growth (Frieden) 2018", inst="Harvard", instr="Frieden", year=2018, level="UG", kind="reading_list")),
    (r"Foundations_of_Political_Economy", dict(course_id="PRIN584", label="Princeton POL584/ECO576 Foundations of PolEcon (Iaryczower) 2023", inst="Princeton", instr="Iaryczower", year=2023, level="PhD", kind="reading_list")),
    (r"Game_Theory_in_Politics", dict(course_id="PRIN347", label="Princeton POL347 Game Theory in Politics (Iaryczower) 2023", inst="Princeton", instr="Iaryczower", year=2023, level="UG", kind="reading_list")),
    (r"pol\.576", dict(course_id="PRIN576", label="Princeton POL576 Formal Political Analysis II (Iaryczower) 2015", inst="Princeton", instr="Iaryczower", year=2015, level="PhD", kind="reading_list")),
    (r"CEMFI_MartinezBravo_DevEcon", dict(course_id="CEMFIDEV", label="CEMFI Development Economics (Martinez-Bravo) 2020", inst="CEMFI", instr="Martinez-Bravo", year=2020, level="PhD", kind="reading_list")),
    (r"CEMFI_MartinezBravo_EmpMethods", dict(course_id="CEMFIEMP", label="CEMFI Empirical Methods for Policy (Martinez-Bravo) 2020", inst="CEMFI", instr="Martinez-Bravo", year=2020, level="MSc", kind="reading_list")),
    (r"BSE_PolEconDev_SantosSilva_WS25", dict(course_id="BSEDEV", label="Berlin SE PolEcon of Development (Santos Silva) 2025", inst="Berlin SE", instr="Santos Silva", year=2025, level="PhD", kind="reading_list")),
    (r"BSE_PolEconDev_SantosSilva_WS24", dict(course_id="BSEDEV", label="Berlin SE PolEcon of Development (Santos Silva) 2024", inst="Berlin SE", instr="Santos Silva", year=2024, level="PhD", kind="reading_list")),
    (r"FUBerlin", dict(course_id="FUBERLIN", label="FU Berlin Political Economy (Prummer, Grigoriadis) 2025", inst="FU Berlin", instr="Prummer, Grigoriadis", year=2025, level="MSc", kind="reading_list")),
    (r"IC3JM", dict(course_id="IC3JM", label="Carlos III-Juan March Political Economy (Manzano, Shin) 2024", inst="IC3JM", instr="Manzano, Shin", year=2024, level="PhD", kind="reading_list")),
    (r"Basel_Stutzer_PolEcon_Fall(\d\d)", dict(course_id="BASEL", label="Basel Political Economy (Stutzer)", inst="Basel", instr="Stutzer", year=None, level="MSc", kind="reading_list")),
    (r"Curso_EconPol_PUC-Rio_2022", dict(course_id="PUCRIO", label="PUC-Rio PolEcon of Development (Ferraz, Finan) 2022", inst="PUC-Rio", instr="Ferraz, Finan", year=2022, level="PhD", kind="reading_list")),
    (r"Curso_EconPol_PUC-Rio_2023", dict(course_id="PUCRIO", label="PUC-Rio PolEcon of Development (Ferraz, Finan) 2023", inst="PUC-Rio", instr="Ferraz, Finan", year=2023, level="PhD", kind="reading_list")),
    (r"Econ_544_Syllabus_2021", dict(course_id="UBC544", label="UBC Econ 544 PolEcon & Institutions (Ferraz) 2021", inst="UBC", instr="Ferraz", year=2021, level="PhD", kind="reading_list")),
    (r"UndergradSyllabus-Political_Economy2021", dict(course_id="UBC485", label="UBC ECON 485 Political Economy (Ferraz) 2021", inst="UBC", instr="Ferraz", year=2021, level="UG", kind="reading_list")),
    (r"UndergradSyllabus-Political_Economy2023", dict(course_id="UBC485", label="UBC ECON 485 Political Economy (Ferraz) 2023", inst="UBC", instr="Ferraz", year=2023, level="UG", kind="reading_list")),
    (r"Uniandes_Fergusson_EconPoliticaPolEcon_2018", dict(course_id="UNIANDES", label="Uniandes Economía Política (Fergusson) 2018", inst="Uniandes", instr="Fergusson", year=2018, level="UG", kind="reading_list")),
    (r"Uniandes_Fergusson_EconPoliticaPolEcon_2016", dict(course_id="UNIANDES", label="Uniandes Economía Política (Fergusson) 2016", inst="Uniandes", instr="Fergusson", year=2016, level="UG", kind="reading_list")),
    (r"Uniandes_Fergusson_EconPolitica_2014", dict(course_id="UNIANDES", label="Uniandes Economía Política (Fergusson) 2014", inst="Uniandes", instr="Fergusson", year=2014, level="UG", kind="reading_list")),
    (r"Uniandes_Fergusson_Querubin_EconPolitica_2012", dict(course_id="UNIANDES", label="Uniandes Economía Política (Fergusson, Querubín) 2012", inst="Uniandes", instr="Fergusson, Querubín", year=2012, level="UG", kind="reading_list")),
    (r"Uniandes_Fergusson_Querubin_EconPolitica_2011", dict(course_id="UNIANDES", label="Uniandes Economía Política (Fergusson, Querubín) 2011", inst="Uniandes", instr="Fergusson, Querubín", year=2011, level="UG", kind="reading_list")),
    (r"research_brief", dict(course_id="USER", label="Your research brief (Sept 2026)", inst="User", instr="Marcelo", year=2026, level="Agenda", kind="user")),
    (r"Branch_Agenda", dict(course_id="USERGPT", label="Your GPT research-agenda draft (Aug 2026)", inst="User", instr="GPT draft", year=2026, level="Agenda", kind="agenda")),
    (r"README", dict(kind="skip")),
]


def lookup(txtname):
    for pat, d in REGISTRY:
        m = re.search(pat, txtname)
        if m:
            d = dict(d)
            if d.get("course_id") == "BASEL":
                d["year"] = 2000 + int(m.group(1))
                d["label"] = f"Basel Political Economy (Stutzer) {d['year']}"
            return d
    raise KeyError(txtname)


if __name__ == "__main__":
    from pathlib import Path
    for f in sorted((Path(__file__).resolve().parents[1] / "text").glob("*.txt")):
        d = lookup(f.name)
        assert d["kind"] == "skip" or d.get("course_id"), f.name
    print("registry covers all files")
