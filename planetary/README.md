# planetary/

Mond- und Mars-Zielsignaturen für das Erd-Scoring. Verbindlich: [`../VERARBEITUNGSPLAN.md`](../VERARBEITUNGSPLAN.md).

| Datei | Inhalt |
|---|---|
| [`ZIELSIGNATUREN.md`](ZIELSIGNATUREN.md) | Spezifikation: Zielorte, Felder, Merkmale, Einheiten, Berechnungsregeln |
| [`targets_template.json`](targets_template.json) | Vorlage für `shackleton_rim`, `shackleton_psr`, `jezero`, `arcadia`, Messwerte noch `null` |
| [`check_targets.py`](check_targets.py) | Prüft die ausgefüllte Datei (Felder, Einheiten, Polygon 10–20 km, Längen 0…360), nur Standard-Python |
| [`CLAUDE.md`](CLAUDE.md) | Regeln für Claude bei der Arbeit in diesem Ordner |
| [`../common/terrain.py`](../common/terrain.py) | Gemeinsame Geländeberechnung, Pflicht für Neigung und Relief |
| `targets.json` | **wird hier angelegt**: die ausgefüllten Werte |

Start im Repo-Wurzelordner:

```bash
cp planetary/targets_template.json planetary/targets.json
```

```bash
python planetary/check_targets.py planetary/targets.json
```

Selbsttest der Geländeberechnung:

```bash
python common/terrain.py
```
