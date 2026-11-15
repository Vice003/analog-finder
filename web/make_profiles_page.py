"""
Writes web/profiles.html (English): one card per site profile with satellite image, 90 m terrain, slope
distribution, which targets the site matches (with rank and robustness) and a short verdict on the cell.

  python web/make_profiles_page.py   (after make_site_profiles.py and scoring/robustness.py)
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
esc = html.escape
GL = "https://vice003.github.io/analog-finder/glossary.html"
ENV_EN = {"eisschild": "Ice sheet & glacier", "salzpfanne": "Salt flat / evaporite", "duenenfeld": "Dune field / sand sea",
          "dunkel_vulkanisch": "Dark bare rock (basalt, lava)", "kalte_polarwueste": "Ice-free cold polar desert",
          "hochplateau": "Arid high plateau", "hyperarid": "Hyperarid desert", "raues_gebirge": "Barren steep terrain",
          "aride_wueste": "Arid desert / semi-desert", "kein_analog": "Bare, but no class matched (wetter or milder)"}


def g(gid, label):
    return f'<a class="gl" href="{GL}#{gid}">{label}</a>'


def fine_cell(f):
    """Terrain match of the box centred on the cell vs the best box nearby, with its position."""
    if not f:
        return "<td class='muted'>–</td>"
    b, c = f["best"], f.get("centre")
    cm = f"{c['match']:.2f}" if c else "–"
    if c and b["match"] - c["match"] < 0.02:
        return f"<td>{cm} at the cell (already the best {f['box_km']:g} km box)</td>"
    osm = f"https://www.openstreetmap.org/?mlat={b['lat']}&mlon={b['lon']}#map=11/{b['lat']}/{b['lon']}"
    return (f"<td>{cm} at the cell → <b>{b['match']:.2f}</b> {b['offset_km']:g} km {b['bearing']} "
            f"(<a href='{osm}' target='_blank' rel='noopener'>{b['lat']:.3f}, {b['lon']:.3f}</a>)</td>")


def verdict(m):
    if m["steep_share"] >= 0.25:
        return "Mixed terrain: a quarter or more of the cell is steeper than 15°, so the 5 km average hides cliffs or valley walls."
    if m["sur_flat_share"] is not None and abs(m["flat_share"] - m["sur_flat_share"]) >= 0.25:
        return "The cell differs from its surroundings; the match is specific to this spot, not to the whole area."
    if m["uniform"]:
        return "Uniform: the cell looks like its surroundings and has hardly any steep ground; the 5 km values describe the place well."
    return "Moderately varied terrain; the 5 km values are a fair summary."


def main():
    import sys
    sys.path.insert(0, str(ROOT / "scoring"))
    from countries import CountryLookup
    P = json.load(open(HERE / "profiles" / "profiles.json", encoding="utf-8"))["sites"]
    RB = json.load(open(ROOT / "results" / "robustness.json", encoding="utf-8"))["targets"]
    fsp = ROOT / "results" / "fine_search.json"
    FS = json.load(open(fsp, encoding="utf-8"))["sites"] if fsp.exists() else {}
    cl = CountryLookup(lang="en")
    key = lambda a, b: f"{a:.3f},{b:.3f}"
    for s in P:
        s["country_en"] = cl.label(s["lat"], s["lon"])[0]
        s["best"] = min(m["cell_rank"] or 10 ** 9 for m in s["matches"])
        s["body"] = "Moon" if all(m["body"] == "Moon" for m in s["matches"]) else ("Mars" if all(m["body"] == "Mars" for m in s["matches"]) else "Both")
    cards = {"Mars": [], "Moon": [], "Both": []}
    for s in sorted(P, key=lambda x: x["best"]):
        m = s["metrics"]
        rows = "".join(
            f"<tr><td>{esc(x['name'])}</td><td>{esc(x['list'])}</td><td class='n'>#{x['rank']}</td>"
            f"<td class='n'>{('{:,}'.format(x['cell_rank'])) if x.get('cell_rank') else '–'}</td>"
            f"<td class='n'>{(str(round(RB.get(x['target'], {}).get(key(s['lat'], s['lon']), 0) * 100)) + ' %') if key(s['lat'], s['lon']) in RB.get(x['target'], {}) else '–'}</td>"
            f"{fine_cell(FS.get(s['id'], {}).get(x['target']))}</tr>"
            for x in sorted(s["matches"], key=lambda x: (x["cell_rank"] or 10 ** 9)))
        lat, lon = s["lat"], s["lon"]
        coords = f"{abs(lat):.3f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.3f}° {'E' if lon >= 0 else 'W'}"
        cards[s["body"]].append(f"""
