> Übernommen aus dem Team-Repo [Vice003/NASA-Challenge](https://github.com/Vice003/NASA-Challenge). Pfade wie `vicente/earth/` entsprechen hier `earth/`, `vicente/scoring/` → `scoring/` usw.

# Verarbeitungsplan (verbindlich für alle)

Stand: Sa 14.11.2026, 13:30. Gilt für Erde, Mond, Mars, Scoring und Karte, und für jeden Claude, der im Repo arbeitet.
Änderungen an diesem Plan nur nach Absprache im Team; dann hier eintragen (Abschnitt 10).

## 1. Grundsatz

**Feine Rasterung, gleiche Methode auf allen Körpern.** Jedes Merkmal wird auf der Erde und auf dem Zielkörper
mit derselben Pixelgröße und demselben Code berechnet. Verglichen wird ein **Zielort von 10–20 km** mit einer
**Erdzelle von ca. 5 km**. Die 100-km-Zielgebiete aus dem ersten Plan sind verworfen.

Die bestehende Pipeline in `scripts/` (37-km-Zellen, `index.html`) bleibt als **Rückfallebene** unverändert
lauffähig, bis die feine Pipeline die Prüfungen in Abschnitt 8 besteht (Ziel: M2, So 13:00).

## 2. Verbindliche Konventionen

| Thema | Festlegung |
|---|---|
| Erd-Analysegitter | 0,05° geographisch (MODIS-CMG-Gitter), 3600 × 7200, Nord oben, Zellmitten, Länge −180…180. Zeile `i` ↔ Breite `90 − 0,05·(i + 0,5)` |
| Flächengewichtung | Jede Statistik über Erdzellen (Perzentile, Spannen) mit Gewicht `cos(Breite)` |
| Zielorte | Polygon 10–20 km als GeoJSON, Koordinaten **planetozentrisch**, Länge **Ost 0…360** (Mond, Mars) |
| Klimazeitraum Erde | 2003–2024 (22 Jahre). Ausnahme: Albedo 2024, Landbedeckung 2022, DEM-Aufnahme |
| Einheiten | Temperatur K, Druck hPa, Länge m, Winkel Grad, Niederschlag mm/Jahr, Wind m/s |
| Fehlwerte | `NaN` in Arrays, `null` in JSON. Niemals 0 als Platzhalter |
| Dateiformate | Gitter: `.npz` (float32) oder GeoTIFF; Tabellen: Parquet; Zielwerte: `planetary/targets.json` |
| Datenquellen | Nur, was die Challenge-Seite nennt: NASA Earthdata, NASA PDS (auch USGS/PGDA-Spiegel), ESA Copernicus |
| Große Dateien | Nicht ins Repo (GitHub-Grenze 100 MB). Ergebnisse > 50 MB als **GitHub-Release-Anhang** |
| Commits | `[Name] Nachricht`, nur eigene Ordner ändern (Abschnitt 6) |

## 3. Zielorte

Jedes Ziel ist ein Ort, an dem tatsächlich gelandet oder gebaut würde. Die Zuständigen für Mond und Mars legen
die Polygone fest und tragen sie in `planetary/targets.json` ein (`region_geojson`).

| ID | Körper | Ort | Größe | Hinweis |
|---|---|---|---|---|
| `shackleton_rim` | Mond | beleuchteter Kamm Shackleton–de Gerlache | ca. 15 × 15 km | Größe einer Artemis-III-Kandidatenregion. Nur der beleuchtete Bereich |
| `shackleton_psr` | Mond | dauerhaft beschatteter Kraterboden | so groß wie nötig | optional; Eis-Ressource. Temperaturen unter 110 K gibt es auf der Erde nicht |
| `jezero` | Mars | Landestelle/Delta im Krater | ca. 10 × 10 km | Größenordnung der Perseverance-Landeellipse (7,7 × 6,6 km) |
| `arcadia` | Mars | eisreiche Ebene | ca. 20 × 20 km | weiträumig gleichförmig |

## 4. Merkmale und gemeinsame Berechnung

**Gelände wird überall mit derselben Funktion berechnet: `common/terrain.py`.** Planetendaten und Erddaten
gehen durch denselben Code. Niemand schreibt eine eigene Neigungsberechnung.

| Merkmal | Pixel/Fenster | Erde | Mond | Mars | Vergleich |
|---|---|---|---|---|---|
| `slope_p50`, `slope_p90` | DEM auf **100 m** (Mond) bzw. **463 m** (Mars) | Copernicus GLO-90, neu abgetastet | LOLA polar | MOLA 463 m | direkt |
| `relief` | P95 − P5 je **5 km**-Fenster, Median | GLO-90 | LOLA | MOLA | direkt |
| `albedo` | nativ | MODIS MCD43C3, schneefrei | LOLA LDAM (1064 nm) | OMEGA ALBEDO_R1080 (1,08 µm) | Rang (verschiedene Wellenlängen) |
| `thermal_inertia` | nativ | ATI = (1 − Albedo)/Tagesgang | kein Produkt → `null` | TES-TI (ODE TIMAP, 3 km) | Rang |
| `dust_opacity` | nativ | MERRA-2 Staub-AOD | – | TES/MCS | Rang |
| `surface_temp_mean`, `_min`, `diurnal_range` | nativ | MODIS Terra+Aqua | Diviner | TES/Literatur | Richtung |
| `pressure` | 0,05° | MERRA-2, mit DEM auf Höhe umgerechnet | Vakuum | Literatur | Richtung |
| `precip`, `humidity`, `ndvi`, `wind_mean` | nativ | MERRA-2 / MODIS | 0 | Literatur / 0 | Richtung |
| `ground_ice` | 0,05° | Permafrost-Karte (ESA CCI), sonst Kälte-Proxy | Diviner-Eisstabilität | Odyssey GRS, wasseräquivalenter Wasserstoff (ca. 300 km) | Richtung |

**Rang-Abgleich:** Das Ziel wird als Perzentil auf seinem Körper angegeben (`body_percentile`). Auf der Erde wird
das Perzentil **nur über vegetationsfreie, eisfreie Landzellen** gebildet, weil Mond und Mars ebenfalls
vegetationsfrei sind. Sonst würde z. B. feuchter Waldboden die Erd-ATI-Verteilung verzerren.

Vollständige Feldbeschreibung: `planetary/ZIELSIGNATUREN.md`.

## 5. Bewertung (eine Metrik für alle)

Eine Implementierung, kein paralleles Scoring: `vicente/scoring/target_scoring.py` → wird nach M1 nach
`scoring/` verschoben.

- **direkt:** S = 1 − |Erde − Ziel| / Spanne, Spanne = Abstand vom Ziel zur unähnlichsten Erde (P2…P98, flächengewichtet). Wie `scripts/rank.py`.
- **Rang:** dasselbe auf Perzentilen (Erde gegen `body_percentile`).
- **Richtung:** flächengewichtetes Perzentil in Richtung Ziel; zusätzlich als Grenze der Analogie ausgewiesen.
- **Verlässlichkeit A/B/C** (Skala aus `docs/official_sources_audit.md`, Branch `Mars_and_Moon`): jedes Merkmal wird mit
  *Note Zielwert × Note Erd-Gegenstück* gewichtet (A = 1, B = 0,7, C = 0,4); jede Dimension zusätzlich mit dem mittleren
  Gewicht ihrer Merkmale. Pflichtfeld `reliability` in `targets.json`.
- Dimensionen = gewichtetes Mittel ihrer Merkmale; Gesamtwert = gewichtetes Mittel der Dimensionen, **nur zum Sortieren**.
- **Mindestabdeckung:** ins Ranking kommt eine Erdzelle nur, wenn sie mindestens 80 % des Gewichts der Dimensionen belegt, für die das Ziel Werte hat.
- Gezeigt wird immer das **Profil**: stärkste Dimension („passt“), schwächste („bricht“), Abdeckung.
- **Masken vor dem Ranking:** Wasser (> 50 % der Zelle), Eisschilde und Gletscher, Zellen mit > 50 % Wald/Acker/Siedlung.
  Eisschilde bleiben nur als eigene Umgebungsklasse „Eis-Prozess“ sichtbar.
- **Bekannte Analoga:** eine gemeinsame Liste `data/known_analogs.csv` (Name, Breite, Länge, Radius km).
  Treffer darin sind „bekannt“, alle anderen „neu“. Die Liste ändert die Bewertung nicht.

## 6. Datenfluss und Zuständigkeiten

```
Erde (A)            vicente/            ──► data/earth/earth_features_005deg.parquet  (Release-Anhang)
Mond (B1), Mars (B2) planetary/          ──► planetary/targets.json  (+ Skripte, keine Rohdaten)
gemeinsam           common/terrain.py   ◄── von A, B1, B2 benutzt, Änderungen nur nach Absprache
Scoring             scoring/            ──► results/<ziel>_top.json, results/<ziel>_<dimension>.png
Karte & Story (C)   web/, index.html    ◄── liest nur results/
```

| Rolle | Ordner | Liefert |
|---|---|---|
| A Erde (Vicente) | `vicente/`, `common/` | Erdmerkmale 0,05°, Gelände bei 100 m und 463 m, Masken, Release-Anhang |
| B1 Mond | `planetary/` | `shackleton_rim` (+ optional `_psr`): Polygon, Gelände, Diviner-Werte mit Quellen |
| B2 Mars | `planetary/` | `jezero`, `arcadia`: Polygon, Gelände, TES-TI/-Albedo/-Staub mit Perzentilen und Quellen |
| Scoring | `scoring/` | Ranking, Kontrollen, `results/` |
| C Karte & Story | `web/`, `index.html` | Karte aus `results/`, Projektseite und Demo auf Englisch |

## 7. Zeitplan

| Wann | Was | Wer |
|---|---|---|
| Sa 16:00 | `common/terrain.py` im Repo; Zielpolygone festgelegt | A; B1, B2 |
| Sa 20:00 (M1) | `targets.json` mit Gelände und Thermik, Prüfskript 0 Fehler; Erdmerkmale komplett inkl. Gelände 100/463 m | B1, B2; A |
| So 10:00 | erstes Ranking mit allen Zielen, `results/` für die Karte | Scoring |
| So 13:00 (M2) | Prüfungen aus Abschnitt 8 bestanden → feine Pipeline ersetzt die Rückfallebene | alle |
| So 22:00 (M3) | Einreichung komplett, Puffer bis 23:59 | C |

## 8. Prüfungen (Pflicht vor M2)

1. **Positivkontrolle:** Bekannte Analoga landen im passenden Ziel in mindestens einer Dimension über dem 90. Perzentil
   (z. B. Atacama bei Jezero/Trockenheit, Haughton bei Mond/Gelände).
2. **Negativkontrolle:** Feuchte Mittelbreiten und Tropenwald landen unten.
3. **Robustheit:** Top 20 bleiben weitgehend gleich, wenn die Dimensionsgewichte um ±25 % schwanken.
4. **Testorte der Umgebungsklassen** (`vicente/scoring/categories.py`): mindestens 12 von 15 richtig.
5. **Plausibilität der Zielwerte:** `planetary/check_targets.py` mit 0 Fehlern, keine Quelle „offen“.

## 9. Gefundene Probleme und Korrekturen

| # | Problem | Folge | Korrektur | Wer |
|---|---|---|---|---|
| 1 | 100-km-Zielgebiete mischen Landschaften (Kraterrand + Kältefalle, Kraterboden + Umland) | Median beschreibt kein reales Gelände | Zielorte 10–20 km (Abschnitt 3) | B1, B2 |
| 2 | Neigung auf Erde und Ziel unterschiedlich berechnet (Kugelfunktionen 18,5 km, 90-m-Pixel, „463 m“ ohne Methode) | Werte nicht vergleichbar | eine Funktion `common/terrain.py`, feste Pixelgrößen | A |
| 3 | ~~Vorbelegte Mondwerte (103 K, 150 K) unplausibel~~ – **berichtigt 14.11. 18:45:** laut Diviner PRP haben sonnige Polflächen im Mittel 110–140 K und im Maximum ~240 K; 103 K und 150 K liegen in der richtigen Größenordnung. Die Werte werden nun pro Ort aus Diviner bestimmt | – | Mondtemperatur aus Diviner PRP je Zielort (`planetary/compute_targets.py`) | Vicente · **erledigt** |
| 4 | Kahl-Regel NDVI < 0,12 stuft den Atacama-Kern (NDVI 0,124, heller Boden) als bewachsen ein | Fehlklassifikation genau der wichtigsten Orte | kahl = NDVI-Jahresmaximum < 0,15 **oder** MODIS-Klasse „barren“ ≥ 50 % | A · **erledigt 14:30** |
| 5 | NDVI-Mittel in Schneegebieten durch Schneemonate gedrückt (Island 0,045, Haughton 0,024) | Vegetation unterschätzt | NDVI nur über schneefreie Monate mitteln | A |
| 6 | Luftdruck aus MERRA-2 (55 km) per nächstem Nachbarn: Gebirge und Täler in einer Zelle gleich | Druck bis über 100 hPa falsch | MERRA-2-Druck mit DEM-Höhe auf 0,05° umrechnen | A |
| 7 | Rang-Abgleich bildet Erd-Perzentile über alle Landzellen, Mars-Perzentile über reine Wüste | Verteilungen nicht vergleichbar | Erd-Referenz nur vegetations- und eisfreies Land | A · **erledigt 14:30** |
| 8 | Eisschilde nicht aus dem Ranking ausgeschlossen (Antarktis-Plateau führt Mars-Listen an) | sinnlose Spitzenplätze | Maske Eisschild/Gletscher vor dem Ranking | A · **erledigt 14:30** |
| 9 | ATI in Schnee- und Feuchtgebieten physikalisch bedeutungslos | Störwerte | ATI nur bei Tagesgang > 5 K, schneefrei, vegetationsfrei | A |
| 10 | Bodeneis-Proxy aus Temperatur (Team-Formel) | grob | ESA-CCI-Permafrost 0,05° ergänzen | A |
| 11 | Zwei Listen bekannter Analoga (50-km-Puffer vs. Radien), zwei Scorings | widersprüchliche Ergebnisse | eine Liste `data/known_analogs.csv`, eine Metrik (Abschnitt 5) | A, Scoring |
| 12 | Zwei Tagesgang-Definitionen (Aqua Tag − Nacht vs. max − min aus 4 Zeiten) | Werte nicht austauschbar | max − min aus Terra+Aqua für alle | A |
| 13 | Längengrade gemischt (Mars 0…360 Ost, Erde −180…180) | Ziele an falscher Stelle | Konvention Abschnitt 2, Prüfskript prüft Bereich | B1, B2 |
| 14 | MERRA-2-Dimensionen (Staub, Wind) nur ca. 55 km aufgelöst | regionale, keine lokalen Werte | als Kontext gewichten (Abschnitt 5), in der Story so benennen | Scoring, C |
| 15 | Höchster Sonnenstand wurde „direkt“ verglichen, die Erde erreicht die ca. 1,5° am Mond-Südpol aber nie (Minimum ca. 23,4° an den Polen). Ein Anteil „Sonne über Horizont“ hilft nicht: über das Jahr ist er auf der ganzen Erde etwa 50 % | Dimension falsch skaliert | Methode „Richtung“: je flacher der höchste Sonnenstand, desto besser | Scoring · **erledigt 14:30** |

## 10. Änderungen an diesem Plan

| Datum | Änderung | Abgestimmt mit |
|---|---|---|
| 14.11. 13:30 | Erste Fassung; 100-km-Zielgebiete verworfen, feine Rasterung beschlossen | Vicente |
| 14.11. 14:30 | Korrekturen 4, 7, 8, 15 umgesetzt. Testorte der Umgebungsklassen: 13 von 14 richtig (Hajar wird als dunkles Gestein erkannt: Semail-Ophiolith, geologisch zutreffend). Dry Valleys bei 5 km nicht auflösbar (MOD10CM meldet überall Dauerschnee), als Datengrenze vermerkt | Vicente |
| 14.11. 16:00 | `common/terrain.py`: beim Vergröbern um nicht ganzzahlige Faktoren wird vorher gemittelt (vorher nur abgetastet; im Test 3,44° statt 3° bei 30 m kleinräumigem Relief). Neuer Selbsttest. Erd-Gelände bei 100/463 m: `vicente/earth/dem_baselines.py` | Vicente |
| 14.11. 16:45 | Nach `docs/official_sources_audit.md`: Albedo auf beiden Körpern als Rang (OMEGA 1,08 µm, LOLA 1064 nm); keine Gesteinshäufigkeit Mars und keine thermische Trägheit Mond in den offiziellen Quellen; Mars-Bodeneis aus Odyssey GRS statt SWIM; Verlässlichkeitsskala A/B/C als Gewicht übernommen | Vicente |
| 14.11. 19:05 | Freie Ziel-IDs; `planetary/targets.json` mit 27 Orten aus der Ortsliste des Mond/Mars-Teams, berechnet von Vicente (`planetary/compute_targets.py`): Gelände MOLA/LOLA mit `common/terrain.py`, Mars-Trägheit TES mit Körper-Perzentil, Mond-Temperatur und -Eis aus Diviner (Jimales Raster). Artemis-Regionen auf beleuchtete Flächen verschoben, weil die Liste Kratermittelpunkte nennt. Korrektur 3 berichtigt | Vicente |
| 14.11. 19:00 | Mindestabdeckung 80 % im Scoring (Zellen mit Lücken kamen sonst nach oben). Geländelücken in hohen Breiten behoben: `common/terrain.py` füllt die Randpixel jeder Kachel, `dem_baselines.py` weist bei Zellen schmaler als ein Pixel (polnah) die Pixelspalte über der Zellmitte zu. Höhenmodell 100/463 m wird neu gerechnet | Vicente |
| 14.11. 20:30 | Höhenmodell 100/463 m neu gerechnet (lückenlos bis in hohe Breiten), volles Scoring 0,05° neu (Perzentile in 64 Bit, vorher > 100 %). Ergebnisse enthalten je Ort die Aufschlüsselung je Merkmal (Ziel- und Erdwert, Methode, Teilnote, Gewicht, Rang auf der Erde) und die Begründung der Umgebungsklasse (erfüllte Regeln und die Bedingung, an der jede vorher geprüfte Klasse scheiterte). Zweite Top-20-Liste je Ziel ohne China (`excl_china`: CHN, HKG, MAC, de-facto-Grenzen Natural Earth, also inkl. Aksai Chin). Web-App: `vicente/web/`, live über GitHub Pages aus `docs/` | Vicente |
| 15.11. 11:00 | Ranking nur über vegetationsfreies Land (Kahl-Regel), vorher 89 von 260 Mond-Treffern in Tundra. Liste „bester Ort je Kontinent“ je Ziel (`by_continent`, auch ohne China). Platz unter allen bewerteten Zellen (`cell_rank`). Ziele: Gale auf Bradbury Landing (4,59° S, 137,44° E); Artemis-Kraterregionen mit Suchradius Kraterradius + 10 km (Haworth 121 K statt 44 K); Diviner-Abfrage auch in den Rasterecken (Cabeus jetzt mit Werten); Mars-Albedo aus TES (USGS-Mosaik 7,4 km), Vergleich über den Rang | Vicente |
