"""
Target views: hillshade of the area around each Moon/Mars target (about 60 x 60 km) with the target box and the
named features nearby (IAU Gazetteer of Planetary Nomenclature: craters with their rim circle, mountains, valleys ...).

  Mars: MOLA 463 m mosaic (USGS), read as a window over HTTP (same source as planetary/compute_targets.py)
  Moon: LOLA LDEM_80S_80M (PDS), south polar stereographic, 80 m
Output: web/targets/<target_id>.jpg

  python web/make_target_views.py
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / "data" / "planetary" / "raw"
OUT = HERE / "targets"
HALF_KM = 30.0
MOLA_URL = "/vsicurl/https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
R_MOON = 1737.4
SHOW_TYPES = ("Crater", "Mons", "Montes", "Vallis", "Valles", "Mensa", "Mensae", "Planitia", "Planum", "Fossa",
              "Fossae", "Rupes", "Dorsum", "Dorsa", "Tholus", "Colles", "Chaos", "Labes", "Promontorium")


def hillshade(z, dx, dy):
    gy, gx = np.gradient(np.nan_to_num(z, nan=float(np.nanmean(z))), dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315), math.radians(35)
    return np.clip(math.sin(alt) * np.cos(slope) + math.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def features(body):
    import shapefile
    p = RAW / "iau" / ("mars/MARS" if body == "Mars" else "moon/MOON") / ""
    r = shapefile.Reader(str(RAW / "iau" / ("mars" if body == "Mars" else "moon") / f"{body.upper()}_nomenclature_center_pts"), encoding="utf-8")
    f = [x[0] for x in r.fields[1:]]
    out = []
    for rec in r.records():
        d = dict(zip(f, rec))
        if not str(d.get("type") or "").startswith(SHOW_TYPES):
            continue
        out.append((d["name"], float(d["center_lat"]), float(d["center_lon"]) % 360, float(d.get("diameter") or 0), d["type"]))
    return out


def mars_view(lat, lon_e):
    import rasterio
    from rasterio.windows import Window
    lon = ((lon_e + 180) % 360) - 180
    with rasterio.open(MOLA_URL) as src:
        R, res = 3396190.0, src.res[0]
        x, y = R * math.radians(lon), R * math.radians(lat)
        col, row = (x - src.bounds.left) / res, (src.bounds.top - y) / res
        hy = int(HALF_KM * 1000 / res)
        hx = int(HALF_KM * 1000 / (res * max(math.cos(math.radians(lat)), 0.05)))
        z = src.read(1, window=Window(int(col - hx), int(row - hy), 2 * hx, 2 * hy)).astype(float)
        z[z == src.nodata] = np.nan
    dx, dy = res * math.cos(math.radians(lat)), res
    # pixel -> lat/lon of the window
    lat_of = lambda r: lat + (hy - r) * res / R * 180 / math.pi
    lon_of = lambda c: lon_e + (c - hx) * res / R * 180 / math.pi
    to_px = lambda la, lo: ((((lo - lon_e + 540) % 360) - 180) * math.pi / 180 * R / res + hx, hy - (la - lat) * math.pi / 180 * R / res)
    km_per_px = dy / 1000
    return z, dx, dy, to_px, km_per_px


def moon_view(lat, lon_e):
    dem = np.memmap(RAW / "ldem_80s_80m.img", dtype="<i2", mode="r", shape=(7600, 7600))
    d = 2 * R_MOON * math.tan(math.radians(90 + lat) / 2)
    x, y = d * math.sin(math.radians(lon_e)), d * math.cos(math.radians(lon_e))
    c0, r0 = 3799.5 + x / 0.08, 3799.5 - y / 0.08
    h = int(HALF_KM / 0.08)
    r1, c1 = int(r0 - h), int(c0 - h)
    z = np.asarray(dem[max(r1, 0):r1 + 2 * h, max(c1, 0):c1 + 2 * h], dtype=float) * 0.5
    z = z[::2, ::2]  # 160 m is enough for the picture

    def to_px(la, lo):
        dd = 2 * R_MOON * math.tan(math.radians(90 + la) / 2)
        xx, yy = dd * math.sin(math.radians(lo)), dd * math.cos(math.radians(lo))
        return ((3799.5 + xx / 0.08) - c1) / 2, ((3799.5 - yy / 0.08) - r1) / 2
    return z, 160.0, 160.0, to_px, 0.16


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    tpath = ROOT.parent / "NASA-Challenge" / "planetary" / "targets.json"
    if not tpath.exists():
        tpath = ROOT / "planetary" / "targets.json"
    T = json.load(open(tpath, encoding="utf-8"))["targets"]
    OUT.mkdir(exist_ok=True)
    feats = {b: features(b) for b in ("Mars", "Moon")}
    for tid, t in T.items():
        body, lat, lon = t["body"], t["center_lat"], t["center_lon"] % 360
        try:
            z, dx, dy, to_px, kmpx = (mars_view if body == "Mars" else moon_view)(lat, lon)
        except Exception as e:
            print(tid, "Fehler:", e); continue
        hs = hillshade(z, dx, dy)
        ny, nx = hs.shape
        fig = plt.figure(figsize=(5.4, 5.4 * ny / nx), dpi=90)
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
        ax.imshow(hs, cmap="gray", vmin=0, vmax=1, extent=(0, nx, ny, 0))
        # target box (half size in km)
        half = 5.0 if body == "Mars" else 7.5
        cx, cy = to_px(lat, lon)
        ax.add_patch(Rectangle((cx - half / kmpx, cy - half / kmpx), 2 * half / kmpx, 2 * half / kmpx, fill=False,
                               ec="#e7b04f", lw=2.2, ls="--"))
        n_lab = 0
        for name, fla, flo, diam, typ in sorted(feats[body], key=lambda f: -f[3]):
            px, py = to_px(fla, flo)
            rad = diam / 2 / kmpx
            if not (-rad < px < nx + rad and -rad < py < ny + rad):
                continue
            if typ.startswith("Crater") and diam > 0:
                ax.add_patch(Circle((px, py), rad, fill=False, ec="#8fd3ff", lw=1.0, alpha=0.8))
            if 0 <= px < nx and 0 <= py < ny and n_lab < 14:
                ax.text(px, py, name, color="#ffffff", fontsize=8, ha="center", va="center",
                        bbox=dict(facecolor="#0b1016", alpha=0.6, edgecolor="none", pad=1.2))
                n_lab += 1
        ax.text(6, ny - 8, f"{2 * HALF_KM:.0f} km · {'MOLA 463 m' if body == 'Mars' else 'LOLA 80 m'} · IAU names",
                color="#cfd6de", fontsize=7, va="bottom", bbox=dict(facecolor="#0b1016", alpha=0.6, edgecolor="none", pad=1))
        ax.set_xlim(0, nx); ax.set_ylim(ny, 0)
        fig.savefig(OUT / f"{tid}.jpg", dpi=90, pil_kwargs=dict(quality=78, optimize=True))
        plt.close(fig)
        print(f"{tid:26s} {n_lab} Namen", flush=True)


if __name__ == "__main__":
    main()
