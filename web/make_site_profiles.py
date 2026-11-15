"""
Site profiles for the best Earth sites: satellite image, 90 m terrain and slope distribution, so one can see whether
a 5 km cell is uniform or mixes cliffs and plains.

Sites: all distinct sites among the top 3 of every target, the best site without China and the best three continent
winners. For each site (20 x 20 km around the cell):
  - Landsat WELD annual true-colour mosaic (NASA GIBS, 30 m); fallback MODIS Terra true colour on a summer day
  - Copernicus DEM GLO-90 (ESA, read from the public AWS bucket): hillshade with the 0.05 deg cell outlined
  - slope distribution (90 m pixels) of the cell against its surroundings
Output: web/profiles/<id>.jpg and web/profiles/profiles.json (metrics, which targets the site matches).

  python web/make_site_profiles.py
"""
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "profiles"
HALF_KM = 10.0
GIBS = ("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1"
        "&LAYERS={layer}&STYLES=&SRS=EPSG:4326&BBOX={w},{s},{e},{n}&WIDTH=600&HEIGHT=600&FORMAT=image/jpeg{time}")
DEM = "/vsicurl/https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"


def site_id(lat, lon):
    return f"{'n' if lat >= 0 else 's'}{abs(lat):.3f}_{'e' if lon >= 0 else 'w'}{abs(lon):.3f}".replace(".", "p")


def bbox(lat, lon, half_km=HALF_KM):
    dlat = half_km / 111.0
    dlon = half_km / (111.0 * max(math.cos(math.radians(lat)), 0.05))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def fetch_image(lat, lon):
    from PIL import Image
    w, s, e, n = bbox(lat, lon)
    summer = "2023-07-15" if lat >= 0 else "2023-01-15"
    for layer, time, label in (("Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual", "", "Landsat WELD annual mosaic (NASA GIBS)"),
                               ("MODIS_Terra_CorrectedReflectance_TrueColor", f"&TIME={summer}", f"MODIS Terra true colour {summer} (NASA GIBS)")):
        url = GIBS.format(layer=layer, w=w, s=s, e=e, n=n, time=time)
        try:
            data = urllib.request.urlopen(url, timeout=60).read()
            img = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
        except Exception:
            continue
        valid = (img.sum(axis=2) > 30).mean()
        if valid > 0.6:
            return img, label
    return None, "no image"


def read_dem(lat, lon):
    import rasterio
    from rasterio.windows import from_bounds
    w, s, e, n = bbox(lat, lon)
    tiles = []
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            name = f"Copernicus_DSM_COG_30_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"
            tiles.append(name)
    # regular grid with ~90 m pixels in both directions (3 arc-seconds in latitude, fewer degrees in longitude near the poles)
    res_lat = 1 / 1200
    ny = int(round((n - s) / res_lat))
    nx = int(round((e - w) / res_lat * max(math.cos(math.radians(lat)), 0.05)))
    z = np.full((ny, nx), np.nan, np.float32)
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    dst_t = from_origin(w, n, (e - w) / nx, (n - s) / ny)
    for name in tiles:
        try:
            with rasterio.open(DEM.format(n=name)) as src:
                part = np.full((ny, nx), np.nan, np.float32)
                reproject(source=rasterio.band(src, 1), destination=part, dst_transform=dst_t, dst_crs="EPSG:4326",
                          resampling=Resampling.bilinear, dst_nodata=np.nan)
                z = np.where(np.isfinite(part), part, z)
        except Exception:
            continue  # ocean tiles do not exist
    return z, (w, s, e, n)


