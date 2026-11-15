"""
Rechnet die Erd-Merkmale auf das Gitter der Team-Pipeline um (scripts/pipeline.py):
10 Bogenminuten, 1080 x 2160, Nord oben, Laenge -180..180, Zellmitten.
Format wie data/derived/*.npz im Team-Repo: eine Datei pro Merkmal, Schluessel "a", float32, NaN = keine Daten.

0,05-Grad-Daten werden mit derselben Zuordnung wie in scripts/modis_lst.py gemittelt
(Zeile r = floor((i + 0,5) * 0,05 * 6)), damit die Zellgrenzen identisch sind.
MERRA-2 und IMERG (groeber bzw. anderes Gitter) werden am Zellmittelpunkt abgegriffen (naechster Nachbar).

Ergebnis: derived/ im Projektordner

  Direkt austauschbar gegen Team-Dateien (gleicher Name, gleiche Bedeutung):
    modis_dtr.npz        Tagesgang (K). Team: Aqua Tag - Nacht, 2023. Hier: 2003-2024, Terra + Aqua,
                         hoechster minus niedrigster der 4 Ueberflugwerte -> etwas groesser als Aqua allein
    modis_ndvi.npz       NDVI-Mittel. Team: 2023. Hier: 2003-2024

  Ersatz fuer WorldClim in pipeline.py (gleiche Einheit):
    prec.npz             Jahresniederschlag (mm), MERRA-2 PRECTOTCORR 2003-2024

  Neue Merkmale (fuer zusaetzliche Dimensionen):
    lst_mean.npz           mittlere Oberflaechentemperatur (Grad C), 4 Ueberflugzeiten, 2003-2024
    lst_cold.npz           kaeltester Monat nachts, Mittel ueber die Jahre (Grad C)
    lst_seasonal_amp.npz   Jahresgang (K)
    freeze_thaw.npz        Monate pro Jahr mit Frost-Tau-Wechsel
    albedo_snowfree.npz    schneefreie Albedo 2024
    ati.npz                scheinbare thermische Traegheit (1 - Albedo) / Tagesgang (1/K)
    snow_perm.npz          Anteil der Monate mit >= 90 % Schnee
    dust_aod.npz           Staub-AOD 550 nm, Mittel 2003-2024
    dust_emission.npz      Staubemission (ug/m2/s)
    dust_event_days.npz    Tage pro Jahr mit Staub-AOD > 0,5
    dust_storm_days.npz    Tage pro Jahr mit Staub-AOD > 1,0
    wind_mean.npz          mittlere Windgeschwindigkeit (m/s)
    wind_storm_days.npz    Tage pro Jahr mit Wind > 17 m/s
    pressure.npz           Luftdruck am Boden (hPa), MERRA-2
    humidity.npz           spezifische Feuchte 2 m (g/kg)
    flat_frac_90m.npz      Anteil landefreundlicher Flaeche (< 5 Grad) aus 90-m-Pixeln
    slope_p90_90m.npz      90-%-Perzentil der Hangneigung aus 90-m-Pixeln (Grad)
  Achtung: Die beiden 90-m-Gelaendemerkmale haben NICHT die 18,5-km-Basislaenge der Team-Pipeline und sind
  deshalb nicht mit LOLA/MOLA-Zielwerten aus pipeline.py vergleichbar. Sie dienen der Charakterisierung.

Fehlende Eingaben werden uebersprungen; nach Abschluss der Laeufe einfach erneut ausfuehren.
Aufruf: python earth/to_team_grid.py
"""

import glob
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CLIM = ROOT / "data" / "earth" / "clim"
OUT = ROOT / "derived"
OUT.mkdir(exist_ok=True)

NR, NC = 1080, 2160
LAT = 90 - (np.arange(NR) + 0.5) / 6
LON = -180 + (np.arange(NC) + 0.5) / 6

# Zuordnung 0,05 Grad -> 10' genau wie in scripts/modis_lst.py des Teams
_r = np.floor((np.arange(3600) + 0.5) * 0.05 * 6).astype(int)
_c = np.floor((np.arange(7200) + 0.5) * 0.05 * 6).astype(int)
_IDX = (_r[:, None] * NC + _c[None, :]).ravel()


def binmean(a):
    v = np.asarray(a, np.float64).ravel()
    ok = ~np.isnan(v)
    s = np.bincount(_IDX[ok], v[ok], NR * NC)
    k = np.bincount(_IDX[ok], minlength=NR * NC)
    return np.where(k > 0, s / np.maximum(k, 1), np.nan).reshape(NR, NC).astype(np.float32)


def sample(grid, lat_c, lon_c):
    """Grobes Gitter am 10'-Zellmittelpunkt abgreifen (naechster Nachbar)."""
    iy = np.abs(LAT[:, None] - np.asarray(lat_c)[None, :]).argmin(1)
    dl = (LON[:, None] - np.asarray(lon_c)[None, :] + 180) % 360 - 180
    ix = np.abs(dl).argmin(1)
    return np.asarray(grid, np.float32)[np.ix_(iy, ix)]


def save(name, a, note):
    np.savez_compressed(OUT / f"{name}.npz", a=a.astype(np.float32))
    v = a[~np.isnan(a)]
    print(f"  {name:20s} {note:46s} gueltig {v.size:>8,}  p2/p50/p98 "
          f"{np.percentile(v, 2):8.3f} {np.percentile(v, 50):8.3f} {np.percentile(v, 98):8.3f}")


def find(pattern):
    hits = sorted(glob.glob(str(CLIM / pattern)))
    return np.load(hits[-1]) if hits else None


done, skipped = [], []

