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
CONT_DE = {"Africa": "Afrika", "Asia": "Asien", "Europe": "Europa", "North America": "Nordamerika",
           "South America": "Südamerika", "Oceania": "Ozeanien", "Antarctica": "Antarktika"}


def cont_summary(body):
    """Je Kontinent: Median des Zellplatzes seines besten Orts ueber alle Ziele des Koerpers."""
    import statistics
    ranks = collections.defaultdict(list)
    for t in T.values():
        if t["body"] == body:
            for x in t.get("by_continent", []):
                ranks[x["continent"]].append(x["cell_rank"])
    rows = sorted(((statistics.median(v), c) for c, v in ranks.items()))
    parts = [f"in {CONT_DE.get(c, c)} auf Platz {de(int(m))}" for m, c in rows]
    return ", ".join(parts[:-1]) + " und " + parts[-1]


from pathlib import Path as _P
_fsp = _P(src).with_name("fine_search.json")
FSR = json.load(open(_fsp, encoding="utf-8"))["sites"] if _fsp.exists() else {}


def fs_summary():
    pairs = [v for d in FSR.values() for v in d.values() if v.get("centre")]
    if not pairs:
        return None
    c = sorted(v["centre"]["match"] for v in pairs)
    b = sorted(v["best"]["match"] for v in pairs)
    imp = sum(v["best"]["match"] - v["centre"]["match"] >= 0.05 for v in pairs)
    edge = sum(v["best"]["offset_km"] >= 7 for v in pairs)
    return dict(n=len(pairs), sites=len(FSR), c=c[len(c) // 2], b=b[len(b) // 2], imp=imp, edge=edge)


FSS = fs_summary()
_ncp = _P(src).with_name("novelty_check.json")
NC = json.load(open(_ncp, encoding="utf-8"))["regions"] if _ncp.exists() else []
NC_URL = "https://github.com/Vice003/analog-finder/blob/main/docs/novelty_check.md"


def nc_summary():
    if not NC:
        return ""
    cnt = collections.Counter(r["status"] for r in NC)
    known = [r["region"] for r in NC if r["status"] in ("established", "studied")]
    return (f"<li><b>Literaturprüfung der „neuen“ Orte:</b> {len(NC)} Regionen per Websuche geprüft. "
            f"{cnt.get('established', 0)} sind etablierte Analog-Orte, {cnt.get('studied', 0)} schon untersucht "
            f"({esc(', '.join(known))}); die beiden etablierten (Salar de Uyuni, Borup Fiord Pass) sind jetzt als bekannt markiert. "
            f"Für {cnt.get('no evidence found', 0)} Regionen fand sich kein Nachweis. Viele davon liegen aber in einer Großregion mit "
            f"bekanntem Analog, darum besser „neuer Ort in bekannter Analog-Landschaft“ statt „unerforscht“. "
            f"Die Suche war englischsprachig und ohne Fachdatenbanken; chinesische und russische Literatur ist kaum abgedeckt. "
            f"<a href='{NC_URL}'>Bericht mit Quellen</a>.</li>")


def rb_summary(body):
    vals = [RB.get(k, {}).get(f"{t['top'][0]['lat']:.3f},{t['top'][0]['lon']:.3f}") for k, t in T.items() if t["body"] == body]
    vals = [v for v in vals if v is not None]
    if not vals:
        return ""
    return f"{sum(v >= 0.8 for v in vals)} von {len(vals)} (Median {sorted(vals)[len(vals) // 2] * 100:.0f} %)"


KNOWN = collections.Counter(x["known_analog"] for t in T.values() for x in t["top"] if x["known_analog"])
CLS["Kein Analog (Vegetation, Wasser)"] = "Kahl, keine Klasse passt"
cls = lambda s: CLS.get(s, s)
GLOSSAR = "https://vice003.github.io/analog-finder/glossar.html"  # absolut: die Seite laeuft auch als Artifact


def g(gid, label):
    """Begriff mit Link auf seine Erklaerung im Glossar."""
    return f'<a class="gl" href="{GLOSSAR}#{gid}" target="_blank" rel="noopener">{label}</a>'


from pathlib import Path as _P
_rbp = _P(src).with_name("robustness.json")
RB = json.load(open(_rbp, encoding="utf-8"))["targets"] if _rbp.exists() else {}
_pfp = _P(__file__).resolve().parent / "profiles" / "profiles.json"
PF = {x["id"] for x in json.load(open(_pfp, encoding="utf-8"))["sites"]} if _pfp.exists() else set()
PROFILES_URL = "https://vice003.github.io/analog-finder/profiles.html"


def _sid(lat, lon):
    return f"{'n' if lat >= 0 else 's'}{abs(lat):.3f}_{'e' if lon >= 0 else 'w'}{abs(lon):.3f}".replace(".", "p")


def robust(tid, x):
    v = RB.get(tid, {}).get(f"{x['lat']:.3f},{x['lon']:.3f}")
    return "–" if v is None else f"{v * 100:.0f} %"


def prof_link(x):
    i = _sid(x["lat"], x["lon"])
    return f' · <a href="{PROFILES_URL}#{i}" target="_blank" rel="noopener">Steckbrief</a>' if i in PF else ""


def cls_link(x):
    return g("cls_" + x["env_class"], esc(cls(x["env_class_name"])))


def flags_link(x):
    return ", ".join(g("flag_" + f, esc(FLAG.get(f, f))) for f in x["flags"])


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
        f"<td><b>{esc(s.get('country') or '–')}</b><div class='small'>{coord(s['lat'], s['lon'])} · {cls_link(s)}{prof_link(s)}</div></td>"
        f"<td class='n'>{rank(s)}<div class='small muted'>robust {robust(k, s)}</div></td>"
        f"<td>{'<span class=muted>gleich</span>' if sx is s or (sx['lat'], sx['lon']) == (s['lat'], s['lon']) else '<b>' + esc(sx.get('country') or '–') + '</b><div class=small>' + coord(sx['lat'], sx['lon']) + ' · ' + rank(sx) + '</div>'}</td>"
        f"<td>{DIM.get(s['best_dim'], s['best_dim'])}</td>"
        f"<td>{DIM.get(s['worst_dim'], s['worst_dim'])}</td><td class='n'>{t['n_new_in_top']} / 20</td></tr>")

details = []
for k in order:
    t = T[k]
    rows = []
    for s in t["top"][:10]:
        rows.append(
            f"<tr><td class='n'>{s['rank']}</td><td><b>{esc(s.get('country') or '–')}</b><div class='small'>{coord(s['lat'], s['lon'])}{prof_link(s)}</div></td><td>{cls_link(s)}"
            f"<div class='muted small'>{flags_link(s)}</div></td><td class='n'>{rank(s)}</td>"
            f"<td class='n'>{robust(k, s)}</td><td class='n'>{s['coverage'] * 100:.0f} %</td><td>{DIM.get(s['best_dim'], s['best_dim'])}</td>"
            f"<td>{DIM.get(s['worst_dim'], s['worst_dim'])}</td><td>{chip(s['known_analog'])}</td></tr>")
    body = "Mars" if t["body"] == "Mars" else "Mond"
    details.append(
        f"<details><summary><span class='tag {t['body'].lower()}'>{body}</span> {esc(t['name'])}"
        f"<span class='muted'> · Ziel {t['center_lat']:.2f}°, {t['center_lon']:.2f}° O · Koordinaten {esc(t.get('coord_quality') or '')}"
        f" · {t['n_new_in_top']} von 20 neu</span></summary>"
        f"<div class='table-wrap'><table><thead><tr><th class='n'>#</th><th>Erdort</th><th>{g('klasse', 'Umgebung')}</th><th class='n'>{g('platz', 'Platz auf der Erde')}</th>"
        f"<th class='n'>{g('robustheit', 'Robust')}</th><th class='n'>{g('abdeckung', 'Abdeckung')}</th><th>{g('passt_bricht', 'passt')}</th><th>{g('passt_bricht', 'bricht')}</th><th>{g('bekannt', 'bekannt/neu')}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
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
a.gl {{ color:inherit; text-decoration:underline dotted; text-decoration-color:var(--muted); text-underline-offset:3px; }}
a.gl:hover {{ color:var(--accent); text-decoration-color:var(--accent); }}
.note {{ border-left:3px solid var(--accent); background:var(--surface); padding:12px 16px; border-radius:0 6px 6px 0; margin:0 0 10px; }}
footer {{ margin-top:36px; padding-top:16px; border-top:1px solid var(--line); font-size:13px; color:var(--muted); }}
</style>
<main>
<header>
  <p class="eyebrow">NASA Space Apps 2026 · Analog Finder · Stand 15.11., 11 Uhr · volles Scoring 0,05°</p>
  <h1>Ergebnisse: Erd-Analoga für 27 Ziele</h1>
  <p class="lede">Für jeden der 27 Landeplätze und Basis-Kandidaten auf Mond und Mars die 20 ähnlichsten Orte auf der Erde, gesucht in 8,9 Millionen Landzellen von etwa 5 km. Für jeden Ort steht dabei, was passt, wo die Analogie bricht und welchen Platz er unter allen Erdzellen belegt. <a href="https://vice003.github.io/analog-finder/">Zur interaktiven Web-App</a> (Englisch, mit Mars-/Mondkarte, China-Filter und Vergleich). Gepunktet unterstrichene Begriffe führen zu ihrer Erklärung im <a href="https://vice003.github.io/analog-finder/glossar.html">Glossar</a>.</p>
</header>

<section>
  <h2>Das Wichtigste</h2>
  <div class="facts">
    <div class="fact"><b>27</b><span>{g('ziel', 'Ziele')}: {SM['n']} auf dem Mars, {SN['n']} am Mond-Südpol</span></div>
    <div class="fact"><b>{mio(N_RANKED)}</b><span>{g('bewertet', 'bewertete')} {g('zelle', 'Erdzellen')} je Ziel (von 8,9 Mio.; nur {g('vegetationsfrei', 'vegetationsfreies')} Land, ohne {g('masken', 'Wasser, Eisschilde')} und {g('mindestabdeckung', 'Datenlücken')})</span></div>
    <div class="fact"><b>{min(SM['new'][0], SN['new'][0])}–{max(SM['new'][1], SN['new'][1])} von 20</b><span>Treffer pro Ziel sind {g('bekannt', 'neue Orte')}, keine etablierten Analoga</span></div>
  </div>
  <ul>
    <li><b>Mars → Hochasien.</b> {SM['cn']} der {SM['top']} Mars-Treffer liegen in China (mit Aksai Chin), vor allem im tibetischen Hochland, im Qaidam-Becken und am Rand der Taklamakan. Danach: {lst(collections.Counter({k: v for k, v in SM['c'].items() if 'China' not in k}), 6)}. Die 14 Mars-Ziele führen auf {SM['uniq']} verschiedene Erdorte.</li>
    <li><b>{g('ohne_china', 'Ohne China')}</b> (Schalter in der Web-App, zweite Liste je Ziel in <code>top_sites.json</code>): Die Mars-Treffer verteilen sich auf {lst(SM['cx'], 6)}. Der beste Ort außerhalb Chinas liegt je Mars-Ziel auf Zellplatz {SM['cost'][0]} bis {de(SM['cost'][-1])}. Bei den Mond-Zielen ändert der Filter praktisch nichts.</li>
    <li><b>{g('kontinent', 'Bester Ort je Kontinent')}</b> (Ansicht „Best per continent“ in der Web-App): Für ein typisches Mars-Ziel liegt der beste Ort {cont_summary("Mars")} (von {de(N_RANKED)} {g('bewertet', 'bewerteten Zellen')}; Platz 1 = ähnlichste Zelle der Erde, siehe {g('platz', 'Zellplatz')}). Für ein typisches Mond-Ziel liegt er {cont_summary("Moon")}.</li>
    <li><b>Mond → arktische Polarwüsten.</b> Für die 13 Südpol-Ziele führen die Treffer in die kanadische Arktis und nach Nordgrönland: {lst(SN['c'], 4)} von {SN['top']} Treffern.</li>
    <li><b>Die Region bestimmen die Umweltbedingungen, den Ort das Gelände.</b> Niedriger Druck, Kälte und Trockenheit, die die Erde nie ganz erreicht, zeigen auf die extremsten Gegenden der Erde. Gelände und Untergrund entscheiden dann, welcher Ort darin am besten passt.</li>
    <li><b>{g('robustheit', 'Robustheit')}:</b> Wie oft bleibt der beste Ort unter den Top 20, wenn man die Gewichte zufällig um ±50 % verändert (1.000 Durchläufe)? Mindestens 80 % der Durchläufe schaffen bei den Mars-Zielen {rb_summary("Mars")}, bei den Mond-Zielen {rb_summary("Moon")}. Die Mond-Treffer hängen also kaum an der Gewichtung, bei einigen Mars-Zielen schon. Für die besten Orte gibt es <a href="{PROFILES_URL}">Steckbriefe</a> mit Satellitenbild und 90-m-Gelände.</li>
    {f"<li><b>{g('feinsuche', 'Feinsuche')}:</b> Für die {FSS['sites']} Steckbrief-Orte wurde je Ziel ein Quadrat in Zielgröße bis zu 8 km um die Zelle verschoben und das Gelände mit 90-m-Daten neu bewertet. Geländenote im Median {FSS['c']:.2f} um die Zelle, {FSS['b']:.2f} im besten Quadrat; bei {FSS['imp']} von {FSS['n']} Ort-Ziel-Paaren bringt die Verschiebung mindestens 0,05. Die verfeinerten Koordinaten stehen in den <a href='{PROFILES_URL}'>Steckbriefen</a> und in der Web-App.</li>" if FSS else ""}
    {nc_summary()}
    <li><b>{g('positivkontrolle', 'Positivkontrolle')}:</b> Etablierte Analoga tauchen in den Listen auf, ohne dass das Verfahren sie kennt: {lst(KNOWN, 5)} (Anzahl Treffer im jeweiligen Radius).</li>
  </ul>
</section>

<section>
  <h2>Bester Treffer je Ziel</h2>
  <p class="muted">{g('platz', '„Platz“')} ist der Rang unter allen {g('bewertet', 'bewerteten Erdzellen')} (1 = bester Treffer der Erde). Die Listen nehmen nur Orte mit mindestens 200 km Abstand, deshalb springen die Plätze. „passt“ und „bricht“ sind die stärkste und die schwächste Dimension des Erdorts. Die Koordinaten führen zu OpenStreetMap.</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Körper</th><th>Ziel</th><th>Bester Erdort</th><th class="n">{g('platz', 'Platz')}</th><th>{g('ohne_china', 'Bester ohne China')}</th><th>{g('passt_bricht', 'passt')}</th><th>{g('passt_bricht', 'bricht')}</th><th class="n">neu in Top 20</th></tr></thead>
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
    <li><b>Zielwerte:</b> Gelände aus MOLA (Mars, 463 m) und LOLA (Mond, 100 m), auf Erde und Zielkörper mit demselben Code. Thermische Trägheit und Albedo Mars aus TES (Albedo über den Rang verglichen). Mondtemperatur und Eis aus Diviner. Druck, Temperatur und Eis auf dem Mars sind vorerst grobe Schätzwerte.</li>
    <li><b>Länder:</b> Natural Earth 1:50m (gemeinfrei), nur zur Beschriftung. Natural Earth zeichnet De-facto-Grenzen. Umstrittene Gebiete sind als solche gekennzeichnet, etwa Aksai Chin. Der China-Filter nimmt China mit Hongkong, Macau und den von China verwalteten Gebieten heraus, Taiwan nicht.</li>
    <li><b>Erde:</b> MODIS (Temperatur, Albedo, NDVI, Schnee), MERRA-2 (Staub, Stürme, Wind, Druck, Niederschlag) und Copernicus-Höhenmodell.</li>
    <li><b>Nur {g('vegetationsfrei', 'vegetationsfreies')} Land:</b> Ins Ranking kommen nur Zellen mit NDVI-Jahresmaximum unter 0,15 oder MODIS-Klasse „barren“ ab 50 %. Vorher landete spärlich bewachsene Tundra unter den Mond-Treffern (89 von 260).</li>
    <li><b>{g('mindestabdeckung', 'Mindestabdeckung')}:</b> Eine Erdzelle kommt nur ins Ranking, wenn sie mindestens 80 % des Gewichts der Dimensionen belegt, für die das Ziel Werte hat.</li>
    <li><b>Vergleich:</b> Gleiche Größen werden {g('methode_direkt', 'Wert gegen Wert')} verglichen, verschiedene Instrumente über den {g('methode_rang', 'Rang')}. Werte, die die Erde nie erreicht, zählen als {g('methode_richtung', '„Richtung“')}. Jedes {g('merkmal', 'Merkmal')} ist nach {g('verlaesslichkeit', 'Verlässlichkeit (A/B/C)')} {g('gewicht', 'gewichtet')}, jede {g('dimension', 'Dimension')} nach dem {g('profil', 'Profil')} des Ziels. {g('masken', 'Wasser, Eisschilde, Wald, Acker und Siedlung')} sind ausgeblendet.</li>
  </ul>
</section>

<section>
  <h2>Was noch nicht stimmt</h2>
  <div class="note"><b>Mars-Werte teils geschätzt.</b> Temperatur, Tagesgang, Druck und Bodeneis auf dem Mars sind grobe Schätzwerte (Note C, geringes Gewicht). Staub (TES) und Bodeneis (Odyssey GRS) sind noch nicht ausgewertet. Die Mars-Albedo kommt seit dem 15.11. aus TES.</div>
  <div class="note"><b>Ballung in Hochasien.</b> Die Top-20-Listen der Mars-Ziele zeigen vor allem eine Region. Die Liste „bester Ort je Kontinent“ zeigt die Alternativen und wie weit sie zurückliegen.</div>
  {f"<div class='note'><b>Feinsuche am Rand.</b> Bei {FSS['edge']} von {FSS['n']} Paaren liegt das beste Quadrat 7–8 km von der Zelle entfernt, also am Rand des Suchbereichs. Dort könnte ein größerer Suchradius noch besser passendes Gelände finden.</div>" if FSS else ""}
  <div class="note"><b>Zielkoordinaten.</b> Gale liegt jetzt auf der Landestelle von Curiosity (Bradbury Landing). Artemis-Regionen, für die die Ortsliste einen Kratermittelpunkt nennt (Haworth, Nobile, de Gerlache, Faustini, Slater), liegen auf dem hellsten 15-km-Ausschnitt innerhalb Kraterradius + 10 km; Haworth hat damit 121 K statt 44 K. Nobile liegt dadurch außerhalb des Diviner-Rasters und hat keinen Temperaturwert. Die übrigen Koordinaten der Ortsliste sind Näherungen.</div>

  <div class="note"><b>Noch nicht ausgewertet:</b> Staub (TES) und Bodeneis (Odyssey GRS) auf dem Mars, Diviner-Werte für Mondziele nördlich von 85° S (Peak near Cabeus B, Mons Mouton, Nobile), Permafrost und UV auf der Erde.</div>
</section>

<footer>Daten: NASA MODIS, MERRA-2, GPM IMERG, MOLA, LOLA, Diviner, TES (PDS) und ESA Copernicus DEM. Code und Daten: <a href="https://github.com/Vice003/analog-finder">github.com/Vice003/analog-finder</a>, im Team-Repo Vice003/NASA-Challenge unter vicente/, planetary/ und common/.</footer>
</main>
"""
open(out, "w", encoding="utf-8").write(page)
print("ok", len(page))
