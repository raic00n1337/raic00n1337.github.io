# -*- coding: utf-8 -*-
"""
Erzeugt aus dem Datenbestand eine statische Seite (docs/index.html) und
einen RSS-Feed (docs/feed.xml). Kein Server, kein Build-Schritt: die Daten
stecken als JSON in der Seite, gefiltert wird im Browser.
"""

import html
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import config

MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


def de_datetime(iso):
    dt = datetime.fromisoformat(iso)
    return f"{dt.day}. {MONTHS[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def de_date(iso):
    dt = datetime.fromisoformat(iso)
    return f"{dt.day}. {MONTHS[dt.month - 1]}"


def de_full(iso):
    """Vollstaendiges Veroeffentlichungsdatum mit Uhrzeit."""
    dt = datetime.fromisoformat(iso)
    return f"{dt.day}. {MONTHS[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def activity_strip(items, days=60):
    """Ein Balken je Tag: Anzahl Meldungen, eingefärbt nach Höchstscore."""
    today = datetime.now(timezone.utc).date()
    buckets = {today - timedelta(days=i): [] for i in range(days)}
    for item in items:
        day = datetime.fromisoformat(item["published"]).date()
        if day in buckets:
            buckets[day].append(item["score"])
    strip = []
    for day in sorted(buckets):
        scores = buckets[day]
        strip.append({"d": day.isoformat(), "n": len(scores),
                      "max": max(scores) if scores else 0})
    return strip


