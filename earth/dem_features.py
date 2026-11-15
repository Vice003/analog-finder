"""
Gelaendemerkmale aus dem Copernicus DEM GLO-90 (90 m, global, frei auf AWS), verdichtet auf 0,05 Grad.
Jede Kachel (1 x 1 Grad) wird geladen, ausgewertet und sofort verworfen; es bleibt nichts liegen.

Merkmale pro 0,05-Grad-Zelle (aus allen 90-m-Pixeln darin):
  elev_mean      mittlere Hoehe (m)
  elev_std       Standardabweichung der Hoehe (m)  -> Rauheit im km-Massstab
  relief         Hoehenunterschied max - min (m)
  slope_mean     mittlere Hangneigung (Grad)
  slope_p90      90-%-Perzentil der Hangneigung (Grad)
  flat_frac      Anteil Pixel mit Neigung < 5 Grad   -> landefreundliche Flaeche
  steep_frac     Anteil Pixel mit Neigung > 30 Grad  -> Steilhaenge, Klippen

Aufruf:  python earth/dem_features.py            (abgebrochene Laeufe machen weiter)
Ergebnis: data/earth/clim/dem_glo90.npz

Quelle/Lizenz: Copernicus DEM GLO-90, (c) DLR e.V. 2010-2014 und (c) Airbus Defence and Space GmbH
2014-2018, bereitgestellt unter COPERNICUS von der EU und ESA. Armenien und Aserbaidschan fehlen
im oeffentlichen Datensatz.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.io import MemoryFile

ROOT = Path(__file__).resolve().parent.parent
CLIM = ROOT / "data" / "earth" / "clim"
WORK = CLIM / "_work_dem"
OUT = CLIM / "dem_glo90.npz"
BASE = "https://copernicus-dem-90m.s3.amazonaws.com"
NY, NX, CPD = 3600, 7200, 20  # 20 Zellen pro Grad
FIELDS = ["elev_mean", "elev_std", "relief", "slope_mean", "slope_p90", "flat_frac", "steep_frac"]
M_PER_DEG = 111_320.0
WORKERS = 8

WORK.mkdir(parents=True, exist_ok=True)

# Ergebnisgitter als Dateien auf der Platte (nicht im RAM), mit NaN vorbelegt
grids = {}
for f in FIELDS:
    p = WORK / f"{f}.f32"
    fresh = not p.exists()
    grids[f] = np.memmap(p, dtype=np.float32, mode="w+" if fresh else "r+", shape=(NY, NX))
    if fresh:
        grids[f][:] = np.nan

done_file = WORK / "done.txt"
done = set(done_file.read_text().split()) if done_file.exists() else set()
lock = threading.Lock()

tiles = requests.get(f"{BASE}/tileList.txt", timeout=60).text.split()
todo = [t for t in tiles if t not in done]
if os.environ.get("DEM_TILES"):  # Test: nur diese Kacheln, z. B. DEM_TILES=Copernicus_DSM_COG_30_N50_00_E013_00_DEM
    todo = os.environ["DEM_TILES"].split(",")
print(f"{len(tiles)} Kacheln, {len(done)} schon fertig, {len(todo)} offen", flush=True)

session = requests.Session()
session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=WORKERS, pool_maxsize=WORKERS))


def parse(name):
    """Copernicus_DSM_COG_30_N50_00_E013_00_DEM -> Suedkante 50, Westkante 13."""
    p = name.split("_")
    lat = int(p[4][1:]) * (1 if p[4][0] == "N" else -1)
    lon = int(p[6][1:]) * (1 if p[6][0] == "E" else -1)
    return lat, lon


def process(name):
    for attempt in range(5):
        try:
            r = session.get(f"{BASE}/{name}/{name}.tif", timeout=120)
            r.raise_for_status()
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
    with MemoryFile(r.content) as mf, mf.open() as ds:
        z = ds.read(1).astype(np.float32)
    H, W = z.shape
    lat0, lon0 = parse(name)
    if H % CPD or W % CPD:
        raise ValueError(f"{name}: Groesse {W}x{H} nicht durch {CPD} teilbar")
    bh, bw = H // CPD, W // CPD

    # Hangneigung mit metrischen Pixelabstaenden (Ost-West-Abstand schrumpft mit cos(Breite))
    row_lat = lat0 + 1 - (np.arange(H) + 0.5) / H
    dy = M_PER_DEG / H
    dx = (M_PER_DEG / W) * np.cos(np.radians(row_lat))[:, None]
    gy, gx = np.gradient(z)
    slope = np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))

    def blocks(a):  # (H, W) -> (20, 20, bh*bw)
        return a.reshape(CPD, bh, CPD, bw).transpose(0, 2, 1, 3).reshape(CPD, CPD, bh * bw)

    zb, sb = blocks(z), blocks(slope)
    res = {
        "elev_mean": zb.mean(-1),
        "elev_std": zb.std(-1),
        "relief": zb.max(-1) - zb.min(-1),
        "slope_mean": sb.mean(-1),
        "slope_p90": np.percentile(sb, 90, axis=-1),
        "flat_frac": (sb < 5).mean(-1),
        "steep_frac": (sb > 30).mean(-1),
    }
    y0 = int(round((90 - (lat0 + 1)) * CPD))
    x0 = int(round((lon0 + 180) * CPD))
    for f in FIELDS:
        grids[f][y0:y0 + CPD, x0:x0 + CPD] = res[f]
    return name


t0, n = time.time(), 0
with ThreadPoolExecutor(WORKERS) as ex, open(done_file, "a") as log:
    futs = [ex.submit(process, t) for t in todo]
    for fu in as_completed(futs):
        try:
            name = fu.result()
        except Exception as e:
            print(f"  FEHLER: {e}", flush=True)
            continue
        with lock:
            log.write(name + "\n")
            n += 1
            if n % 500 == 0:
                log.flush()
                for g in grids.values():
                    g.flush()
                rate = n / (time.time() - t0)
                print(f"  {n}/{len(todo)} Kacheln, {rate:.1f}/s, noch ~{(len(todo) - n) / rate / 60:.0f} min", flush=True)

for g in grids.values():
    g.flush()
missing = len(tiles) - len(set(done_file.read_text().split()))
if missing:
    raise SystemExit(f"{missing} Kacheln fehlgeschlagen. Skript erneut starten, es macht dort weiter.")

np.savez_compressed(OUT, **{f: np.asarray(grids[f]) for f in FIELDS})
print(f"Fertig: {OUT}", flush=True)
