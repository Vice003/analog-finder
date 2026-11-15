"""
Erd-Gelaende bei den Pixelgroessen der Zielkoerper (VERARBEITUNGSPLAN.md, Abschnitt 4):
100 m fuer Mond-Vergleiche (LOLA), 463 m fuer Mars-Vergleiche (MOLA).
Benutzt die gemeinsamen Funktionen aus common/terrain.py (resample, slope_deg), damit Erde, Mond und Mars
mit demselben Code gerechnet werden.

Pro Copernicus-GLO-90-Kachel (1 x 1 Grad): DEM auf 100 m bzw. 463 m bringen, Neigung berechnen, dann je
0,05-Grad-Zelle (ca. 5 km, entspricht dem 5-km-Relieffenster aus terrain.py):
  slope_p50_<px>m   Median der Neigung (Grad)
  slope_p90_<px>m   90-%-Perzentil der Neigung (Grad)
  relief_<px>m      Hoehe P95 - P5 in der Zelle (m)
Jede Kachel wird geladen, ausgewertet und verworfen. Rechnet in parallelen Prozessen (alle Kerne).

Aufruf:  python earth/dem_baselines.py            (abgebrochene Laeufe machen weiter)
Test:    DEM_TILES=Copernicus_DSM_COG_30_N52_00_E013_00_DEM python earth/dem_baselines.py
Ergebnis: data/earth/clim/dem_baselines.npz
Quelle/Lizenz: Copernicus DEM GLO-90, (c) DLR e.V. 2010-2014 und (c) Airbus Defence and Space GmbH 2014-2018,
bereitgestellt unter COPERNICUS von der EU und ESA.
"""

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import requests
from rasterio.io import MemoryFile

ROOT = Path(__file__).resolve().parent.parent
for cand in (ROOT.parent, ROOT):  # im Repo: vicente/../common, lokal: Verknuepfung common/
    if (cand / "common" / "terrain.py").exists():
        sys.path.insert(0, str(cand))
        break
from common.terrain import resample, slope_deg  # noqa: E402

CLIM = ROOT / "data" / "earth" / "clim"
WORK = CLIM / "_work_dem_baselines"
OUT = CLIM / "dem_baselines.npz"
BASE = "https://copernicus-dem-90m.s3.amazonaws.com"
NY, NX, CPD = 3600, 7200, 20
PIXELS = (100, 463)
M_PER_DEG = 111_320.0
WORKERS = 7  # Prozesse (8 Kerne, einer bleibt frei)
FIELDS = [f"{k}_{p}m" for p in PIXELS for k in ("slope_p50", "slope_p90", "relief")]

_session = None


def _get(url):
    global _session
    if _session is None:  # eine Verbindung je Prozess
        _session = requests.Session()
    return _session.get(url, timeout=120)


def parse(name):
    p = name.split("_")
    return int(p[4][1:]) * (1 if p[4][0] == "N" else -1), int(p[6][1:]) * (1 if p[6][0] == "E" else -1)


def cell_quantiles(values, cid, qs, n_cells=CPD * CPD):
    """Quantile je Zelle ohne Python-Schleife: nach (Zelle, Wert) sortieren, Positionen direkt ablesen."""
    ok = np.isfinite(values)
    v, c = values[ok], cid[ok]
    order = np.lexsort((v, c))
    v, c = v[order], c[order]
    counts = np.bincount(c, minlength=n_cells)
    starts = np.cumsum(counts) - counts
    out = []
    for q in qs:
        idx = starts + np.round(q * np.maximum(counts - 1, 0)).astype(int)
        r = np.full(n_cells, np.nan)
        has = counts > 0
        r[has] = v[np.minimum(idx[has], len(v) - 1)]
        out.append(r.reshape(CPD, CPD))
    return out


