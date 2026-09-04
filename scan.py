#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroneWatch – Marktbeobachtung Drohnenabwehr / Counter-UAS

Ablauf eines Laufs:
  1. Alle Feeds aus config.SOURCES abrufen (parallel, fehlertolerant)
  2. Themen-Gate: nur Beiträge mit einschlägigen Begriffen behalten
  3. Bewerten: Kategorie, Geschäftsrelevanz, Akteure, Aktualität -> Score 0..100
  4. Deduplizieren: gleiche Meldung aus mehreren Quellen zusammenführen
     (mehrfache Berichterstattung erhöht den Score statt die Liste zu fluten)
  5. Mit dem bestehenden Bestand (data/items.json) zusammenführen
  6. Optional: die stärksten Neuzugänge per Anthropic API kurz bewerten lassen
  7. docs/index.html + docs/feed.xml + data/items.json schreiben

Aufrufe:
  python scan.py            normaler Lauf
  python scan.py --check    nur Quellen auf Erreichbarkeit prüfen
  python scan.py --no-ai    Lauf ohne KI-Bewertung
"""

import concurrent.futures as futures
from collections import Counter
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import feedparser

import config
from render import render_site

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
STORE = os.path.join(DATA_DIR, "items.json")

USER_AGENT = ("Mozilla/5.0 (compatible; DroneWatch/1.0; "
              "Marktbeobachtung Counter-UAS)")

WORD_RE = re.compile(r"[a-zäöüß0-9\-]+", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")

# Deutsche/englische Füllwörter, die beim Dedup-Vergleich nichts beitragen.
NOISE_WORDS = {
    "der", "die", "das", "und", "oder", "von", "mit", "für", "auf", "bei", "aus",
    "dem", "den", "des", "ein", "eine", "einen", "einem", "einer", "im", "in",
    "zu", "zum", "zur", "ist", "sind", "wird", "werden", "nach", "über", "vor",
    "the", "and", "for", "with", "from", "that", "this", "will", "has", "have",
    "its", "new", "says", "said", "after", "over", "into", "amid", "more",
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def clean(text):
    """HTML entfernen, Whitespace normalisieren."""
    if not text:
        return ""
    text = TAG_RE.sub(" ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


def tokens(text):
    return {w for w in WORD_RE.findall(text.lower()) if len(w) > 3 and w not in NOISE_WORDS}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap(a, b):
    """Überlappungsquote: wie viel der kürzeren Menge steckt in der längeren."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def entry_date(entry):
    """Veröffentlichungsdatum robust ermitteln, Fallback auf jetzt."""
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)


