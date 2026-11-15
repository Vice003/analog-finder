"""
Mehrjaehrige MODIS-Klimatologie auf dem 0,05-Grad-Gitter, im Durchlauf berechnet:
Monat laden -> aufaddieren -> Rohdatei loeschen. Es bleibt also nichts Grosses liegen.

  python earth/clim_modis.py lst    MOD11C3 (Terra 10:30/22:30) + MYD11C3 (Aqua 13:30/01:30)
  python earth/clim_modis.py ndvi   MOD13C2
  python earth/clim_modis.py snow   MOD10CM

Zeitraum: 2003-2024 (erste vollen Jahre mit Terra und Aqua). Mit --years 2010 2012 abweichend.
Nach jedem Jahr wird ein Zwischenstand gespeichert; ein abgebrochener Lauf macht dort weiter.
Ergebnis: data/earth/clim/<produkt>_<von>_<bis>.npz
"""

import argparse
import shutil
import sys
import threading
import queue
from pathlib import Path

import numpy as np
import earthaccess
from pyhdf.SD import SD

ROOT = Path(__file__).resolve().parent.parent
CLIM = ROOT / "data" / "earth" / "clim"
NY, NX = 3600, 7200

ap = argparse.ArgumentParser()
ap.add_argument("product", choices=["lst", "ndvi", "snow"])
ap.add_argument("--years", nargs=2, type=int, default=[2003, 2024])
args = ap.parse_args()
Y0, Y1 = args.years
WORK = CLIM / f"_work_{args.product}"
CKPT = CLIM / f"_ckpt_{args.product}_{Y0}_{Y1}.npz"
OUT = CLIM / f"{args.product}_{Y0}_{Y1}.npz"
WORK.mkdir(parents=True, exist_ok=True)

PRODUCTS = {
    "lst": [("MOD11C3", "061"), ("MYD11C3", "061")],
    "ndvi": [("MOD13C2", "061")],
    "snow": [("MOD10CM", "61")],
}[args.product]


def read(sd, name, divide=False):
    """Datensatz lesen, Fuell-/Fehlwerte -> NaN, skalieren (MODIS-VI teilt, alle anderen multiplizieren)."""
    ds = sd.select(name)
    a = ds.attributes()
    raw = ds.get()
    lo, hi = a["valid_range"]
    bad = (raw == a["_FillValue"]) | (raw < lo) | (raw > hi)
    sf = np.float32(a.get("scale_factor", 1.0))
    out = raw.astype(np.float32)
    out = out / sf if divide else out * sf + np.float32(a.get("add_offset", 0.0))
    out[bad] = np.nan
    return out


def month_of(granule):
    """Jahr und Monat aus dem Dateinamen (…AJJJJTTT…)."""
    name = granule.data_links()[0].rsplit("/", 1)[-1]
    tag = name.split(".")[1]  # AJJJJTTT
    y, doy = int(tag[1:5]), int(tag[5:8])
    return y,(np.datetime64(f"{y}-01-01") + np.timedelta64(doy - 1, "D")).astype(object).month


# ------------------------------------------------------------------ Suche
earthaccess.login(strategy="netrc")
index = {}  # (jahr, monat) -> {short_name: granule}
for short, ver in PRODUCTS:
    found = earthaccess.search_data(short_name=short, version=ver, temporal=(f"{Y0}-01-01", f"{Y1}-12-31"))
    for g in found:
        index.setdefault(month_of(g), {})[short] = g
    print(f"{short}: {len(found)} Monate gefunden", flush=True)
need = [s for s, _ in PRODUCTS]
months = sorted(k for k, v in index.items() if all(s in v for s in need) and Y0 <= k[0] <= Y1)
missing = 12 * (Y1 - Y0 + 1) - len(months)
print(f"{len(months)} vollstaendige Monate, {missing} fehlen", flush=True)

# ------------------------------------------------------------------ Akkumulatoren
f32 = lambda v=0.0: np.full((NY, NX), v, np.float32)
u16 = lambda: np.zeros((NY, NX), np.uint16)

