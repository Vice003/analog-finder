"""
Berechnet planetary/targets.json fuer alle 27 Orte aus der Ortsliste des Mond/Mars-Teams
(data_scripts/landing_sites.py, Branch Mars_and_Moon, Stand 14.11. 17:48). Von Vicente am 14.11. ~18:30
geschrieben, weil bis M1 noch keine Zielwerte vorlagen; Rohdaten und Werte sind PDS/USGS-Produkte.

Pro Ort ein quadratisches Polygon (Mars 10 x 10 km, Mond 15 x 15 km) um die Koordinate der Liste.
Die Koordinaten der Liste sind Naeherungen (coord_quality "approx"/"unverified"), das Polygon trifft
deshalb die Region, nicht zwingend die exakte Landestelle.

Mars
  Gelaende          MOLA-Mosaik 463 m (USGS Astrogeology, Lesen eines Ausschnitts per HTTP),
                    common/terrain.py mit pixel_m = 463                               reliability A
  thermal_inertia   TES nachts (Putzig & Mellon 2007, PDS MGST_9001, 20 ppd),
                    Median im Polygon + body_percentile ueber den ganzen Mars              reliability A
  pressure          aus MOLA-Hoehe: 6,1 hPa * exp(-z / 11,1 km), grobe Naeherung          reliability C
  surface_temp_mean, diurnal_range, ground_ice
                    Schaetzwerte der Musterziele (jezero bzw. arcadia, pipeline.py, Quelle offen),
                    auf trockene bzw. eisreiche Orte uebertragen                            reliability C
Mond
  Gelaende          LOLA LDEM_80S_80M (PDS), common/terrain.py mit pixel_m = 100           reliability A
  surface_temp_mean Diviner PRP (temp_avg), aus data_scripts/output/moon_south/features.npz
                    (Jimale, 240-m-Raster 85-90 S), Median im Polygon                       reliability B
  ground_ice        Anteil der Polygonzellen mit Eis stabil in <= 1 m Tiefe (Diviner PRP)   reliability B
  (Diviner-Werte nur fuer Orte suedlich 85 S, weil das Raster dort endet)
Beide
  sun_elevation_max, precip, ndvi (und am Mond pressure, wind_mean, humidity): physikalisch/berechnet, A

Aufruf (im Repo-Wurzelordner):
  python planetary/compute_targets.py --raw ~/SpaceApps/analog-finder/data/planetary/raw
Rohdaten im Ordner --raw:
  ldem_80s_80m.img                       https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/
  tes/mgst_9001/data/global_ti_night_2007.img   https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/mgst_9001.zip
  jimale_moon_features.npz               git show origin/Mars_and_Moon:data_scripts/output/moon_south/features.npz
MOLA wird direkt gelesen: https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from common.terrain import terrain_stats, pixel_size_latlon  # noqa: E402
from common.body_percentile import body_percentile, latlon_weights  # noqa: E402

# name, body, lat, lon_E, category, source  (aus data_scripts/landing_sites.py, Branch Mars_and_Moon)
SITES = [
    ("Peak near Cabeus B", "moon", -82.5, 307.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Haworth", "moon", -87.4, 355.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Malapert Massif", "moon", -86.0, 3.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Mons Mouton Plateau", "moon", -84.5, 32.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Mons Mouton", "moon", -84.0, 31.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Nobile Rim 1 / 2", "moon", -85.3, 53.5, "Artemis III region (2024)", "NASA 2024-10-28 (Nobile crater centre)"),
    ("de Gerlache Rim 2", "moon", -88.5, 272.9, "Artemis III region (2022+2024)", "NASA; ESA (de Gerlache centre)"),
    ("Slater Plain", "moon", -88.0, 110.0, "Artemis III region (2024)", "NASA 2024-10-28 - coords UNVERIFIED"),
    ("Peak near Shackleton", "moon", -89.0, 200.0, "Artemis III region (2022)", "NASA 2022-08-19 - coords approx"),
    ("Connecting Ridge (Shackleton-de Gerlache)", "moon", -89.4, 260.0, "Artemis III region (2022)", "NASA 2022-08-19 - coords approx"),
    ("Faustini Rim A", "moon", -87.3, 77.0, "Artemis III region (2022)", "NASA 2022; ESA (Faustini centre)"),
    ("Shackleton crater (PSR)", "moon", -89.67, 129.78, "PSR / ice target", "Wikipedia/IAU"),
    ("Cabeus (LCROSS impact, PSR)", "moon", -84.9, 324.5, "PSR / confirmed water ice", "LCROSS 2009"),
    ("Jezero crater (Perseverance)", "mars", 18.4, 77.5, "landed 2021", "NASA JPL"),
    ("Gale crater (Curiosity)", "mars", -5.4, 137.8, "landed 2012", "NASA JPL"),
    ("Meridiani Planum (Opportunity)", "mars", -1.9, 354.5, "landed 2004", "NASA JPL"),
    ("Gusev / Columbia Hills (Spirit)", "mars", -14.6, 175.5, "landed 2004; M2020 finalist", "NASA JPL"),
    ("Elysium Planitia (InSight)", "mars", 4.5, 135.6, "landed 2018", "NASA JPL"),
    ("Phoenix site (Vastitas Borealis)", "mars", 68.2, 234.3, "landed 2008, ground ice", "NASA JPL"),
    ("Utopia Planitia (Zhurong, CNSA)", "mars", 25.1, 109.9, "landed 2021 (non-NASA)", "CNSA"),
    ("NE Syrtis", "mars", 17.8, 77.1, "M2020 finalist", "Mars 2020 site selection"),
    ("Mawrth Vallis", "mars", 24.0, 341.0, "MSL + M2020 candidate", "MSL site selection"),
    ("Eberswalde crater (delta)", "mars", -23.9, 326.7, "MSL finalist", "MSL site selection"),
    ("Holden crater", "mars", -26.4, 325.1, "MSL finalist", "MSL site selection"),
    ("Oxia Planum (Rosalind Franklin, ESA)", "mars", 18.3, 335.4, "ESA ExoMars target", "ESA"),
    ("Arcadia Planitia", "mars", 40.0, 200.0, "SWIM ice target / human EZ", "SWIM, Morgan et al. 2021"),
    ("Deuteronilus Mensae", "mars", 44.0, 22.0, "SWIM ice target / human EZ", "SWIM, Morgan et al. 2021"),
]

R_KM = {"moon": 1737.4, "mars": 3389.5}
HALF_KM = {"moon": 7.5, "mars": 5.0}
UNITS = dict(slope_p50="deg", slope_p90="deg", relief="m", albedo="1", thermal_inertia="J m-2 K-1 s-1/2",
             dust_opacity="1", dust_storm_days="d/yr", surface_temp_mean="K", surface_temp_min="K",
             diurnal_range="K", pressure="hPa", wind_mean="m/s", precip="mm/yr", humidity="g/kg",
             ndvi="1", ground_ice="1", sun_elevation_max="deg")
MOLA_URL = "/vsicurl/https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
PHYS = "physikalisch: keine Atmosphaere bzw. kein Wasserkreislauf"


def slug(name):
    base = name.split(" (")[0].split(" / ")[0]
    return re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")


def feat(key, value=None, source="", reliability=None, pixel=None, p10=None, p90=None, bp=None, notes=""):
    if value is not None and not np.isfinite(value):
        value, source, reliability = None, "", None
    r = lambda x: None if x is None else float(f"{x:.5g}")  # signifikante Stellen (Vakuum 1e-12 bleibt erhalten)
    return dict(value=r(value), p10=r(p10), p90=r(p90), unit=UNITS[key], pixel_m=pixel, body_percentile=r(bp),
                source=source if value is not None else "", reliability=reliability if value is not None else None,
                notes=notes)


def square_polygon(lat, lon_e, half_km, body):
    """Quadrat um den Ort; nahe dem Mondpol in polarstereographischen Koordinaten, sonst in Breite/Laenge."""
    R = R_KM[body]
    if body == "moon" and lat < -80:
        d = 2 * R * math.tan(math.radians(90 + lat) / 2)
        x, y = d * math.sin(math.radians(lon_e)), d * math.cos(math.radians(lon_e))
        pts = []
        for dx, dy in [(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)]:
            px, py = x + dx * half_km, y + dy * half_km
            dd = math.hypot(px, py)
            la = -90 + math.degrees(2 * math.atan(dd / (2 * R)))
            lo = math.degrees(math.atan2(px, py)) % 360
            pts.append([round(lo, 5), round(la, 5)])
        return pts
    dlat = math.degrees(half_km / R)
    dlon = dlat / math.cos(math.radians(lat))
    return [[round((lon_e + a * dlon) % 360, 5), round(lat + b * dlat, 5)] for a, b in
            [(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)]]


# ------------------------------------------------------------------ Mars
def mars_terrain(lat, lon_e, half_km):
    import rasterio
    from rasterio.windows import Window
    lon = ((lon_e + 180) % 360) - 180
    with rasterio.open(MOLA_URL) as src:
        R = 3396190.0  # Kugelradius der Projektion laut Datei
        res = src.res[0]
        x, y = R * math.radians(lon), R * math.radians(lat)
        col = (x - src.bounds.left) / res
        row = (src.bounds.top - y) / res
        hy = half_km * 1000 / res
        hx = hy / math.cos(math.radians(lat))
        win = Window(int(col - hx), int(row - hy), int(2 * hx) + 1, int(2 * hy) + 1)
        z = src.read(1, window=win).astype(float)
        z[z == src.nodata] = np.nan
    rows_lat = lat + (hy - np.arange(z.shape[0])) * res / R * 180 / math.pi
    dx, dy = pixel_size_latlon(rows_lat, 1 / 128, 1 / 128, "Mars")
    return terrain_stats(z, dx, dy, 463.0), float(np.nanmedian(z))


def tes_lookup(ti, lat, lon_e, half_km):
    lon = ((lon_e + 180) % 360) - 180
    r0, c0 = (90 - lat) * 20, (lon + 180) * 20
    dlat = math.degrees(half_km / R_KM["mars"]) * 20
    dlon = dlat / math.cos(math.radians(lat))
    rs = slice(int(r0 - dlat), int(r0 + dlat) + 1)
    cs = slice(int(c0 - dlon), int(c0 + dlon) + 1)
    v = ti[rs, cs].astype(float)
    v = v[v > 0]
    return v


# ------------------------------------------------------------------ Mond
def moon_terrain(dem, lat, lon_e, half_km):
    d = 2 * R_KM["moon"] * math.tan(math.radians(90 + lat) / 2)
    x, y = d * math.sin(math.radians(lon_e)), d * math.cos(math.radians(lon_e))
    col = 3799.5 + x / 0.08
    row = 3799.5 - y / 0.08
    h = half_km / 0.08
    z = dem[int(row - h):int(row + h) + 1, int(col - h):int(col + h) + 1].astype(float) * 0.5
    return terrain_stats(z, 80.0, 80.0, 100.0)


def diviner_lookup(f, lat, lon_e, half_km):
    """Zellen von Jimales 240-m-Raster (85-90 S) im Quadrat um den Ort."""
    if lat > -85:
        return None
    R, CELL, N = 1737.4, 0.240, 1264
    HALF = N * CELL / 2
    d = 2 * R * math.tan(math.radians(90 - abs(lat)) / 2)
    x, y = d * math.sin(math.radians(lon_e)), d * math.cos(math.radians(lon_e))
    c0, r0 = (x + HALF) / CELL, (HALF - y) / CELL
    h = half_km / CELL
    sl = (slice(max(int(r0 - h), 0), int(r0 + h) + 1), slice(max(int(c0 - h), 0), int(c0 + h) + 1))
    return {k: f[k][sl] for k in ("temp_avg", "temp_max", "ice_depth")}


def sunniest_box(f, lat, lon_e, half_km, search_km=12.0):
    """
    Artemis-Regionen sind beleuchtete Landeflaechen am Rand der benannten Krater, die Ortsliste nennt aber oft den
    Kratermittelpunkt (Dauerschatten). Regel: das Quadrat auf den Ausschnitt mit der hoechsten mittleren
    LOLA-Sonnensichtbarkeit innerhalb search_km um die Koordinate legen (Jimales 240-m-Raster, nur 85-90 S).
    Rueckgabe: (lat, lon_e, mittlere Sonnensichtbarkeit) oder None.
    """
    if lat > -85:
        return None
    from scipy.ndimage import uniform_filter
    R, CELL, N = 1737.4, 0.240, 1264
    HALF = N * CELL / 2
    sun = np.nan_to_num(f["sun_mean"], nan=0.0)
    box = uniform_filter(sun, size=int(2 * half_km / CELL), mode="nearest")
    d = 2 * R * math.tan(math.radians(90 - abs(lat)) / 2)
    x0, y0 = d * math.sin(math.radians(lon_e)), d * math.cos(math.radians(lon_e))
    c0, r0 = (x0 + HALF) / CELL, (HALF - y0) / CELL
    rr, cc = np.mgrid[0:N, 0:N]
    near = np.hypot(rr - r0, cc - c0) * CELL <= search_km
    edge = int(half_km / CELL) + 1
    near &= (rr > edge) & (rr < N - edge) & (cc > edge) & (cc < N - edge)
    if not near.any():
        return None
    i = np.argmax(np.where(near, box, -1))
    r, c = divmod(i, N)
    return float(f["lat"][r, c]), float(f["lon"][r, c]), float(box[r, c])


def pcts(v):
    v = v[np.isfinite(v)]
    return (float(np.median(v)), float(np.percentile(v, 10)), float(np.percentile(v, 90))) if v.size else (None,) * 3


def main():
    ap = argparse.ArgumentParser()
    own_raw = REPO / "data" / "planetary" / "raw"
    ap.add_argument("--raw", default=str(own_raw if own_raw.exists() else Path.home() / "SpaceApps/analog-finder/data/planetary/raw"))
    ap.add_argument("--out", default=str(REPO / "planetary" / "targets.json"))
    args = ap.parse_args()
    raw = Path(args.raw)

    ti = np.fromfile(raw / "tes/mgst_9001/data/global_ti_night_2007.img", ">i2").reshape(3600, 7200)
    ti_f = np.where(ti > 0, ti, np.nan).astype(float)
    ti_w = latlon_weights(3600)
    lola = np.memmap(raw / "ldem_80s_80m.img", dtype="<i2", mode="r", shape=(7600, 7600))
    div = dict(np.load(raw / "jimale_moon_features.npz"))

    targets = {}
    for name, body, lat, lon_e, cat, src in SITES:
        tid = slug(name)
        cq = "unverified" if "UNVERIFIED" in src.upper() else "approx"
        half = HALF_KM[body]
        psr = "PSR" in cat
        note = f"Quadrat {2 * half:g} x {2 * half:g} km um die Koordinate der Ortsliste (automatisch)"
        lat0, lon0 = lat, lon_e
        if body == "moon" and "Artemis" in cat:
            moved = sunniest_box(div, lat, lon_e, half)
            if moved:
                lat, lon_e, sun = moved
                note = (f"Quadrat {2 * half:g} x {2 * half:g} km auf den am besten beleuchteten Ausschnitt innerhalb "
                        f"12 km um die Listenkoordinate ({lat0}, {lon0}) gelegt; mittlere LOLA-Sonnensichtbarkeit "
                        f"{sun:.2f}. Grund: Artemis-Regionen sind beleuchtete Landeflaechen, die Liste nennt oft "
                        f"den Kratermittelpunkt")
        t = dict(body="Moon" if body == "moon" else "Mars", name=name, category=cat, center_lat=round(lat, 4),
                 center_lon=round(lon_e % 360, 4), coord_quality=cq,
                 site_source=f"{src} (Ortsliste data_scripts/landing_sites.py, Branch Mars_and_Moon)",
                 region_geojson={"type": "Polygon", "coordinates": [square_polygon(lat, lon_e, half, body)]},
                 region_notes=note, features={})
        F = t["features"]
        if body == "mars":
            st, z_med = mars_terrain(lat, lon_e, half)
            s_mola = "MOLA-Mosaik 463 m (USGS Astrogeology), common/terrain.py"
            F["slope_p50"] = feat("slope_p50", st["slope_p50"], s_mola, "A", 463)
            F["slope_p90"] = feat("slope_p90", st["slope_p90"], s_mola, "A", 463)
            F["relief"] = feat("relief", st["relief"], s_mola, "A", 463)
            v = tes_lookup(ti, lat, lon_e, half)
            med, p10, p90 = pcts(v)
            bp = body_percentile(ti_f, ti_w, med) if med is not None else None
            F["thermal_inertia"] = feat("thermal_inertia", med, "TES nachts, Putzig & Mellon 2007 (PDS MGST_9001)", "A",
                                        p10=p10, p90=p90, bp=bp, notes=f"{v.size} TES-Pixel (3 km) im Polygon")
            F["albedo"] = feat("albedo", notes="OMEGA ALBEDO_R1080 noch nicht ausgewertet")
            F["dust_opacity"] = feat("dust_opacity", notes="TES-Staubopazitaet noch nicht ausgewertet")
            icy = "ice" in cat.lower()
            ref = "arcadia" if icy else "jezero"
            est = dict(arcadia=(203.15, 60, 1), jezero=(218.15, 75, 0))[ref]
            s_est = f"Schaetzwert der Musterziels {ref} (pipeline.py, gerundet - Quelle offen), uebertragen"
            F["surface_temp_mean"] = feat("surface_temp_mean", est[0], s_est, "C")
            F["diurnal_range"] = feat("diurnal_range", est[1], s_est, "C")
            F["ground_ice"] = feat("ground_ice", est[2], s_est, "C", notes="Odyssey GRS noch nicht ausgewertet")
            F["pressure"] = feat("pressure", 6.1 * math.exp(-z_med / 11100.0),
                                 "aus MOLA-Hoehe (Median im Polygon): 6,1 hPa * exp(-z / 11,1 km), Naeherung - Quelle offen",
                                 "C", notes=f"MOLA-Hoehe {z_med:.0f} m")
            F["precip"] = feat("precip", 0, PHYS, "A")
            F["ndvi"] = feat("ndvi", 0, PHYS, "A")
            F["sun_elevation_max"] = feat("sun_elevation_max", min(90.0, 90 - abs(lat) + 25.19),
                                          "berechnet: 90 - |Breite| + Achsneigung 25,19 Grad", "A")
        else:
            st = moon_terrain(lola, lat, lon_e, half)
            s_lola = "LOLA LDEM_80S_80M (PDS), common/terrain.py"
            F["slope_p50"] = feat("slope_p50", st["slope_p50"], s_lola, "A", 100)
            F["slope_p90"] = feat("slope_p90", st["slope_p90"], s_lola, "A", 100)
            F["relief"] = feat("relief", st["relief"], s_lola, "A", 100)
            F["thermal_inertia"] = feat("thermal_inertia", notes="kein Produkt in den offiziellen Quellen")
            dv = diviner_lookup(div, lat, lon_e, half)
            s_div = "Diviner PRP via data_scripts/output/moon_south/features.npz (Jimale, 240 m)"
            if dv is not None:
                med, p10, p90 = pcts(dv["temp_avg"])
                F["surface_temp_mean"] = feat("surface_temp_mean", med, s_div, "B", p10=p10, p90=p90,
                                              notes="Diviner-Dreiecke (km) mischen Sonne und Schatten")
                ice = dv["ice_depth"][np.isfinite(dv["ice_depth"])]
                F["ground_ice"] = feat("ground_ice", float((ice <= 1.0).mean()) if ice.size else None, s_div, "B",
                                       notes="Anteil der Polygonzellen mit Eis stabil in <= 1 m Tiefe")
            else:
                F["surface_temp_mean"] = feat("surface_temp_mean", notes="noerdlich 85 S, ausserhalb des Diviner-Rasters")
                F["ground_ice"] = feat("ground_ice", notes="noerdlich 85 S, ausserhalb des Diviner-Rasters")
            F["pressure"] = feat("pressure", 1e-12, PHYS, "A", notes="Vakuum")
            for k in ("wind_mean", "precip", "humidity", "ndvi"):
                F[k] = feat(k, 0, PHYS, "A")
            F["sun_elevation_max"] = feat("sun_elevation_max", 0.0 if psr else 90 - abs(lat) + 1.54,
                                          "dauerhaft beschattet" if psr else "berechnet: 90 - |Breite| + Achsneigung 1,54 Grad",
                                          "A")
        targets[tid] = t
        print(f"{tid:26s} {t['body']:4s} {st['slope_p50']:5.1f} {st['slope_p90']:5.1f} {st['relief']:7.0f}  "
              + (f"TI {F['thermal_inertia']['value']} (P{(F['thermal_inertia']['body_percentile'] or 0) * 100:.0f})"
                 if body == "mars" else f"T {F['surface_temp_mean']['value']}  Eis {F['ground_ice']['value']}"), flush=True)

    json.dump({"schema_version": 2, "targets": targets}, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\n{len(targets)} Ziele -> {args.out}")


if __name__ == "__main__":
    main()