def process(name):
    """Eine Kachel: laden, auf 100/463 m bringen, Neigung und Relief je 0,05-Grad-Zelle."""
    for attempt in range(5):
        try:
            r = _get(f"{BASE}/{name}/{name}.tif")
            r.raise_for_status()
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
    with MemoryFile(r.content) as mf, mf.open() as ds:
        z = ds.read(1).astype(np.float64)
    H, W = z.shape
    lat0, lon0 = parse(name)
    row_lat = lat0 + 1 - (np.arange(H) + 0.5) / H
    dy = M_PER_DEG / H
    dx = (M_PER_DEG / W) * np.cos(np.radians(row_lat))
    res = {}
    for px in PIXELS:
        zr = resample(z, dx, dy, float(px))   # gemeinsame Funktion
        s = slope_deg(zr, float(px))          # gemeinsame Funktion
        ny, nx = zr.shape
        if nx < CPD:
            # Nahe den Polen ist eine 0,05-Grad-Zelle in Ost-West-Richtung schmaler als ein Pixel (bei 89 Grad
            # Breite ca. 100 m). Dann bekommt jede Zelle die Pixelspalte, die ihre Mitte ueberdeckt, statt leer
            # zu bleiben (Aenderung 14.11. 19:00).
            idx = np.minimum(((np.arange(CPD) + 0.5) * nx / CPD).astype(int), nx - 1)
            zr, s = zr[:, idx], s[:, idx]
            nx = CPD
        rr = np.minimum((np.arange(ny) * CPD) // ny, CPD - 1)
        cc = np.minimum((np.arange(nx) * CPD) // nx, CPD - 1)
        cid = (rr[:, None] * CPD + cc[None, :]).ravel()
        p50, p90 = cell_quantiles(s.ravel(), cid, [0.5, 0.9])
        e5, e95 = cell_quantiles(zr.ravel(), cid, [0.05, 0.95])
        res[f"slope_p50_{px}m"], res[f"slope_p90_{px}m"], res[f"relief_{px}m"] = p50, p90, e95 - e5
    y0 = int(round((90 - (lat0 + 1)) * CPD))
    x0 = int(round((lon0 + 180) * CPD))
    return name, y0, x0, {k: v.astype(np.float32) for k, v in res.items()}


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    grids = {}
    for f in FIELDS:
        p = WORK / f"{f}.f32"
        fresh = not p.exists()
        grids[f] = np.memmap(p, dtype=np.float32, mode="w+" if fresh else "r+", shape=(NY, NX))
        if fresh:
            grids[f][:] = np.nan

    done_file = WORK / "done.txt"
    done = set(done_file.read_text().split()) if done_file.exists() else set()
    tiles = requests.get(f"{BASE}/tileList.txt", timeout=60).text.split()
    todo = [t for t in tiles if t not in done]
    test = bool(os.environ.get("DEM_TILES"))
    if test:
        todo = os.environ["DEM_TILES"].split(",")
    print(f"{len(tiles)} Kacheln, {len(done)} fertig, {len(todo)} offen, {WORKERS} Prozesse", flush=True)

    t0, n = time.time(), 0
    with ProcessPoolExecutor(WORKERS) as ex, open(done_file, "a") as log:
        futs = [ex.submit(process, t) for t in todo]
        for fu in as_completed(futs):
            try:
                name, y0, x0, res = fu.result()
            except Exception as e:
                print(f"  FEHLER: {e}", flush=True)
                continue
            for f in FIELDS:  # nur der Hauptprozess schreibt in die Ergebnisgitter
                grids[f][y0:y0 + CPD, x0:x0 + CPD] = res[f]
            if not test:
                log.write(name + "\n")
            n += 1
            if n % 500 == 0:
                log.flush()
                for g in grids.values():
                    g.flush()
                rate = n / (time.time() - t0)
                print(f"  {n}/{len(todo)} Kacheln, {rate:.1f}/s, noch ~{(len(todo) - n) / rate / 60:.0f} min",
                      flush=True)

    for g in grids.values():
        g.flush()
    if test:
        print(f"Test fertig: {n} Kacheln in {time.time() - t0:.1f} s")
        return
    missing = len(tiles) - len(set(done_file.read_text().split()))
    if missing:
        raise SystemExit(f"{missing} Kacheln fehlgeschlagen. Skript erneut starten, es macht dort weiter.")
    np.savez_compressed(OUT, **{f: np.asarray(grids[f]) for f in FIELDS})
    print(f"Fertig: {OUT}", flush=True)


if __name__ == "__main__":
    main()
