"""
Fuehrt alle Erd-Bausteine aus data/earth/clim/ zu einer Merkmalstabelle pro Landzelle zusammen.
Fehlende Bausteine werden uebersprungen (mit Hinweis), das Skript laeuft also schon mit Teildaten.

Bausteine (jeweils eigenes Skript):
  surface_static.npz   earth/surface_static.py   Albedo 2024 (auch schneefrei), Landbedeckung 2022
  lst_2003_2024.npz    earth/clim_modis.py lst   Temperatur Terra+Aqua, 22 Jahre
  ndvi_2003_2024.npz   earth/clim_modis.py ndvi  Vegetation
  snow_2003_2024.npz   earth/clim_modis.py snow  Schneebedeckung
  dem_glo90.npz        earth/dem_features.py     Hoehe, Relief, Hangneigung (aus 90 m)
  merra2_monthly_*.npz earth/clim_merra.py monthly  Staub, Wind, Druck, Feuchte (0,5 x 0,625 Grad)
  merra2_daily_*.npz   earth/clim_merra.py daily    Staubsturm- und Sturmtage
  merra2_precip_*.npz  earth/clim_merra.py precip   Niederschlag, stationskorrigiert (Hauptquelle)
  imerg_*.npz          earth/clim_imerg.py          Niederschlag 0,1 Grad als Zusatz (imerg_*),
                                                    in hyperariden Gebieten unzuverlaessig

Abgeleitet:
  ati               scheinbare thermische Traegheit = (1 - Albedo schneefrei) / Tagesgang  [1/K]
                    vergleichbar mit Karten der thermischen Traegheit von Mars und Mond:
                    niedrig = lockerer Staub/Sand, hoch = Fels/verfestigter Boden
  pressure_est_hpa  Luftdruck grob aus der Hoehe (Skalenhoehe 8,4 km), falls MERRA-2 fehlt

Ausgabe:
  data/earth/earth_features_005deg.parquet   0,05 Grad, nur Landzellen  (fuer scoring/)
  data/earth/earth_features_025deg.parquet   0,25 Grad gemittelt        (fuer web/)
  data/earth/earth_features_quicklook.png    Kontrollkarte

Aufruf: python earth/build_features.py
"""

import glob
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLIM = ROOT / "data" / "earth" / "clim"
OUT = ROOT / "data" / "earth"
NY, NX, RES, C = 3600, 7200, 0.05, 5  # C: 5 x 5 Zellen -> 0,25 Grad
warnings.simplefilter("ignore", RuntimeWarning)


def find(pattern):
    hits = sorted(glob.glob(str(CLIM / pattern)))
    return hits[-1] if hits else None


