"""Erzeugt die deutsche Ergebnisseite fuers Team aus results/top_sites.json.
Aufruf: python web/make_results_page.py results/top_sites.json web/ergebnisse.html"""
import collections
import html
import json
import sys

src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
T = d["targets"]
esc = html.escape

DIM = dict(gelaende="Gelände", oberflaeche="Material", thermik="Temperatur", trockenheit="Trockenheit",
           atmosphaere="Atmosphäre", staub_wind="Staub & Wind", eis_wasser="Eis", leben="Vegetation",
           beleuchtung="Beleuchtung")
FLAG = dict(staubquelle="Staubquelle", staubsturmreich="staubsturmreich", windsturmreich="sturmreich",
            windstill="windstill", frost_tau="Frost-Tau", extrem_kalt="extrem kalt", niedriger_druck="niedriger Druck",
            dunkle_oberflaeche="dunkle Oberfläche", landefreundlich="landefreundlich", polar="polar")
CLS = {"Duenenfeld / Sandmeer": "Dünenfeld / Sandmeer", "Eisfreie kalte Polarwueste": "Eisfreie kalte Polarwüste",
       "Hyperaride Wueste": "Hyperaride Wüste", "Aride Wueste / Halbwueste": "Aride Wüste / Halbwüste"}
CN = {"CHN", "HKG", "MAC"}
de = lambda n: f"{n:,}".replace(",", ".")
mio = lambda n: f"{n / 1e6:.1f}".replace(".", ",") + " Mio."


def rank(s):
    return f"Platz {de(s['cell_rank'])}" if s.get("cell_rank") else f"{s['better_than_pct']:.2f} %"


def stats(body):
    ts = [t for t in T.values() if t["body"] == body]
    top = [x for t in ts for x in t["top"]]
    cn = sum(1 for x in top if x.get("country_iso") in CN or "verwaltet: Volksrepublik China" in (x.get("country") or ""))
    cx = collections.Counter(x["country"] for t in ts for x in t["excl_china"])
    c = collections.Counter(x["country"] for x in top)
    cls_ = collections.Counter(x["env_class"] for x in top)
    return dict(n=len(ts), top=len(top), cn=cn, c=c, cx=cx, cls=cls_, uniq=len({(x["lat"], x["lon"]) for x in top}),
                new=(min(t["n_new_in_top"] for t in ts), max(t["n_new_in_top"] for t in ts)),
                cost=sorted(t["excl_china"][0]["cell_rank"] for t in ts if t.get("excl_china")))


SM, SN = stats("Mars"), stats("Moon")
N_RANKED = next(iter(T.values()))["top"][0].get("n_ranked", 0)
lst = lambda cnt, k: ", ".join(f"{esc(n.split(' (')[0])} {v}" for n, v in cnt.most_common(k))
KNOWN = collections.Counter(x["known_analog"] for t in T.values() for x in t["top"] if x["known_analog"])
cls = lambda s: CLS.get(s, s)


def coord(la, lo):
    ns, ew = ("N" if la >= 0 else "S"), ("O" if lo >= 0 else "W")
    url = f"https://www.openstreetmap.org/?mlat={la:.3f}&mlon={lo:.3f}#map=8/{la:.3f}/{lo:.3f}"
    return f'<a href="{url}" target="_blank" rel="noopener">{abs(la):.2f}° {ns}, {abs(lo):.2f}° {ew}</a>'


def chip(known):
    return f'<span class="chip known">bekannt: {esc(known)}</span>' if known else '<span class="chip new">neu</span>'


order = [k for k, v in T.items() if v["body"] == "Mars"] + [k for k, v in T.items() if v["body"] == "Moon"]

