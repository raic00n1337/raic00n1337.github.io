# DroneWatch

Laufende Beobachtung des Marktes für Drohnenabwehr / Counter-UAS. Das Skript
zieht rund zwei Dutzend Quellen, filtert das Thema heraus, bewertet jede
Meldung nach Relevanz für den zivilen Sicherheitstechnik-Markt und erzeugt
daraus eine statische Webseite plus RSS-Feed.

Kein Server, keine Datenbank, kein Build-Werkzeug. Ein Python-Skript, das
HTML schreibt.

---

## Einrichtung auf GitHub Pages (ca. 10 Minuten)

1. Neues Repository anlegen, den Inhalt dieses Ordners hineinlegen, pushen.
2. **Settings → Pages → Source** auf `GitHub Actions` stellen.
3. **Settings → Actions → General → Workflow permissions** auf
   `Read and write permissions` stellen.
4. Optional für die KI-Ersteinschätzung:
   **Settings → Secrets and variables → Actions → New repository secret**,
   Name `ANTHROPIC_API_KEY`.
5. Reiter **Actions → DroneWatch Scan → Run workflow**.

Danach läuft der Scan werktags stündlich. Die Seite liegt unter
`https://<konto>.github.io/<repository>/`.

Soll die Seite nicht öffentlich sein: Repository privat lassen und Pages auf
`Private` stellen (setzt GitHub Enterprise voraus). Alternative ohne
Enterprise: Ergebnis nur als RSS in Outlook einbinden oder das Skript intern
laufen lassen (siehe unten).

## Betrieb im Haus statt bei GitHub

Das Skript ist bewusst anspruchslos. Auf einem beliebigen Windows- oder
Linux-Rechner mit Python 3.11+:

```
pip install -r requirements.txt
python scan.py
```

`docs/` danach auf einen internen Webserver oder eine Dateifreigabe legen.
`index.html` funktioniert auch direkt per Doppelklick, ohne Webserver.
Als Zeitplan reicht die Windows-Aufgabenplanung oder ein Cron-Eintrag.

## Nützliche Aufrufe

| Befehl | Zweck |
|---|---|
| `python scan.py` | normaler Lauf |
| `python scan.py --check` | prüft alle Quellen auf Erreichbarkeit |
| `python scan.py --no-ai` | Lauf ohne KI-Bewertung |
| `python selftest.py` | Trockenlauf mit Beispieldaten, ohne Netz |

`--check` ist der Befehl für den Monatsanfang: Feeds ziehen um, Betreiber
schalten sie ab. Tote Quellen brechen den Lauf nicht ab, sie werden auf der
Seite unten protokolliert.

---

## Wie die Bewertung zustande kommt

Jede Meldung durchläuft fünf Schritte:

**1. Themen-Gate.** Ohne einen Begriff aus `CORE_TERMS` (Drohnenabwehr,
Counter-UAS, Drohnendetektion, C-UAS …) fliegt der Beitrag raus. Das ist
nötig, weil die Google-News-Quellen breit gestellt sind. `STOP_TERMS` wirft
zusätzlich die üblichen Fehltreffer weg (Drohnenshows, Luftaufnahmen).

**2. Kategorie.** Sechs Kategorien mit eigenen Stichwortlisten und
Basisgewichten. Beschaffung und Regulatorik zählen am meisten, weil dort die
Marktbewegung sichtbar wird, bevor Produkte erscheinen.

**3. Geschäftsrelevanz.** Der Teil, der die Auswertung erst brauchbar macht.
Meldungen mit zivilem Schutzobjekt (KRITIS, Flughafen, Rechenzentrum, JVA,
Perimeter, Leitstellenanbindung) bekommen Aufschlag; reine Gefechtsfeldthemen
werden gedämpft. Der Militärmarkt verschwindet damit nicht, rutscht aber nach
unten. Alle Werte stehen in `BUSINESS_RELEVANCE` und sind einzeln anpassbar.

**4. Akteure.** Nennungen aus `VENDORS` werden als Tag gesetzt und geben einen
kleinen Aufschlag. Wettbewerber, Hersteller und Integrationspartner an einer
Stelle pflegen.

**5. Aktualität und Quellengewicht.** Halbwertszeit 12 Tage, dazu ein
Vertrauensfaktor je Quelle (Fachmedien 1,2–1,3, Meta-Suchen 0,85).

Anschließend werden Meldungen zum selben Ereignis zusammengeführt. Berichten
mehrere Quellen darüber, steigt der Score, statt dass die Liste zuläuft.

