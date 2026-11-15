"""
Builds the Analog Finder web app: one self-contained HTML file (no server, works as Artifact and on GitHub Pages).

Inputs
  ../planetary/targets.json          target sites with their values (repo)
  results/top_sites.json             top 20 Earth sites per target (0.05 deg scoring)
  data/earth/earth_features_025deg.parquet   Earth table for the heat maps (0.25 deg)
  data/ref/ne_110m_admin_0_countries  country outlines for the base map (Natural Earth, public domain)
Output
  web/index.html

Heat map per target: area-weighted percentile of the analog score among all ranked Earth land cells (0.25 deg),
re-projected to Web Mercator (lat +-85.05) because the map draws images in that projection.

Run:  python web/build_web.py [--targets ../planetary/targets.json]
"""

import argparse
import base64
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scoring"))
from target_scoring import load_targets, score_target, _weighted_pct, profile_for, country_raster, POOL_DIMS  # noqa: E402
from categories import classify, ENV_CLASSES, TARGETS as PROFILES  # noqa: E402
from countries import CountryLookup  # noqa: E402

MAPLIBRE = "4.7.1"
MERC_LAT = 85.0511287798
IMG_W, IMG_H = 1440, 1440

ENV_EN = {"eisschild": "Ice sheet & glacier", "salzpfanne": "Salt flat / evaporite", "duenenfeld": "Dune field / sand sea",
          "dunkel_vulkanisch": "Dark bare rock (basalt, lava)", "kalte_polarwueste": "Ice-free cold polar desert",
          "hochplateau": "Arid high plateau", "hyperarid": "Hyperarid desert", "raues_gebirge": "Barren steep terrain",
          "aride_wueste": "Arid desert / semi-desert", "kein_analog": "Bare, but no class matched (wetter or milder)"}
DIM_EN = {"gelaende": "Terrain", "oberflaeche": "Surface material", "thermik": "Temperature", "trockenheit": "Dryness",
          "atmosphaere": "Atmosphere", "staub_wind": "Dust & wind", "eis_wasser": "Ice & water", "leben": "Vegetation",
          "beleuchtung": "Sunlight"}
FLAG_EN = {"staubquelle": "dust source", "staubsturmreich": "frequent dust storms", "windsturmreich": "frequent gales",
           "windstill": "calm", "frost_tau": "freeze-thaw", "extrem_kalt": "extreme cold", "niedriger_druck": "low pressure",
           "dunkle_oberflaeche": "dark surface", "landefreundlich": "landing-friendly", "polar": "polar light"}
FEAT_EN = {"slope_p50": "Slope, median", "slope_p90": "Slope, 90th percentile", "relief": "Relief (P95-P5, 5 km)",
           "albedo": "Albedo", "thermal_inertia": "Thermal inertia", "dust_opacity": "Dust opacity",
           "dust_storm_days": "Dust storm days", "surface_temp_mean": "Mean surface temperature",
           "surface_temp_min": "Minimum surface temperature", "diurnal_range": "Day-night range",
           "pressure": "Surface pressure", "wind_mean": "Mean wind", "precip": "Precipitation", "humidity": "Humidity",
           "ndvi": "Vegetation (NDVI)", "ground_ice": "Ground ice", "sun_elevation_max": "Highest sun elevation"}


EXCLUDE = {"china": ["CHN", "HKG", "MAC"]}
# Earth-side unit where it differs from the target's (rank-matched features compare different instruments)
EARTH_UNIT = {"thermal_inertia": "ATI 1/K", "albedo": "", "dust_opacity": "(AOD)"}


def mask_png(df, isos):
    """Cells of the given countries (0.25 deg) as a Mercator mask PNG (255 = excluded)."""
    iso = country_raster(df)
    grid = np.zeros((720, 1440), np.uint8)
    iy = np.clip(((90 - df["lat"].to_numpy()) / 0.25).astype(int), 0, 719)
    ix = np.clip(((df["lon"].to_numpy() + 180) / 0.25).astype(int), 0, 1439)
    hit = iso.isin(isos).to_numpy()
    grid[iy[hit], ix[hit]] = 255
    return png_merc(grid)


