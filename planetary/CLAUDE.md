# planetary/ – Mond- und Mars-Zielsignaturen

Verbindlich ist der [`VERARBEITUNGSPLAN.md`](../VERARBEITUNGSPLAN.md) im Repo-Wurzelordner. Hier werden die Werte der
Zielorte auf Mond und Mars eingetragen, mit denen das Erd-Scoring jede Erdzelle (ca. 5 km) vergleicht.
Vollständige Spezifikation: `ZIELSIGNATUREN.md`. **Beides vor jeder Arbeit hier lesen.**

## Kurzfassung

- Ergebnis gehört in `planetary/targets.json`. Start: `cp planetary/targets_template.json planetary/targets.json`.
- Zielorte (10–20 km, keine 100-km-Regionen): `shackleton_rim` (Mond, beleuchteter Kamm), `shackleton_psr`
  (Mond, Kältefalle, optional), `jezero` (Mars), `arcadia` (Mars). Polygon als `region_geojson`,
  planetozentrische Breite, Länge Ost 0…360.
- Gelände (`slope_p50`, `slope_p90`, `relief`) **nur mit `common/terrain.py`**:
  `terrain_stats(dem, dx, dy, pixel_m)` mit `pixel_m` = 100 (Mond) bzw. 463 (Mars). In `source` vermerken.
- Pro Merkmal: `value`, `p10`/`p90`, `unit`, `source`, `reliability` (A/B/C wie in `docs/official_sources_audit.md`).
  Methode `quantile` (auch Albedo) zusätzlich `body_percentile`
  (flächengewichtet über den ganzen Himmelskörper).
- Nach jeder Änderung: `python planetary/check_targets.py planetary/targets.json`. Fertig erst bei 0 Fehlern.

## Verbindliche Regeln

- Keine Werte schätzen oder aus dem Gedächtnis eintragen. Unbekannt bleibt `null`.
- Literaturwerte nur mit vollständiger Quelle (Autor, Jahr, Tabelle/Seite).
- Vorbelegte Werte mit Quelle „pipeline.py, gerundet - Quelle offen“ prüfen und ersetzen oder bestätigen.
  Die Mondwerte 103 K und 150 K wurden entfernt, weil sie für einen beleuchteten Polkamm nicht plausibel sind.
- Nur in `planetary/` arbeiten. `common/` (gemeinsamer Code), `vicente/` (Erdseite) und `scripts/` nicht ändern.
- Rohdaten (DEM, PDS-Dateien) nicht committen, nur Skripte und `targets.json`.
- Commit-Nachrichten wie im Team: `[Name] Nachricht`.

## Wie die Werte benutzt werden

`vicente/scoring/target_scoring.py` liest `planetary/targets.json`. Testlauf im Repo-Wurzelordner:
`python vicente/scoring/target_scoring.py planetary/targets.json`
(braucht die Erdtabelle, die nur bei Vicente lokal liegt bzw. als Release-Anhang kommt).
