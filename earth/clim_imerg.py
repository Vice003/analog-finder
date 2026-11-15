"""
Niederschlag aus GPM IMERG V07 (monatlich, 0,1 Grad), 2003-2024, ueber OPeNDAP nur die Niederschlagsvariable.

Ergebnis: data/earth/clim/imerg_2003_2024.npz mit
  imerg_mm_yr           mittlerer Jahresniederschlag (mm)
  imerg_min_year_mm     trockenstes Jahr (mm)
  imerg_cv              Schwankung von Jahr zu Jahr (Variationskoeffizient)
  imerg_dry_month_frac  Anteil Monate mit < 1 mm
  imerg_max_month_mm    nassester Monat im ganzen Zeitraum (mm) -> Starkregen-/Unwetterneigung

ACHTUNG: In hyperariden Gebieten misst IMERG falsch (Atacama-Kern ueber 200 mm/Jahr statt weniger als
10 mm, Satelliten-Mikrowelle ueber hellen, trockenen Flaechen). Hauptquelle fuer Niederschlag ist deshalb
MERRA-2 PRECTOTCORR (earth/clim_merra.py precip); IMERG dient nur als Zusatz fuer feuchte Regionen.

Aufruf: python earth/clim_imerg.py
"""

import calendar
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import earthaccess
import netCDF4

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "earth" / "clim" / "imerg_2003_2024.npz"
Y0, Y1 = 2003, 2024

earthaccess.login(strategy="netrc")
session = earthaccess.get_requests_https_session()
granules = earthaccess.search_data(short_name="GPM_3IMERGM", version="07", temporal=(f"{Y0}-01-01", f"{Y1}-12-31"))
print(f"{len(granules)} Monate gefunden", flush=True)


def url_and_month(g):
    u = [x["URL"] for x in g["umm"]["RelatedUrls"] if "opendap.earthdata" in x["URL"]][0]
    tag = g.data_links()[0].split("3IMERG.")[1][:8]  # JJJJMMTT
    return u, int(tag[:4]), int(tag[4:6])


NC_LOCK = threading.Lock()


def fetch(g):
    u, y, m = url_and_month(g)
    for attempt in range(6):
        try:
            r = session.get(u + ".dap.nc4", params={"dap4.ce": "/Grid/precipitation;/Grid/lat;/Grid/lon"}, timeout=300)
            r.raise_for_status()
            with NC_LOCK:  # netCDF/HDF5 ist nicht threadsicher
                d = netCDF4.Dataset("m", memory=r.content)
                G = d["Grid"] if "Grid" in d.groups else d
                p = np.ma.filled(G["precipitation"][0].astype(np.float32), np.nan)  # (lon, lat), mm/h
                lat, lon = np.asarray(G["lat"][:], np.float32), np.asarray(G["lon"][:], np.float32)
                d.close()
            hours = calendar.monthrange(y, m)[1] * 24
            return y, m, (p.T[::-1] * hours), lat[::-1], lon  # -> (lat absteigend = Nord oben, lon), mm/Monat
        except Exception:
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))


lock = threading.Lock()
yearly, months, n_months, dry, mx = {}, 0, None, None, None
grid = {}
with ThreadPoolExecutor(6) as ex:
    for i, fu in enumerate(as_completed([ex.submit(fetch, g) for g in granules]), 1):
        y, m, p, lat, lon = fu.result()
        with lock:
            grid.setdefault("lat", lat); grid.setdefault("lon", lon)
            if n_months is None:
                n_months = np.zeros(p.shape, np.int16); dry = np.zeros(p.shape, np.int16)
                mx = np.full(p.shape, -np.inf, np.float32)
            ok = ~np.isnan(p)
            ys = yearly.setdefault(y, [np.zeros(p.shape, np.float32), np.zeros(p.shape, np.int16)])
            ys[0][ok] += p[ok]; ys[1] += ok
            n_months += ok; dry += ok & (p < 1.0)
            np.fmax(mx, p, out=mx)
        if i % 50 == 0:
            print(f"  {i}/{len(granules)}", flush=True)

# Jahressummen (nur vollstaendige Jahre), daraus Mittel, Minimum, Variationskoeffizient
tot = np.stack([s for s, n in yearly.values()])
cnt = np.stack([n for s, n in yearly.values()])
tot[cnt < 12] = np.nan
with np.errstate(invalid="ignore", divide="ignore"):
    mean = np.nanmean(tot, axis=0)
    res = dict(
        lat=grid["lat"], lon=grid["lon"],
        imerg_mm_yr=mean.astype(np.float32),
        imerg_min_year_mm=np.nanmin(tot, axis=0).astype(np.float32),
        imerg_cv=(np.nanstd(tot, axis=0) / mean).astype(np.float32),
        imerg_dry_month_frac=(dry / np.maximum(n_months, 1)).astype(np.float32),
        imerg_max_month_mm=np.where(np.isinf(mx), np.nan, mx).astype(np.float32),
    )
np.savez_compressed(OUT, **res)
print(f"Fertig: {OUT}  ({len(yearly)} Jahre)")
