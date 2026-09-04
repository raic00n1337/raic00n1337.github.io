# -*- coding: utf-8 -*-
"""
Konfiguration des DroneWatch-Scanners.

Alles, was regelmaessig angepasst wird (Quellen, Stichwoerter, Gewichte),
steht in dieser Datei. scan.py selbst muss dafuer nicht angefasst werden.
"""

# ---------------------------------------------------------------------------
# 1. QUELLEN
# ---------------------------------------------------------------------------
# weight = Vertrauens-/Qualitaetsgewicht der Quelle (0.6 - 1.3).
# Google-News-Feeds sind Meta-Quellen: sie liefern breite Abdeckung, aber
# auch Rauschen -> niedrigeres Gewicht, dafuer viele Treffer.
#
# Hinweis: Nicht jeder Feed ist dauerhaft erreichbar. `python scan.py --check`
# prueft alle Quellen und meldet tote Feeds, ohne den Lauf abzubrechen.

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def gnews(query, lang="de"):
    from urllib.parse import quote
    if lang == "de":
        return GOOGLE_NEWS.format(q=quote(query), hl="de", gl="DE", ceid="DE:de")
    return GOOGLE_NEWS.format(q=quote(query), hl="en-US", gl="US", ceid="US:en")


SOURCES = [
    # --- Meta-Suchen (breite Abdeckung, sprachlich getrennt) ---
    {"name": "Google News DE – Drohnenabwehr",
     "url": gnews('Drohnenabwehr OR "Drohnendetektion" OR "Anti-Drohnen"'), "weight": 0.85},
    {"name": "Google News DE – Drohnensichtung KRITIS",
     "url": gnews('Drohne (Flughafen OR Kraftwerk OR "kritische Infrastruktur" OR Kaserne) gesperrt OR gesichtet'),
     "weight": 0.85},
    {"name": "Google News DE – Beschaffung/Recht",
     "url": gnews('Drohnenabwehr (Bundeswehr OR Bundespolizei OR Gesetz OR Beschaffung OR Ausschreibung)'),
     "weight": 0.9},
    {"name": "Google News EN – Counter-UAS",
     "url": gnews('"counter-UAS" OR "counter-drone" OR "C-UAS"', "en"), "weight": 0.85},
    {"name": "Google News EN – C-UAS contracts",
     "url": gnews('"counter-drone" (contract OR procurement OR tender OR order)', "en"), "weight": 0.9},
    {"name": "Google News EN – Airport drone disruption",
     "url": gnews('drone airport airspace closed OR suspended', "en"), "weight": 0.8},

    # --- Fachmedien (direkte Feeds) ---
    {"name": "Unmanned Airspace", "url": "https://www.unmannedairspace.info/feed/", "weight": 1.3},
    {"name": "DroneLife", "url": "https://dronelife.com/feed/", "weight": 1.0},
    {"name": "sUAS News", "url": "https://www.suasnews.com/feed/", "weight": 1.0},
    {"name": "Breaking Defense", "url": "https://breakingdefense.com/feed/", "weight": 1.15},
    {"name": "Defense News", "url": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "weight": 1.15},
    {"name": "The Defense Post", "url": "https://thedefensepost.com/feed/", "weight": 1.0},
    {"name": "Army Recognition", "url": "https://armyrecognition.com/rss/news.xml", "weight": 0.9},
    {"name": "hartpunkt", "url": "https://www.hartpunkt.de/feed/", "weight": 1.2},
    {"name": "ESUT", "url": "https://esut.de/feed/", "weight": 1.2},
    {"name": "Militär Aktuell", "url": "https://militaeraktuell.at/feed/", "weight": 1.0},
    {"name": "Behörden Spiegel", "url": "https://www.behoerden-spiegel.de/feed/", "weight": 1.1},
    {"name": "Protector (Sicherheitstechnik)", "url": "https://www.protector.de/rss", "weight": 1.1},
    {"name": "GIT Sicherheit", "url": "https://www.git-sicherheit.de/rss.xml", "weight": 1.1},

    # --- Regulatorik / Behörden ---
    {"name": "EASA News", "url": "https://www.easa.europa.eu/en/rss/news.xml", "weight": 1.25},
    {"name": "BMI Pressemitteilungen",
     "url": "https://www.bmi.bund.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed.xml", "weight": 1.25},
    {"name": "EU Kommission – Home Affairs",
     "url": "https://home-affairs.ec.europa.eu/rss_en", "weight": 1.15},

    # --- Vergabe / Ausschreibungen ---
    {"name": "TED – EU-Ausschreibungen C-UAS",
     "url": "https://ted.europa.eu/en/simap/rss?query=counter-drone", "weight": 1.3},
    {"name": "service.bund.de – Ausschreibungen",
     "url": "https://www.service.bund.de/Content/Globals/Functions/RSSFeed/RSSGenerator.xml"
            "?nn=4641514&type=ausschreibungen&sortOrder=score+desc&f_bekanntmachungstyp=Ausschreibungen",
     "weight": 1.3},
]

