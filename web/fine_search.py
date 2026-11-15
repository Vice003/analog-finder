"""
Fine search: within the area around each profiled site, find the patch that matches the target's terrain best.

The scoring works on 5 km cells. A target site, however, is a box of 10 x 10 km (Mars) or 15 x 15 km (Moon), and the
site profiles show that many top cells mix plains and steep ground. For every profiled site and every target it
matches, a box of the target's size is moved in 1 km steps up to MAX_SHIFT_KM around the cell. For each position the
terrain values are computed exactly like for the target (common/terrain.py: Copernicus DEM 90 m resampled to the
target's pixel size, 100 m Moon / 463 m Mars; slope P50/P90, relief P95-P5 in 5 km windows) and scored like in the
scoring (value against value: 1 - |Earth - target| / span, same span as in results/top_sites.json).

Output: results/fine_search.json
  {site_id: {target_id: {best: {lat, lon, offset_km, bearing, slope_p50, slope_p90, relief, match},
                         centre: {... same for the box centred on the cell ...}, target: {...}, box_km, pixel_m}}}

  python web/fine_search.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from common.terrain import resample, slope_deg  # noqa: E402

MAX_SHIFT_KM, STEP_KM, WINDOW_M = 8.0, 1.0, 5000.0
BOX_HALF_KM = {"Mars": 5.0, "Moon": 7.5}
DEM = "/vsicurl/https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"
TERRAIN = ("slope_p50", "slope_p90", "relief")


def read_dem(lat, lon, half_km):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    dlat = half_km / 111.0
    coslat = max(math.cos(math.radians(lat)), 0.05)
    dlon = half_km / (111.0 * coslat)
    w, s, e, n = lon - dlon, lat - dlat, lon + dlon, lat + dlat
    res = 1 / 1200
    ny, nx = int(round((n - s) / res)), int(round((e - w) / res * coslat))
    z = np.full((ny, nx), np.nan, np.float32)
    t = from_origin(w, n, (e - w) / nx, (n - s) / ny)
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            name = f"Copernicus_DSM_COG_30_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"
            try:
                with rasterio.open(DEM.format(n=name)) as src:
                    part = np.full((ny, nx), np.nan, np.float32)
                    reproject(source=rasterio.band(src, 1), destination=part, dst_transform=t, dst_crs="EPSG:4326",
                              resampling=Resampling.bilinear, dst_nodata=np.nan)
                    z = np.where(np.isfinite(part), part, z)
            except Exception:
                continue  # no tile over the ocean
    pix_m = (n - s) / ny * 111320.0
    return z, (w, s, e, n), pix_m


def box_stats(zr, sr, r0, c0, half_px, win_px):
    zz = zr[r0 - half_px:r0 + half_px, c0 - half_px:c0 + half_px]
    ss = sr[r0 - half_px:r0 + half_px, c0 - half_px:c0 + half_px]
    if zz.size == 0 or np.isfinite(zz).mean() < 0.9:
        return None
    s = ss[np.isfinite(ss)]
    rel = []
    for i in range(0, zz.shape[0] - win_px + 1, win_px):
        for j in range(0, zz.shape[1] - win_px + 1, win_px):
            win = zz[i:i + win_px, j:j + win_px]
            if np.isfinite(win).mean() >= 0.5:
                p5, p95 = np.nanpercentile(win, [5, 95])
                rel.append(p95 - p5)
    if not rel:
        p5, p95 = np.nanpercentile(zz, [5, 95])
        rel = [p95 - p5]
    return dict(slope_p50=float(np.percentile(s, 50)), slope_p90=float(np.percentile(s, 90)), relief=float(np.median(rel)))


def match(st, tv, span):
    parts = [max(0.0, 1 - abs(st[k] - tv[k]) / span[k]) for k in TERRAIN if k in tv and k in span]
    return float(np.mean(parts)) if parts else None


BEARINGS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def main():
    from countries import CountryLookup  # noqa: F401  (keeps scoring/ on the path check simple)
    P = json.load(open(HERE / "profiles" / "profiles.json", encoding="utf-8"))["sites"]
    R = json.load(open(ROOT / "results" / "top_sites.json", encoding="utf-8"))["targets"]
    tpath = ROOT.parent / "NASA-Challenge" / "planetary" / "targets.json"
    if not tpath.exists():
        tpath = ROOT / "planetary" / "targets.json"
    T = json.load(open(tpath, encoding="utf-8"))["targets"]
    out = {}
    for n_site, st in enumerate(P, 1):
        targets = sorted({m["target"] for m in st["matches"]})
        bodies = {R[t]["body"] for t in targets}
        half_win = max(BOX_HALF_KM[b] for b in bodies) + MAX_SHIFT_KM + 1.0
        z, (w, s, e, n), pix = read_dem(st["lat"], st["lon"], half_win)
        if not np.isfinite(z).any():
            continue
        cache = {}
        res_site = {}
        for tid in targets:
            body = R[tid]["body"]
            f = T[tid]["features"]
            pixel_m = int(f["slope_p50"].get("pixel_m") or (100 if body == "Moon" else 463))
            if pixel_m not in cache:
                zr = resample(z.astype(float), pix, pix, pixel_m)
                cache[pixel_m] = (zr, slope_deg(zr, pixel_m))
            zr, sr = cache[pixel_m]
            ny, nx = zr.shape
            tv = {k: f[k]["value"] for k in TERRAIN if f.get(k, {}).get("value") is not None}
            span = {m["key"]: m["span"] for m in R[tid]["features_used"] if m["method"] == "direct" and m.get("span")}
            half_px = int(round(BOX_HALF_KM[body] * 1000 / pixel_m))
            win_px = max(int(round(WINDOW_M / pixel_m)), 2)
            step = max(int(round(STEP_KM * 1000 / pixel_m)), 1)
            shift = int(round(MAX_SHIFT_KM * 1000 / pixel_m))
            rc, cc = ny // 2, nx // 2
            lat_of = lambda r: n - (r + 0.5) * (n - s) / ny
            lon_of = lambda c: w + (c + 0.5) * (e - w) / nx
            best, centre = None, None
            offs = [k * step for k in range(-(shift // step), shift // step + 1)]  # symmetric, contains 0
            for dr in offs:
                for dc in offs:
                    if dr * dr + dc * dc > shift * shift:
                        continue
                    r0, c0 = rc + dr, cc + dc
                    if r0 - half_px < 0 or c0 - half_px < 0 or r0 + half_px > ny or c0 + half_px > nx:
                        continue
                    bs = box_stats(zr, sr, r0, c0, half_px, win_px)
                    if bs is None:
                        continue
                    bs["match"] = match(bs, tv, span)
                    if bs["match"] is None:
                        continue
                    dy_km, dx_km = -dr * pixel_m / 1000, dc * pixel_m / 1000
                    bs.update(lat=round(lat_of(r0), 4), lon=round(lon_of(c0), 4), offset_km=round(math.hypot(dx_km, dy_km), 1),
                              bearing=BEARINGS[int(((math.degrees(math.atan2(dx_km, dy_km)) + 360 + 22.5) % 360) // 45)] if (dx_km or dy_km) else "")
                    if dr == 0 and dc == 0:
                        centre = bs
                    if best is None or bs["match"] > best["match"] + 1e-9:
                        best = bs
            if best is None:
                continue
            rnd = lambda d: None if d is None else {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}
            res_site[tid] = dict(best=rnd(best), centre=rnd(centre), target={k: round(v, 3) for k, v in tv.items()},
                                 box_km=2 * BOX_HALF_KM[body], pixel_m=pixel_m)
        if res_site:
            out[st["id"]] = res_site
            msg = "; ".join(f"{tid}: {v['centre']['match'] if v['centre'] else float('nan'):.2f} -> {v['best']['match']:.2f} "
                            f"({v['best']['offset_km']} km {v['best']['bearing']})" for tid, v in list(res_site.items())[:2])
            print(f"{n_site:3d} {st['id']}: {msg}", flush=True)
    p = ROOT / "results" / "fine_search.json"
    json.dump(dict(meta=dict(max_shift_km=MAX_SHIFT_KM, step_km=STEP_KM, box_half_km=BOX_HALF_KM), sites=out),
              open(p, "w", encoding="utf-8"), indent=1)
    print("->", p, len(out), "Orte")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scoring"))
    main()
