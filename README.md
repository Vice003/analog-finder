# Analog Finder

**NASA Space Apps Challenge 2026 – "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars"**

Where on Earth is most like a landing site or base candidate on the Moon or Mars? The Analog Finder gives every patch
of Earth's land (0.05°, about 5 km, 8.9 million cells, climate 2003–2024) the same fingerprint as 27 target sites on
Mars and at the lunar south pole. It then ranks Earth by how closely each patch matches and shows, for every match,
where the analogy holds and where it breaks.

- **Web app:** https://vice003.github.io/analog-finder/ (English; Mars and Moon maps to pick a target, world map of
  similarity, top 20 Earth sites per target, "Exclude China" option, side-by-side comparison of up to 3 sites, and an
  explanation for every site: feature by feature and the rules behind its environment class)
- **Results (German):** [`docs/ergebnisse.html`](https://vice003.github.io/analog-finder/ergebnisse.html)
- **Glossary:** [English](https://vice003.github.io/analog-finder/glossary.html) · [Deutsch](https://vice003.github.io/analog-finder/glossar.html) – every term, class rule, weight and data source; all pages link their terms here
- **Earth data basis (German):** [`docs/datenbasis.html`](https://vice003.github.io/analog-finder/datenbasis.html)
- **Processing plan agreed in the team (German):** [`VERARBEITUNGSPLAN.md`](VERARBEITUNGSPLAN.md)

## How it works

| Step | What | Where |
|---|---|---|
| 1. Earth features | MODIS (surface temperature at 4 overpass times, albedo incl. snow-free, NDVI, snow, land cover), MERRA-2 (dust optical depth, dust emission, dust-storm and gale days, wind, pressure, humidity, precipitation), Copernicus DEM GLO-90 (slope and relief at 100 m and 463 m) on a 0.05° grid | `earth/` |
| 2. Target signatures | 27 sites from the team's site list. Terrain from MOLA (Mars, 463 m) and LOLA (Moon, 100 m) with the **same** code as on Earth (`common/terrain.py`), Mars thermal inertia and albedo from TES, Moon temperature and ice stability from Diviner | `planetary/compute_targets.py` → `planetary/targets.json` |
| 3. Environment classes | 10 Earth environment classes (salt flat, dune field, dark volcanic, cold polar desert, high plateau, hyperarid …) and 10 flags (dust source, frequent dust storms, freeze-thaw, landing-friendly …) | `scoring/categories.py` |
| 4. Scoring | per feature: same quantity → value against value; different instruments → rank against rank (`common/body_percentile.py`); values Earth never reaches (vacuum, 6 hPa) → the closer the better. Weighted by reliability grade (A/B/C) of target and Earth value. Only vegetation-free land is ranked (no water, ice sheets, forest, cropland or settlements); a cell must cover 80 % of the target's profile | `scoring/target_scoring.py` |
| 5. Output | top 20 sites per target, at least 200 km apart, with country, rank among all ranked Earth cells (about 0.84 million vegetation-free cells), known/new analog, per-feature breakdown and class reasons; a second list without China; the best site per continent | `results/top_sites.json`, `.csv` |
| 6. Web app | one self-contained HTML file (MapLibre GL), no server | `web/build_web.py`, `web/template.html` → `docs/index.html` |

`derived/` holds the Earth features on the team's 10′ grid (1080 × 2160, `.npz`, key `a`).

## Run it

```bash
pip install -r requirements.txt
python earth/download_modis.py            # NASA Earthdata login needed (earthaccess)
python earth/clim_modis.py && python earth/clim_merra.py && python earth/surface_static.py
python earth/dem_features.py && python earth/dem_baselines.py
python earth/build_features.py            # -> data/earth/earth_features_005deg.parquet (+ 0.25° version)
python planetary/compute_targets.py       # needs MOLA (read remotely), LOLA, TES, Diviner in data/planetary/raw
python scoring/target_scoring.py planetary/targets.json earth_features_005deg.parquet
python web/build_web.py                   # -> web/index.html; copy to docs/ for GitHub Pages
python web/make_results_page.py results/top_sites.json web/ergebnisse.html
python web/make_glossary_page.py           # -> web/glossar.html, web/glossary.html (generated from scoring/)
```

Raw and intermediate data (`data/`, about 30 GB) are not in the repository. Country names come from Natural Earth
1:50m (public domain, de-facto borders, disputed areas marked) in `data/ref/`; they are used for labels and the China
filter only.

## Data sources

NASA: MODIS (LP DAAC, NSIDC), MERRA-2 (GES DISC), GPM IMERG (supplementary), MOLA and TES (PDS), LOLA and Diviner
(PDS). ESA: Copernicus DEM GLO-90. Natural Earth for country labels.

## Known limits

- No place on Earth has the Moon's vacuum, Mars's thin CO₂ air, their low gravity or their radiation.
- Target sites are 10 × 10 km (Mars) and 15 × 15 km (Moon) boxes around published coordinates, many of them approximate
  (Gale uses the Curiosity landing site; lunar crater regions sit on the best-lit square at the crater rim).
- Some Mars values (temperature, day-night range, pressure, ice) are rough estimates (grade C, low weight); Mars dust
  (TES) and ground ice (Odyssey GRS) are not yet included.
- Mars matches cluster in High Asia; the best-per-continent list shows the alternatives and how far behind they are.

## Team

Built for NASA Space Apps 2026. Earth data basis, target computation, scoring and web app: Vicente (Vice003), with
Claude. Site list and planetary research: the Moon/Mars team in
[Vice003/NASA-Challenge](https://github.com/Vice003/NASA-Challenge).