# ---------------------------------------------------------------------------
# 2. THEMEN-GATE
# ---------------------------------------------------------------------------
# Ein Beitrag muss mindestens einen dieser Begriffe enthalten, sonst wird er
# verworfen. Das haelt das Rauschen aus den breiten Meta-Suchen draussen.
CORE_TERMS = [
    "drohnenabwehr", "drohnenerkennung", "drohnendetektion", "drohnenortung",
    "anti-drohne", "antidrohne", "drohnenschutz", "drohnenwall", "drohnenabwehrsystem",
    "uav-abwehr", "abwehr von drohnen", "drohnenalarm", "drohnensichtung", "drohnenvorfall",
    "counter-uas", "counter uas", "c-uas", "cuas", "counter-drone", "counter drone",
    "anti-drone", "antidrone", "drone defence", "drone defense", "drone detection",
    "drone mitigation", "drone jammer", "uas mitigation", "airspace security",
    "unbemannte luftfahrzeuge abwehr", "kamikazedrohne abwehr", "interceptor drone",
    "abfangdrohne", "drohnendetektionssystem",
]

# Begriffe, die einen Treffer sofort verwerfen (typische Fehltreffer).
STOP_TERMS = [
    "drohnenshow", "lichtshow", "drone show", "modellbau", "spielzeug",
    "drohnenaufnahmen", "luftaufnahmen", "drohnenvideo", "gewinnspiel",
]

# ---------------------------------------------------------------------------
# 3. KATEGORIEN
# ---------------------------------------------------------------------------
# Jede Kategorie hat Stichwoerter und ein Basisgewicht. Ein Beitrag kann
# mehreren Kategorien zugeordnet werden; die staerkste wird zur Hauptkategorie.
CATEGORIES = {
    "Beschaffung & Aufträge": {
        "weight": 26, "color": "#1f5f4e",
        "terms": ["auftrag", "vertrag", "beschaffung", "ausschreibung", "vergabe",
                  "rahmenvertrag", "zuschlag", "millionenauftrag", "bestellt", "order",
                  "contract", "procurement", "tender", "awarded", "framework agreement",
                  "deal worth", "selected to supply"],
    },
    "Regulatorik & Recht": {
        "weight": 24, "color": "#4a3d7a",
        "terms": ["gesetz", "gesetzentwurf", "novelle", "luftsicherheitsgesetz",
                  "luftverkehrsgesetz", "bundestag", "bundesrat", "verordnung", "richtlinie",
                  "eu-kommission", "aktionsplan", "befugnis", "zulassung", "genehmigung",
                  "regulation", "directive", "legislation", "legal framework", "easa",
                  "faa", "authority", "mandate", "rechtsgrundlage", "abschussbefugnis"],
    },
    "Technologie & Produkte": {
        "weight": 18, "color": "#1d5a7a",
        "terms": ["produkt", "vorgestellt", "launch", "neue generation", "prototyp",
                  "radar", "hochfrequenz", "jamming", "jammer", "spoofing", "laser",
                  "hpm", "richtfunk", "sensorfusion", "ki-gestützt", "machine learning",
                  "effektor", "interceptor", "netzfänger", "akustik", "rf-sensor",
                  "unveiled", "launches", "new system", "demonstrated", "trial", "erprobung"],
    },
    "Vorfälle & Lagebild": {
        "weight": 20, "color": "#8a3b2a",
        "terms": ["gesperrt", "gesichtet", "überflug", "überflogen", "vorfall", "eingedrungen",
                  "flugbetrieb eingestellt", "sichtung", "unbekannte drohne", "spionage",
                  "sabotage", "störung", "incident", "sighting", "airspace closed",
                  "suspended flights", "grounded", "intrusion", "breach", "unidentified drone"],
    },
    "Markt & Unternehmen": {
        "weight": 16, "color": "#7a5a1d",
        "terms": ["übernahme", "akquisition", "fusion", "beteiligung", "finanzierungsrunde",
                  "investition", "umsatz", "marktstudie", "marktvolumen", "wachstum",
                  "börsengang", "partnerschaft", "joint venture", "kooperation",
                  "acquisition", "merger", "funding round", "series a", "series b",
                  "revenue", "market report", "partnership", "expands"],
    },
    "Programme & Verbände": {
        "weight": 17, "color": "#3d5a3d",
        "terms": ["nato", "european sky shield", "eu-programm", "edf", "pesco", "bundeswehr",
                  "bundespolizei", "landespolizei", "programm", "initiative", "pilotprojekt",
                  "konsortium", "arbeitsgruppe", "roadmap", "strategie", "readiness 2030",
                  "rearm", "drone wall", "consortium", "task force"],
    },
}