CSS = """
:root{
  --ink:#16262E; --ink-soft:#41565F; --ink-faint:#77898F;
  --paper:#E8EBEA; --surface:#FFFFFF; --rule:#C4CDCE;
  --signal:#1F6B4A; --alert:#A2352A; --watch:#8A6A15;
  --focus:#0F5C8C;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Barlow",-apple-system,"Segoe UI",sans-serif;
  font-size:16px; line-height:1.5; font-variant-numeric:tabular-nums;
}
a{color:inherit}
:focus-visible{outline:2px solid var(--focus); outline-offset:2px}
.wrap{max-width:1080px; margin:0 auto; padding:0 20px}

/* Kopfband */
.masthead{background:var(--ink); color:#EDF1F0; padding:22px 0 0}
.mast-row{display:flex; align-items:baseline; gap:16px; flex-wrap:wrap}
.mast-row>*+*{margin-left:16px}
.mast-title{
  font-family:"Barlow Condensed",sans-serif; font-weight:600;
  font-size:34px; letter-spacing:.02em; margin:0; line-height:1;
}
.mast-sub{color:#9DB1B0; font-size:15px; margin:0}
.mast-meta{margin-left:auto; font-size:14px; color:#9DB1B0; text-align:right}

/* Aktivitätsstreifen */
.pulse{display:flex; align-items:flex-end; gap:2px; height:52px; margin:18px 0 0}
.pulse i{flex:1; min-height:2px; background:#3E5761; border-radius:1px 1px 0 0; display:block}
.pulse i[data-hot="1"]{background:#C8846E}
.pulse i[data-hot="2"]{background:#E0A03F}
.pulse-legend{
  display:flex; justify-content:space-between; font-size:12.5px;
  color:#8CA1A2; padding:6px 0 16px; border-top:1px solid #2C4049; margin-top:4px;
}

/* Kennzahlen */
.figures{display:flex; gap:0; border-top:1px solid var(--rule); background:var(--surface)}
.figure{padding:14px 20px; border-right:1px solid var(--rule); flex:1}
.figure:last-child{border-right:0}
.figure b{display:block; font-size:26px; font-weight:600; line-height:1.1}
.figure span{font-size:13px; color:var(--ink-soft)}

/* Filterleiste */
.controls{
  position:sticky; top:0; z-index:5; background:var(--paper);
  border-bottom:1px solid var(--rule); padding:12px 0;
}
.controls-inner{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
.search{
  flex:1 1 220px; min-width:180px; padding:8px 11px; font:inherit; font-size:15px;
  border:1px solid var(--rule); background:var(--surface); color:var(--ink); border-radius:2px;
}
.pill{
  font:inherit; font-size:14px; padding:6px 11px; cursor:pointer; border-radius:2px;
  border:1px solid var(--rule); background:var(--surface); color:var(--ink-soft);
}
.pill[aria-pressed="true"]{background:var(--ink); border-color:var(--ink); color:#fff}
.pill em{font-style:normal; color:var(--ink-faint); margin-left:5px; font-size:12.5px}
.pill[aria-pressed="true"] em{color:#9DB1B0}
.count{font-size:14px; color:var(--ink-soft); padding:14px 0 4px}

/* Meldungen */
.feed{list-style:none; margin:0 0 40px; padding:0; background:var(--surface);
      border:1px solid var(--rule); border-radius:2px}
.entry{display:flex; gap:14px; padding:16px 18px; border-bottom:1px solid var(--rule)}
.controls-inner>*+*{margin-left:0}
.entry:last-child{border-bottom:0}
.entry[hidden]{display:none}
.gauge{width:44px; flex:0 0 44px; text-align:right; margin-right:14px}
.gauge b{font-size:19px; font-weight:600; display:block; line-height:1.1}
.gauge u{
  display:block; height:3px; margin:4px 0 0 auto; background:var(--signal);
  text-decoration:none; border-radius:2px;
}
.entry[data-band="hoch"] .gauge b{color:var(--alert)}
.entry[data-band="hoch"] .gauge u{background:var(--alert)}
.entry[data-band="mittel"] .gauge b{color:var(--watch)}
.entry[data-band="mittel"] .gauge u{background:var(--watch)}
.body{flex:1; min-width:0}
.headline{font-size:17.5px; font-weight:500; line-height:1.35; margin:0 0 4px}
.headline a{text-decoration:none}
.headline a:hover{text-decoration:underline}
.meta{font-size:13.5px; color:var(--ink-soft); margin:0 0 7px}
.cat{
  display:inline-block; padding:1px 7px; border-radius:2px; color:#fff;
  font-size:12.5px; margin-right:7px; vertical-align:1px;
}
.excerpt{font-size:14.5px; color:var(--ink-soft); margin:0}
.tags{margin:8px 0 0; font-size:13px; color:var(--ink-faint)}
.rel{color:var(--ink-faint); margin-left:7px}
.rel[data-frisch="1"]{color:var(--signal); font-weight:500}
.sortlabel{font-size:13.5px; color:var(--ink-faint); margin-left:6px}
.tags b{font-weight:600; color:var(--ink-soft)}
.verdict{
  margin:10px 0 0; padding:10px 12px; background:#F4F6F5;
  border-left:3px solid var(--signal); font-size:14.5px;
}
.verdict[data-stufe="handeln"]{border-left-color:var(--alert)}
.verdict[data-stufe="prüfen"]{border-left-color:var(--watch)}
.verdict strong{font-weight:600}
.verdict p{margin:0 0 4px}
.verdict p:last-child{margin:0}
.verdict small{color:var(--ink-faint)}

footer{padding:26px 0 46px; font-size:13.5px; color:var(--ink-soft)}
footer p{margin:0 0 6px}
.dead{color:var(--alert)}
.empty{padding:34px 18px; color:var(--ink-soft)}

@media (max-width:640px){
  .mast-title{font-size:27px}
  .mast-meta{margin-left:0; text-align:left; width:100%}
  .figures{flex-wrap:wrap}
  .figure{flex:1 0 50%; border-bottom:1px solid var(--rule)}
  .entry{padding:14px}
  .pulse{height:40px}
}
@media (prefers-reduced-motion:no-preference){
  .entry{transition:background .12s ease}
}
"""