def heat_png(df, total, ranked):
    """Percentile of the score (area-weighted, ranked cells only) on the 0.25 deg grid -> Mercator 8-bit PNG."""
    w = pd.Series(np.cos(np.radians(df["lat"].to_numpy())), index=df.index)
    pct = _weighted_pct(total.where(ranked), w)
    grid = np.zeros((720, 1440), np.uint8)
    iy = np.clip(((90 - df["lat"].to_numpy()) / 0.25).astype(int), 0, 719)
    ix = np.clip(((df["lon"].to_numpy() + 180) / 0.25).astype(int), 0, 1439)
    v = pct.to_numpy()
    ok = np.isfinite(v)
    grid[iy[ok], ix[ok]] = np.clip(1 + np.round(v[ok] * 254), 1, 255).astype(np.uint8)
    return png_merc(grid)


def png_merc(grid):
    """0.25 deg lat/lon grid (720x1440, uint8) -> Web Mercator PNG data URL."""
    y = (np.arange(IMG_H) + 0.5) / IMG_H                      # 0 top .. 1 bottom
    ymerc = math.pi * (1 - 2 * y)
    lat = np.degrees(np.arctan(np.sinh(ymerc)))
    src_rows = np.clip(((90 - lat) / 0.25).astype(int), 0, 719)
    src_cols = np.clip((np.arange(IMG_W) * 1440 / IMG_W).astype(int), 0, 1439)
    merc = grid[np.ix_(src_rows, src_cols)]
    buf = io.BytesIO()
    Image.fromarray(merc, "L").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------------ body maps (target picker)
RAW = ROOT / "data" / "planetary" / "raw"
MOON_R, MOON_HALF_KM = 1737.4, 240.0   # crop of LOLA LDEM_80S_80M around the south pole (covers 82.4 S)