# (Datei-Muster, Schluessel in der Datei, Spaltenname, Aggregation auf 0,25 Grad)
FIELDS = [
    ("surface_static.npz", "land_pct", "land_pct", "mean"),
    ("surface_static.npz", "albedo_sw_mean", "albedo_sw_mean", "mean"),
    ("surface_static.npz", "albedo_snowfree", "albedo_snowfree", "mean"),
    ("surface_static.npz", "albedo_sw_std", "albedo_sw_std", "mean"),
    ("surface_static.npz", "albedo_vis_mean", "albedo_vis_mean", "mean"),
    ("surface_static.npz", "landcover", "landcover", "lc"),
    ("surface_static.npz", "barren_pct", "barren_pct", "mean"),
    ("surface_static.npz", "snow_ice_pct", "snow_ice_pct", "mean"),
    ("surface_static.npz", "water_pct", "water_pct", "mean"),
    ("lst_*.npz", "lst_mean", "lst_mean", "mean"),
    ("lst_*.npz", "lst_day_mean", "lst_day_mean", "mean"),
    ("lst_*.npz", "lst_night_mean", "lst_night_mean", "mean"),
    ("lst_*.npz", "lst_diurnal_mean", "lst_diurnal_mean", "mean"),
    ("lst_*.npz", "lst_seasonal_amp", "lst_seasonal_amp", "mean"),
    ("lst_*.npz", "lst_warm_mean", "lst_warm_mean", "mean"),
    ("lst_*.npz", "lst_cold_mean", "lst_cold_mean", "mean"),
    ("lst_*.npz", "lst_abs_max", "lst_abs_max", "max"),
    ("lst_*.npz", "lst_abs_min", "lst_abs_min", "min"),
    ("lst_*.npz", "lst_interannual_std", "lst_interannual_std", "mean"),
    ("lst_*.npz", "freeze_thaw_months", "freeze_thaw_months", "mean"),
    ("lst_*.npz", "lst_years", "lst_years", "mean"),
    ("ndvi_*.npz", "ndvi_mean", "ndvi_mean", "mean"),
    ("ndvi_*.npz", "ndvi_peak_mean", "ndvi_peak_mean", "mean"),
    ("ndvi_*.npz", "ndvi_barren_frac", "ndvi_barren_frac", "mean"),
    ("snow_*.npz", "snow_mean_pct", "snow_mean_pct", "mean"),
    ("snow_*.npz", "snow_months_frac", "snow_months_frac", "mean"),
    ("snow_*.npz", "snow_perm_frac", "snow_perm_frac", "mean"),
    ("dem_glo90.npz", "elev_mean", "elev_mean", "mean"),
    ("dem_glo90.npz", "elev_std", "elev_std", "mean"),
    ("dem_glo90.npz", "relief", "relief", "max"),
    ("dem_glo90.npz", "slope_mean", "slope_mean", "mean"),
    ("dem_glo90.npz", "slope_p90", "slope_p90", "mean"),
    ("dem_glo90.npz", "flat_frac", "flat_frac", "mean"),
    ("dem_glo90.npz", "steep_frac", "steep_frac", "mean"),
    # Gelaende bei den Pixelgroessen der Zielkoerper (common/terrain.py), fuer den Vergleich mit LOLA/MOLA
    ("dem_baselines.npz", "slope_p50_100m", "slope_p50_100m", "mean"),
    ("dem_baselines.npz", "slope_p90_100m", "slope_p90_100m", "mean"),
    ("dem_baselines.npz", "relief_100m", "relief_100m", "max"),
    ("dem_baselines.npz", "slope_p50_463m", "slope_p50_463m", "mean"),
    ("dem_baselines.npz", "slope_p90_463m", "slope_p90_463m", "mean"),
    ("dem_baselines.npz", "relief_463m", "relief_463m", "max"),
]


def coarse_grid_to_fine(g, lat_c, lon_c):
    """Grobes Gitter (z. B. MERRA-2) per naechstem Nachbarn auf das 0,05-Grad-Gitter abbilden."""
    lat = 90 - RES * (np.arange(NY) + 0.5)
    lon = -180 + RES * (np.arange(NX) + 0.5)
    iy = np.abs(lat[:, None] - lat_c[None, :]).argmin(1)
    dl = (lon[:, None] - lon_c[None, :] + 180) % 360 - 180
    ix = np.abs(dl).argmin(1)
    return g[np.ix_(iy, ix)]