if args.product == "lst":
    # gesamt
    A = dict(all_sum=f32(), all_n=u16(), day_sum=f32(), day_n=u16(), night_sum=f32(), night_n=u16(),
             diur_sum=f32(), diur_n=u16(), abs_max=f32(-np.inf), abs_min=f32(np.inf),
             # ueber Jahre gemittelte Jahreskennwerte
             seas_sum=f32(), warm_sum=f32(), cold_sum=f32(), ext_n=u16(),
             ann_sum=f32(), ann_sq=f32(), ann_n=u16(), ft_sum=f32(), ft_n=u16())
    Y = None  # Jahresakkumulatoren

    def new_year():
        return dict(mm_max=f32(-np.inf), mm_min=f32(np.inf), day_max=f32(-np.inf), night_min=f32(np.inf),
                    s=f32(), n=u16(), ft=u16())

    def add_month(files):
        sdT, sdA = SD(files["MOD11C3"]), SD(files["MYD11C3"])
        dT, nT = read(sdT, "LST_Day_CMG"), read(sdT, "LST_Night_CMG")
        dA, nA = read(sdA, "LST_Day_CMG"), read(sdA, "LST_Night_CMG")
        sdT.end(); sdA.end()
        stack = np.stack([dT, nT, dA, nA])  # 4 Ueberflugzeiten
        with np.errstate(invalid="ignore"), _quiet():
            day = np.nanmean(stack[[0, 2]], axis=0)
            night = np.nanmean(stack[[1, 3]], axis=0)
            mean4 = np.nanmean(stack, axis=0)
            all4 = ~np.isnan(stack).any(axis=0)
            # Tagesgang nur, wenn alle 4 Ueberflugzeiten gueltig sind
            rng = np.where(all4, np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0), np.nan) if all4.any() else None
        for v, s, n in ((day, "day_sum", "day_n"), (night, "night_sum", "night_n")):
            ok = ~np.isnan(v); A[s][ok] += v[ok]; A[n] += ok
        ok = ~np.isnan(stack)
        A["all_sum"] += np.where(ok, stack, 0).sum(axis=0); A["all_n"] += ok.sum(axis=0).astype(np.uint16)
        if rng is not None:
            A["diur_sum"][all4] += rng[all4]; A["diur_n"] += all4
        np.fmax(A["abs_max"], day, out=A["abs_max"]); np.fmin(A["abs_min"], night, out=A["abs_min"])
        np.fmax(Y["mm_max"], mean4, out=Y["mm_max"]); np.fmin(Y["mm_min"], mean4, out=Y["mm_min"])
        np.fmax(Y["day_max"], day, out=Y["day_max"]); np.fmin(Y["night_min"], night, out=Y["night_min"])
        okm = ~np.isnan(mean4); Y["s"][okm] += mean4[okm]; Y["n"] += okm
        # Frost-Tau-Monat: tagsueber ueber, nachts unter 0 Grad C
        Y["ft"] += (day > 273.15) & (night < 273.15)

    def close_year():
        full = Y["n"] >= 10  # Jahr zaehlt, wenn mindestens 10 Monate gueltig
        A["seas_sum"][full] += (Y["mm_max"] - Y["mm_min"])[full]
        A["warm_sum"][full] += Y["day_max"][full]
        A["cold_sum"][full] += Y["night_min"][full]
        A["ext_n"] += full
        am = np.where(full, Y["s"] / np.maximum(Y["n"], 1), 0)
        A["ann_sum"] += am; A["ann_sq"] += am * am; A["ann_n"] += full
        A["ft_sum"][full] += Y["ft"][full]; A["ft_n"] += full

    def finish():
        with np.errstate(invalid="ignore", divide="ignore"):
            r = dict(
                lst_mean=A["all_sum"] / A["all_n"],
                lst_day_mean=A["day_sum"] / A["day_n"],
                lst_night_mean=A["night_sum"] / A["night_n"],
                lst_diurnal_mean=A["diur_sum"] / A["diur_n"],
                lst_seasonal_amp=A["seas_sum"] / A["ext_n"],
                lst_warm_mean=A["warm_sum"] / A["ext_n"],     # mittlerer waermster Monat (Tag)
                lst_cold_mean=A["cold_sum"] / A["ext_n"],     # mittlerer kaeltester Monat (Nacht)
                lst_abs_max=np.where(np.isinf(A["abs_max"]), np.nan, A["abs_max"]),
                lst_abs_min=np.where(np.isinf(A["abs_min"]), np.nan, A["abs_min"]),
                lst_interannual_std=np.sqrt(np.maximum(A["ann_sq"] / A["ann_n"] - (A["ann_sum"] / A["ann_n"]) ** 2, 0)),
                freeze_thaw_months=A["ft_sum"] / A["ft_n"],    # Monate pro Jahr mit Frost-Tau-Wechsel
                lst_years=A["ann_n"],
                lst_diurnal_n=A["diur_n"],
            )
        for k in ("lst_mean", "lst_day_mean", "lst_night_mean", "lst_diurnal_mean"):
            r[k][A[{"lst_mean": "all_n", "lst_day_mean": "day_n", "lst_night_mean": "night_n",
                    "lst_diurnal_mean": "diur_n"}[k]] == 0] = np.nan
        return r