overview = []
for k in order:
    t = T[k]
    s = t["top"][0]
    sx = (t.get("excl_china") or [s])[0]
    q = "" if t.get("coord_quality") == "verified" else f' <span class="muted">({esc(t.get("coord_quality") or "")})</span>'
    overview.append(
        f"<tr><td>{'Mars' if t['body'] == 'Mars' else 'Mond'}</td><td><b>{esc(t['name'])}</b>{q}"
        f"<div class='muted small'>{esc(t.get('category') or '')}</div></td>"
        f"<td><b>{esc(s.get('country') or '–')}</b><div class='small'>{coord(s['lat'], s['lon'])} · {esc(cls(s['env_class_name']))}</div></td>"
        f"<td class='n'>{rank(s)}</td>"
        f"<td>{'<span class=muted>gleich</span>' if sx is s or (sx['lat'], sx['lon']) == (s['lat'], s['lon']) else '<b>' + esc(sx.get('country') or '–') + '</b><div class=small>' + coord(sx['lat'], sx['lon']) + ' · ' + rank(sx) + '</div>'}</td>"
        f"<td>{DIM.get(s['best_dim'], s['best_dim'])}</td>"
        f"<td>{DIM.get(s['worst_dim'], s['worst_dim'])}</td><td class='n'>{t['n_new_in_top']} / 20</td></tr>")

