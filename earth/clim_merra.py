"""
MERRA-2 (NASA-Reanalyse, 0,5 x 0,625 Grad): Staub, Wind, Stuerme, Luftdruck, Feuchte.
Geladen werden nur die benoetigten Variablen ueber OPeNDAP (Ausschnitt statt ganzer Dateien).

  python earth/clim_merra.py monthly   Monatsmittel 2003-2024 -> data/earth/clim/merra2_monthly_2003_2024.npz
  python earth/clim_merra.py daily     Ereignis-Tage aus Stundenwerten -> data/earth/clim/merra2_daily_<von>_<bis>.npz
                                       (Standard 2003-2024, mit --years anders)

Monatsmittel (Spalten im Ergebnis):
  DUEXTTAU_mean       Staub-AOD 550 nm, Mittel                     -> wie staubig ist es im Schnitt
  DUEXTTAU_maxmonth   Staub-AOD im staubigsten Monat (Jahresmittel)
  DUSMASS_mean        Staubkonzentration am Boden (ug/m3)
  DUEM_mean           Staubemission (ug/m2/s)                      -> ist der Ort selbst eine Staubquelle
  SPEED_mean          mittlere Windgeschwindigkeit am Boden (m/s)
  SPEEDMAX_mean       Mittel der stuendlichen Maxima (m/s, liegt nahe am Mittelwind)
  PS_hpa              Luftdruck am Boden (hPa)
  T2M_mean            Lufttemperatur 2 m (K)
  QV2M_gkg            spezifische Feuchte 2 m (g/kg)               -> Trockenheit der Luft
  TQV_mm              Wasserdampf in der Luftsaeule (mm)

Ereignis-Tage pro Jahr (aus 3-stuendlichen Werten):
  dust_event_days     Tage mit Staub-AOD > 0,5   (deutliches Staubereignis)
  dust_storm_days     Tage mit Staub-AOD > 1,0   (Staubsturm)
  wind_strong_days    Tage mit Wind > 10 m/s (stuendliches Maximum, kein Boeenwert)
  wind_storm_days     Tage mit Wind > 17 m/s (Sturm, ab Beaufort 8)
  dust_aod_p95        95-%-Perzentil der taeglichen Staub-AOD-Maxima (naeherungsweise, aus Histogramm)

  python earth/clim_merra.py precip    Niederschlag (PRECTOTCORR, mit Messstationen korrigiert)
                                       -> data/earth/clim/merra2_precip_2003_2024.npz
  precip_mm_yr        mittlerer Jahresniederschlag (mm)
  precip_min_year_mm  trockenstes Jahr (mm)
  precip_cv           Schwankung von Jahr zu Jahr
  dry_month_frac      Anteil Monate mit < 1 mm
  precip_max_month_mm nassester Monat (mm)
  Hauptquelle fuer Niederschlag: IMERG misst in hyperariden Gebieten falsch (Atacama-Kern ueber
  200 mm/Jahr statt weniger als 10 mm), MERRA-2 PRECTOTCORR liefert dort 3-5 mm.
"""

import argparse
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import earthaccess
import netCDF4

ROOT = Path(__file__).resolve().parent.parent
CLIM = ROOT / "data" / "earth" / "clim"
CLIM.mkdir(parents=True, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["monthly", "daily", "precip"])
ap.add_argument("--years", nargs=2, type=int)
ap.add_argument("--workers", type=int, default=6)
ap.add_argument("--max-days", type=int, default=0, help="nur zum Testen (daily)")
args = ap.parse_args()
Y0, Y1 = args.years or (2003, 2024)

earthaccess.login(strategy="netrc")
session = earthaccess.get_requests_https_session()


def opendap_url(g):
    for u in g["umm"].get("RelatedUrls", []):
        if "opendap.earthdata.nasa.gov" in u["URL"]:
            return u["URL"]
    raise RuntimeError("kein OPeNDAP-Link")


NC_LOCK = threading.Lock()


def fetch(url, variables, time_stride=None):
    """Holt die Variablen als netCDF4-Ausschnitt und gibt {name: array} zurueck."""
    ce = ";".join(f"/{v}" + (f"[0:{time_stride}:23][0:360][0:575]" if time_stride and v not in ("lat", "lon") else "")
                  for v in variables + ["lat", "lon"])
    for attempt in range(6):
        try:
            r = session.get(f"{url}.dap.nc4", params={"dap4.ce": ce}, timeout=300)
            if r.status_code in (401, 403):
                raise SystemExit(f"Zugriff verweigert ({r.status_code}). GES-DISC-Freigabe im Earthdata-Profil pruefen.")
            r.raise_for_status()
            # Die netCDF/HDF5-Bibliothek ist nicht threadsicher: laden parallel, einlesen nacheinander
            with NC_LOCK:
                ds = netCDF4.Dataset("mem", memory=r.content)
                out = {}
                for v in variables + ["lat", "lon"]:
                    x = ds[v]
                    x.set_auto_maskandscale(True)
                    a = x[:]
                    out[v] = np.ma.filled(a.astype(np.float32), np.nan) if np.ma.isMaskedArray(a) else np.asarray(a, np.float32)
                ds.close()
            return out
        except SystemExit:
            raise
        except Exception as e:
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))


