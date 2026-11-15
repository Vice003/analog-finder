"""
Prueft eine Zielsignatur-Datei (planetary/targets.json) gegen die Spezifikation in ZIELSIGNATUREN.md
und den VERARBEITUNGSPLAN.md. Braucht nur Python, keine Zusatzpakete.

Aufruf:  python planetary/check_targets.py planetary/targets.json
Ausgabe: FEHLER (muss behoben werden), WARNUNG (pruefen), Uebersicht welche Werte noch fehlen.
Exit-Code 1, wenn es Fehler gibt.
"""

import json
import math
import sys

SCHEMA = 2
FEATURES = {
    # Schluessel: (Einheit, Methode, erlaubter Bereich)
    "slope_p50": ("deg", "direct", (0, 90)),
    "slope_p90": ("deg", "direct", (0, 90)),
    "relief": ("m", "direct", (0, 30000)),
    "albedo": ("1", "quantile", (0, 1)),
    "thermal_inertia": ("J m-2 K-1 s-1/2", "quantile", (0, 5000)),
    "dust_opacity": ("1", "quantile", (0, 20)),
    "dust_storm_days": ("d/yr", "quantile", (0, 700)),
    "surface_temp_mean": ("K", "direction", (20, 400)),
    "surface_temp_min": ("K", "direction", (10, 400)),
    "diurnal_range": ("K", "direction", (0, 400)),
    "pressure": ("hPa", "direction", (0, 2000)),
    "wind_mean": ("m/s", "direction", (0, 100)),
    "precip": ("mm/yr", "direction", (0, 20000)),
    "humidity": ("g/kg", "direction", (0, 50)),
    "ndvi": ("1", "direction", (-1, 1)),
    "ground_ice": ("1", "direction", (0, 1)),
    "sun_elevation_max": ("deg", "direction", (0, 90)),
}
TERRAIN = {"slope_p50", "slope_p90", "relief"}
PIXEL = {"Moon": 100, "Mars": 463}
RADIUS_KM = {"Moon": 1737.4, "Mars": 3389.5}
import re
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")  # freie Ziel-IDs (Plan, Aenderung 14.11. 18:30)
BODIES = {"Moon", "Mars"}
SIZE_KM = (5, 30)  # Seitenlaenge des Zielpolygons
COORD_QUALITY = {"verified", "approx", "unverified"}
TARGET_FIELDS = {"body", "name", "category", "center_lat", "center_lon", "coord_quality", "site_source",
                 "region_geojson", "region_notes", "features"}
FIELDS = {"value", "p10", "p90", "unit", "pixel_m", "body_percentile", "source", "reliability", "notes"}
RELIABILITY = {"A", "B", "C"}

errors, warnings = [], []
err = errors.append
warn = warnings.append


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def check_polygon(where, g, body):
    if g is None:
        warn(f"{where} region_geojson fehlt noch (Polygon des Zielorts, 10-20 km)")
        return
    if not isinstance(g, dict) or g.get("type") != "Polygon":
        err(f"{where} region_geojson muss ein GeoJSON-Objekt mit type 'Polygon' sein")
        return
    try:
        ring = g["coordinates"][0]
        pts = [(float(p[0]), float(p[1])) for p in ring]
    except (KeyError, IndexError, TypeError, ValueError):
        err(f"{where} region_geojson.coordinates muss [[[lon, lat], ...]] sein")
        return
    if len(pts) < 4 or pts[0] != pts[-1]:
        err(f"{where} Polygon-Ring braucht mindestens 4 Punkte und muss geschlossen sein (erster = letzter)")
    if any(not 0 <= lo <= 360 for lo, _ in pts):
        err(f"{where} Polygon-Laengen muessen Ost 0..360 sein (Konvention im Plan)")
    if any(not -90 <= la <= 90 for _, la in pts):
        err(f"{where} Polygon-Breiten ausserhalb -90..90 (Reihenfolge ist [Laenge, Breite])")
        return
    # Ausdehnung grob in km (Nord-Sued und Ost-West ueber die Mittelbreite)
    lats = [la for _, la in pts]
    lons = [lo for lo, _ in pts]
    r = RADIUS_KM.get(body)
    if not r:
        return
    ns = math.radians(max(lats) - min(lats)) * r
    dlon = max(lons) - min(lons)
    dlon = min(dlon, 360 - dlon)
    ew = math.radians(dlon) * r * math.cos(math.radians(sum(lats) / len(lats)))
    if abs(sum(lats) / len(lats)) > 85:
        ew = ns  # nahe dem Pol ist die Laengenausdehnung nicht aussagekraeftig
    lo_km, hi_km = SIZE_KM
    size = max(ns, ew)
    if not lo_km <= size <= hi_km:
        err(f"{where} Polygon ist ca. {ns:.1f} x {ew:.1f} km; erwartet {lo_km}-{hi_km} km (Plan, Abschnitt 3)")