elif args.product == "ndvi":
    A = dict(s=f32(), n=u16(), barren_n=u16(), ymax_sum=f32(), ymax_n=u16())
    Y = None
    new_year = lambda: dict(mx=f32(-np.inf))

    def add_month(files):
        sd = SD(files["MOD13C2"])
        v = read(sd, "CMG 0.05 Deg Monthly NDVI", divide=True)
        sd.end()
        ok = ~np.isnan(v)
        A["s"][ok] += v[ok]; A["n"] += ok
        A["barren_n"] += ok & (v < 0.1)
        np.fmax(Y["mx"], v, out=Y["mx"])

    def close_year():
        ok = ~np.isinf(Y["mx"])
        A["ymax_sum"][ok] += Y["mx"][ok]; A["ymax_n"] += ok

    def finish():
        with np.errstate(invalid="ignore", divide="ignore"):
            return dict(ndvi_mean=np.where(A["n"] > 0, A["s"] / A["n"], np.nan),
                        ndvi_peak_mean=np.where(A["ymax_n"] > 0, A["ymax_sum"] / A["ymax_n"], np.nan),
                        ndvi_barren_frac=np.where(A["n"] > 0, A["barren_n"] / A["n"], np.nan),  # Anteil Monate NDVI < 0,1
                        ndvi_n=A["n"])

else:  # snow
    A = dict(s=f32(), n=u16(), snowy_n=u16(), perm_n=u16())
    Y = None
    new_year = lambda: {}

    def add_month(files):
        sd = SD(files["MOD10CM"])
        v = read(sd, "Snow_Cover_Monthly_CMG")
        sd.end()
        ok = ~np.isnan(v)
        A["s"][ok] += v[ok]; A["n"] += ok
        A["snowy_n"] += ok & (v >= 50)
        A["perm_n"] += ok & (v >= 90)

    close_year = lambda: None

    def finish():
        with np.errstate(invalid="ignore", divide="ignore"):
            return dict(snow_mean_pct=np.where(A["n"] > 0, A["s"] / A["n"], np.nan),
                        snow_months_frac=np.where(A["n"] > 0, A["snowy_n"] / A["n"], np.nan),  # Anteil Monate >= 50 %
                        snow_perm_frac=np.where(A["n"] > 0, A["perm_n"] / A["n"], np.nan),     # Anteil Monate >= 90 %
                        snow_n=A["n"])


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings(); self._w.__enter__(); warnings.simplefilter("ignore", RuntimeWarning)
    def __exit__(self, *e):
        self._w.__exit__(*e)


# ------------------------------------------------------------------ Zwischenstand
done_years = set()
if CKPT.exists():
    z = np.load(CKPT)
    for k in A:
        A[k] = z[k]
    done_years = set(int(y) for y in z["_done_years"])
    print(f"Zwischenstand geladen, fertig: {sorted(done_years)}", flush=True)


def save_ckpt():
    tmp = CKPT.with_suffix(".tmp.npz")
    np.savez(tmp, _done_years=np.array(sorted(done_years)), **A)
    tmp.replace(CKPT)


# ------------------------------------------------------------------ Laden im Voraus (1 Monat Vorlauf)
todo = [m for m in months if m[0] not in done_years]
q = queue.Queue(maxsize=2)


def loader():
    for ym in todo:
        d = WORK / f"{ym[0]}_{ym[1]:02d}"
        d.mkdir(exist_ok=True)
        files = {}
        for short, g in index[ym].items():
            for attempt in range(5):
                try:
                    p = earthaccess.download([g], local_path=str(d), show_progress=False)
                    if p:
                        files[short] = str(p[0]); break
                except Exception as e:
                    print(f"  Fehler {short} {ym}: {e}, neuer Versuch", flush=True)
        q.put((ym, d, files))
    q.put(None)


threading.Thread(target=loader, daemon=True).start()

cur_year = None
while True:
    item = q.get()
    if item is None:
        break
    (y, m), d, files = item
    if y != cur_year:
        if cur_year is not None:
            close_year(); done_years.add(cur_year); save_ckpt()
            print(f"Jahr {cur_year} fertig, Zwischenstand gespeichert", flush=True)
        cur_year, Y = y, new_year()
        globals()["Y"] = Y
    if len(files) == len(need):
        add_month(files)
        print(f"  {y}-{m:02d} verrechnet", flush=True)
    else:
        print(f"  {y}-{m:02d} UEBERSPRUNGEN (Download fehlgeschlagen)", flush=True)
    shutil.rmtree(d, ignore_errors=True)

if cur_year is not None:
    close_year(); done_years.add(cur_year); save_ckpt()

res = finish()
np.savez_compressed(OUT, years=np.array([Y0, Y1]), **{k: v.astype(np.float32) if v.dtype.kind == "f" else v for k, v in res.items()})
print(f"Fertig: {OUT}", flush=True)
CKPT.unlink(missing_ok=True)
shutil.rmtree(WORK, ignore_errors=True)