<section class="card" id="{s['id']}">
  <div class="hd"><div><h2>{esc(s['country_en'] or 'Unknown country')}</h2><div class="mono muted">{coords}</div></div>
  <div class="cls">{g('cls_' + s['env'], esc(ENV_EN.get(s['env'], s['env'])))}</div></div>
  <img src="profiles/{s['image']}" alt="Satellite image, terrain and slope distribution around {coords}" loading="lazy" width="1080" height="368">
  <p class="verdict"><b>{esc(verdict(m))}</b></p>
  <p class="small">The 5 km cell (yellow box): median slope {m['slope_p50']:.1f}° (surroundings {m['sur_slope_p50'] if m['sur_slope_p50'] is None else round(m['sur_slope_p50'], 1)}°),
  {m['flat_share']:.0%} of the area below 5°, {m['steep_share']:.0%} steeper than 15°, elevation {m['elev_min']:.0f}–{m['elev_max']:.0f} m. Image: {esc(s['image_source'])}.</p>
  <div class="tw"><table><thead><tr><th>Matches target</th><th>List</th><th class="n">Place in list</th><th class="n">{g('platz', 'Rank on Earth')}</th><th class="n">{g('robustheit', 'Robustness')}</th><th>{g('feinsuche', 'Fine search: terrain match')}</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="links small"><a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=10/{lat}/{lon}" target="_blank" rel="noopener">OpenStreetMap</a> ·
  <a href="https://worldview.earthdata.nasa.gov/?v={lon - 0.5},{lat - 0.35},{lon + 0.5},{lat + 0.35}" target="_blank" rel="noopener">NASA Worldview</a></p>
</section>""")
    nav = " · ".join(f'<a href="#sec-{k.lower()}">{t} ({len(cards[k])})</a>' for k, t in (("Mars", "Mars matches"), ("Moon", "Moon matches"), ("Both", "Matches for both")) if cards[k])
    secs = "".join(f'<h2 class="sec" id="sec-{k.lower()}">{t}</h2>' + "".join(cards[k]) for k, t in (("Mars", "Sites matching Mars targets"), ("Moon", "Sites matching Moon targets"), ("Both", "Sites matching Mars and Moon targets")) if cards[k])
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analog Finder · Site profiles</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{ --bg:#0e1319; --surface:#151c24; --raise:#1c2530; --fg:#e5e9ee; --muted:#8f9aa8; --line:#26303c; --accent:#e7b04f;
  --f-display:"Space Grotesk","Helvetica Neue",Arial,sans-serif; --f-body:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif; --f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace; color-scheme:dark; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font-family:var(--f-body); font-size:15px; line-height:1.55;
  padding:0 max(16px, env(safe-area-inset-right)) 56px max(16px, env(safe-area-inset-left)); }}
main {{ max-width:1120px; margin:0 auto; }}
header {{ padding:30px 0 12px; border-bottom:1px solid var(--line); }}
h1 {{ font:700 clamp(26px,4vw,36px)/1.1 var(--f-display); margin:0 0 8px; }}
h2 {{ font:600 19px var(--f-display); margin:0; }} h2.sec {{ font-size:22px; margin:28px 0 8px; }}
a {{ color:var(--accent); }} .muted {{ color:var(--muted); }} .small {{ font-size:13.5px; }} .mono {{ font-family:var(--f-mono); font-size:13px; }}
a.gl {{ color:inherit; text-decoration:underline dotted; text-decoration-color:var(--muted); text-underline-offset:3px; }}
.lede {{ color:var(--muted); max-width:78ch; margin:0; }}
nav {{ margin:10px 0 0; font-size:14px; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:12px 0; scroll-margin-top:10px; }}
.card:target {{ border-color:var(--accent); box-shadow:0 0 0 2px var(--accent); }}
.card .hd {{ display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; align-items:baseline; margin-bottom:8px; }}
.card img {{ width:100%; height:auto; border-radius:6px; display:block; background:#151c24; }}
.verdict {{ margin:10px 0 4px; }}
.tw {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums; margin-top:6px; }}
th, td {{ text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); }} th {{ font:500 11px var(--f-mono); letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }}
td.n, th.n {{ text-align:right; white-space:nowrap; }}
.links {{ margin:8px 0 0; }}
</style>
</head>
<body>
<main>
<header>
  <p class="mono" style="color:var(--accent);margin:0 0 6px">NASA SPACE APPS 2026 · ANALOG FINDER</p>
  <h1>Site profiles</h1>
  <p class="lede">A closer look at the best Earth analogs ({len(P)} sites): the top 3 of every target, the best site without China and the best three continent winners. Each profile shows a satellite image, the terrain at 90 m with the 5 km cell outlined (yellow) and the best-matching box of the target's size nearby (cyan, from the {g('feinsuche', 'fine search')}), and the cell's slope distribution against its surroundings, so you can see whether the cell is uniform or whether its average mixes cliffs and plains. {g('robustheit', 'Robustness')} says how often the site stays in the top 20 when the weights change. <a href="./">Back to the web app</a> · <a href="{GL}#steckbrief">What is a site profile?</a></p>
  <nav>{nav}</nav>
</header>
{secs}
</main>
</body>
</html>
"""
    (HERE / "profiles.html").write_text(page, encoding="utf-8")
    print("->", HERE / "profiles.html", len(P), "Orte")


if __name__ == "__main__":
    main()