def block(g, how):
    b = g.astype(np.float32).reshape(NY // C, C, NX // C, C)
    return {"mean": np.nanmean, "max": np.nanmax, "min": np.nanmin}[how](b, axis=(1, 3))


# ---------------------------------------------------------------- Landmaske
static = find("surface_static.npz")
if not static:
    raise SystemExit("surface_static.npz fehlt. Erst: python earth/surface_static.py")
S = np.load(static)
land_pct = S["land_pct"]
keep = ~np.isnan(land_pct) & ((S["albedo_n"] > 0) | (land_pct > 0))
lst_file = find("lst_*.npz")
if lst_file:
    keep &= ~np.isnan(np.load(lst_file)["lst_mean"]) | (S["albedo_n"] > 0)
iy, ix = np.nonzero(keep)
lat = (90 - RES * (np.arange(NY) + 0.5)).astype(np.float32)
lon = (-180 + RES * (np.arange(NX) + 0.5)).astype(np.float32)
fine = pd.DataFrame({"lat": lat[iy], "lon": lon[ix]})

ckeep = keep.reshape(NY // C, C, NX // C, C).any(axis=(1, 3))
cy, cx = np.nonzero(ckeep)
clat = (90 - RES * C * (np.arange(NY // C) + 0.5)).astype(np.float32)
clon = (-180 + RES * C * (np.arange(NX // C) + 0.5)).astype(np.float32)
small = pd.DataFrame({"lat": clat[cy], "lon": clon[cx]})
coarse_maps = {}  # fuer die Kontrollkarte


def add(name, grid, how):
    fine[name] = grid[iy, ix]
    if how == "lc":
        return
    g = grid.astype(np.float32).copy()
    g[~keep] = np.nan
    cg = block(g, how)
    small[name] = cg[cy, cx]
    coarse_maps[name] = cg


# ---------------------------------------------------------------- Gitter-Bausteine (0,05 Grad)
loaded, missing = [], []
cache = {}
for pattern, key, name, how in FIELDS:
    f = find(pattern)
    if not f:
        if pattern not in missing:
            missing.append(pattern)
        continue
    if f not in cache:
        cache[f] = np.load(f)
        loaded.append(Path(f).name)
    add(name, cache[f][key], how)
cache.clear()

# Landbedeckung 0,25 Grad: Klasse mit dem groessten mittleren Flaechenanteil
pct = S["lc_pct"]
best, best_cls = np.full((NY // C, NX // C), -1.0, np.float32), np.zeros((NY // C, NX // C), np.uint8)
for c in range(pct.shape[2]):
    g = pct[:, :, c].astype(np.float32)
    g[~keep] = np.nan
    m = np.nan_to_num(block(g, "mean"), nan=-1)
    better = m > best
    best[better], best_cls[better] = m[better], c
small["landcover"] = best_cls[cy, cx]
del pct

# ---------------------------------------------------------------- Grobe Bausteine (MERRA-2, IMERG)
for pattern in ("merra2_monthly_*.npz", "merra2_daily_*.npz", "merra2_precip_*.npz", "imerg_*.npz"):
    f = find(pattern)
    if not f:
        missing.append(pattern)
        continue
    z = np.load(f)
    loaded.append(Path(f).name)
    for key in z.files:
        if key in ("lat", "lon", "years"):
            continue
        add(key, coarse_grid_to_fine(z[key], z["lat"], z["lon"]), "mean")

# ---------------------------------------------------------------- Abgeleitete Merkmale
for df in (fine, small):
    if "lst_diurnal_mean" in df:
        alb = df["albedo_snowfree"].fillna(df["albedo_sw_mean"])
        dt = df["lst_diurnal_mean"].where(df["lst_diurnal_mean"] > 1)  # Polarnacht u. ae. ausschliessen
        df["ati"] = (1 - alb) / dt
    if "elev_mean" in df:
        df["pressure_est_hpa"] = 1013.25 * np.exp(-df["elev_mean"].clip(lower=-500) / 8434.0)

fine.to_parquet(OUT / "earth_features_005deg.parquet", index=False)
small.to_parquet(OUT / "earth_features_025deg.parquet", index=False)
print("Geladen:", ", ".join(loaded))
if missing:
    print("Fehlt noch:", ", ".join(missing))
print(f"0,05 Grad: {len(fine):,} Zellen x {fine.shape[1]} Spalten")
print(f"0,25 Grad: {len(small):,} Zellen x {small.shape[1]} Spalten")

# ---------------------------------------------------------------- Kontrollkarte
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

panels = [(k, t, cm) for k, t, cm in [
    ("lst_mean", "Temperatur, Mittel 4 Ueberflugzeiten (K)", "inferno"),
    ("lst_diurnal_mean", "Tagesgang (K)", "viridis"),
    ("albedo_snowfree", "Albedo schneefrei", "gray"),
    ("ndvi_mean", "NDVI, Mittel", "YlGn"),
    ("slope_mean", "Hangneigung, Mittel (Grad)", "magma"),
    ("snow_mean_pct", "Schneebedeckung (%)", "Blues"),
    ("DUEXTTAU_mean", "Staub-AOD, Mittel", "YlOrBr"),
    ("precip_mm_yr", "Niederschlag (mm/Jahr)", "Blues"),
] if k in coarse_maps]
if panels:
    n = len(panels)
    cols = 2
    rows = (n + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(14, 3.8 * rows), constrained_layout=True, squeeze=False)
    for ax, (k, title, cmap) in zip(axes.flat, panels):
        g = coarse_maps[k].copy()
        g[~ckeep] = np.nan
        lo, hi = np.nanpercentile(g, [1, 99])
        im = ax.imshow(g, extent=(-180, 180, -90, 90), cmap=cmap, vmin=lo, vmax=hi, interpolation="nearest")
        ax.set_title(title); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.8)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.savefig(OUT / "earth_features_quicklook.png", dpi=100)
    print("Kontrollkarte -> earth_features_quicklook.png")