def _hillshade(z, dx, dy, az=315, alt=40):
    gy, gx = np.gradient(z, dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, h = np.radians(az), np.radians(alt)
    return np.clip(np.sin(h) * np.cos(slope) + np.cos(h) * np.sin(slope) * np.cos(a - aspect), 0, 1)


def _jpeg(rgb, q=82):
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def mars_map():
    """MOLA MEGDR 4 px/deg (NASA PDS), hillshade x elevation tint, centred on 0 E. Returns (data URL, w, h)."""
    z = np.fromfile(RAW / "mola_megdr" / "megt90n000cb.img", dtype=">i2").reshape(720, 1440).astype(np.float32)
    z = np.roll(z, 720, axis=1)                             # 0..360 E -> -180..180, 0 E in the centre
    lat = 90 - (np.arange(720) + 0.5) / 4
    dy = 3389.5e3 * np.radians(0.25)
    dx = np.maximum(np.cos(np.radians(lat)), 0.05)[:, None] * dy
    gy, gx = np.gradient(z, dy, axis=0), np.gradient(z, axis=1) / dx
    slope = np.arctan(np.hypot(gx, gy) * 7)
    aspect = np.arctan2(-gx, gy)
    a, h = np.radians(315), np.radians(40)
    hs = np.clip(np.sin(h) * np.cos(slope) + np.cos(h) * np.sin(slope) * np.cos(a - aspect), 0, 1)
    t = np.clip((z + 8000) / 20000, 0, 1)[..., None]       # elevation tint: low = dark rust, high = pale ochre
    lo, hi = np.array([70, 34, 22]), np.array([222, 170, 120])
    rgb = (lo + (hi - lo) * t) * (0.2 + 0.95 * hs[..., None])
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").resize((1000, 500), Image.LANCZOS)
    return _jpeg(np.asarray(img)), 1000, 500


def moon_map():
    """LOLA LDEM_80S_80M (NASA PDS), south polar stereographic crop, hillshade. Returns (data URL, w, h)."""
    dem = np.memmap(RAW / "ldem_80s_80m.img", dtype="<i2", mode="r", shape=(7600, 7600))
    h = int(MOON_HALF_KM / 0.08)
    c = 3800
    z = np.asarray(dem[c - h:c + h, c - h:c + h], dtype=np.float32) * 0.5
    f = 8                                                   # 80 m -> 640 m
    z = z[: z.shape[0] // f * f, : z.shape[1] // f * f].reshape(z.shape[0] // f, f, z.shape[1] // f, f).mean(axis=(1, 3))
    hs = _hillshade(z, 640, 640, az=315, alt=30)
    t = np.clip((z + 5000) / 10000, 0, 1)
    g = (30 + 200 * hs * (0.55 + 0.45 * t))
    rgb = np.stack([g * 0.96, g * 0.98, g * 1.04], -1)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").resize((700, 700), Image.LANCZOS)
    return _jpeg(np.asarray(img)), 700, 700


def map_xy(body, lat, lon_e):
    """Position of a target on its body map, as fractions 0..1 of width and height."""
    if body == "Moon":
        d = 2 * MOON_R * math.tan(math.radians(90 + lat) / 2)
        x, y = d * math.sin(math.radians(lon_e)), d * math.cos(math.radians(lon_e))
        return round((x + MOON_HALF_KM) / (2 * MOON_HALF_KM), 4), round((MOON_HALF_KM - y) / (2 * MOON_HALF_KM), 4)
    return round((((lon_e + 180) % 360)) / 360, 4), round((90 - lat) / 180, 4)


def fine(f):
    """Fine-search result for one site and target, compact: [best lat, lon, offset km, bearing, best match, centre match, box km]."""
    if not f:
        return None
    b, c = f["best"], f.get("centre") or {}
    return [b["lat"], b["lon"], b["offset_km"], b["bearing"], b["match"], c.get("match"), f["box_km"]]


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def iso_names():
    """ISO-A3 -> short English country name (Natural Earth 1:50m), for pool cells without a precomputed label."""
    import shapefile
    r = shapefile.Reader(str(ROOT / "data" / "ref" / "ne_50m_admin_0_countries"), encoding="utf-8")
    f = [x[0] for x in r.fields[1:]]
    out = {}
    for rec in r.records():
        d = dict(zip(f, rec))
        iso = d.get("ISO_A3") if d.get("ISO_A3") not in (None, "", "-99") else d.get("ADM0_A3")
        out.setdefault(iso, d.get("NAME") or d.get("ADMIN"))
    return out


def pack_pool(z, tid, names, pfz=None, rbz=None):
    """Candidate pool of one target, compact for the browser (little-endian typed arrays as base64).
    flags: uint16 bitmask per cell (bit order = poolMeta.flags, results/pool_flags.npz);
    rb: robustness share per cell, uint8 round(share * 254), 255 = missing (results/robustness_pool.npz)."""
    g = lambda k: z[f"{tid}/{k}"]
    iso = g("iso")
    iso_list = sorted(set(iso.tolist()))
    n = len(g("lat"))
    extra = {}
    if pfz is not None and tid in pfz.files and len(pfz[tid]) == n:
        extra["flags"] = b64(pfz[tid].astype("<u2"))
    if rbz is not None and tid in rbz.files and len(rbz[tid]) == n:
        extra["rb"] = b64(rbz[tid].astype(np.uint8))
    return dict(**extra, n=int(len(g("lat"))), nr=int(g("nranked")), fkeys=g("fkeys").tolist(),
                lat=b64(g("lat").astype("<f4")), lon=b64(g("lon").astype("<f4")), total=b64(g("total").astype("<f4")),
                rank=b64(g("rank").astype("<i4")), cov=b64(g("cov")), dims=b64(g("dims")), conf=b64(g("conf")),
                fs=b64(g("fs")), fv=b64(g("fv").astype("<f2")), cls=b64(g("cls")), cont=b64(g("cont")),
                known=b64(g("known").astype("<i2")), isoi=b64(np.array([iso_list.index(x) for x in iso], "<u2")),
                isos=iso_list, isonames=[names.get(x) or x for x in iso_list])


def countries_geojson(path):
    import shapefile
    r = shapefile.Reader(str(path), encoding="utf-8")
    fields = [f[0] for f in r.fields[1:]]
    feats = []
    for sr in r.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        g = sr.shape.__geo_interface__

        def rnd(c):
            return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 2), round(c[1], 2)]
        feats.append({"type": "Feature", "properties": {"n": rec.get("NAME")},
                      "geometry": {"type": g["type"], "coordinates": rnd(g["coordinates"])}})
    return {"type": "FeatureCollection", "features": feats}