JS = """
const DATA = JSON.parse(document.getElementById('daten').textContent);
const feed = document.getElementById('feed');
const counter = document.getElementById('counter');
const search = document.getElementById('search');
const state = {cats:new Set(), q:'', days:0, actionOnly:false, sort:'datum'};

// Relative Zeitangabe neben dem Datum, beim Laden berechnet
function relativ(iso){
  const min = Math.round((Date.now() - Date.parse(iso)) / 60000);
  if (min < 60) return ['vor ' + Math.max(1, min) + ' Min.', 1];
  const std = Math.round(min / 60);
  if (std < 24) return ['vor ' + std + (std === 1 ? ' Stunde' : ' Stunden'), 1];
  const tage = Math.round(std / 24);
  if (tage < 31) return ['vor ' + tage + (tage === 1 ? ' Tag' : ' Tagen'), tage <= 2 ? 1 : 0];
  return ['vor ' + Math.round(tage / 30) + ' Monaten', 0];
}
document.querySelectorAll('.rel').forEach(el => {
  const [text, frisch] = relativ(el.dataset.pub);
  el.textContent = '· ' + text;
  el.dataset.frisch = frisch;
});

// Sortierung: Reihenfolge im DOM umhaengen
function sortieren(){
  const rows = Array.prototype.slice.call(feed.children);
  rows.sort((a, b) => state.sort === 'datum'
    ? Date.parse(b.dataset.pub) - Date.parse(a.dataset.pub)
    : (+b.dataset.score) - (+a.dataset.score));
  const frag = document.createDocumentFragment();
  rows.forEach(r => frag.appendChild(r));
  feed.appendChild(frag);
}
document.querySelectorAll('[data-sort]').forEach(btn => {
  btn.addEventListener('click', () => {
    state.sort = btn.dataset.sort;
    document.querySelectorAll('[data-sort]').forEach(b =>
      b.setAttribute('aria-pressed', b.dataset.sort === state.sort));
    sortieren();
  });
});

function apply(){
  let shown = 0;
  const now = Date.now();
  for (const el of Array.prototype.slice.call(feed.children)){
    const d = el.dataset;
    let ok = true;
    if (state.cats.size && !state.cats.has(d.cat)) ok = false;
    if (ok && state.days && (now - Date.parse(d.pub)) > state.days*86400000) ok = false;
    if (ok && state.actionOnly && d.stufe !== 'handeln' && +d.score < 70) ok = false;
    if (ok && state.q && !d.hay.includes(state.q)) ok = false;
    el.hidden = !ok;
    if (ok) shown++;
  }
  counter.textContent = shown === DATA.total
    ? `${shown} Meldungen`
    : `${shown} von ${DATA.total} Meldungen`;
  document.getElementById('leer').hidden = shown > 0;
}

document.querySelectorAll('[data-cat-filter]').forEach(btn => {
  btn.addEventListener('click', () => {
    const cat = btn.dataset.catFilter;
    state.cats.has(cat) ? state.cats.delete(cat) : state.cats.add(cat);
    btn.setAttribute('aria-pressed', state.cats.has(cat));
    apply();
  });
});
document.querySelectorAll('[data-days]').forEach(btn => {
  btn.addEventListener('click', () => {
    const v = +btn.dataset.days;
    state.days = state.days === v ? 0 : v;
    document.querySelectorAll('[data-days]').forEach(b =>
      b.setAttribute('aria-pressed', +b.dataset.days === state.days));
    apply();
  });
});
const actionBtn = document.getElementById('nur-handlung');
actionBtn.addEventListener('click', () => {
  state.actionOnly = !state.actionOnly;
  actionBtn.setAttribute('aria-pressed', state.actionOnly);
  apply();
});
let timer;
search.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(() => { state.q = search.value.trim().toLowerCase(); apply(); }, 120);
});
sortieren();
apply();
"""


def band(score):
    if score >= 70:
        return "hoch"
    if score >= 45:
        return "mittel"
    return "niedrig"