def item_id(link, title):
    base = (link or "") + "|" + (title or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def strip_gnews_suffix(title):
    """Google News hängt ' - Quellenname' an die Überschrift."""
    return re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip()


_PATTERNS = {}


def pattern(term):
    """
    Stichwortmuster mit linker Wortgrenze. Rechts bleibt offen, damit deutsche
    Komposita greifen ("Drohnenabwehr" findet auch "Drohnenabwehrsystem").
    Kurze Begriffe (SOC, HPM, FAA) bekommen zusätzlich eine rechte Grenze,
    sonst treffen sie in "Society" oder "Association".
    """
    if term not in _PATTERNS:
        t = re.escape(term.lower())
        right = r"(?![\wäöüß])" if len(term) <= 4 else ""
        _PATTERNS[term] = re.compile(r"(?<![\wäöüß])" + t + right)
    return _PATTERNS[term]


def count_hits(haystack_title, haystack_body, terms):
    """Zählt Treffer; Treffer in der Überschrift zählen stärker."""
    hits, matched = 0.0, []
    mult = config.SCORING["title_hit_multiplier"]
    for term in terms:
        pat = pattern(term)
        in_title = bool(pat.search(haystack_title))
        in_body = bool(pat.search(haystack_body))
        if in_title or in_body:
            matched.append(term)
            hits += mult if in_title else 1.0
    return hits, matched


# ---------------------------------------------------------------------------
# 1. Feeds abrufen
# ---------------------------------------------------------------------------

def fetch_source(source):
    """Einen Feed abrufen. Gibt (source, entries, fehler) zurück."""
    try:
        parsed = feedparser.parse(
            source["url"],
            agent=USER_AGENT,
            request_headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"},
        )
        status = getattr(parsed, "status", None)
        if parsed.bozo and not parsed.entries:
            return source, [], f"nicht lesbar ({type(parsed.bozo_exception).__name__})"
        if status and status >= 400:
            return source, [], f"HTTP {status}"
        if not parsed.entries:
            return source, [], "keine Einträge"
        return source, parsed.entries, None
    except Exception as exc:  # Ein toter Feed darf den Lauf nie stoppen
        return source, [], f"{type(exc).__name__}: {exc}"


def fetch_all(sources):
    results, problems = [], []
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        for source, entries, error in pool.map(fetch_source, sources):
            if error:
                problems.append((source["name"], error))
                print(f"  !  {source['name']}: {error}", file=sys.stderr)
            else:
                print(f"  ok {source['name']}: {len(entries)} Einträge")
                results.append((source, entries))
    return results, problems


# ---------------------------------------------------------------------------
# 2./3. Filtern und bewerten
# ---------------------------------------------------------------------------

def evaluate(entry, source, now):
    """Prüft Themenrelevanz und berechnet den Score. None = verworfen."""
    title = clean(entry.get("title", ""))
    if not title:
        return None
    title = strip_gnews_suffix(title)
    summary = clean(entry.get("summary", "") or entry.get("description", ""))[:1200]
    link = entry.get("link", "")

    lt, lb = title.lower(), summary.lower()
    blob = lt + " " + lb

    # Ausschluss offensichtlicher Fehltreffer
    if any(pattern(s).search(blob) for s in config.STOP_TERMS):
        return None

    # Themen-Gate
    core_hits, core_matched = count_hits(lt, lb, config.CORE_TERMS)
    if core_hits == 0:
        return None

    published = entry_date(entry)
    age_days = max(0.0, (now - published).total_seconds() / 86400)
    if age_days > config.SCORING["max_age_days"]:
        return None

    # --- Kategorien ---
    cat_scores, matched_terms = {}, []
    for name, cfg in config.CATEGORIES.items():
        hits, matched = count_hits(lt, lb, cfg["terms"])
        if hits:
            cat_scores[name] = cfg["weight"] * min(1.0, 0.45 + 0.18 * hits)
            matched_terms.extend(matched[:3])
    if cat_scores:
        primary = max(cat_scores, key=cat_scores.get)
        category_points = sum(sorted(cat_scores.values(), reverse=True)[:2])
    else:
        primary = "Sonstiges"
        category_points = 8.0

    # --- Geschäftsrelevanz ---
    business_points, business_tags = 0.0, []
    for term, value in config.BUSINESS_RELEVANCE.items():
        pat = pattern(term)
        if pat.search(blob):
            business_points += value * (1.4 if pat.search(lt) else 1.0)
            if value > 0:
                business_tags.append(term)
    business_points = max(-25.0, min(38.0, business_points))

    # --- Akteure ---
    vendor_points, vendors = 0.0, []
    for vendor, value in config.VENDORS.items():
        if pattern(vendor).search(blob):
            vendors.append(vendor)
            vendor_points += value
    vendor_points = min(20.0, vendor_points)

    # --- Themenschärfe und Aktualität ---
    core_points = min(22.0, 7.0 * core_hits)
    half_life = config.SCORING["half_life_days"]
    recency = 0.5 ** (age_days / half_life)

    raw = (core_points + category_points + business_points + vendor_points)
    score = raw * source["weight"] * (0.55 + 0.45 * recency)

    return {
        "id": item_id(link, title),
        "title": title,
        "summary": summary[:400],
        "link": link,
        "source": source["name"],
        "source_weight": source["weight"],
        "published": published.isoformat(),
        "category": primary,
        "categories": sorted(cat_scores, key=cat_scores.get, reverse=True),
        "vendors": sorted(set(vendors)),
        "business_tags": sorted(set(business_tags))[:6],
        "signals": sorted(set(matched_terms))[:6],
        "core_terms": sorted(set(core_matched))[:4],
        "score_raw": round(score, 2),
        "score": max(1, min(100, round(score))),
        "corroboration": 1,
        "also_in": [],
        "first_seen": datetime.now(timezone.utc).isoformat(),
        "ai_review": None,
    }


# ---------------------------------------------------------------------------
# 4. Deduplizieren
# ---------------------------------------------------------------------------

def deduplicate(items):
    """
    Führt Meldungen zusammen, die dasselbe Ereignis beschreiben.
    Mehrfachberichterstattung erhöht den Score (Bestätigung), statt die
    Liste mit Dubletten zu füllen.
    """
    threshold = config.SCORING["dedup_threshold"]
    bonus = config.SCORING["corroboration_bonus"]
    cap = config.SCORING["corroboration_cap"]

    items = sorted(items, key=lambda i: (-i["score_raw"], i["title"]))
    kept, fingerprints = [], []

    for item in items:
        fp = tokens(item["title"])
        merged = False
        for idx, existing_fp in enumerate(fingerprints):
            lead_item = kept[idx]
            same_link = lead_item["link"] and lead_item["link"] == item["link"]
            # Jaccard ist bei deutschen Komposita streng ("Drohnendetektion" vs.
            # "Drohnenabwehr"). Deshalb greift zusätzlich die Überlappungsquote,
            # wenn Kategorie und Zeitpunkt ebenfalls zusammenpassen.
            near = (overlap(fp, existing_fp) >= 0.6
                    and lead_item["category"] == item["category"]
                    and abs((datetime.fromisoformat(lead_item["published"])
                             - datetime.fromisoformat(item["published"])).days) <= 4)
            if same_link or jaccard(fp, existing_fp) >= threshold or near:
                lead = lead_item
                lead["corroboration"] += 1
                if item["source"] not in lead["also_in"] and item["source"] != lead["source"]:
                    lead["also_in"].append(item["source"])
                lead["vendors"] = sorted(set(lead["vendors"]) | set(item["vendors"]))
                lead["business_tags"] = sorted(set(lead["business_tags"]) | set(item["business_tags"]))[:6]
                extra = min(cap, bonus * (lead["corroboration"] - 1))
                lead["score"] = max(1, min(100, round(lead["score_raw"] + extra)))
                merged = True
                break
        if not merged:
            kept.append(item)
            fingerprints.append(fp)
    return kept


# ---------------------------------------------------------------------------
# 5. Bestand pflegen
# ---------------------------------------------------------------------------

def load_store():
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                pass
    return {"items": [], "runs": []}


def merge_store(store, fresh, now):
    """Neue Beiträge einpflegen, bekannte aktualisieren, alte ausmustern."""
    by_id = {i["id"]: i for i in store.get("items", [])}
    new_ids = []

    for item in fresh:
        if item["id"] in by_id:
            old = by_id[item["id"]]
            old["score"] = item["score"]
            old["score_raw"] = item["score_raw"]
            old["corroboration"] = max(old.get("corroboration", 1), item["corroboration"])
            old["also_in"] = sorted(set(old.get("also_in", [])) | set(item["also_in"]))
        else:
            by_id[item["id"]] = item
            new_ids.append(item["id"])

    cutoff = now - timedelta(days=config.SCORING["max_age_days"])
    items = [i for i in by_id.values()
             if datetime.fromisoformat(i["published"]) >= cutoff]
    items.sort(key=lambda i: (i["published"], i["score"]), reverse=True)

    store["items"] = items
    store.setdefault("runs", []).append({
        "at": now.isoformat(), "found": len(fresh), "new": len(new_ids),
    })
    store["runs"] = store["runs"][-200:]
    return store, new_ids


# ---------------------------------------------------------------------------
# 6. Optionale KI-Bewertung
# ---------------------------------------------------------------------------

def local_verdict(item):
    """
    Einordnung ohne API: leitet Einstufung und Begründung aus den Signalen ab,
    die beim Bewerten ohnehin erkannt wurden. Deterministisch, kostenlos,
    nachvollziehbar — jede Aussage lässt sich auf eine Regel zurückführen.
    """
    score = item["score"]
    cat = item["category"]
    biz = item.get("business_tags", [])
    vendors = item.get("vendors", [])
    sources = item.get("corroboration", 1)

    entscheidend = cat in ("Beschaffung & Aufträge", "Regulatorik & Recht")

    if score >= 90 or (score >= 70 and entscheidend and biz):
        stufe = "handeln"
    elif score >= 52 or (score >= 42 and biz and entscheidend):
        stufe = "prüfen"
    else:
        stufe = "beobachten"

    # Begründung aus den tatsächlich getroffenen Merkmalen zusammensetzen
    teile = []
    if biz:
        teile.append("ziviler Objektbezug: " + ", ".join(biz[:3]))
    else:
        teile.append("kein erkennbarer Bezug zu unseren Schutzobjekten")
    if vendors:
        teile.append(("Wettbewerber genannt: " if len(vendors) > 1 else "Akteur genannt: ")
                     + ", ".join(vendors[:3]))
    if sources > 1:
        teile.append(f"von {sources} Quellen gemeldet")

    hinweis = {
        "Beschaffung & Aufträge": "Vergabeunterlagen und Losschnitt ansehen, "
                                  "falls das Segment zu uns passt.",
        "Regulatorik & Recht": "Auf Auswirkungen für Betreiberpflichten und "
                               "Leistungsbeschreibungen prüfen.",
        "Vorfälle & Lagebild": "Als Argument in der Kundenansprache verwendbar.",
        "Technologie & Produkte": "Gegen unser Portfolio und die Integrierbarkeit halten.",
        "Markt & Unternehmen": "Wettbewerbsbild aktualisieren.",
        "Programme & Verbände": "Auf Anschlussmöglichkeiten und Fristen achten.",
    }.get(cat, "Ohne konkreten Anschlusspunkt.")

    return {
        "kern": cat + " – " + "; ".join(teile) + ".",
        "bedeutung": hinweis if stufe != "beobachten" else "Kein Handlungsbedarf erkennbar.",
        "einstufung": stufe,
        "konfidenz": "regelbasiert",
    }


def ai_review(items):
    """
    Lässt die stärksten Neuzugänge kurz einschätzen: Kernaussage plus
    Bedeutung für das eigene Geschäft. Ohne API-Key passiert nichts,
    der Rest des Laufs bleibt davon unberührt.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    cfg = config.AI_REVIEW
    if not key or not cfg["enabled"] or not items:
        return 0

    try:
        import urllib.request
    except ImportError:
        return 0

    todo = [i for i in items
            if i.get("ai_review") is None and i["score"] >= cfg["min_score"]]
    todo = sorted(todo, key=lambda i: -i["score"])[:cfg["top_n"]]
    if not todo:
        return 0

    listing = "\n\n".join(
        f"[{n}] {i['title']}\nQuelle: {i['source']} | Kategorie: {i['category']}\n{i['summary'][:300]}"
        for n, i in enumerate(todo, 1)
    )
    prompt = (
        f"Kontext des Lesers: {cfg['context']}\n\n"
        "Bewerte die folgenden Meldungen aus dem Bereich Drohnenabwehr/Counter-UAS. "
        "Antworte ausschließlich mit einem JSON-Array, ohne Markdown und ohne Vorrede. "
        "Ein Objekt je Meldung, in derselben Reihenfolge, mit den Feldern:\n"
        '  "n": Nummer der Meldung,\n'
        '  "kern": ein Satz, worum es sachlich geht,\n'
        '  "bedeutung": ein bis zwei Sätze, was das konkret für den Leser bedeutet '
        "(Chance, Risiko, Wettbewerb, Regulatorik, kein Handlungsbedarf),\n"
        '  "einstufung": genau eines von "beobachten", "prüfen", "handeln",\n'
        '  "konfidenz": "hoch", "mittel" oder "niedrig" – wie belastbar die Quelle wirkt.\n'
        "Sei nüchtern. Wenn eine Meldung für den Leser irrelevant ist, sage das klar.\n\n"
        f"Meldungen:\n{listing}"
    )

    body = json.dumps({
        "model": cfg["model"],
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in payload.get("content", []))
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        verdicts = json.loads(text)
    except Exception as exc:
        print(f"  !  KI-Bewertung übersprungen: {exc}", file=sys.stderr)
        return 0

    applied = 0
    for verdict in verdicts:
        try:
            item = todo[int(verdict["n"]) - 1]
        except (KeyError, ValueError, IndexError):
            continue
        item["ai_review"] = {
            "kern": verdict.get("kern", ""),
            "bedeutung": verdict.get("bedeutung", ""),
            "einstufung": verdict.get("einstufung", "beobachten"),
            "konfidenz": verdict.get("konfidenz", "mittel"),
        }
        if item["ai_review"]["einstufung"] == "handeln":
            item["score"] = min(100, item["score"] + 8)
        elif item["ai_review"]["einstufung"] == "prüfen":
            item["score"] = min(100, item["score"] + 3)
        applied += 1
    return applied


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------

def check_sources():
    print("Quellenprüfung\n" + "-" * 60)
    ok = 0
    for source, entries, error in map(fetch_source, config.SOURCES):
        if error:
            print(f"  FEHLER  {source['name']:<42} {error}")
        else:
            ok += 1
            print(f"  ok      {source['name']:<42} {len(entries)} Einträge")
    print("-" * 60)
    print(f"{ok} von {len(config.SOURCES)} Quellen erreichbar.")
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if "--check" in args:
        return check_sources()

    now = datetime.now(timezone.utc)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    print(f"DroneWatch-Lauf {now:%d.%m.%Y %H:%M} UTC")
    print(f"Quellen abrufen ({len(config.SOURCES)}) …")
    feeds, problems = fetch_all(config.SOURCES)

    scored = []
    for source, entries in feeds:
        for entry in entries:
            item = evaluate(entry, source, now)
            if item:
                scored.append(item)
    print(f"Themenrelevant: {len(scored)} Beiträge")

    scored = deduplicate(scored)
    print(f"Nach Zusammenführung: {len(scored)} Meldungen")

    store = load_store()
    store, new_ids = merge_store(store, scored, now)
    print(f"Neu im Bestand: {len(new_ids)} | Gesamt: {len(store['items'])}")

    # Regelbasierte Einordnung: laeuft immer, kostet nichts, wird bei jedem
    # Lauf neu berechnet (Scores aendern sich mit dem Alter).
    for item in store["items"]:
        item["verdict"] = local_verdict(item)
    print("Einordnung: " + ", ".join(
        f"{n}x {s}" for s, n in Counter(
            i["verdict"]["einstufung"] for i in store["items"]).most_common()))

    # Optionaler Zusatz, nur wenn ein API-Key hinterlegt ist.
    if "--no-ai" not in args:
        fresh_items = [i for i in store["items"] if i["id"] in new_ids]
        reviewed = ai_review(fresh_items)
        if reviewed:
            print(f"KI-Bewertung: {reviewed} Meldungen zusaetzlich eingeschaetzt")

    store["generated"] = now.isoformat()
    store["problems"] = problems
    with open(STORE, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=1)

    render_site(store, DOCS_DIR)
    print(f"Webseite geschrieben: {os.path.join(DOCS_DIR, 'index.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
