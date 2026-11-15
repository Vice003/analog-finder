"""
Langsam veraenderliche Oberflaechenmerkmale aus den lokal liegenden MODIS-Dateien (data/earth/modis/):
Albedo 2024 (MCD43C3, 12 Termine) und Landbedeckung 2022 (MCD12C1). Fuer diese Groessen reicht ein Jahr.

Neu gegenueber der ersten Version: zusaetzlich eine schneefreie Albedo (nur Termine mit < 10 % Schnee),
damit Schnee nicht als "helles Gestein" in den Vergleich eingeht.

Ergebnis: data/earth/clim/surface_static.npz
Aufruf:   python earth/surface_static.py
"""

import glob
from pathlib import Path

import numpy as np
from pyhdf.SD import SD

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "earth" / "modis"
OUT = ROOT / "data" / "earth" / "clim" / "surface_static.npz"
NY, NX = 3600, 7200


def read(sd, name):
    ds = sd.select(name)
    a = ds.attributes()
    raw = ds.get()
    lo, hi = a["valid_range"]
    bad = (raw == a["_FillValue"]) | (raw < lo) | (raw > hi)
    out = raw.astype(np.float32) * np.float32(a.get("scale_factor", 1.0)) + np.float32(a.get("add_offset", 0.0))
    out[bad] = np.nan
    return out


z = lambda: np.zeros((NY, NX), np.float32)
sw_s, sw_q, sw_n, vis_s, vis_n, sf_s, sf_n = z(), z(), z(), z(), z(), z(), z()
for f in sorted(glob.glob(str(RAW / "MCD43C3" / "*.hdf"))):
    sd = SD(f)
    sw, vis, snow = read(sd, "Albedo_WSA_shortwave"), read(sd, "Albedo_WSA_vis"), read(sd, "Percent_Snow")
    sd.end()
    ok = ~np.isnan(sw)
    sw_s[ok] += sw[ok]; sw_q[ok] += sw[ok] ** 2; sw_n += ok
    ok = ~np.isnan(vis)
    vis_s[ok] += vis[ok]; vis_n += ok
    ok = ~np.isnan(sw) & (snow < 10)
    sf_s[ok] += sw[ok]; sf_n += ok
    print("  ", Path(f).name, flush=True)

with np.errstate(invalid="ignore", divide="ignore"):
    albedo_sw_mean = sw_s / sw_n
    albedo_sw_std = np.sqrt(np.maximum(sw_q / sw_n - albedo_sw_mean ** 2, 0))
    albedo_vis_mean = vis_s / vis_n
    albedo_snowfree = sf_s / sf_n
del sw_s, sw_q, vis_s, sf_s

lst24 = SD(sorted(glob.glob(str(RAW / "MYD11C3" / "*.hdf")))[0])
land_pct = read(lst24, "Percent_land_in_grid")
lst24.end()

sd = SD(glob.glob(str(RAW / "MCD12C1" / "*.hdf"))[0])
landcover = sd.select("Majority_Land_Cover_Type_1").get()
pct_all = sd.select("Land_Cover_Type_1_Percent").get()  # (3600, 7200, 17) Flaechenanteile je Klasse
sd.end()

np.savez_compressed(
    OUT,
    land_pct=land_pct,
    albedo_sw_mean=albedo_sw_mean.astype(np.float32),
    albedo_sw_std=albedo_sw_std.astype(np.float32),
    albedo_vis_mean=albedo_vis_mean.astype(np.float32),
    albedo_snowfree=albedo_snowfree.astype(np.float32),
    albedo_n=sw_n.astype(np.uint8),
    albedo_snowfree_n=sf_n.astype(np.uint8),
    landcover=landcover,
    water_pct=pct_all[:, :, 0],
    snow_ice_pct=pct_all[:, :, 15],
    barren_pct=pct_all[:, :, 16],
    lc_pct=pct_all,  # alle 17 Klassen, fuer die Aggregation auf 0,25 Grad
)
print(f"Fertig: {OUT}")
