"""
Laedt die MODIS-Erddaten fuer das Analog-Projekt von NASA Earthdata.

  MYD11C3 v061  Oberflaechentemperatur Tag/Nacht, monatlich, 0,05 Grad  -> 12 Dateien (2024)
  MCD43C3 v061  Albedo, taeglich, 0,05 Grad                             -> 12 Dateien (jeweils der 15. eines Monats, 2024)
  MCD12C1 v061  Landbedeckung, jaehrlich, 0,05 Grad                     -> 1 Datei (2022, neuestes Jahr)

Voraussetzung: kostenloses Earthdata-Login (https://urs.earthdata.nasa.gov/users/new)
Aufruf:        python earth/download_modis.py          (erst anzeigen, dann nachfragen)
               python earth/download_modis.py --yes    (ohne Rueckfrage laden)
"""

import sys
from datetime import date
from pathlib import Path

import earthaccess

# Zielordner relativ zum Projektordner analog-finder/, egal von wo das Skript gestartet wird
OUT = Path(__file__).resolve().parent.parent / "data" / "earth" / "modis"
YEAR = 2024

# 1) Anmelden. Fragt beim ersten Mal nach Benutzername/Passwort und speichert sie
#    mit persist=True in ~/.netrc, damit spaetere Laeufe ohne Eingabe funktionieren.
auth = earthaccess.login(persist=True)
if not auth or not auth.authenticated:
    sys.exit("Login fehlgeschlagen. Benutzername/Passwort pruefen.")

# 2) Suchen (CMR-Such-API von NASA, earthaccess kapselt sie nur).
jobs = {}

jobs["MYD11C3"] = earthaccess.search_data(
    short_name="MYD11C3",
    version="061",
    temporal=(f"{YEAR}-01-01", f"{YEAR}-12-31"),
)

# MCD43C3: jede Tagesdatei deckt ein 16-Tage-Fenster ab, eine Suche nach einem Tag
# liefert daher bis zu 16 Dateien. Behalten wird nur die mit genau diesem Datum
# im Dateinamen (MCD43C3.AJJJJTTT..., TTT = Tag im Jahr).
albedo = []
for month in range(1, 13):
    day = date(YEAR, month, 15)
    tag = f".A{YEAR}{day.timetuple().tm_yday:03d}."
    hits = earthaccess.search_data(
        short_name="MCD43C3",
        version="061",
        temporal=(day.isoformat(), day.isoformat()),
    )
    albedo += [g for g in hits if any(tag in link for link in g.data_links())]
jobs["MCD43C3"] = albedo

jobs["MCD12C1"] = earthaccess.search_data(
    short_name="MCD12C1",
    version="061",
    temporal=("2022-01-01", "2022-12-31"),
)

# 3) Uebersicht: Anzahl Dateien und Gesamtgroesse, bevor irgendetwas geladen wird.
total_mb = 0.0
for name, granules in jobs.items():
    # Groesse in MB laut Metadaten; ab earthaccess 0.19 ist size ein Wert statt einer Methode
    mb = sum((g.size() if callable(g.size) else g.size) or 0 for g in granules)
    total_mb += mb
    print(f"{name}: {len(granules)} Dateien, {mb / 1024:.2f} GB")
print(f"Gesamt: {total_mb / 1024:.2f} GB")

if any(len(g) == 0 for g in jobs.values()):
    print("WARNUNG: Fuer mindestens ein Produkt wurden 0 Dateien gefunden.")

if "--yes" not in sys.argv:
    if input("Herunterladen? [j/N] ").strip().lower() != "j":
        sys.exit("Abgebrochen, nichts geladen.")

# 4) Laden, jedes Produkt in einen eigenen Ordner. Vorhandene Dateien werden
#    uebersprungen, ein abgebrochener Lauf kann einfach neu gestartet werden.
for name, granules in jobs.items():
    target = OUT / name
    target.mkdir(parents=True, exist_ok=True)
    earthaccess.download(granules, local_path=str(target))

print(f"Fertig. Dateien liegen unter {OUT}")