def render_entry(item):
    cat_color = config.CATEGORIES.get(item["category"], {}).get("color", "#4A5C63")
    esc = html.escape
    hay = " ".join([item["title"], item["summary"], item["source"],
                    " ".join(item["vendors"]), " ".join(item["business_tags"])]).lower()

    meta = [esc(item["source"]),
            f'<time datetime="{item["published"]}">{de_full(item["published"])} Uhr</time>'
            f'<span class="rel" data-pub="{item["published"]}"></span>']
    if item["corroboration"] > 1:
        meta.append(f"{item['corroboration']} Quellen")

    tags = []
    if item["vendors"]:
        tags.append("<b>Akteure</b> " + esc(", ".join(item["vendors"])))
    if item["business_tags"]:
        tags.append("<b>Bezug</b> " + esc(", ".join(item["business_tags"])))

    review = ""
    r = item.get("ai_review") or item.get("verdict")
    if r:
        herkunft = ("automatisch eingeordnet nach Regelwerk"
                    if r.get("konfidenz") == "regelbasiert"
                    else f'Konfidenz {r.get("konfidenz", "mittel")} · KI-Ersteinschätzung')
        review = (
            f'<div class="verdict" data-stufe="{esc(r["einstufung"])}">'
            f'<p>{esc(r["kern"])}</p>'
            f'<p><strong>{esc(r["einstufung"].capitalize())}.</strong> {esc(r["bedeutung"])}</p>'
            f'<p><small>{herkunft}</small></p>'
            f'</div>'
        )

    return f"""<li class="entry" data-cat="{esc(item['category'])}" data-pub="{item['published']}"
    data-score="{item['score']}" data-band="{band(item['score'])}"
    data-stufe="{esc((item.get('ai_review') or item.get('verdict') or {}).get('einstufung', ''))}"
    data-hay="{esc(hay)}">
  <div class="gauge"><b>{item['score']}</b><u style="width:{max(8, item['score'])}%"></u></div>
  <div class="body">
    <p class="headline"><a href="{esc(item['link'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></p>
    <p class="meta"><span class="cat" style="background:{cat_color}">{esc(item['category'])}</span>{' · '.join(meta)}</p>
    <p class="excerpt">{esc(item['summary'][:260])}</p>
    {f'<p class="tags">{" &nbsp;|&nbsp; ".join(tags)}</p>' if tags else ''}
    {review}
  </div>
</li>"""


def render_site(store, docs_dir):
    items = sorted(store["items"], key=lambda i: (-i["score"], i["published"]))[:400]
    generated = store.get("generated", datetime.now(timezone.utc).isoformat())
    now = datetime.now(timezone.utc)

    cat_counts = Counter(i["category"] for i in items)
    week = [i for i in items if datetime.fromisoformat(i["published"]) > now - timedelta(days=7)]
    high = [i for i in items if i["score"] >= config.SCORING["alert_threshold"]]
    strip = activity_strip(items)
    peak = max((b["n"] for b in strip), default=1) or 1

    bars = "".join(
        f'<i style="height:{max(2, round(100 * b["n"] / peak))}%" '
        f'data-hot="{2 if b["max"] >= 70 else (1 if b["max"] >= 55 else 0)}" '
        f'title="{de_date(b["d"] + "T00:00:00+00:00")}: {b["n"]} Meldungen"></i>'
        for b in strip)

    cat_pills = "".join(
        f'<button class="pill" data-cat-filter="{html.escape(c)}" aria-pressed="false">'
        f'{html.escape(c)}<em>{n}</em></button>'
        for c, n in cat_counts.most_common())

    entries = "\n".join(render_entry(i) for i in items)

    problems = store.get("problems", [])
    problem_line = ""
    if problems:
        names = ", ".join(f"{html.escape(n)} ({html.escape(e)})" for n, e in problems[:6])
        problem_line = f'<p class="dead">Quellen ohne Antwort in diesem Lauf: {names}</p>'

    payload = json.dumps({"total": len(items)}).replace("</", "<\\/")

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DroneWatch – Marktbeobachtung Drohnenabwehr</title>
<meta name="description" content="Laufende Auswertung von Meldungen zu Drohnenabwehr und Counter-UAS.">
<link rel="alternate" type="application/rss+xml" title="DroneWatch" href="feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header class="masthead">
  <div class="wrap">
    <div class="mast-row">
      <h1 class="mast-title">DroneWatch</h1>
      <p class="mast-sub">Drohnenabwehr und Counter-UAS, laufend ausgewertet</p>
      <p class="mast-meta">Letzter Scan<br>{de_datetime(generated)} UTC</p>
    </div>
    <div class="pulse" role="img" aria-label="Meldungsaufkommen der letzten 60 Tage">{bars}</div>
    <p class="pulse-legend"><span>vor 60 Tagen</span><span>Meldungen pro Tag, eingefärbt nach höchster Bewertung</span><span>heute</span></p>
  </div>
