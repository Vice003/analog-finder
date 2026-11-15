# Zielsignaturen: Schnittstelle Mond/Mars → Erd-Scoring

Gehört zum [`VERARBEITUNGSPLAN.md`](../VERARBEITUNGSPLAN.md) (verbindlich). Diese Datei beschreibt, wie die Werte
der Zielorte auf Mond und Mars an das Erd-Scoring übergeben werden. Sie richtet sich an die Mond- und
Mars-Verantwortlichen **und an deren Claude**.

Kurz: Pro Zielort wird in **`planetary/targets.json`** eingetragen, welche Werte der Ort hat. Das Scoring vergleicht
jede Erdzelle (ca. 5 km) mit diesen Werten. Prüfen im Repo-Wurzelordner:
`python planetary/check_targets.py planetary/targets.json`

## Ablage

- Vorlage: [`targets_template.json`](targets_template.json). Start: `cp planetary/targets_template.json planetary/targets.json`
- Prüfskript: [`check_targets.py`](check_targets.py), nur Standard-Python
- Geländeberechnung: [`../common/terrain.py`](../common/terrain.py), **Pflicht** für `slope_p50`, `slope_p90`, `relief`

## Zielorte

| ID | Körper | Ort | Größe |
|---|---|---|---|
| `shackleton_rim` | Mond | beleuchteter Kamm Shackleton–de Gerlache | ca. 15 × 15 km |
| `shackleton_psr` | Mond | dauerhaft beschatteter Kraterboden (optional) | so groß wie nötig |
| `jezero` | Mars | Landestelle/Delta im Krater | ca. 10 × 10 km |
| `arcadia` | Mars | eisreiche Ebene | ca. 20 × 20 km |


**Seit 14.11. 18:30: freie Ziel-IDs.** Erlaubt ist jede ID aus Kleinbuchstaben, Ziffern und `_`, mit Pflichtfeld `body`
und optional `category`, `coord_quality` (`verified`/`approx`/`unverified`) und `site_source`. `planetary/targets.json`
enthält derzeit **27 Orte** aus der Ortsliste des Mond/Mars-Teams, automatisch berechnet mit `planetary/compute_targets.py`
(Mars 10 × 10 km, Mond 15 × 15 km; Artemis-Regionen auf den am besten beleuchteten Ausschnitt innerhalb 12 km verschoben).

Ein Zielort ist ein Ort, an dem gelandet oder gebaut würde, keine ganze Region. Kraterrand und Kältefalle,
Kraterboden und Umland gehören in getrennte Zielorte.

## Aufbau

```json
{
  "schema_version": 2,
  "targets": {
    "jezero": {
      "body": "Mars",
      "name": "Jezero-Krater, Landestelle",
      "center_lat": 18.44, "center_lon": 77.45,
      "region_geojson": {"type": "Polygon", "coordinates": [[[77.40, 18.39], [77.50, 18.39], [77.50, 18.49], [77.40, 18.49], [77.40, 18.39]]]},
      "features": {
        "slope_p90": {
          "value": 6.1, "p10": null, "p90": null,
          "unit": "deg", "pixel_m": 463, "body_percentile": null,
          "source": "MOLA MEGDR 128 ppd, common/terrain.py", "reliability": "A",
          "notes": ""
        }
      }
    }
  }
}
```

(Die Zahlen im Beispiel sind nur Platzhalter.)

Koordinaten: **planetozentrische Breite**, **Länge Ost 0…360**, in Grad. GeoJSON-Reihenfolge ist `[Länge, Breite]`,
der Ring ist geschlossen (erster = letzter Punkt).

## Felder pro Merkmal

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `value` | ja (oder `null`) | Wert für den Zielort (Median über das Polygon bzw. Ergebnis von `terrain_stats`) |
| `p10`, `p90` | empfohlen | 10- und 90-%-Perzentil im Polygon. Zeigt die Streuung bzw. Unsicherheit |
| `unit` | ja | Genau die Einheit aus der Merkmalsliste |
| `pixel_m` | bei Gelände | Pixelgröße, auf die das DEM gebracht wurde: **Mond 100, Mars 463** |
| `body_percentile` | bei Methode `quantile` | Anteil der **ganzen** Körperoberfläche mit niedrigerem Wert, 0…1, flächengewichtet |
| `source` | ja, sobald `value` gesetzt | Produkt und Literatur |
| `reliability` | ja, sobald `value` gesetzt | Verlässlichkeit nach der Skala aus `docs/official_sources_audit.md` (Branch `Mars_and_Moon`): **`A`** direkte Messung · **`B`** grob/lückenhaft oder bewährter Ersatzwert · **`C`** schwacher Ersatzwert. Geht als Gewicht ins Scoring ein (A = 1, B = 0,7, C = 0,4) |
| `notes` | nein | Freitext |

## Merkmalsliste