def search(short):
    g = earthaccess.search_data(short_name=short, version="5.12.4", temporal=(f"{Y0}-01-01", f"{Y1}-12-31"))
    print(f"{short}: {len(g)} Dateien", flush=True)
    return g


# =================================================================== Monatsmittel
if args.mode == "monthly":
    SPEC = {
        "M2TMNXAER": ["DUEXTTAU", "DUSMASS"],
        "M2TMNXADG": ["DUEM001", "DUEM002", "DUEM003", "DUEM004", "DUEM005"],
        "M2TMNXFLX": ["SPEED", "SPEEDMAX"],
        "M2TMNXSLV": ["PS", "T2M", "QV2M", "TQV"],
    }
    acc, lock, grid = {}, threading.Lock(), {}
    yearly_dust = {}  # jahr -> max Monats-Staub-AOD

    def add(name, a):
        a = np.squeeze(a)
        with lock:
            if name not in acc:
                acc[name] = [np.zeros_like(a, np.float64), np.zeros(a.shape, np.int32)]
            ok = ~np.isnan(a)
            acc[name][0][ok] += a[ok]
            acc[name][1] += ok

    def job(short, g):
        d = fetch(opendap_url(g), SPEC[short])
        grid.setdefault("lat", d["lat"]); grid.setdefault("lon", d["lon"])
        if short == "M2TMNXADG":
            add("DUEM", sum(np.squeeze(d[v]) for v in SPEC[short]))
        else:
            for v in SPEC[short]:
                add(v, d[v])
        if short == "M2TMNXAER":
            y = int(g.data_links()[0].rsplit(".", 2)[-2][:4])
            a = np.squeeze(d["DUEXTTAU"])
            with lock:
                yearly_dust[y] = np.fmax(yearly_dust[y], a) if y in yearly_dust else a
        return short

    jobs = [(s, g) for s in SPEC for g in search(s)]
    done = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for fu in as_completed([ex.submit(job, s, g) for s, g in jobs]):
            fu.result()
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)

    mean = lambda k: (acc[k][0] / np.maximum(acc[k][1], 1)).astype(np.float32)
    res = dict(
        lat=grid["lat"], lon=grid["lon"],
        DUEXTTAU_mean=mean("DUEXTTAU"),
        DUEXTTAU_maxmonth=np.mean(np.stack(list(yearly_dust.values())), axis=0).astype(np.float32),
        DUSMASS_mean=mean("DUSMASS") * 1e9,   # kg/m3 -> ug/m3
        DUEM_mean=mean("DUEM") * 1e9,         # kg/m2/s -> ug/m2/s
        SPEED_mean=mean("SPEED"),
        SPEEDMAX_mean=mean("SPEEDMAX"),
        PS_hpa=mean("PS") / 100,
        T2M_mean=mean("T2M"),
        QV2M_gkg=mean("QV2M") * 1000,
        TQV_mm=mean("TQV"),
    )
    out = CLIM / f"merra2_monthly_{Y0}_{Y1}.npz"
    np.savez_compressed(out, **res)
    print(f"Fertig: {out}")

# =================================================================== Niederschlag
elif args.mode == "precip":
    import calendar

    gs = search("M2TMNXFLX")
    yearly, lock, grid = {}, threading.Lock(), {}
    dry = n_m = mx = None

    def job(g):
        ym = g.data_links()[0].rsplit(".", 2)[-2]
        y, m = int(ym[:4]), int(ym[4:])
        d = fetch(opendap_url(g), ["PRECTOTCORR"])
        p = np.squeeze(d["PRECTOTCORR"]) * 86400 * calendar.monthrange(y, m)[1]  # kg/m2/s -> mm/Monat
        return y, p, d

    with ThreadPoolExecutor(args.workers) as ex:
        for i, fu in enumerate(as_completed([ex.submit(job, g) for g in gs]), 1):
            y, p, d = fu.result()
            grid.setdefault("lat", d["lat"]); grid.setdefault("lon", d["lon"])
            if dry is None:
                dry, n_m, mx = np.zeros(p.shape, np.int16), np.zeros(p.shape, np.int16), np.full(p.shape, -np.inf, np.float32)
            ys = yearly.setdefault(y, [np.zeros(p.shape, np.float64), 0])
            ys[0] += p; ys[1] += 1
            dry += p < 1.0; n_m += 1
            np.fmax(mx, p, out=mx)
            if i % 50 == 0:
                print(f"  {i}/{len(gs)}", flush=True)

    tot = np.stack([s for s, n in yearly.values() if n == 12])
    mean = tot.mean(0)
    res = dict(lat=grid["lat"], lon=grid["lon"],
               precip_mm_yr=mean.astype(np.float32),
               precip_min_year_mm=tot.min(0).astype(np.float32),
               precip_cv=(tot.std(0) / np.maximum(mean, 1e-6)).astype(np.float32),
               dry_month_frac=(dry / n_m).astype(np.float32),
               precip_max_month_mm=mx)
    out = CLIM / f"merra2_precip_{Y0}_{Y1}.npz"
    np.savez_compressed(out, **res)
    print(f"Fertig: {out}  ({len(tot)} volle Jahre)")