</header>

<div class="wrap">
  <div class="figures">
    <div class="figure"><b>{len(week)}</b><span>neue Meldungen in 7 Tagen</span></div>
    <div class="figure"><b>{len(high)}</b><span>mit Bewertung ab {config.SCORING['alert_threshold']}</span></div>
    <div class="figure"><b>{len(items)}</b><span>im Bestand</span></div>
    <div class="figure"><b>{len(config.SOURCES) - len(problems)}</b><span>von {len(config.SOURCES)} Quellen erreichbar</span></div>
  </div>

  <div class="controls">
    <div class="controls-inner">
      <input id="search" class="search" type="search" placeholder="Volltext durchsuchen, z. B. Flughafen oder Hensoldt" aria-label="Meldungen durchsuchen">
      <button class="pill" data-days="7" aria-pressed="false">7 Tage</button>
      <button class="pill" data-days="30" aria-pressed="false">30 Tage</button>
      <button class="pill" id="nur-handlung" aria-pressed="false">Nur Handlungsbedarf</button>
      <span class="sortlabel">Sortierung</span>
      <button class="pill" data-sort="datum" aria-pressed="true">Neueste zuerst</button>
      <button class="pill" data-sort="score" aria-pressed="false">Bewertung</button>
    </div>
    <div class="controls-inner" style="margin-top:8px">{cat_pills}</div>
  </div>

  <p class="count" id="counter">{len(items)} Meldungen</p>
  <ul class="feed" id="feed">
{entries}
  </ul>
  <p class="empty" id="leer" hidden>Keine Meldung passt zu dieser Auswahl. Filter zurücksetzen oder Suchbegriff kürzen.</p>

  <footer>
    <p>Bewertung 0–100 aus Themenschärfe, Kategorie, Bezug zum eigenen Geschäft, genannten Akteuren, Quellengewicht und Aktualität. Mehrfach gemeldete Ereignisse werden zusammengefasst und höher gewichtet.</p>
    <p>Quellen und Gewichte stehen in <code>config.py</code>. <a href="feed.xml">RSS-Feed</a> für Outlook oder Teams.</p>
    {problem_line}
  </footer>
</div>

<script type="application/json" id="daten">{payload}</script>
<script>{JS}</script>
</body>
</html>"""

    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(os.path.join(docs_dir, ".nojekyll"), "w") as fh:
        fh.write("")
    _write_feed(items[:60], docs_dir, generated)


def _write_feed(items, docs_dir, generated):
    esc = html.escape
    entries = []
    for i in items:
        pub = datetime.fromisoformat(i["published"]).strftime("%a, %d %b %Y %H:%M:%S +0000")
        desc = f"[{i['score']}] {i['category']} – {i['summary'][:300]}"
        if i.get("ai_review"):
            desc += f" || Einschätzung: {i['ai_review']['bedeutung']}"
        entries.append(f"""  <item>
    <title>{esc(i['title'])}</title>
    <link>{esc(i['link'])}</link>
    <guid isPermaLink="false">{i['id']}</guid>
    <pubDate>{pub}</pubDate>
    <category>{esc(i['category'])}</category>
    <description>{esc(desc)}</description>
  </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>DroneWatch – Marktbeobachtung Drohnenabwehr</title>
  <link>./index.html</link>
  <description>Bewertete Meldungen zu Drohnenabwehr und Counter-UAS</description>
  <language>de</language>
  <lastBuildDate>{datetime.fromisoformat(generated).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
{chr(10).join(entries)}
</channel></rss>"""
    with open(os.path.join(docs_dir, "feed.xml"), "w", encoding="utf-8") as fh:
        fh.write(feed)