| Schlüssel | Einheit | Methode | Mond | Mars |
|---|---|---|---|---|
| `slope_p50` | deg | direct | LOLA → `terrain_stats(..., pixel_m=100)` | MOLA → `pixel_m=463` |
| `slope_p90` | deg | direct | wie oben | wie oben |
| `relief` | m | direct | wie oben (P95 − P5 je 5-km-Fenster, Median) | wie oben |
| `albedo` | 1 | quantile | LOLA `LDAM` (Normalalbedo 1064 nm) | OMEGA `ALBEDO_R1080` (1,08 µm, global) |
| `thermal_inertia` | J m-2 K-1 s-1/2 | quantile | kein Produkt in den offiziellen Quellen → `null` | TES `GLOBAL_TI_*_2007` (ODE `TIMAP`, 3 km, global) |
| `dust_opacity` | 1 | quantile | – | TES/MCS |
| `dust_storm_days` | d/yr | quantile | – | optional |
| `surface_temp_mean` | K | direction | Diviner | TES/Literatur |
| `surface_temp_min` | K | direction | Diviner PRP | TES/Literatur |
| `diurnal_range` | K | direction | Diviner | TES/Literatur |
| `pressure` | hPa | direction | Vakuum (1e-12) | Literatur |
| `wind_mean` | m/s | direction | 0 | Literatur/Modell |
| `precip` | mm/yr | direction | 0 | 0 |
| `humidity` | g/kg | direction | 0 | Literatur |
| `ndvi` | 1 | direction | 0 | 0 |
| `ground_ice` | 1 | direction | Anteil der Polygonfläche, in der Eis laut Diviner PRP in ≤ 1 m Tiefe stabil ist (ggf. mit LOLA-PSR-Karte) | wasseräquivalenter Wasserstoff aus Odyssey GRS als Massenanteil 0…1 (ca. 300 km grob, ein Wert für das ganze Polygon, Verlässlichkeit B) |
| `sun_elevation_max` | deg | direction | höchster Sonnenstand im Jahr (90 − \|Breite\| + Achsneigung 1,54°) | wie Mond, Achsneigung 25,19°, höchstens 90 |

**Methoden:** `direct` = Wert gegen Wert (gleiche Größe, gleiche Berechnung). `quantile` = Perzentil gegen Perzentil
(anderes Instrument, z. B. TES-Trägheit gegen Erd-ATI; deshalb `body_percentile` Pflicht). `direction` = die Erde
erreicht den Wert nie; bewertet wird, wie weit eine Erdzelle in diese Richtung geht.

**Albedo immer als Rang:** Die verfügbaren Albedo-Produkte messen bei einer Wellenlänge (LOLA 1064 nm, OMEGA 1,08 µm),
die Erde (MODIS) breitbandig. Das sind verschiedene Größen, deshalb `quantile` mit `body_percentile`.

**Nicht verfügbar in den offiziellen Quellen** (laut `docs/official_sources_audit.md`): thermische Trägheit Mond,
Gesteinshäufigkeit Mars, globale Gesteinshäufigkeit Erde. Diese Felder bleiben `null` bzw. werden nicht angelegt.

**Übersicht der Produkte und Zugriffswege** (PDS, ODE, Earthdata, Copernicus, ESA): `docs/official_sources_audit.md`
im Branch `Mars_and_Moon`. ODE (`oderest.rsl.wustl.edu`) enthält viele Produkte, die im PDS-Register fehlen.

## Regeln für die Berechnung

1. **Polygon** 10–20 km (siehe Zielorte), als `region_geojson`. Alle Werte beziehen sich auf dieses Polygon.
2. **Gelände nur mit `common/terrain.py`:** DEM-Ausschnitt laden, Pixelabstand in Metern bestimmen
   (bei Breite/Länge-Gittern `pixel_size_latlon`), dann `terrain_stats(dem, dx, dy, pixel_m)` mit `pixel_m` 100 (Mond)
   bzw. 463 (Mars). Ergebnis in `slope_p50`, `slope_p90`, `relief`. Kein eigener Neigungscode.
3. **Andere Merkmale:** Median der Pixel im Polygon, dazu `p10`/`p90`.
4. **`body_percentile`:** über die ganze Körperoberfläche, flächengewichtet (Breite/Länge-Gitter: Gewicht cos(Breite);
   polarstereographisch: Pixelfläche). Beispiel: Anteil der Marsfläche mit niedrigerer Trägheit als der Zielort.
5. **Einheiten** exakt wie in der Tabelle. Temperatur in Kelvin, Druck in hPa.
6. **Quellen** immer: Produktname und Literatur.

## Für Claude: verbindliche Regeln

- Keine Werte schätzen oder aus dem Gedächtnis eintragen. Unbekannt bleibt `null`.
- Literaturwerte nur mit vollständiger Quelle (Autor, Jahr, Tabelle/Seite).
- Schlüssel, Ziel-IDs und Einheiten nicht ändern oder übersetzen. Neue Merkmale nur nach Absprache.
- Gelände ausschließlich mit `common/terrain.py`. `common/` nicht ändern (gemeinsamer Code, nur nach Absprache).
- Nach jeder Änderung `python planetary/check_targets.py planetary/targets.json` ausführen und alle Fehler beheben.
- Nur in `planetary/` arbeiten. Rohdaten (DEM, PDS-Dateien) nicht committen, nur Skripte und `targets.json`.
- Werte mit Quelle „pipeline.py, gerundet - Quelle offen“ prüfen und mit echter Quelle ersetzen oder bestätigen.

## Was mit den Werten passiert

`vicente/scoring/target_scoring.py` (später `scoring/`) bewertet jede Erdzelle:
`direct`: S = 1 − |Erde − Ziel| / Spanne (Spanne = Abstand zur unähnlichsten Erde, P2…P98, flächengewichtet).
`quantile`: dasselbe auf Perzentilen; Erd-Referenz sind nur vegetations- und eisfreie Landzellen.
`direction`: flächengewichtetes Perzentil in Richtung Ziel.
Merkmale ohne Wert zählen nicht; die Spalte `coverage` zeigt den belegten Anteil.
