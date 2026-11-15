"""
Writes the glossary pages: web/glossar.html (German) and web/glossary.html (English), complete documents.
Every entry has an anchor (#platz, #cls_hyperarid, #feat_albedo ...) that the other pages link to.

  python web/make_glossary_page.py
"""
import html
from pathlib import Path

from glossary import GROUPS, entries

HERE = Path(__file__).resolve().parent
esc = html.escape
TXT = {
    "de": dict(file="glossar.html", title="Analog Finder · Glossar", h1="Glossar",
               lede="Was die Begriffe auf der Projektseite, der Ergebnisseite und in der Web-App bedeuten. Klassen, Regeln, Gewichte und bekannte Analoga sind direkt aus dem Code erzeugt, sie entsprechen also genau dem, was gerechnet wird.",
               back="nach oben", other=("English version", "glossary.html"), filter="Begriff suchen …"),
    "en": dict(file="glossary.html", title="Analog Finder · Glossary", h1="Glossary",
               lede="What the terms on the project page, the results page and in the web app mean. Classes, rules, weights and known analogs are generated from the code, so they match exactly what is computed.",
               back="back to top", other=("Deutsche Fassung", "glossar.html"), filter="Search terms …"),
}

CSS = """
:root { --bg:#0e1319; --surface:#151c24; --raise:#1c2530; --fg:#e5e9ee; --muted:#8f9aa8; --line:#26303c; --accent:#de7a4c;
  --f-display:"Space Grotesk","Helvetica Neue",Arial,sans-serif; --f-body:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif; --f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace; color-scheme:dark; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { --bg:#f4f5f6; --surface:#fff; --raise:#f1f3f5; --fg:#1b2129; --muted:#5b6573; --line:#d9dde2; --accent:#a3561b; color-scheme:light; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font-family:var(--f-body); font-size:15.5px; line-height:1.6;
  padding:0 max(16px, env(safe-area-inset-right)) 64px max(16px, env(safe-area-inset-left)); }
main { max-width:920px; margin:0 auto; }
header { padding:36px 0 14px; border-bottom:1px solid var(--line); }
.eyebrow { font:500 12px var(--f-mono); letter-spacing:.08em; text-transform:uppercase; color:var(--accent); margin:0 0 6px; }
h1 { font:700 clamp(28px,4.5vw,38px)/1.1 var(--f-display); margin:0 0 10px; }
h2 { font:600 21px var(--f-display); margin:32px 0 6px; padding-top:8px; border-top:1px solid var(--line); }
h3 { font:600 16px var(--f-display); margin:0 0 4px; }
a { color:var(--accent); } a:focus-visible, input:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.lede { color:var(--muted); max-width:70ch; margin:0; }
nav.toc { display:flex; flex-wrap:wrap; gap:6px 14px; margin:14px 0 4px; font-size:14px; }
.search { margin:14px 0 0; } .search input { width:100%; max-width:360px; font:inherit; padding:7px 10px; border-radius:7px; border:1px solid var(--line); background:var(--surface); color:var(--fg); }
section.e { background:var(--surface); border:1px solid var(--line); border-radius:9px; padding:12px 14px; margin:8px 0; scroll-margin-top:12px; }
section.e:target { border-color:var(--accent); box-shadow:0 0 0 2px var(--accent); }
section.e p { margin:0; max-width:75ch; }
.gmeta { font-size:13px; color:var(--muted); }
ul.grules { margin:4px 0 0; padding-left:20px; font-size:14px; }
.gtw { overflow-x:auto; margin-top:8px; }
table.gtab { border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums; }
table.gtab th, table.gtab td { border-bottom:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; }
table.gtab th { font:500 11px var(--f-mono); letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }
table.gtab td.n { text-align:right; white-space:nowrap; }
.anchor { font:12px var(--f-mono); color:var(--muted); text-decoration:none; margin-left:6px; }
.top { font-size:13px; }
footer { margin-top:28px; font-size:13px; color:var(--muted); }
"""


def build(lang):
    t = TXT[lang]
    es = entries(lang)
    toc = " · ".join(f'<a href="#g-{i}">{esc(g)}</a>' for i, g in enumerate(GROUPS[lang]))
    body = []
    for i, g in enumerate(GROUPS[lang]):
        body.append(f'<h2 id="g-{i}">{esc(g)}</h2>')
        for e in (x for x in es if x["group"] == g):
            body.append(f'<section class="e" id="{e["id"]}" data-s="{esc((e["title"] + " " + e["id"]).lower())}">'
                        f'<h3>{esc(e["title"])}<a class="anchor" href="#{e["id"]}" aria-label="Link">#</a></h3><p>{e["html"]}</p></section>')
        body.append(f'<p class="top"><a href="#top">{t["back"]}</a></p>')
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t["title"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
</head>
<body id="top">
<main>
<header>
  <p class="eyebrow">NASA Space Apps 2026 · Analog Finder</p>
  <h1>{esc(t["h1"])}</h1>
  <p class="lede">{esc(t["lede"])}</p>
  <nav class="toc" aria-label="Inhalt">{toc} · <a href="{t["other"][1]}">{esc(t["other"][0])}</a></nav>
  <div class="search"><input type="search" id="q" placeholder="{esc(t["filter"])}" aria-label="{esc(t["filter"])}"></div>
</header>
{''.join(body)}
<footer>Analog Finder · NASA Space Apps Challenge 2026 · github.com/Vice003/analog-finder</footer>
</main>
<script>
document.getElementById("q").addEventListener("input", (ev) => {{
  const q = ev.target.value.trim().toLowerCase();
  document.querySelectorAll("section.e").forEach((s) => {{ s.hidden = q && !(s.dataset.s.includes(q) || s.textContent.toLowerCase().includes(q)); }});
}});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    for lang in ("de", "en"):
        p = HERE / TXT[lang]["file"]
        p.write_text(build(lang), encoding="utf-8")
        print("->", p)