def main():
    ap = argparse.ArgumentParser()
    own = ROOT / "planetary" / "targets.json"  # eigenes Repo; sonst das Team-Repo daneben
    ap.add_argument("--targets", default=str(own if own.exists() else ROOT.parent / "NASA-Challenge" / "planetary" / "targets.json"))
    ap.add_argument("--results", default=str(ROOT / "results" / "top_sites.json"))
    ap.add_argument("--table", default=str(ROOT / "data" / "earth" / "earth_features_025deg.parquet"))
    ap.add_argument("--out", default=str(HERE / "index.html"), help="eigenstaendige Seite (GitHub Pages)")
    ap.add_argument("--artifact", default=str(HERE / "artifact.html"), help="Fragment fuer das Artifact")
    args = ap.parse_args()

    T = load_targets(args.targets)
    R = json.load(open(args.results, encoding="utf-8"))
    df = pd.read_parquet(args.table)
    cl = CountryLookup(lang="en")

    rb_path = Path(args.results).with_name("robustness.json")
    RB = json.load(open(rb_path, encoding="utf-8"))["targets"] if rb_path.exists() else {}
    pf_path = HERE / "profiles" / "profiles.json"
    PF = {s["id"] for s in json.load(open(pf_path, encoding="utf-8"))["sites"]} if pf_path.exists() else set()
    from make_site_profiles import site_id
    fs_path = Path(args.results).with_name("fine_search.json")
    FSR = json.load(open(fs_path, encoding="utf-8"))["sites"] if fs_path.exists() else {}
    pool_path = Path(args.results).with_name("pool.npz")
    Z = np.load(pool_path) if pool_path.exists() else None
    names = iso_names() if Z is not None else {}
    # flags and robustness of every pool cell (scoring/pool_flags.py, scoring/robustness.py)
    pf_npz, rb_npz = Path(args.results).with_name("pool_flags.npz"), Path(args.results).with_name("robustness_pool.npz")
    PFZ = np.load(pf_npz) if Z is not None and pf_npz.exists() else None
    RBZ = np.load(rb_npz) if Z is not None and rb_npz.exists() else None
    FLAG_IDS = PFZ["_flags"].tolist() if PFZ is not None else []
    targets = []
    for tid, t in T.items():
        if tid not in R["targets"]:
            continue
        s = score_target(df, t, verbose=False)
        heat = heat_png(df, s["total"], s.get("in_ranking", pd.Series(True, index=df.index)))
        RT = R["targets"][tid]
        sites, key2i = [], {}
        # flags of the list sites from the pool bitmask (computed on the full table), so the default lists and the
        # in-browser ranking agree; top_sites.json flags are only the fallback
        pool_fk = {}
        if PFZ is not None and tid in PFZ.files and f"{tid}/lat" in Z.files:
            for a, b_, m in zip(Z[f"{tid}/lat"], Z[f"{tid}/lon"], PFZ[tid]):
                pool_fk[f"{float(a):.3f},{float(b_):.3f}"] = [f for q, f in enumerate(FLAG_IDS) if int(m) >> q & 1]

        def add(x):
            k = (x["lat"], x["lon"])
            if k in key2i:
                return key2i[k]
            x = dict(x, flags=pool_fk.get(f"{x['lat']:.3f},{x['lon']:.3f}", x["flags"]))
            name, iso = cl.label(x["lat"], x["lon"])
            er = x.get("env_reason") or {}
            er = {"rules": er} if isinstance(er, list) else er
            rule = lambda r: dict(t=r["text"], v=r["value"], u=r["unit"], ok=r["ok"])
            sites.append(dict(lat=x["lat"], lon=x["lon"], c=name, iso=iso, ct=x.get("continent"), ec=x["env_class"], fk=x["flags"], s=x["score"],
                              p=x["better_than_pct"], rk=x.get("cell_rank"), nr=x.get("n_ranked"), cov=x["coverage"], env=ENV_EN.get(x["env_class"], x["env_class"]),
                              fl=[FLAG_EN.get(f, f) for f in x["flags"]], b=DIM_EN.get(x["best_dim"], x["best_dim"]),
                              w=DIM_EN.get(x["worst_dim"], x["worst_dim"]), k=x["known_analog"],
                              d={DIM_EN.get(k, k): v for k, v in x["dims"].items()},
                              fv=[[f["earth"], f["score"], f["earth_pct"]] for f in x.get("features", [])],
                              rb=RB.get(tid, {}).get(f"{x['lat']:.3f},{x['lon']:.3f}"),
                              fsr=fine(FSR.get(site_id(x["lat"], x["lon"]), {}).get(tid)),
                              pf=site_id(x["lat"], x["lon"]) if site_id(x["lat"], x["lon"]) in PF else None,
                              er=dict(rules=[rule(r) for r in er.get("rules", [])],
                                      no=[dict(c=ENV_EN.get(n["cls"], n["cls"]), f=[rule(r) for r in n["failed"]])
                                          for n in er.get("not_", [])])))
            key2i[k] = len(sites) - 1
            return key2i[k]
        lists = {"all": [add(x) for x in RT["top"]]}
        for name in EXCLUDE:
            lists[name] = [add(x) for x in RT.get(f"excl_{name}", [])]
        lists["cont"] = [add(x) for x in RT.get("by_continent", [])]
        for name in EXCLUDE:
            lists[f"cont_{name}"] = [add(x) for x in RT.get(f"by_continent_excl_{name}", [])]
        fm = [dict(k=m["key"], ph=(t["features"].get(m["key"], {}).get("source") or "").startswith("physikalisch"),
                   n=FEAT_EN.get(m["key"], m["key"]), dim=DIM_EN.get(m["dim"], m["dim"]), m=m["method"], tv=m["target"],
                   u=m.get("unit"), tp=m.get("body_percentile"), dir=m.get("direction"), w=round(m["weight"], 2),
                   rt=m["rel_target"], re=m["rel_earth"], eu=EARTH_UNIT.get(m["key"], m.get("unit"))) for m in RT.get("features_used", [])]
        feats = []
        for k, f in t["features"].items():
            if f.get("value") is None:
                continue
            feats.append(dict(k=k, ph=(f.get("source") or "").startswith("physikalisch"), n=FEAT_EN.get(k, k), v=f["value"], u=f.get("unit"), rel=f.get("reliability"),
                              src=f.get("source", ""), bp=f.get("body_percentile")))
        targets.append(dict(id=tid, name=t.get("name"), body=t.get("body"), cat=t.get("category"),
                            cq=t.get("coord_quality"), lat=t.get("center_lat"), lon=t.get("center_lon"),
                            note=t.get("region_notes"), prof=profile_for(t), feats=feats, sites=sites, lists=lists,
                            fm=fm, heat=heat, pool=pack_pool(Z, tid, names, PFZ, RBZ) if Z is not None and f"{tid}/lat" in Z.files else None,
                            w={DIM_EN[d]: PROFILES[profile_for(t)]["weights"].get(d, 0) for d in POOL_DIMS}, mxy=map_xy(t.get("body"), t.get("center_lat"), t.get("center_lon"))))
        print(f"  {tid:26s} {len(heat) // 1024} KB", flush=True)

    masks = {name: mask_png(df, isos) for name, isos in EXCLUDE.items()}
    (mi, mw, mh), (ni, nw, nh) = mars_map(), moon_map()
    bodymaps = dict(Mars=dict(img=mi, w=mw, h=mh, cap="Mars · MOLA elevation, 0° E in the centre"),
                    Moon=dict(img=ni, w=nw, h=nh, cap=f"Moon · south pole to 82.4° S · LOLA elevation"))
    from glossary import GROUPS as GL_GROUPS, entries as gl_entries
    gl = gl_entries("en", base="https://vice003.github.io/analog-finder/glossary.html")
    glossary = dict(groups=GL_GROUPS["en"], items={e["id"]: [e["title"], e["html"], e["group"]] for e in gl},
                    order=[e["id"] for e in gl], page="https://vice003.github.io/analog-finder/glossary.html")
    pool_meta = None
    if Z is not None:
        pool_meta = dict(dims=[DIM_EN[d] for d in Z["_dims"].tolist()], classIds=Z["_classes"].tolist(),
                         classes=[ENV_EN.get(c, c) for c in Z["_classes"].tolist()], continents=Z["_continents"].tolist(),
                         known=Z["_known"].tolist(), flags=FLAG_IDS, flagLabels=[FLAG_EN.get(f, f) for f in FLAG_IDS])
    data = dict(targets=targets, masks=masks, bodymaps=bodymaps, glossary=glossary, poolMeta=pool_meta,
                profiles="https://vice003.github.io/analog-finder/profiles.html", countries=countries_geojson(ROOT / "data" / "ref" / "ne_110m_admin_0_countries"),
                meta=dict(earth_cells=R["meta"]["earth_cells"], table=R["meta"]["earth_table"]))
    css = urllib.request.urlopen(f"https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/{MAPLIBRE}/maplibre-gl.css",
                                 timeout=30).read().decode()
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    assert "</script" not in js.lower()
    page = tpl.replace("/*MAPLIBRE_CSS*/", css).replace("/*APP_DATA*/", js).replace("{{MAPLIBRE}}", MAPLIBRE)
    Path(args.artifact).write_text(page, encoding="utf-8")
    full = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            "</head>\n<body>\n" + page + "\n</body>\n</html>\n")
    Path(args.out).write_text(full, encoding="utf-8")
    print(f"-> {args.out} (GitHub Pages) und {args.artifact} (Artifact), {len(full) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