S = find("surface_static.npz")
L = find("lst_*.npz")
N = find("ndvi_*.npz")
W = find("snow_*.npz")
D = find("dem_glo90.npz")
M = find("merra2_monthly_*.npz")
P = find("merra2_precip_*.npz")
E = find("merra2_daily_*.npz")

print(f"Ziel: {OUT}  (1080 x 2160, 10')")

# Landmaske: 10'-Zellen, in denen MODIS mindestens ein 0,05-Grad-Landpixel meldet
LAND = ~np.isnan(binmean(S["land_pct"])) if S is not None else np.ones((NR, NC), bool)


def sample(grid, lat_c, lon_c, _raw=sample):
    """wie oben, aber nur auf Landzellen (Meer -> NaN)"""
    return np.where(LAND, _raw(grid, lat_c, lon_c), np.nan).astype(np.float32)

if L is not None:
    save("modis_dtr", binmean(L["lst_diurnal_mean"]), "Tagesgang K, 2003-2024, Terra+Aqua")
    save("lst_mean", binmean(L["lst_mean"]) - 273.15, "Oberflaechentemperatur Grad C")
    save("lst_cold", binmean(L["lst_cold_mean"]) - 273.15, "kaeltester Monat nachts Grad C")
    save("lst_seasonal_amp", binmean(L["lst_seasonal_amp"]), "Jahresgang K")
    save("freeze_thaw", binmean(L["freeze_thaw_months"]), "Frost-Tau-Monate pro Jahr")
    done.append("Temperatur")
else:
    skipped.append("Temperatur (lst_*.npz fehlt noch)")

if N is not None:
    save("modis_ndvi", binmean(N["ndvi_mean"]), "NDVI-Mittel 2003-2024")
    done.append("NDVI")
else:
    skipped.append("NDVI (ndvi_*.npz fehlt noch)")

if S is not None:
    alb = np.where(np.isnan(S["albedo_snowfree"]), S["albedo_sw_mean"], S["albedo_snowfree"])
    save("albedo_snowfree", binmean(alb), "Albedo schneefrei (sonst Jahresmittel)")
    if L is not None:
        dt = L["lst_diurnal_mean"]
        ati = np.where(dt > 1, (1 - alb) / np.where(dt > 1, dt, np.nan), np.nan)
        save("ati", binmean(ati), "(1 - Albedo) / Tagesgang, 1/K")
    done.append("Albedo")

if W is not None:
    save("snow_perm", binmean(W["snow_perm_frac"]), "Anteil Monate >= 90 % Schnee")
    done.append("Schnee")

if D is not None:
    # Hoehe (m) aus Copernicus GLO-90, Mittel der 90-m-Pixel; Meer = NaN. Ersatz fuer ETOPO1 (NOAA) in scripts/pipeline.py
    save("elevation", binmean(D["elev_mean"]), "Hoehe m, Copernicus GLO-90 (Ersatz ETOPO1)")
    save("flat_frac_90m", binmean(D["flat_frac"]), "Anteil < 5 Grad (90-m-Pixel)")
    save("slope_p90_90m", binmean(D["slope_p90"]), "Neigung P90 Grad (90-m-Pixel)")
    done.append("Gelaende")

B = find("dem_baselines.npz")
if B is not None:  # gleiche Pixelgroessen wie LOLA (100 m) und MOLA (463 m), common/terrain.py
    for k in B.files:
        save(k, binmean(B[k]), {"slope_p50": "Neigung Median", "slope_p90": "Neigung P90",
                                "relief": "Relief P95-P5"}[k.rsplit("_", 1)[0]] + f" bei {k.rsplit('_', 1)[1]}")
    done.append("Gelaende 100/463 m")

if M is not None:
    g = lambda k: sample(M[k], M["lat"], M["lon"])
    save("dust_aod", g("DUEXTTAU_mean"), "Staub-AOD Mittel")
    save("dust_emission", g("DUEM_mean"), "Staubemission ug/m2/s")
    save("wind_mean", g("SPEED_mean"), "Wind m/s")
    save("pressure", g("PS_hpa"), "Luftdruck hPa")
    save("humidity", g("QV2M_gkg"), "spez. Feuchte g/kg")
    done.append("MERRA-2 Monatswerte")

if P is not None:
    save("prec", sample(P["precip_mm_yr"], P["lat"], P["lon"]), "Niederschlag mm/Jahr (MERRA-2)")
    done.append("Niederschlag")

if E is not None:
    g = lambda k: sample(E[k], E["lat"], E["lon"])
    save("dust_event_days", g("dust_event_days"), "Tage/Jahr Staub-AOD > 0,5")
    save("dust_storm_days", g("dust_storm_days"), "Tage/Jahr Staub-AOD > 1,0")
    save("wind_storm_days", g("wind_storm_days"), "Tage/Jahr Wind > 17 m/s")
    done.append("Ereignistage")
else:
    skipped.append("Ereignistage (merra2_daily_*.npz fehlt noch)")

print("\nFertig:", ", ".join(done))
if skipped:
    print("Noch offen:", "; ".join(skipped))

# Gegenprobe an denselben Orten wie in den Team-Skripten
files = sorted(OUT.glob("*.npz"))
print("\nGegenprobe (10'-Zelle):")
for nme, la, lo in [("Atacama", -24.1, -69.9), ("Haughton", 75.4, -89.8), ("Kunlun", 35.83, 88.5),
                    ("Sahara", 23, 12), ("Amazon", -3, -60), ("Stuttgart", 48.8, 9.2)]:
    i, j = np.abs(LAT - la).argmin(), np.abs(LON - lo).argmin()
    vals = {f.stem: round(float(np.load(f)["a"][i, j]), 2) for f in files}
    print(f"  {nme:10s}", vals)
