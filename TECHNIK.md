# Analog Finder – technische Beschreibung

NASA Space Apps Challenge 2026, Challenge „Identify Earth Locations that Analog the Permanent Moon Base Locations and
Mars“. Stand: 15.11.2026. Dieses Dokument beschreibt alles, was gebaut wurde: Daten, Verfahren, Code, Ausgaben,
Web-App, Server und Veröffentlichung. Begriffe sind im [Glossar](https://vice003.github.io/analog-finder/glossar.html)
erklärt.

**Kurz:** Jede Landzelle der Erde (0,05°, ca. 5 km, 8,9 Mio. Zellen, Klima 2003–2024) bekommt denselben „Fingerabdruck“
wie 27 Zielorte auf Mars (14) und am Mond-Südpol (13). Ein Scoring vergleicht die Fingerabdrücke Merkmal für Merkmal,
bildet je Ziel eine Rangliste und erklärt für jeden Treffer, was passt und wo die Analogie bricht. Robustheit,
Steckbriefe mit 90-m-Gelände, eine Feinsuche und eine Literaturprüfung sichern die besten Treffer ab. Alles ist in
einer Web-App und auf Ergebnisseiten zugänglich.

| | Adresse |
|---|---|
| Repo (dieses) | https://github.com/Vice003/analog-finder |
| Team-Repo | https://github.com/Vice003/NASA-Challenge (Ordner `vicente/`, `planetary/`, `common/`) |
| Web-App | https://vice003.github.io/analog-finder/ |
| Ergebnisse (Deutsch) | https://vice003.github.io/analog-finder/ergebnisse.html |
| Steckbriefe | https://vice003.github.io/analog-finder/profiles.html |
| Glossar | https://vice003.github.io/analog-finder/glossar.html · [English](https://vice003.github.io/analog-finder/glossary.html) |
| Projektseite mit To-do | http://85.215.254.38/ (IONOS-Server, siehe Abschnitt 12) |
| Verarbeitungsplan | [`VERARBEITUNGSPLAN.md`](VERARBEITUNGSPLAN.md) (verbindliche Konventionen im Team, Änderungsprotokoll) |

Pfade beziehen sich auf dieses Repo. Im Team-Repo liegen `earth/`, `scoring/`, `web/`, `results/` unter `vicente/`;
`planetary/` und `common/` liegen dort im Wurzelverzeichnis.

---

## 1. Architektur

```
 Erde (NASA/ESA)                         Mond/Mars (NASA PDS, USGS)
 MODIS, MERRA-2, GPM IMERG,              MOLA, TES, LOLA, Diviner
 Copernicus DEM GLO-90                   Ortsliste des Mond/Mars-Teams
        │                                         │
 earth/*.py  (Klimatologien, Gelände)      planetary/compute_targets.py
        │                                         │
 data/earth/earth_features_005deg.parquet  planetary/targets.json
 (8,9 Mio. Zellen × Merkmale)              (27 Ziele × Merkmale, Verlässlichkeit)
        └──────────────┬──────────────────────────┘
                       │   common/terrain.py, common/body_percentile.py (gleiche Rechenwege für alle Körper)
                       ▼
        scoring/categories.py  (Umgebungsklassen, Zusatzeigenschaften, Profile, bekannte Analoga)
        scoring/target_scoring.py (Teilnoten → Dimensionen → Gesamtwert → Listen, Pool)
                       │
        results/top_sites.json · top_sites.csv · pool.npz
                       │
 Nachbearbeitung: augment_pool · robustness · pool_flags · relabel_known
                  web/make_site_profiles · web/fine_search · Literaturprüfung (novelty_check)
                       │
 Ausgabe: web/build_web.py → Web-App (eine HTML-Datei) · make_results_page · make_profiles_page ·
          make_glossary_page · server/make_project_page → GitHub Pages, Claude-Artifacts, IONOS-Server
```

Sprache: Python 3.12 (Anaconda). Wichtige Pakete: numpy, pandas, pyarrow, scipy, rasterio (mit `affine==2.4.0`),
netCDF4, pyhdf, earthaccess, requests, pyshp, Pillow, matplotlib (siehe `requirements.txt`). Frontend: reines
HTML/CSS/JavaScript mit MapLibre GL 4.7.1 (cdnjs), keine Build-Werkzeuge.

---

## 2. Datenquellen

Nur Quellen der Challenge-Seite (NASA, ESA) für Messwerte; Natural Earth und das IAU-Verzeichnis nur für Beschriftung.

### Erde

| Produkt | Inhalt | Auflösung | Zeitraum | Zugriff |
|---|---|---|---|---|
| MODIS MOD11C3 / MYD11C3 v061 | Oberflächentemperatur, 4 Überflüge (Terra 10:30/22:30, Aqua 13:30/01:30) | 0,05°, monatlich | 2003–2024 | NASA Earthdata (earthaccess) |
| MODIS MCD43C3 v061 | Albedo (auch schneefrei: nur Termine mit < 10 % Schnee) | 0,05° | 2024, 12 Termine | Earthdata |
| MODIS MCD12C1 v061 | Landbedeckung (IGBP), Anteil „barren“ | 0,05° | 2022 | Earthdata |
| MODIS MOD13C2 | Vegetationsindex NDVI (Mittel, Jahresmaximum) | 0,05°, monatlich | 2003–2024 | Earthdata |
| MODIS MOD10CM | Schneebedeckung | 0,05°, monatlich | 2003–2024 | Earthdata |
| MERRA-2 (GES DISC) | Staub-AOD, Staubemission, Staubsturm- und Sturmtage, Wind, Druck, Feuchte, Niederschlag `PRECTOTCORR` | 0,5° × 0,625° | 2003–2024 | OPeNDAP-Ausschnitte |
| GPM IMERG V07 | Niederschlag (nur Zusatz; misst über heller, trockener Wüste falsch) | 0,1° | 2003–2024 | OPeNDAP |
| Copernicus DEM GLO-90 (ESA) | Höhe | 90 m | – | öffentlicher AWS-Bucket, COG je 1°-Kachel |
| Landsat WELD (NASA GIBS) | Satellitenbilder für Steckbriefe und Karte | 30 m | Jahresmosaik | GIBS WMS/WMTS |

### Mars und Mond

| Produkt | Verwendung | Auflösung | Zugriff |
|---|---|---|---|
| MOLA-Mosaik (USGS) | Gelände der Mars-Ziele | 463 m | `/vsicurl/` Ausschnitt, keine Kopie |
| MOLA MEGDR (PDS) | Mars-Karte in der App | 4 px/° | Download 2 MB |
| TES thermische Trägheit nachts (Putzig & Mellon 2007, PDS MGST_9001) | Mars-Trägheit | 20 px/° | Download |
| TES-Lambert-Albedo (USGS-Mosaik) | Mars-Albedo | 7,4 km | Download 17 MB |
| LOLA LDEM_80S_80M (PDS) | Gelände der Mond-Ziele, Mond-Karte | 80 m | Download 116 MB |
| Diviner Polar Resource Product (über `features.npz` des Mond/Mars-Teams) | Mond-Temperatur, Eisstabilität, LOLA-Sonnensichtbarkeit | 240 m, 85–90° S | Branch `Mars_and_Moon` |
| IAU-Namensverzeichnis (USGS) | Kraternamen (für die geplanten Zielausschnitte) | – | Download |

### Hilfsdaten

Natural Earth 1:50m/1:110m (Länder, Kontinente, umstrittene Gebiete, De-facto-Grenzen) für Beschriftung und Filter.

Lokal liegen in `data/` rund 7,4 GB (Klimatologien, Zwischenstände, Erdtabelle, Planetendaten); `data/` ist nicht im
Repo.

---

## 3. Erdseite (`earth/`)

| Skript | Aufgabe | Ergebnis |
|---|---|---|
| `download_modis.py` | MODIS-Einzeldateien von Earthdata laden (Login über `~/.netrc`) | `data/earth/modis/` |
| `clim_modis.py lst\|ndvi\|snow` | Klimatologie 2003–2024 im Durchlauf: Monat laden, aufaddieren, Rohdatei löschen; Zwischenstand je Jahr | `lst_2003_2024.npz` usw. |
| `surface_static.py` | Albedo 2024 (auch schneefrei), Landbedeckung 2022 | `surface_static.npz` |
| `clim_merra.py monthly\|daily\|precip` | MERRA-2-Monatsmittel, Ereignistage aus Stundenwerten, Niederschlag | `merra2_*.npz` |
| `clim_imerg.py` | IMERG-Niederschlag (Zusatz) | `imerg_2003_2024.npz` |
| `dem_features.py` | aus 90-m-Pixeln je 0,05°-Zelle: Höhe, Streuung, Relief, Neigung, Anteil flach (< 5°) und steil (> 30°) | `dem_glo90.npz` |
| `dem_baselines.py` | Neigung P50/P90 und Relief (P95 − P5 der Höhe je 0,05°-Zelle, entspricht dem 5-km-Fenster) bei 100 m (Mond-Vergleich) und 463 m (Mars-Vergleich), mit `common/terrain.py`; 26.475 Kacheln, ProcessPool mit 7 Prozessen, ca. 1 h | `dem_baselines.npz` |
| `build_features.py` | alle Bausteine zu einer Tabelle je Landzelle; abgeleitet u. a. scheinbare thermische Trägheit ATI = (1 − Albedo schneefrei) / Tagesgang | `earth_features_005deg.parquet` (8.869.122 Zeilen, 1,1 GB) und `_025deg` (für die Heatmap) |
| `to_team_grid.py` | Merkmale auf das 10′-Gitter der Team-Pipeline (1080 × 2160, `npz`, Schlüssel `a`) | `derived/*.npz` |

Wichtige Spalten der Erdtabelle: `lst_mean`, `lst_cold_mean`, `lst_diurnal_mean`, `lst_abs_min`, `lst_warm_mean`,
`albedo_snowfree`, `ati`, `ndvi_mean`, `ndvi_peak_mean`, `snow_perm_frac`, `landcover`, `barren_pct`, `water_pct`,
`precip_mm_yr`, `DUEXTTAU_mean`, `DUEM_mean`, `dust_storm_days`, `wind_storm_days`, `SPEED_mean`, `PS_hpa`, `QV2M_gkg`,
`elev_mean`, `slope_mean`, `flat_frac`, `slope_p50_100m/_463m`, `slope_p90_100m/_463m`, `relief_100m/_463m`.

---

## 4. Gemeinsamer Code (`common/`)

* **`terrain.py`**: eine Geländefunktion für alle drei Körper. `resample(dem, dx, dy, pixel_m)` bringt ein DEM auf die
  Ziel-Pixelgröße (beim Vergröbern vorher gemittelt, Randpixel aufgefüllt); `slope_deg` zentrale Differenzen;
  `terrain_stats` liefert Neigung P50, P90 und Relief (P95 − P5 der Höhe in 5-km-Fenstern, Median der Fenster).
  Pixelgrößen: Mond 100 m, Mars 463 m. Selbsttests 1–4 im Modul.
* **`body_percentile.py`**: flächengewichteter Anteil der Oberfläche eines Körpers mit kleinerem Wert
  (`body_percentile(values, weights, target)`, `latlon_weights(n_rows)`); Grundlage des Rangvergleichs.

---

## 5. Zielseite (`planetary/`, Team-Repo)

`compute_targets.py` berechnet für alle 27 Orte der Ortsliste (`data_scripts/landing_sites.py`, Branch
`Mars_and_Moon`, Stand 14.11. 13:30) ein Zielquadrat und dessen Merkmale; Ergebnis `targets.json` (Schema 2,
geprüft mit `check_targets.py`: 0 Fehler).

* **Zielquadrat:** Mars 10 × 10 km, Mond 15 × 15 km (am Mond polarstereografisch).
* **Artemis-Regionen:** Quadrat auf den hellsten Ausschnitt (mittlere LOLA-Sonnensichtbarkeit) innerhalb 12 km; bei
  Kraterregionen (Haworth, Nobile, de Gerlache, Faustini, Slater) innerhalb Kraterradius + 10 km, weil die Liste den
  Kratermittelpunkt im Dauerschatten nennt (Haworth damit 121 K statt 44 K).
* **Gale** auf der Curiosity-Landestelle Bradbury Landing (4,59° S, 137,44° E).

| Merkmal | Mars | Mond | Verlässlichkeit |
|---|---|---|---|
| Neigung P50/P90, Relief | MOLA 463 m, `terrain.py` | LOLA 80 m → 100 m, `terrain.py` | A |
| Albedo | TES-Lambert-Albedo, Median + Körper-Perzentil | – | A |
| Thermische Trägheit | TES nachts, Median + Körper-Perzentil | – (kein offizielles Produkt) | A |
| Oberflächentemperatur | Schätzwert des Musterziels | Diviner (Median im Quadrat) | C bzw. B |
| Tagesgang | Schätzwert | – | C |
| Bodeneis | Schätzwert | Diviner: Anteil mit Eis stabil ≤ 1 m | C bzw. B |
| Luftdruck | 6,1 hPa · e^(−z/11,1 km) aus MOLA-Höhe | Vakuum (1e-12) | C bzw. A |
| Niederschlag, NDVI (Mond auch Wind, Feuchte) | 0 (physikalisch) | 0 (physikalisch) | A |
| Höchster Sonnenstand | 90° − \|Breite\| + 25,19° | 90° − \|Breite\| + 1,54° (Dauerschatten 0) | A |

Diviner-Werte gibt es nur, wo das Quadrat im 240-m-Raster liegt und das Produkt Daten hat (praktisch südlich 85° S);
Peak near Cabeus B, Mons Mouton (Plateau) und Nobile haben deshalb keine Temperatur.

---

## 6. Umgebungsklassen, Eigenschaften, Profile (`scoring/categories.py`)

**Umgebungsklassen** (beschreiben den Ort, gehen nicht in den Gesamtwert ein). Geprüft in dieser Reihenfolge, die
erste zutreffende gewinnt: Eisschild, Salzpfanne, Dünenfeld, dunkles kahles Gestein, eisfreie kalte Polarwüste, arides
Hochplateau, hyperaride Wüste, kahles Steilgelände, aride Wüste, keine Klasse. Die Regeln stehen als `CLASS_RULES`
(Text, Spalte, Vergleich, Schwelle) im Code; `explain_class_full` liefert je Ort die erfüllten Regeln mit Werten und
für jede vorher geprüfte Klasse die Bedingung, an der der Ort scheiterte. „Kahl“ heißt: NDVI-Jahresmaximum < 0,15
oder MODIS „barren“ ≥ 50 %.

**Zusatzeigenschaften** (`FLAGS`, mehrere je Ort): Staubquelle (Emission im obersten 5 % des Landes), staubsturmreich
(≥ 10 Tage AOD > 1), sturmreich (≥ 5 Tage Wind > 17 m/s), windstill, Frost-Tau (≥ 3 Monate), extrem kalt (< 220 K),
niedriger Druck (< 700 hPa), dunkle Oberfläche, landefreundlich (≥ 80 % unter 5°, P90 < 8°), polar.

**Profile** (Gewicht je Dimension; 0 = zählt nicht):

| Profil | Gelände | Material | Temperatur | Trockenheit | Atmosphäre | Staub/Wind | Eis/Wasser | Vegetation | Beleuchtung |
|---|---|---|---|---|---|---|---|---|---|
| Mond-Südpol | 1,0 | 1,0 | 1,5 | 1,0 | 0,5 | 1,0 | 1,5 | 0,5 | 1,5 |
| Mars äquatorial | 1,0 | 1,5 | 1,0 | 1,5 | 1,0 | 1,5 | 0,25 | 1,0 | 0 |
| Mars eisreiche Mittelbreiten | 1,5 | 0,75 | 1,5 | 1,0 | 0,5 | 0,5 | 2,0 | 1,0 | 0 |

**Bekannte Analoga:** 29 Standorte mit Radius (z. B. Atacama, Qaidam, Haughton, Axel Heiberg; nach der
Literaturprüfung ergänzt: Salar de Uyuni, Borup Fiord Pass). Ein Ort im Radius gilt als „bekannt“, sonst „neu“.

---

## 7. Scoring (`scoring/target_scoring.py`)

### Merkmale und Vergleichsmethoden

| Merkmal | Methode | Dimension | Erdspalte | Erd-Note |
|---|---|---|---|---|
| Neigung P50, P90, Relief | Wert gegen Wert | Gelände | `*_100m` bzw. `*_463m` | A |
| Albedo | Rang gegen Rang | Material | `albedo_snowfree` | A |
| Thermische Trägheit | Rang gegen Rang | Material | `ati` | B |
| Staubtrübung, Staubsturmtage | Rang gegen Rang | Staub & Wind | `DUEXTTAU_mean`, `dust_storm_days` | A, B |
| Wind | Richtung | Staub & Wind | `SPEED_mean` | A |
| Temperatur Mittel, kältester Monat, Tagesgang | Richtung | Temperatur | `lst_mean`, `lst_cold_mean`, `lst_diurnal_mean` | A |
| Luftdruck, Feuchte | Richtung | Atmosphäre | `PS_hpa`, `QV2M_gkg` | A |
| Niederschlag | Richtung | Trockenheit | `precip_mm_yr` | A |
| NDVI | Richtung | Vegetation | `ndvi_mean` | A |
| Bodeneis | Richtung | Eis & Wasser | (272,15 − `lst_mean`) / 7, begrenzt 0–1 | C |
| Höchster Sonnenstand | Richtung | Beleuchtung | 90° − \|Breite\| + 23,44° | A |

* **Wert gegen Wert** (gleiche Größe, gleicher Rechenweg): Teilnote = 1 − |Erde − Ziel| / Spanne; Spanne = größerer
  Abstand des Zielwerts zum 2. bzw. 98. Perzentil der Erde (flächengewichtet).
* **Rang gegen Rang** (verschiedene Instrumente): Erdwert → Perzentil unter kahlem, eisfreiem Land; Teilnote = 1 −
  |Perzentil Erde − Körper-Perzentil Ziel| / max(p, 1 − p).
* **Richtung** (Werte, die die Erde nie erreicht): Teilnote = flächengewichteter Anteil des Erdlands, das weiter vom
  Ziel entfernt ist.
* **Gewicht** eines Merkmals = Note Ziel × Note Erde (A 1, B 0,7, C 0,4).
* **Dimension** = gewichtetes Mittel ihrer Teilnoten; **Konfidenz** = mittleres Gewicht der vorhandenen Merkmale.
* **Gesamtwert** = Σ (Profilgewicht × Konfidenz × Dimension) / Σ (Profilgewicht × Konfidenz) über vorhandene
  Dimensionen; nur zum Sortieren.

### Ranking

* **Masken:** Wasser > 50 %, Eisschild (Dauerschnee und wärmster Monat < 280 K), Landbedeckung Wald/Acker/Siedlung
  (IGBP 1–5, 12–14), und seit 15.11. alles, was nicht kahl ist. Bewertet werden damit je Ziel rund 837.500 Zellen.
* **Mindestabdeckung:** Eine Zelle braucht Daten für mindestens 80 % des Profilgewichts der Dimensionen, für die das
  Ziel Werte hat.
* **Zellplatz:** Rang unter allen bewerteten Zellen (1 = beste), dazu flächengewichtetes Perzentil (64-Bit-Summen).
* **Listen je Ziel:** Top 20 mit mindestens 200 km Abstand (`top`), dieselbe ohne China (`excl_china`: CHN, HKG, MAC
  nach Natural-Earth-De-facto-Grenzen, also inkl. Aksai Chin; Taiwan bleibt), bester Ort je Kontinent
  (`by_continent`, auch ohne China). Länder- und Kontinentzuordnung über die auf 0,05° gerasterten Natural-Earth-Grenzen.
* **Je Ort gespeichert:** Koordinaten, Land, Kontinent, Zellplatz, Perzentil, Datenabdeckung, Klasse samt Begründung,
  Zusatzeigenschaften (über die ganze Tabelle berechnet), stärkste/schwächste Dimension, Noten je Dimension, je Merkmal
  Erdwert, Teilnote, Erd-Perzentil, bekannt/neu.
* **Kandidatenpool** (`export_pool`): je Ziel die besten 600 nach Gesamtwert, je Dimension die besten 80, je Kontinent
  25, je Klasse 30, die besten 200 außerhalb Chinas, dazu alle Listen-Orte (`augment_pool.py`); zusammen 41.789 Zellen
  mit allen Teilnoten (uint8), Erdwerten (float16), Konfidenzen, Klasse, Land, Kontinent, bekannt/neu, Zellplatz.

Aufruf: `python scoring/target_scoring.py planetary/targets.json earth_features_005deg.parquet` (ca. 30 min für
27 Ziele auf dem Team-Laptop; am Ende wird `augment_pool` automatisch ausgeführt).

---

## 8. Nachbearbeitung und Absicherung

| Skript | Was es tut | Ergebnis |
|---|---|---|
| `scoring/augment_pool.py` | nimmt Listen-Orte, die wegen der 200-km-Regel außerhalb der Top 600 liegen, in den Pool auf (Konfidenz = Median des Pools) | `pool.npz` |
| `scoring/robustness.py` | 1.000 zufällige Gewichtungen (jedes Profilgewicht × U(0,5; 1,5)); je Durchlauf Top 20 aus dem Pool neu; gezählt wird, ob der Ort oder einer im Umkreis von 50 km darin ist | `robustness.json` (Listen-Orte), `robustness_pool.npz` (alle Pool-Zellen) |
| `scoring/pool_flags.py` | Zusatzeigenschaften aller Pool-Zellen über die ganze Erdtabelle (Bitmaske) | `pool_flags.npz` |
| `scoring/relabel_known.py` | wendet die Liste bekannter Analoga neu an, ohne neues Scoring | `top_sites.json`, `pool.npz` |
| `web/make_site_profiles.py` | 104 Steckbriefe (Top 3 je Ziel, bester ohne China, Top 3 je Kontinent): Landsat-WELD-Bild, Copernicus-90-m-Schummerung mit Zelle und bestem Feinsuche-Quadrat, Neigungsverteilung Zelle gegen 36-km-Umgebung, Kennzahlen (Neigung, Anteil flach/steil, Höhenspanne, einheitlich ja/nein) | `web/profiles/*.jpg`, `profiles.json` |
| `web/fine_search.py` | Feinsuche: Quadrat in Zielgröße in 1-km-Schritten bis 8 km um jede Steckbrief-Zelle; Neigung und Relief wie beim Ziel (`terrain.py`, Ziel-Pixelgröße), Bewertung Wert gegen Wert mit der Spanne aus dem Scoring | `fine_search.json` |
| Literaturprüfung | Websuche zu 30 Regionen mit „neuen“ Spitzenorten: 2 etabliert, 3 untersucht, 25 ohne Nachweis | `novelty_check.json`, `docs/novelty_check.md` |

Kennzahlen (Stand 15.11.): Der beste Ort bleibt bei 7 von 14 Mars-Zielen und 11 von 13 Mond-Zielen in mindestens
80 % der Gewichtungen in den Top 20. Steckbriefe: 53 von 104 Zellen einheitlich, bei 25 mindestens ein Viertel
steiler als 15°. Feinsuche (134 Ort-Ziel-Paare): Geländenote im Median 0,86 → 0,94; bei 61 Paaren Verbesserung
≥ 0,05; bei 43 liegt das beste Quadrat am Rand des Suchbereichs.

---

## 9. Ausgabedateien (`results/`)

| Datei | Format | Inhalt |
|---|---|---|
| `top_sites.json` | JSON, 9 MB | `meta`; je Ziel Name, Körper, Kategorie, Koordinaten, `top`, `excl_china`, `by_continent`, `by_continent_excl_china`, `features_used` (Methode, Zielwert, Spanne, Perzentil, Gewicht, Noten) |
| `top_sites.csv` | CSV | Top 20 je Ziel als flache Tabelle |
| `pool.npz` | numpy, je Ziel `<id>/lat`, `/lon`, `/total`, `/rank`, `/dims`, `/conf`, `/fs`, `/fv`, `/fkeys`, `/cls`, `/iso`, `/cont`, `/known`, `/nranked`; global `_dims`, `_classes`, `_continents`, `_known` | Kandidatenpool |
| `pool_flags.npz`, `robustness_pool.npz` | numpy, je Ziel ein Array in Pool-Reihenfolge | Eigenschaften (uint16-Bitmaske), Robustheit (uint8, ·254) |
| `robustness.json` | JSON `{ziel: {"lat,lon": Anteil}}` | Robustheit der Listen-Orte |
| `fine_search.json` | JSON `{ort: {ziel: {best, centre, target, box_km, pixel_m}}}` | Feinsuche |
| `novelty_check.json` | JSON | Literaturprüfung mit Quellen |

Beispiel:
```python
import json; R = json.load(open("results/top_sites.json"))
site = R["targets"]["jezero_crater"]["top"][0]
print(site["country"], site["cell_rank"], site["env_reason"], site["features"])
```

---

## 10. Web-App (`web/`)

**Bau:** `python web/build_web.py` erzeugt `web/index.html` (vollständiges Dokument für GitHub Pages und Server) und
`web/artifact.html` (Fragment für das Claude-Artifact) aus `template.html` und allen Daten; eine Datei, ca. 8 MB,
kein Server nötig. Eingebettet: Zielwerte, Listen, Heatmaps (je Ziel ein Perzentil-PNG in Web Mercator, im Browser
eingefärbt), Pool (base64), Mars- und Mondkarte (MOLA/LOLA-Schummerung als JPEG), China-Maske, Glossar, Grundkarte
(Natural Earth 1:110m).

**Funktionen:**
* **Zielwahl:** Mars/Mond-Reiter, Zielliste, anklickbare Karten von Mars (global) und Mond-Südpol (bis 82,4° S); nah
  beieinanderliegende Ziele werden mit Hilfslinie auseinandergezogen; große Ansicht mit allen Namen.
* **Weltkarte:** Heatmap der Ähnlichkeit (ab 65. Perzentil), nummerierte Pins (neu golden, bekannt grau);
  umschaltbarer Satelliten-Hintergrund (NASA GIBS, Landsat-WELD-Jahresmosaik, Kacheln bis Zoom 12); beim gewählten
  Ort sind die 5-km-Zelle (gelb) und das beste Quadrat der Feinsuche (cyan) eingezeichnet; „Show on satellite map“
  zoomt dorthin.
* **Listen:** Top 20 oder bester Ort je Kontinent; Spalten Land, Klasse, Zellplatz, Robustheit, stärkste/schwächste
  Dimension, bekannt/neu; Schalter „Exclude China“ und „Only new sites“; Zustand im Link (`#gale-crater&exclude=china&view=continents`).
* **Eigene Auswertung:** Filter nach Umgebungsklasse, nach Zusatzeigenschaften (alle angekreuzten müssen zutreffen),
  „nur robuste Orte (≥ 80 %)“, „Most important“ (Dimension × 3) und Regler je Dimension. Bei Filtern oder eigener
  Gewichtung rechnet die App Liste, Pins und Kontinent-Ansicht im Browser aus dem Pool neu (gleiche Formel und
  200-km-Regel wie das Scoring); mit eigener Gewichtung zeigt sie den eigenen Gesamtwert statt des Zellplatzes.
* **Zielkarte:** Mess- und Schätzwerte mit Verlässlichkeitsnote und Quelle; physikalisch feste Werte (Vakuum, kein
  Wind, kein Niederschlag …) getrennt in einer Zeile; Grenzen der Analogie.
* **Ortskarte:** Land, Koordinaten, Klasse, Eigenschaften, bekannt/neu, Zellplatz, Datenabdeckung, Robustheit,
  Profil der Dimensionen, „What makes this terrain special“ (2–4 Aussagen aus den Messwerten, `highlights.py`),
  Ergebnis der Feinsuche, Links zu Steckbrief, OpenStreetMap und NASA Worldview.
* **Begründung:** Tabelle je Merkmal (Ziel, Erde, Methode, Teilnote, Gewicht) und Klassenbegründung (erfüllte Regeln,
  Grund für jede ausgeschlossene Klasse).
* **Vergleich:** bis zu 3 Orte nebeneinander mit allen Werten, bester Wert je Zeile markiert.
* **Glossar:** jeder Begriff unterstrichen oder mit „?“; Klick öffnet die Erklärung; vollständiges Glossar unten.

**Weitere Seiten:**
* `make_results_page.py` → `ergebnisse.html` (Deutsch): Kennzahlen, bester Treffer je Ziel (auch ohne China), Top 10
  je Ziel, Robustheit, Feinsuche, Literaturprüfung, Methode, Grenzen; Begriffe mit dem Glossar verlinkt.
* `make_profiles_page.py` → `profiles.html` (Englisch): die 104 Steckbriefe mit Einschätzung und Feinsuche je Ziel.
* `glossary.py` + `make_glossary_page.py` → `glossar.html`, `glossary.html` (je 89 Einträge); Klassenregeln,
  Profilgewichte und bekannte Analoga werden aus dem Code erzeugt.

**Kernaussagen** („What makes this terrain special“, `web/highlights.py`): 2–4 Aussagen je Ort aus den
Messwerten (Gelände im Vergleich zum Ziel, Trockenheit, Höhe/Druck, Kälte, Tagesgang, Albedo- und Trägheitsrang,
Staubstürme, tiefe Sonne, Eigenschaften) und ein Satz zur Bedeutung der Umgebungsklasse; in der App (für Pool-Orte
im Browser nachgebaut), in den Steckbriefe und auf der Ergebnisseite (Top 3 je Ziel).

**Geplant:** Zielausschnitte mit Zielquadrat und benannten Kratern (IAU-Namensverzeichnis liegt bereit).

---

## 11. Kontrolle und behobene Fehler

Die Änderungen an der Web-App wurden im Browser geprüft (Konsole ohne Fehler, Stichproben der Werte, das Layout stichprobenweise auch bei Telefonbreite); Skripte mit Testläufen auf dem gröberen 0,25°-Raster vor dem vollen Lauf.
Wichtige Korrekturen während des Projekts:

* 32-Bit-Summen über Millionen Zellen ergaben Perzentile über 100 % → 64 Bit.
* Fehlende Mindestabdeckung ließ Zellen mit Datenlücken nach oben rutschen → 80-%-Regel.
* Geländelücken in hohen Breiten (Zellen schmaler als ein Pixel, Randpixel) → Spaltenzuordnung, Randauffüllung.
* `terrain.py` tastete beim Vergröbern nur ab → vorher mitteln.
* Tundra unter den Mond-Treffern (89 von 260) → nur kahles Land im Ranking.
* Artemis-Kraterregionen lagen im Dauerschatten, Gale auf dem Zentralberg → Kraterrand-Suche, Landestelle.
* Listen-Orte fehlten im Pool (200-km-Regel) → `augment_pool.py`.
* Zusatzeigenschaft „Staubquelle“ wurde für Listen-Orte über die Liste statt über alle Landzellen berechnet (114
  falsch) → einmal über die ganze Tabelle.
* Klassenregeln: Salzpfannen als Schnee (Temperaturbedingung), Atacama als bewachsen (NDVI-Jahresmaximum).
* Mond-Ortsliste: die 14 früheren Landungen kamen erst nach dem Aufbau von `targets.json` in die Liste und fehlen
  (siehe Grenzen).

---

## 12. Projektseite und Server (IONOS, `server/`, nur lokal im Projekt)

* **Maschine:** AlmaLinux 9.7, SELinux aktiv. Auf derselben Maschine laufen andere Dienste, die unverändert bleiben.
* **nginx:** eigene Konfiguration `/etc/nginx/conf.d/analog.conf` (Hauptkonfiguration unverändert), statischer Ordner
  `/var/www/analog`, Sicherheits-Header, gzip, nur HTTP (keine Domain).
* **To-do-Dienst:** `server/todo/server.py`, nur Python-Standardbibliothek, lauscht auf `127.0.0.1:8009`, systemd-Dienst
  `analog-todo` als Systembenutzer `analogtodo` ohne Login, Daten in `/var/lib/analog-todo/todos.json` (atomar
  geschrieben). API: `GET/POST /api/todos`, `PATCH/DELETE /api/todos/<id>`; Felder Text, Gruppe (frei), Priorität
  (hoch/mittel/niedrig), zuständig, erledigt. nginx verlangt für alles außer GET HTTP Basic Auth
  (`/etc/nginx/analog-todo.htpasswd`, Zugänge legt Vicente an); SELinux-Schalter `httpd_can_network_relay`.
* **Projektseite:** `server/make_project_page.py` erzeugt Stand, Meilensteine mit Countdown, die To-do-Liste
  (sortierbar nach Gruppe oder Priorität, Erledigte ausblendbar) und bettet die Web-App ein.
* **Auslieferung:** `server/deploy.sh` (Seite bauen, Web-App, Ergebnisse, Glossar, Steckbriefe kopieren, per SSH
  austauschen); `--setup` richtet nginx, Dienst und Benutzer einmalig ein. Der Ordner liegt nicht im öffentlichen
  Repo, weil er die Serveradresse enthält.

---

## 13. Veröffentlichung

* **Repos:** `Vice003/analog-finder` (öffentlich, eigene Arbeit ohne die grobe Team-Pipeline) und
  `Vice003/NASA-Challenge` (Team-Repo, Kopie unter `vicente/`, Zielseite unter `planetary/`). Commits als
  „Vicente <Vice003@users.noreply.github.com>“.
* **GitHub Pages:** jeweils aus `docs/` auf `main`.
* **Claude-Artifacts (privat):** Web-App und deutsche Ergebnisseite.

---

## 14. Nachbauen

```bash
pip install -r requirements.txt
python earth/download_modis.py --yes
python earth/clim_modis.py lst && python earth/clim_modis.py ndvi && python earth/clim_modis.py snow
python earth/surface_static.py
python earth/clim_merra.py monthly && python earth/clim_merra.py daily && python earth/clim_merra.py precip
python earth/dem_features.py && python earth/dem_baselines.py
python earth/build_features.py
python planetary/compute_targets.py            # Rohdaten in data/planetary/raw (siehe Kopf des Skripts)
python scoring/target_scoring.py planetary/targets.json earth_features_005deg.parquet
python scoring/pool_flags.py && python scoring/robustness.py
python web/make_site_profiles.py && python web/fine_search.py && python web/make_site_profiles.py
python web/make_profiles_page.py && python web/make_glossary_page.py
python web/build_web.py
python web/make_results_page.py results/top_sites.json web/ergebnisse.html
```

`make_site_profiles.py` läuft zweimal, weil die Bilder das beste Quadrat der Feinsuche einzeichnen und die
Feinsuche die Steckbrief-Liste braucht. Danach `web/index.html`, `web/profiles.html`, `web/profiles/`,
`web/glossar.html`, `web/glossary.html` und die Ergebnisseite nach `docs/` kopieren.

---

## 15. Grenzen und offene Punkte

* Kein Ort der Erde hat Vakuum, niedrige Schwerkraft oder die Strahlung von Mond und Mars.
* Mars-Temperatur, Tagesgang, Druck und Bodeneis sind Schätzwerte (Note C); Mars-Staub (TES) und Bodeneis (Odyssey
  GRS) fehlen.
* MERRA-2 (55 km) ist regional, nicht lokal.
* Nur Mond-Südpol-Ziele; die 14 früheren Mond-Landungen der Ortsliste und die Nordpol-Kandidaten aus dem globalen
  Screening des Mond/Mars-Teams sind nicht aufgenommen (Eis dort nicht bestätigt, lange Nächte).
* Mars-Treffer ballen sich in Hochasien; die Liste je Kontinent und die eigene Gewichtung zeigen die Alternativen.
* Feinsuche nur für Gelände und bis 8 km; bei 43 Paaren liegt das beste Quadrat am Rand.
* Literaturprüfung englischsprachig, ohne Fachdatenbanken; Lop Nur und Dunhuang/Kumtag nachprüfen.
* „Extreme cold“ kommt im Ranking nicht vor (alle so kalten Zellen sind Eisschilde).
* Kraterausschnitte der Zielorte noch nicht gebaut (Abschnitt 10).
