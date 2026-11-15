> Ursprünglich der Ordner `vicente/` im Team-Repo Vice003/NASA-Challenge. Vergleiche mit „Team-Pipeline (`scripts/`)“ beziehen sich auf jenes Repo.

# Erd-Datenbasis (Vicente)

Eigener Arbeitsordner neben der Team-Pipeline in `scripts/`. Hier liegt eine **mehrjährige, feiner aufgelöste
Erd-Datenbasis** mit Kategorien und Scoring. Die Team-Dateien außerhalb dieses Ordners sind unverändert.

Ausführliche Beschreibung als Seite: [`docs/datenbasis.html`](docs/datenbasis.html) (im Browser öffnen).

**Web-App (Englisch):** `web/` – `python web/build_web.py --targets ../planetary/targets.json` baut `web/index.html`
(eine Datei, ohne Server). Live über GitHub Pages aus dem Ordner `docs/` im Repo-Wurzelverzeichnis.
Funktionen: Mars- und Mondkarte mit anklickbaren Zielen, Weltkarte mit Ähnlichkeit, Top 20 je Ziel,
Schalter „Exclude China“, Vergleich von bis zu 3 Orten, Begründung je Ort (Merkmale und Umgebungsklasse).

## Was hier anders ist als in der Team-Pipeline

Bewusst als Alternative gebaut, nichts davon ersetzt die Entscheidungen in `CLAUDE.md` ohne Absprache.

| Punkt | Team-Pipeline (`scripts/`) | Dieser Ordner |
|---|---|---|
| Gitter | 20′ (ca. 37 km) bzw. EASE-Grid 10 km geplant | 0,05° geographisch (ca. 5,5 km), 8,9 Mio. Landzellen |
| Zeitraum Thermik | MYD11C3 2023/2024, ein Jahr | 2003–2024, Terra **und** Aqua (4 Messzeiten pro Tag) |
| Gelände | ETOPO1 bzw. DEM nur für Kandidatenzonen | Copernicus GLO-90 global, aus 90-m-Pixeln pro 0,05°-Zelle |
| Staub, Wind, Stürme | nicht enthalten | MERRA-2: Staub-AOD, Staubemission, Staubsturm- und Sturmtage pro Jahr |
| Niederschlag | WorldClim 2.1 | MERRA-2 `PRECTOTCORR` (IMERG nur Zusatz, misst in der Atacama falsch) |
| Albedo | MCD43C3 2024 | MCD43C3 2024, zusätzlich **schneefrei** |
| Scoring | Abstand zum Zielwert, Perzentile 2–98 | Perzentil-Rang Richtung Ziel (flächengewichtet), Zielwert nur wo die Erde ihn erreicht |
| Bekannte Analoga | 50-km-Puffer | Radius je Ort (20–300 km), Markierung „bekannt“/„NEU“ |

Alle Quellen sind NASA Earthdata (LP DAAC, NSIDC, GES DISC) oder Copernicus und damit von der Challenge-Seite gedeckt.

## Einbindung in die Team-Pipeline

`derived/` enthält die Merkmale auf dem Gitter von `scripts/pipeline.py`: 10′, 1080 × 2160, Nord oben,
Zellmitten, Format wie `data/derived/*.npz` (Schlüssel `a`, float32, NaN = keine Daten). Die 0,05°-Pixel sind
mit derselben Zuordnung gemittelt wie in `scripts/modis_lst.py`, die Zellgrenzen sind also identisch.
Erzeugt mit `python earth/to_team_grid.py`.

**Direkt austauschbar** (gleicher Dateiname, gleiche Bedeutung, kein Code ändern):

| Datei | Team-Version | Diese Version |
|---|---|---|
| `modis_dtr.npz` | Aqua Tag − Nacht, 2023 | 2003–2024, Terra + Aqua, max − min der 4 Überflugwerte |
| `modis_ndvi.npz` | 2023 | 2003–2024 |

Ausprobieren: diese beiden Dateien nach `data/derived/` kopieren und die Pipeline neu laufen lassen.

**Ersatz für WorldClim-Niederschlag** (gleiche Einheit mm/Jahr): `prec.npz` aus MERRA-2. In `pipeline.py`
müsste dafür nur die Zeile `prec, _ = packed('prec.rda')` durch `prec = np.load(f'{D}/prec.npz')['a']`
ersetzt werden (nicht umgesetzt, Team-Datei).

**Neue Merkmale** für zusätzliche Dimensionen: `lst_mean`, `lst_cold`, `lst_seasonal_amp`, `freeze_thaw`,
`albedo_snowfree`, `ati`, `snow_perm`, `dust_aod`, `dust_emission`, `dust_event_days`, `dust_storm_days`,
`wind_mean`, `wind_storm_days`, `pressure`, `humidity`. Für eine neue Dimension braucht `pipeline.py` je einen
Eintrag in `F_raw`, `TR` und `RNG` sowie einen Zielwert in `TARGETS`.