def main(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"Datei nicht gefunden: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"FEHLER: Kein gueltiges JSON ({e}).")

    if data.get("schema_version") != SCHEMA:
        err(f"schema_version muss {SCHEMA} sein (aktuelle Vorlage verwenden)")
    targets = data.get("targets")
    if not isinstance(targets, dict) or not targets:
        err("'targets' fehlt oder ist leer")
        return report({})

    summary = {}
    for tid, t in targets.items():
        where = f"[{tid}]"
        if not ID_PATTERN.match(tid):
            err(f"{where} Ziel-ID nur Kleinbuchstaben, Ziffern, _ (2-41 Zeichen)")
            continue
        extra = set(t) - TARGET_FIELDS
        if extra:
            err(f"{where} unbekannte Felder {sorted(extra)}")
        body = t.get("body")
        if body not in BODIES:
            err(f"{where} body muss Moon oder Mars sein, ist '{body}'")
        cq = t.get("coord_quality")
        if cq is not None and cq not in COORD_QUALITY:
            err(f"{where} coord_quality muss verified, approx oder unverified sein")
        elif cq in ("approx", "unverified"):
            warn(f"{where} Koordinaten {cq}: Ergebnis nur als Naeherung verwenden")
        lat, lon = t.get("center_lat"), t.get("center_lon")
        if not num(lat) or not -90 <= lat <= 90:
            err(f"{where} center_lat fehlt oder liegt ausserhalb -90..90")
        if not num(lon) or not 0 <= lon <= 360:
            err(f"{where} center_lon fehlt oder liegt nicht in Ost 0..360")
        check_polygon(where, t.get("region_geojson"), body)

        feats = t.get("features", {})
        filled, missing = [], []
        for key, f in feats.items():
            w = f"{where} {key}:"
            if key not in FEATURES:
                err(f"{w} unbekannter Merkmalsschluessel. Erlaubt: {', '.join(FEATURES)}")
                continue
            unit, method, (lo, hi) = FEATURES[key]
            extra = set(f) - FIELDS
            if extra:
                err(f"{w} unbekannte Felder {sorted(extra)}")
            if f.get("unit") != unit:
                err(f"{w} unit muss '{unit}' sein, ist '{f.get('unit')}'")
            if key in TERRAIN and f.get("pixel_m") != PIXEL.get(body):
                err(f"{w} pixel_m muss {PIXEL.get(body)} sein ({body}, Plan Abschnitt 4)")
            v = f.get("value")
            if v is None:
                missing.append(key)
                continue
            if not num(v):
                err(f"{w} value muss eine Zahl oder null sein")
                continue
            if not lo <= v <= hi:
                err(f"{w} value {v} ausserhalb des plausiblen Bereichs {lo}..{hi} {unit}")
            src = str(f.get("source", "")).strip()
            if not src:
                err(f"{w} value gesetzt, aber source leer. Quelle angeben oder value auf null setzen")
            rel = f.get("reliability")
            if rel is None:
                err(f"{w} value gesetzt, aber reliability fehlt (A, B oder C, siehe ZIELSIGNATUREN.md)")
            elif rel not in RELIABILITY:
                err(f"{w} reliability muss A, B oder C sein, ist '{rel}'")
            if "Quelle offen" in src:
                warn(f"{w} Wert aus pipeline.py vorbelegt, Quelle noch offen")
            if key in TERRAIN and "terrain.py" not in src + str(f.get("notes", "")):
                warn(f"{w} in source/notes ist nicht vermerkt, dass common/terrain.py benutzt wurde")
            p10, p90 = f.get("p10"), f.get("p90")
            if (p10 is None) != (p90 is None):
                err(f"{w} p10 und p90 nur gemeinsam angeben")
            elif p10 is not None:
                if not (num(p10) and num(p90)):
                    err(f"{w} p10/p90 muessen Zahlen sein")
                elif not p10 <= v <= p90:
                    err(f"{w} erwartet p10 <= value <= p90, ist {p10} / {v} / {p90}")
            if method == "quantile":
                bp = f.get("body_percentile")
                if not num(bp) or not 0 <= bp <= 1:
                    err(f"{w} Methode 'quantile' braucht body_percentile zwischen 0 und 1 "
                        f"(flaechengewichtet ueber den ganzen Himmelskoerper)")
            filled.append(key)
        summary[tid] = (filled, missing)
    return report(summary)


def report(summary):
    for tid, (filled, missing) in summary.items():
        print(f"{tid:28s} {len(filled):2d} Werte gesetzt, {len(missing):2d} offen"
              + (f": {', '.join(missing)}" if missing else ""))
    print()
    for m in errors:
        print("FEHLER  ", m)
    for m in warnings:
        print("WARNUNG ", m)
    print(f"\n{len(errors)} Fehler, {len(warnings)} Warnungen")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Aufruf: python planetary/check_targets.py planetary/targets.json")
    sys.exit(main(sys.argv[1]))