# =================================================================== Ereignis-Tage
else:
    STRIDE = 3  # jede 3. Stunde (0, 3, ..., 21 UTC): 8 Werte pro Tag
    aer, flx = search("M2T1NXAER"), search("M2T1NXFLX")
    by_day = {}
    for g in aer:
        by_day.setdefault(g.data_links()[0].rsplit(".", 2)[-2], {})["aer"] = g
    for g in flx:
        by_day.setdefault(g.data_links()[0].rsplit(".", 2)[-2], {})["flx"] = g
    days = sorted(k for k, v in by_day.items() if len(v) == 2)
    print(f"{len(days)} Tage mit beiden Dateien", flush=True)

    ckpt = CLIM / f"_ckpt_merra2_daily_{Y0}_{Y1}.npz"
    BINS = np.array([0, .05, .1, .15, .2, .3, .4, .5, .6, .8, 1.0, 1.5, 2.0, 3.0, np.inf], np.float32)
    shape = (361, 576)
    acc = dict(n=np.zeros(shape, np.int32), dust05=np.zeros(shape, np.int32), dust10=np.zeros(shape, np.int32),
               wind15=np.zeros(shape, np.int32), wind20=np.zeros(shape, np.int32),
               hist=np.zeros((len(BINS) - 1,) + shape, np.int32))
    done = set()
    if ckpt.exists():
        z = np.load(ckpt)
        acc = {k: z[k] for k in acc}
        done = set(z["_done"].tolist())
        print(f"Zwischenstand: {len(done)} Tage fertig", flush=True)
    todo = [d for d in days if d not in done]
    lock, grid = threading.Lock(), {}

    def job(day):
        a = fetch(opendap_url(by_day[day]["aer"]), ["DUEXTTAU"], STRIDE)
        f = fetch(opendap_url(by_day[day]["flx"]), ["SPEEDMAX"], STRIDE)
        dust = np.nanmax(a["DUEXTTAU"], axis=0)
        wind = np.nanmax(f["SPEEDMAX"], axis=0)
        idx = np.clip(np.searchsorted(BINS, dust, side="right") - 1, 0, len(BINS) - 2)
        with lock:
            grid.setdefault("lat", a["lat"]); grid.setdefault("lon", a["lon"])
            acc["n"] += 1
            acc["dust05"] += dust > 0.5
            acc["dust10"] += dust > 1.0
            acc["wind15"] += wind > 10
            acc["wind20"] += wind > 17
            for b in range(len(BINS) - 1):  # Histogramm der taeglichen Staub-Maxima
                acc["hist"][b] += idx == b
            done.add(day)
        return day

    if args.max_days:  # Test: nur die ersten n Tage, ohne Ergebnisdatei
        todo = todo[:args.max_days]
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(job, d) for d in todo]
        for i, fu in enumerate(as_completed(futs), 1):
            try:
                fu.result()
            except BaseException:
                # sofort abbrechen, statt alle offenen Downloads noch zu Ende laufen zu lassen
                ex.shutdown(wait=False, cancel_futures=True)
                raise
            if i % 100 == 0:
                with lock:
                    np.savez(ckpt, _done=np.array(sorted(done)), **acc)
                rate = i / (time.time() - t0)
                print(f"  {i}/{len(todo)} Tage, noch ~{(len(todo) - i) / rate / 60:.0f} min", flush=True)

    if args.max_days:
        print(f"Test fertig: {acc['n'].max()} Tage, Staubereignisse max {acc['dust05'].max()}, "
              f"Histogramm-Summe pro Zelle {acc['hist'].sum(0).max()}")
        raise SystemExit
    yrs = acc["n"] / 365.25
    # 95-%-Perzentil aus dem Histogramm (obere Klassengrenze)
    cum = np.cumsum(acc["hist"], axis=0) / np.maximum(acc["n"], 1)
    p95 = BINS[1:][np.argmax(cum >= 0.95, axis=0)]
    lat = grid.get("lat", np.linspace(-90, 90, 361).astype(np.float32))
    lon = grid.get("lon", (-180 + 0.625 * np.arange(576)).astype(np.float32))
    res = dict(lat=lat, lon=lon,
               dust_event_days=(acc["dust05"] / yrs).astype(np.float32),
               dust_storm_days=(acc["dust10"] / yrs).astype(np.float32),
               wind_strong_days=(acc["wind15"] / yrs).astype(np.float32),
               wind_storm_days=(acc["wind20"] / yrs).astype(np.float32),
               dust_aod_p95=np.where(np.isinf(p95), 3.0, p95).astype(np.float32))
    out = CLIM / f"merra2_daily_{Y0}_{Y1}.npz"
    np.savez_compressed(out, **res)
    ckpt.unlink(missing_ok=True)
    print(f"Fertig: {out}")