details = []
for k in order:
    t = T[k]
    rows = []
    for s in t["top"][:10]:
        fl = ", ".join(FLAG.get(f, f) for f in s["flags"])
        rows.append(
            f"<tr><td class='n'>{s['rank']}</td><td><b>{esc(s.get('country') or '–')}</b><div class='small'>{coord(s['lat'], s['lon'])}</div></td><td>{esc(cls(s['env_class_name']))}"
            f"<div class='muted small'>{esc(fl)}</div></td><td class='n'>{rank(s)}</td>"
            f"<td class='n'>{s['coverage'] * 100:.0f} %</td><td>{DIM.get(s['best_dim'], s['best_dim'])}</td>"
            f"<td>{DIM.get(s['worst_dim'], s['worst_dim'])}</td><td>{chip(s['known_analog'])}</td></tr>")
    body = "Mars" if t["body"] == "Mars" else "Mond"
    details.append(
        f"<details><summary><span class='tag {t['body'].lower()}'>{body}</span> {esc(t['name'])}"
        f"<span class='muted'> · Ziel {t['center_lat']:.2f}°, {t['center_lon']:.2f}° O · Koordinaten {esc(t.get('coord_quality') or '')}"
        f" · {t['n_new_in_top']} von 20 neu</span></summary>"
        f"<div class='table-wrap'><table><thead><tr><th class='n'>#</th><th>Erdort</th><th>Umgebung</th><th class='n'>Platz auf der Erde</th>"
        f"<th class='n'>Abdeckung</th><th>passt</th><th>bricht</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        f"</details>")

page = f"""<title>Analog Finder Ergebnisse</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: eine Lesespalte; Übersichtstabelle oben, aufklappbare Ziel-Listen darunter */
:root {{
  --bg:#f4f5f6; --surface:#fff; --fg:#1b2129; --muted:#5b6573; --line:#d9dde2; --accent:#a3561b; --accent-soft:#f3e6da;
  --mars:#b5532a; --mars-soft:#f6e3da; --moon:#4d5d75; --moon-soft:#e3e8f0; --ok:#2f7a4f; --ok-soft:#e1f0e6; --warn:#8a6a12; --warn-soft:#f5edd3;
  --f-display:"Space Grotesk","Helvetica Neue",Arial,sans-serif; --f-body:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif; --f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#14181d; --surface:#1b2027; --fg:#e3e6ea; --muted:#9aa3ae; --line:#2c333c; --accent:#e09a5f; --accent-soft:#3a2a1d;
  --mars:#e88b62; --mars-soft:#3d2419; --moon:#a9b8cf; --moon-soft:#232b38; --ok:#7cc89a; --ok-soft:#1d3326; --warn:#e2c26a; --warn-soft:#3a3219; color-scheme:dark; }} }}
:root[data-theme="dark"] {{
  --bg:#14181d; --surface:#1b2027; --fg:#e3e6ea; --muted:#9aa3ae; --line:#2c333c; --accent:#e09a5f; --accent-soft:#3a2a1d;
  --mars:#e88b62; --mars-soft:#3d2419; --moon:#a9b8cf; --moon-soft:#232b38; --ok:#7cc89a; --ok-soft:#1d3326; --warn:#e2c26a; --warn-soft:#3a3219; color-scheme:dark; }}
* {{ box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--fg); font-family:var(--f-body); font-size:16px; line-height:1.6;
  padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); padding-block:0 64px; }}
main {{ max-width:1060px; margin:0 auto; }}
header {{ padding-block:52px 24px; border-bottom:1px solid var(--line); }}
.eyebrow {{ font-family:var(--f-mono); font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); margin:0 0 10px; }}
h1 {{ font-family:var(--f-display); font-weight:700; font-size:clamp(30px,5vw,42px); line-height:1.1; margin:0 0 14px; text-wrap:balance; }}
h2 {{ font-family:var(--f-display); font-weight:600; font-size:24px; margin:0 0 12px; text-wrap:balance; }}
.lede {{ font-size:18px; color:var(--muted); max-width:66ch; margin:0; }}
section {{ padding-block:32px 4px; }}
p, li {{ max-width:70ch; }}
ul {{ padding-left:20px; margin:0 0 12px; }} li {{ margin-bottom:6px; }}
a {{ color:var(--accent); }} a:focus-visible, summary:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
.muted {{ color:var(--muted); }} .small {{ font-size:13px; }}
.facts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin:8px 0 6px; }}
.fact {{ background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:14px 16px; min-width:0; }}
.fact b {{ display:block; font-family:var(--f-display); font-size:26px; font-weight:600; line-height:1.15; font-variant-numeric:tabular-nums; }}
.fact span {{ font-size:14px; color:var(--muted); }}
.table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--surface); margin:8px 0 16px; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-family:var(--f-mono); font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); font-weight:500; background:var(--bg); white-space:nowrap; }}
tr:last-child td {{ border-bottom:0; }} td.n, th.n {{ text-align:right; white-space:nowrap; }}
.chip {{ display:inline-block; font-family:var(--f-mono); font-size:11.5px; padding:2px 8px; border-radius:999px; white-space:nowrap; }}
.chip.new {{ background:var(--ok-soft); color:var(--ok); }} .chip.known {{ background:var(--warn-soft); color:var(--warn); }}
.tag {{ font-family:var(--f-mono); font-size:11px; letter-spacing:.06em; text-transform:uppercase; padding:2px 7px; border-radius:4px; margin-right:6px; }}
.tag.mars {{ background:var(--mars-soft); color:var(--mars); }} .tag.moon {{ background:var(--moon-soft); color:var(--moon); }}
details {{ background:var(--surface); border:1px solid var(--line); border-radius:8px; margin:0 0 8px; }}
summary {{ cursor:pointer; padding:11px 14px; font-weight:500; }}
details .table-wrap {{ border:0; border-top:1px solid var(--line); border-radius:0 0 8px 8px; margin:0; }}
.note {{ border-left:3px solid var(--accent); background:var(--surface); padding:12px 16px; border-radius:0 6px 6px 0; margin:0 0 10px; }}
footer {{ margin-top:36px; padding-top:16px; border-top:1px solid var(--line); font-size:13px; color:var(--muted); }}
</style>
<main>
<header>
  <p class="eyebrow">NASA Space Apps 2026 · Analog Finder · Stand 15.11. · volles Scoring 0,05°</p>
  <h1>Ergebnisse: Erd-Analoga für 27 Ziele</h1>
  <p class="lede">Für jeden der 27 Landeplätze und Basis-Kandidaten auf Mond und Mars die 20 ähnlichsten Orte auf der Erde, gesucht in 8,9 Millionen Landzellen von etwa 5 km. Für jeden Ort steht dabei, was passt, wo die Analogie bricht und welchen Platz er unter allen Erdzellen belegt. <a href="https://vice003.github.io/analog-finder/">Zur interaktiven Web-App</a> (Englisch, mit Mars-/Mondkarte, China-Filter und Vergleich).</p>
</header>

<section>
  <h2>Das Wichtigste</h2>
  <div class="facts">
    <div class="fact"><b>27</b><span>Ziele: {SM['n']} auf dem Mars, {SN['n']} am Mond-Südpol</span></div>
    <div class="fact"><b>{mio(N_RANKED)}</b><span>bewertete Erdzellen je Ziel (von 8,9 Mio.; ohne Wasser, Eisschilde, Wald, Acker, Siedlung, Datenlücken)</span></div>
    <div class="fact"><b>{min(SM['new'][0], SN['new'][0])}–{max(SM['new'][1], SN['new'][1])} von 20</b><span>Treffer pro Ziel sind neue Orte, keine etablierten Analoga</span></div>
  </div>
  <ul>
    <li><b>Mars → Hochasien.</b> {SM['cn']} der {SM['top']} Mars-Treffer liegen in China (mit Aksai Chin), vor allem im tibetischen Hochland, im Qaidam-Becken und am Rand der Taklamakan. Danach: {lst(collections.Counter({k: v for k, v in SM['c'].items() if 'China' not in k}), 6)}. Die 14 Mars-Ziele führen auf {SM['uniq']} verschiedene Erdorte.</li>
    <li><b>Ohne China</b> (Schalter in der Web-App, zweite Liste je Ziel in <code>top_sites.json</code>): Die Mars-Treffer verteilen sich auf {lst(SM['cx'], 6)}. Der beste Ort außerhalb Chinas liegt je Mars-Ziel auf Zellplatz {SM['cost'][0]} bis {de(SM['cost'][-1])}. Bei den Mond-Zielen ändert der Filter praktisch nichts.</li>
    <li><b>Mond → arktische Polarwüsten.</b> Für die 13 Südpol-Ziele führen die Treffer in die kanadische Arktis und nach Nordgrönland: {lst(SN['c'], 4)} von {SN['top']} Treffern.</li>
    <li><b>Die Region bestimmen die Umweltbedingungen, den Ort das Gelände.</b> Niedriger Druck, Kälte und Trockenheit, die die Erde nie ganz erreicht, zeigen auf die extremsten Gegenden der Erde. Gelände und Untergrund entscheiden dann, welcher Ort darin am besten passt.</li>
    <li><b>Positivkontrolle:</b> Etablierte Analoga tauchen in den Listen auf, ohne dass das Verfahren sie kennt: {lst(KNOWN, 5)} (Anzahl Treffer im jeweiligen Radius).</li>
  </ul>
</section>

<section>
  <h2>Bester Treffer je Ziel</h2>
  <p class="muted">„Platz“ ist der Rang unter allen bewerteten Erdzellen (1 = bester Treffer der Erde). Die Listen nehmen nur Orte mit mindestens 200 km Abstand, deshalb springen die Plätze. „passt“ und „bricht“ sind die stärkste und die schwächste Dimension des Erdorts. Die Koordinaten führen zu OpenStreetMap.</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Körper</th><th>Ziel</th><th>Bester Erdort</th><th class="n">Platz</th><th>Bester ohne China</th><th>passt</th><th>bricht</th><th class="n">neu in Top 20</th></tr></thead>
    <tbody>{''.join(overview)}</tbody>
  </table></div>
</section>

<section>
  <h2>Top 10 je Ziel</h2>
  <p class="muted">Die vollständigen Listen mit 20 Orten und allen Dimensionswerten stehen in <code>results/top_sites.json</code> und <code>.csv</code> im Repo, dort je Ort auch die Aufschlüsselung je Merkmal und die Begründung der Umgebungsklasse. Die Web-App zeigt beides an.</p>
  {''.join(details)}
</section>

<section>
  <h2>So wurde gerechnet</h2>
  <ul>
    <li><b>Ziele:</b> alle 27 Orte aus der Ortsliste des Mond/Mars-Teams. Mars 10 × 10 km, Mond 15 × 15 km. Artemis-Regionen liegen auf dem am besten beleuchteten Ausschnitt innerhalb von 12 km, weil die Liste oft Kratermittelpunkte nennt.</li>
    <li><b>Zielwerte:</b> Gelände aus MOLA (Mars, 463 m) und LOLA (Mond, 100 m), auf Erde und Zielkörper mit demselben Code. Thermische Trägheit Mars aus TES. Mondtemperatur und Eis aus Diviner. Druck, Temperatur und Eis auf dem Mars sind vorerst grobe Schätzwerte.</li>
    <li><b>Länder:</b> Natural Earth 1:50m (gemeinfrei), nur zur Beschriftung. Natural Earth zeichnet De-facto-Grenzen. Umstrittene Gebiete sind als solche gekennzeichnet, etwa Aksai Chin. Der China-Filter nimmt China mit Hongkong, Macau und den von China verwalteten Gebieten heraus, Taiwan nicht.</li>
    <li><b>Erde:</b> MODIS (Temperatur, Albedo, NDVI, Schnee), MERRA-2 (Staub, Stürme, Wind, Druck, Niederschlag) und Copernicus-Höhenmodell.</li>
    <li><b>Mindestabdeckung:</b> Eine Erdzelle kommt nur ins Ranking, wenn sie mindestens 80 % des Gewichts der Dimensionen belegt, für die das Ziel Werte hat.</li>
    <li><b>Vergleich:</b> Gleiche Größen werden Wert gegen Wert verglichen, verschiedene Instrumente über den Rang. Werte, die die Erde nie erreicht, zählen als „Richtung“. Jedes Merkmal ist nach Verlässlichkeit (A/B/C) gewichtet. Wasser, Eisschilde, Wald, Acker und Siedlung sind ausgeblendet.</li>
  </ul>
</section>

<section>
  <h2>Was noch nicht stimmt</h2>
  <div class="note"><b>Tundra unter den Mond-Treffern.</b> {SN['cls'].get('kein_analog', 0)} der {SN['top']} Mond-Treffer haben die Umgebungsklasse „Kein Analog“: arktische Tundra mit etwas Bewuchs (NDVI-Jahresmaximum über 0,15). Das Ranking schließt bisher nur Wald, Acker, Siedlung, Wasser und Eisschilde aus, nicht spärlich bewachsene Tundra. Vorschlag: für Mond-Ziele nur vegetationsfreie Zellen zulassen.</div>
  <div class="note"><b>Ballung in Hochasien.</b> Die Mars-Listen zeigen eine Region statt vieler. Vorschläge: bester Ort je Kontinent oder ein zweistufiges Ranking (erst Umweltfilter, dann ortsspezifisch).</div>
  <div class="note"><b>Ungenaue Zielkoordinaten.</b> Gale liegt auf dem Zentralberg statt an der Landestelle, Haworth bleibt im Schatten. Die Koordinaten der Ortsliste sind Näherungen.</div>
  <div class="note"><b>Noch nicht ausgewertet:</b> Mars-Albedo (OMEGA), Staub (TES), Bodeneis (Odyssey GRS), Diviner-Werte für Mondziele nördlich von 85° S, Permafrost und UV auf der Erde.</div>
</section>

<footer>Daten: NASA MODIS, MERRA-2, GPM IMERG, MOLA, LOLA, Diviner, TES (PDS) und ESA Copernicus DEM. Code und Daten: <a href="https://github.com/Vice003/analog-finder">github.com/Vice003/analog-finder</a>, im Team-Repo Vice003/NASA-Challenge unter vicente/, planetary/ und common/.</footer>
</main>
"""
open(out, "w", encoding="utf-8").write(page)
print("ok", len(page))