def slope_hillshade(z, lat, extent):
    w, s, e, n = extent
    ny, nx = z.shape
    dy = (n - s) / ny * 111320.0
    dx = (e - w) / nx * 111320.0 * math.cos(math.radians(lat))
    gy, gx = np.gradient(np.nan_to_num(z, nan=np.nanmean(z) if np.isfinite(z).any() else 0), dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    az, alt = math.radians(315), math.radians(45)
    aspect = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(np.radians(slope)) + np.cos(alt) * np.sin(np.radians(slope)) * np.cos(az - aspect)
    slope[~np.isfinite(z)] = np.nan
    return slope, np.clip(hs, 0, 1)


def cell_mask(shape, extent, lat, lon):
    w, s, e, n = extent
    ny, nx = shape
    la0, lo0 = math.floor(lat / 0.05) * 0.05, math.floor(lon / 0.05) * 0.05
    yy = n - (np.arange(ny) + 0.5) * (n - s) / ny
    xx = w + (np.arange(nx) + 0.5) * (e - w) / nx
    return ((yy >= la0) & (yy < la0 + 0.05))[:, None] & ((xx >= lo0) & (xx < lo0 + 0.05))[None, :], (lo0, la0)


def figure(img, label, hs, slope, inside, cell0, extent, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    w, s, e, n = extent
    fig, ax = plt.subplots(1, 3, figsize=(13.5, 4.6), gridspec_kw=dict(width_ratios=[1, 1, 1.15]))
    fig.patch.set_facecolor("#151c24")
    for a in ax[:2]:
        a.set_xticks([]); a.set_yticks([])
    if img is not None:
        ax[0].imshow(img, extent=(w, e, s, n), aspect="auto")
    ax[0].set_title(label, color="#cfd6de", fontsize=9)
    ax[1].imshow(hs, cmap="gray", extent=(w, e, s, n), aspect="auto", vmin=0, vmax=1)
    ax[1].set_title("Terrain, Copernicus DEM 90 m (ESA)", color="#cfd6de", fontsize=9)
    for a in ax[:2]:
        a.add_patch(Rectangle(cell0, 0.05, 0.05, fill=False, ec="#e7b04f", lw=1.8))
        a.set_xlim(w, e); a.set_ylim(s, n)
    bins = np.arange(0, 46, 1.5)
    out = slope[~inside & np.isfinite(slope)]
    cin = slope[inside & np.isfinite(slope)]
    if out.size:
        ax[2].hist(np.clip(out, 0, 45), bins=bins, density=True, color="#5f6b78", alpha=.8, label="surroundings (20 km)")
    if cin.size:
        ax[2].hist(np.clip(cin, 0, 45), bins=bins, density=True, color="#e7b04f", alpha=.85, label="the 5 km cell")
    ax[2].set_facecolor("#1c2530"); ax[2].tick_params(colors="#cfd6de", labelsize=8)
    for sp in ax[2].spines.values():
        sp.set_color("#3a4552")
    ax[2].set_xlabel("slope at 90 m pixels (degrees)", color="#cfd6de", fontsize=9)
    ax[2].set_title("Slope distribution", color="#cfd6de", fontsize=9)
    ax[2].legend(fontsize=8, facecolor="#1c2530", edgecolor="#3a4552", labelcolor="#cfd6de")
    fig.suptitle(title, color="#e5e9ee", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=80, facecolor=fig.get_facecolor(), pil_kwargs=dict(quality=82, optimize=True))
    plt.close(fig)


def select_sites(R):
    sites = {}
    for tid, t in R["targets"].items():
        picks = [(x, "top") for x in t["top"][:3]] + [(x, "excl_china") for x in t.get("excl_china", [])[:1]] + \
                [(x, "continent") for x in t.get("by_continent", [])[:3]]
        for x, why in picks:
            k = site_id(x["lat"], x["lon"])
            s = sites.setdefault(k, dict(id=k, lat=x["lat"], lon=x["lon"], country=x.get("country"), env=x["env_class"],
                                         matches=[]))
            lst = {"top": "top 20", "excl_china": "without China", "continent": f"best in {x.get('continent')}"}[why]
            entry = dict(target=tid, name=t["name"], body=t["body"], rank=x["rank"], cell_rank=x.get("cell_rank"), list=lst)
            if not any(m["target"] == tid and m["list"] == lst for m in s["matches"]):
                s["matches"].append(entry)
    return list(sites.values())


def main():
    sys.path.insert(0, str(ROOT / "scoring"))
    R = json.load(open(ROOT / "results" / "top_sites.json", encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    sites = select_sites(R)
    print(len(sites), "Orte")
    done = []
    for i, st in enumerate(sites, 1):
        lat, lon = st["lat"], st["lon"]
        img, label = fetch_image(lat, lon)
        z, ext = read_dem(lat, lon)
        if not np.isfinite(z).any():
            print(f"  {i:3d} {st['id']}: kein DEM"); continue
        slope, hs = slope_hillshade(z, lat, ext)
        inside, cell0 = cell_mask(z.shape, ext, lat, lon)
        cin, cout = slope[inside & np.isfinite(slope)], slope[~inside & np.isfinite(slope)]
        zin = z[inside & np.isfinite(z)]
        m = dict(slope_p50=float(np.percentile(cin, 50)), slope_p90=float(np.percentile(cin, 90)),
                 flat_share=float((cin < 5).mean()), steep_share=float((cin > 15).mean()),
                 elev_min=float(zin.min()), elev_max=float(zin.max()),
                 sur_slope_p50=float(np.percentile(cout, 50)) if cout.size else None,
                 sur_flat_share=float((cout < 5).mean()) if cout.size else None)
        # uniform: the cell looks like its surroundings and has no large steep share
        m["uniform"] = bool(m["steep_share"] < 0.1 and (m["sur_flat_share"] is None or abs(m["flat_share"] - m["sur_flat_share"]) < 0.25))
        title = f"{abs(lat):.3f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.3f}° {'E' if lon >= 0 else 'W'}"
        figure(img, label, hs, slope, inside, cell0, ext, title, OUT / f"{st['id']}.jpg")
        st.update(metrics={k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}, image=f"{st['id']}.jpg",
                  image_source=label)
        done.append(st)
        print(f"  {i:3d} {st['id']}: {label[:22]}, Neigung P50 {m['slope_p50']:.1f}°, flach {m['flat_share']:.0%}", flush=True)
    json.dump(dict(sites=done), open(OUT / "profiles.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT / "profiles.json", len(done))


if __name__ == "__main__":
    main()