**Höhe:** `elevation.npz` = mittlere Höhe in Metern aus Copernicus GLO-90 (ESA), Mittel der 90-m-Pixel je 10′-Zelle,
Meer = NaN. Ein Erdprodukt aus den Challenge-Quellen; wer ein Höhenmodell auf diesem Gitter braucht, kann es statt
ETOPO1 (NOAA) verwenden. Über Land vollständig (geprüft gegen die MODIS-Landmaske).

`flat_frac_90m` und `slope_p90_90m` stammen aus 90-m-Pixeln und haben **nicht** die 18,5-km-Basislänge der
Pipeline. Mit den LOLA/MOLA-Zielwerten sind sie deshalb nicht vergleichbar; sie dienen nur der Beschreibung
von Kandidaten (z. B. „wie viel landefreundliche Fläche hat die Zelle“).

Stand der Dateien: vollständig (alle Erdmerkmale 2003–2024).


## Mond- und Mars-Zielsignaturen

Die Planetendaten kommen über [`../planetary/`](../planetary/): Dort tragen die Mond/Mars-Verantwortlichen die
Werte der Zielgebiete in `planetary/targets.json` ein (Spezifikation `planetary/ZIELSIGNATUREN.md`).
`scoring/target_scoring.py` liest die Datei und bewertet jede Erdzelle je Merkmal auf eine von drei Arten:
direkter Wertvergleich (gleiche Größe), Rang-Abgleich (anderes Instrument, z. B. TES-Trägheit gegen ATI)
oder Richtung (die Erde erreicht den Wert nie, z. B. Luftdruck).

```bash
python scoring/target_scoring.py ../planetary/targets.json
```

## Aufbau

```
vicente/
├── earth/
│   ├── download_modis.py   erste MODIS-Dateien (Albedo 2024, Landbedeckung 2022, LST 2024)
│   ├── surface_static.py   Albedo inkl. schneefrei, Landbedeckung
│   ├── clim_modis.py       Temperatur (lst), NDVI (ndvi), Schnee (snow) 2003–2024
│   ├── dem_features.py     Höhe, Relief, Hangneigung, landefreundliche Fläche aus GLO-90
│   ├── clim_merra.py       monthly | precip | daily: Staub, Wind, Druck, Feuchte, Niederschlag, Ereignistage
│   ├── clim_imerg.py       IMERG-Niederschlag als Zusatz
│   ├── build_features.py   alles zur Merkmalstabelle (Parquet, 0,05° und 0,25°)
│   └── to_team_grid.py     Merkmale auf das 10′-Gitter der Team-Pipeline -> derived/
├── derived/                Merkmale im Format von data/derived/ (10′, Schlüssel "a")
├── scoring/
│   ├── categories.py       Umgebungsklassen, Flags, 9 Dimensionen, 3 Zielprofile, Bewertung, Testorte
│   └── target_scoring.py   Bewertung gegen die gemessenen Zielsignaturen aus planetary/targets.json
├── docs/
│   ├── datenbasis.html     ausführliche Beschreibung
│   └── earth_features_quicklook.png   Kontrollkarte mit allen Bausteinen
└── MODIS_laden.command     Doppelklick-Start für download_modis.py (macOS)
```

## Ausführen

Im Ordner `vicente/`. Pakete: `earthaccess pyhdf netCDF4 rasterio affine==2.4.0 pandas pyarrow matplotlib`.
Earthdata-Login nötig; für MERRA-2 und IMERG im Profil die App „NASA GESDISC DATA ARCHIVE“ freigeben.

```bash
python earth/download_modis.py
python earth/surface_static.py
python earth/clim_modis.py lst
python earth/clim_modis.py ndvi
python earth/clim_modis.py snow
python earth/dem_features.py
python earth/clim_merra.py monthly
python earth/clim_merra.py precip
python earth/clim_merra.py daily
python earth/clim_imerg.py
python earth/build_features.py
python scoring/categories.py
```

Die Läufe laden zusammen rund 200 GB, rechnen im Durchlauf und behalten nur wenige GB. Abgebrochene Läufe
setzen beim letzten Zwischenstand wieder an. Die Ergebnisse landen in `data/earth/` und sind nicht im Repo
(einzelne Dateien bis 140 MB).

## Stand 14.11.2026

- Fertig: Albedo/Landbedeckung, Schnee, MERRA-2 Monatswerte, MERRA-2 Niederschlag, IMERG
- Fertig: Temperatur 2003–2024, NDVI, Höhenmodell GLO-90 global
- Fertig: MERRA-2 Ereignistage (Staubsturm- und Sturmtage)
- Testorte der Umgebungsklassen: 13 von 14 richtig
- Fertig: Gelände bei 100/463 m mit common/terrain.py (`slope_p50_100m` … `relief_463m` in derived/)
- Offen: Korrekturen 5, 6, 9–12 aus VERARBEITUNGSPLAN.md; Permafrost, UV, Erreichbarkeit
