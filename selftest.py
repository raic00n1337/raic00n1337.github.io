# -*- coding: utf-8 -*-
"""Trockenlauf ohne Netz: prüft Gate, Scoring, Dedup und Rendering."""
import json
from datetime import datetime, timedelta, timezone

import config
import scan
from render import render_site

now = datetime.now(timezone.utc)


def e(title, summary, days=1):
    d = now - timedelta(days=days)
    return {"title": title, "summary": summary, "link": "https://example.org/" + str(abs(hash(title))),
            "published_parsed": d.timetuple()}


SRC_A = {"name": "Unmanned Airspace", "url": "", "weight": 1.3}
SRC_B = {"name": "Google News DE – Drohnenabwehr", "url": "", "weight": 0.85}
SRC_C = {"name": "hartpunkt", "url": "", "weight": 1.2}

samples = [
    (SRC_A, e("Frankfurt Airport awards counter-UAS detection contract to Dedrone",
              "The airport operator has signed a framework agreement for drone detection covering critical infrastructure perimeter surveillance and control room integration.", 2)),
    (SRC_B, e("Flughafen Frankfurt vergibt Auftrag für Drohnenabwehr an Dedrone",
              "Der Betreiber hat einen Rahmenvertrag zur Drohnendetektion geschlossen. Die Anbindung erfolgt an die bestehende Leitstelle.", 2)),
    (SRC_C, e("Bundestag berät Novelle des Luftsicherheitsgesetzes zur Drohnenabwehr",
              "Der Gesetzentwurf regelt Befugnisse der Bundespolizei bei der Abwehr von Drohnen über kritischer Infrastruktur.", 4)),
    (SRC_A, e("Hensoldt unveils new C-UAS radar for critical infrastructure",
              "The sensor combines radar and RF detection with AI classification, aimed at data centre and power plant operators.", 6)),
    (SRC_B, e("Drohnensichtung über Kraftwerk: Flugbetrieb kurzzeitig gestört",
              "Unbekannte Drohne über dem Gelände gesichtet, Polizei ermittelt. Drohnenabwehr war nicht im Einsatz.", 1)),
    (SRC_C, e("Ukrainische Einheiten melden Abfangdrohne gegen Shahed an der Frontlinie",
              "Im Gefechtsfeld bei Charkiw wurden Interceptor-Drohnen gegen Kamikazedrohnen eingesetzt.", 3)),
    (SRC_B, e("Spektakuläre Drohnenshow zum Stadtfest",
              "Über 300 Drohnen zeichneten Figuren in den Himmel.", 1)),
    (SRC_B, e("Neues Rathaus wird saniert", "Die Arbeiten beginnen im Herbst.", 1)),
    (SRC_A, e("DroneShield reports record revenue amid European counter-drone demand",
              "The company expands manufacturing in the EU as procurement programmes accelerate.", 12)),
    (SRC_A, e("Alte Meldung zur Drohnenabwehr", "Counter-UAS Rückblick.", 200)),
    (SRC_C, e("Flughafen Frankfurt beauftragt Dedrone mit Drohnendetektion",
              "Rahmenvertrag für Drohnenabwehr am Flughafen, Anbindung an die Leitstelle vorgesehen.", 2)),
    (SRC_B, e("Bericht: Industrieanlage bestellt Sensoren, Drohnenabwehr im Fokus",
              "Ein Industriebetrieb ordert Radar für die Freigeländeüberwachung. Trial an einem Standort läuft.", 5)),
]

scored = [x for x in (scan.evaluate(entry, src, now) for src, entry in samples) if x]
print(f"Gate: {len(scored)} von {len(samples)} Beiträgen relevant")
for i in sorted(scored, key=lambda i: -i["score"]):
    print(f"  {i['score']:3d}  {i['category']:<24} {i['title'][:62]}")

merged = scan.deduplicate(scored)
print(f"\nNach Dedup: {len(merged)} Meldungen")
for i in merged:
    if i["corroboration"] > 1:
        print(f"  zusammengeführt ({i['corroboration']} Quellen, Score {i['score']}): {i['title'][:60]}")

for i in merged:
    i["verdict"] = scan.local_verdict(i)
print("\nEinordnung:")
for i in merged:
    print(f"  {i['verdict']['einstufung']:<11} {i['score']:3d}  {i['title'][:52]}")
    print(f"              {i['verdict']['kern'][:96]}")

store = {"items": merged, "generated": now.isoformat(),
         "problems": [("TED – EU-Ausschreibungen C-UAS", "HTTP 404")]}
render_site(store, "docs")
print("\ndocs/index.html geschrieben")
print(json.dumps(merged[0], ensure_ascii=False, indent=1)[:500])