Stichwörter werden mit linker Wortgrenze gesucht, rechts offen. Damit findet
„Drohnenabwehr" auch „Drohnenabwehrsystem", aber „order" nicht mehr „border".

### Bekannte Grenze

Deutsche und englische Berichte über dasselbe Ereignis werden nicht
zusammengeführt, weil der Vergleich auf Wortebene arbeitet. In der Praxis ist
das eher nützlich (man sieht, ob ein Thema nur national läuft). Wer es anders
will, setzt in `config.SCORING` die Schwelle herunter oder ergänzt eine
Übersetzungsstufe.

## Was angepasst werden sollte

Alles Fachliche steht in `config.py`, `scan.py` bleibt unangetastet:

- **Quellen**: `SOURCES` — Fachdienste, Verbandsnewsletter, Vergabeportale
  ergänzen. Jede Quelle mit realistischem Gewicht.
- **Suchbegriffe**: die `gnews(...)`-Zeilen sind normale Google-Suchen und
  lassen sich beliebig verschärfen.
- **Geschäftsrelevanz**: `BUSINESS_RELEVANCE` an die eigenen Zielsegmente
  anpassen. Das ist die Stellschraube mit dem größten Effekt.
- **Schwelle für „Handlungsbedarf"**: `SCORING["alert_threshold"]`.

Nach zwei Wochen Betrieb lohnt ein Blick in `data/items.json`: Was oben steht
und nicht oben stehen sollte, zeigt, welches Gewicht falsch sitzt.

## Einordnung der Meldungen

Jede Meldung bekommt eine Einstufung *beobachten / prüfen / handeln* samt
Begründung. Das läuft lokal im Skript, kostet nichts und braucht kein Konto:

- **handeln** ab Score 90, oder ab 70 wenn es um Beschaffung oder Regulatorik
  geht *und* ein ziviles Schutzobjekt genannt ist.
- **prüfen** ab Score 52, oder ab 42 bei Beschaffung/Regulatorik mit Objektbezug.
- **beobachten** sonst.

Die Begründung nennt die Merkmale, die tatsächlich getroffen haben — Objektbezug,
genannte Akteure, Anzahl der Quellen. Damit ist jede Einstufung nachvollziehbar
und im Zweifel gegenüber dem Chef begründbar. Die Schwellen stehen in
`local_verdict()` in `scan.py`.

## Optional: zusätzliche KI-Einschätzung

In `config.py` steht `AI_REVIEW["enabled"] = False`. So bleibt der Betrieb
kostenlos. Wer später doch eine ausformulierte Einschätzung möchte, setzt den
Wert auf `True` und hinterlegt einen API-Key (siehe unten). Die regelbasierte
Einordnung läuft weiter, die KI-Fassung kommt nur bei den stärksten Neuzugängen
zusätzlich dazu.

Kostenloser Zwischenweg: einmal pro Woche die `feed.xml` oder die Top-Meldungen
von der Seite kopieren und in einer Claude-Unterhaltung bewerten lassen. Das
läuft über ein vorhandenes Abo statt über die API.

## Dateien

```
scan.py       Abruf, Filterung, Bewertung, Zusammenführung
config.py     Quellen, Stichwörter, Gewichte  ← hier wird gepflegt
render.py     erzeugt docs/index.html und docs/feed.xml
selftest.py   Trockenlauf mit Beispielmeldungen
data/         Datenbestand, wächst mit jedem Lauf
docs/         die veröffentlichte Seite
```

## API-Key besorgen und hinterlegen (nur für den optionalen Zusatz)

1. Konto auf https://console.anthropic.com anlegen (geschäftliche Adresse).
2. Unter **Billing** ein Guthaben aufladen — ohne Guthaben liefert die API
   einen Fehler, der Scan läuft dann ohne Einschätzung weiter.
3. Unter **API keys → Create Key** einen Schlüssel erzeugen und sofort
   kopieren. Er wird nur einmal angezeigt.
4. Hinterlegen — **niemals in `config.py` oder ins Repository**:
   - GitHub: *Settings → Secrets and variables → Actions → New repository
     secret*, Name exakt `ANTHROPIC_API_KEY`.
   - Lokal unter Windows: `setx ANTHROPIC_API_KEY "sk-ant-..."`, danach ein
     neues Terminalfenster öffnen.
   - Lokal unter Linux/macOS: `export ANTHROPIC_API_KEY="sk-ant-..."` in
     `~/.bashrc` bzw. `~/.zshrc`.

Das Skript liest den Schlüssel aus der Umgebungsvariable. Fehlt er, wird die
KI-Bewertung stillschweigend übersprungen; alles andere funktioniert.