# ---------------------------------------------------------------------------
# 4. GESCHÄFTSRELEVANZ (Securitas Technology – ziviler Integrationsmarkt)
# ---------------------------------------------------------------------------
# Zivile Schutzobjekte und Leitstellenbezug sind fuer uns wertvoller als reine
# Gefechtsfeld-Meldungen. Negative Werte daempfen, ohne auszuschliessen.
BUSINESS_RELEVANCE = {
    "kritische infrastruktur": 14, "kritis": 14, "critical infrastructure": 14,
    "flughafen": 12, "airport": 12, "verkehrsflughafen": 12,
    "rechenzentrum": 12, "data cen": 12,
    "umspannwerk": 10, "kraftwerk": 10, "power plant": 9, "substation": 9,
    "chemiepark": 10, "raffinerie": 9, "refinery": 8,
    "justizvollzug": 11, "gefängnis": 11, "prison": 10, "correctional": 10,
    "stadion": 9, "großveranstaltung": 9, "stadium": 8, "major event": 8,
    "werkschutz": 10, "betriebsgelände": 9, "industriegelände": 8,
    "perimeter": 11, "zaunanlage": 8, "freigeländeüberwachung": 10,
    "leitstelle": 12, "notrufleitstelle": 12, "control room": 10,
    "security operations cen": 11, "soc": 6,
    "videomanagement": 9, "vms": 7, "pids": 9, "sicherheitsleitsystem": 10,
    "integration": 6, "schnittstelle": 6, "onvif": 7, "milestone": 6, "genetec": 6,
    "hafen": 8, "port security": 8, "bahn": 7, "logistikzentrum": 8,
    "versicherung": 5, "haftung": 6, "liability": 5,
    "dsgvo": 7, "datenschutz": 7, "privacy": 5,
    # Daempfung: rein militaerische Gefechtsfeldthemen
    "frontlinie": -8, "front line": -8, "gefechtsfeld": -7, "battlefield": -7,
    "loitering munition": -5, "kamikaze": -4, "artillerie": -6, "artillery": -6,
    "panzer": -5, "infanterie": -6, "schützengraben": -8, "trench": -7,
}

# ---------------------------------------------------------------------------
# 5. AKTEURE
# ---------------------------------------------------------------------------
# Werden als Tags gesetzt. Wettbewerber/Partner im eigenen Zielmarkt geben
# einen kleinen Bonus, weil sie direkt beobachtungsrelevant sind.
VENDORS = {
    "Dedrone": 8, "Axon": 6, "DroneShield": 8, "Hensoldt": 8, "Rheinmetall": 7,
    "Diehl": 7, "ESG": 6, "Aaronia": 8, "Robin Radar": 8, "MyDefence": 7,
    "Fortem": 6, "D-Fend": 7, "Anduril": 6, "Elbit": 5, "Rafael": 5, "Thales": 6,
    "Leonardo": 6, "Saab": 5, "Indra": 5, "Airbus": 5, "Frequentis": 7,
    "TYTAN": 7, "Alpine Eagle": 7, "Argus Interception": 6, "Squarehead": 6,
    "Bosch": 6, "Siemens": 5, "Securiton": 7, "Telenot": 6, "Aritech": 6,
    "Ajax Systems": 5, "Genetec": 6, "Milestone": 6, "Advancis": 6,
    "QinetiQ": 5, "Chess Dynamics": 5, "Blighter": 6, "Origin Robotics": 5,
    "Skysec": 5, "Hexamite": 4, "Zen Technologies": 4,
}

# ---------------------------------------------------------------------------
# 6. SCORING-PARAMETER
# ---------------------------------------------------------------------------
SCORING = {
    "half_life_days": 12,       # Halbwertszeit der Aktualitaet
    "max_age_days": 120,        # aelter -> wird nicht mehr angezeigt
    "title_hit_multiplier": 2.0,  # Treffer in der Ueberschrift zaehlen doppelt
    "corroboration_bonus": 6,   # pro zusaetzlicher Quelle, die dasselbe meldet
    "corroboration_cap": 18,
    "dedup_threshold": 0.50,    # Jaccard-Aehnlichkeit fuer "gleiche Meldung"
    "alert_threshold": 70,      # ab hier: Meldung im Lagebild oben
}

# Optionale KI-Bewertung (Anthropic API). Nur aktiv, wenn ANTHROPIC_API_KEY gesetzt ist.
AI_REVIEW = {
    "enabled": False,   # bewusst aus: erst einschalten, wenn ein API-Key vorliegt
    "model": "claude-sonnet-5",
    "top_n": 12,                # nur die staerksten Neuzugaenge je Lauf bewerten
    "min_score": 55,
    "context": (
        "Securitas Technology Deutschland, Geschäftsbereich Sicherheitstechnik-Integration. "
        "Wir integrieren Detektions- und Sicherheitssysteme für zivile Kunden "
        "(KRITIS, Flughäfen, Rechenzentren, Industrie, Justiz) und betreiben eine eigene "
        "Notruf- und Serviceleitstelle (NSL) sowie SOC-Dienstleistungen. "
        "Wir sind kein Effektoren-Hersteller, sondern Systemintegrator und Dienstleister."
    ),
}
