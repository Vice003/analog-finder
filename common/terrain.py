"""
Gemeinsame Gelaendeberechnung fuer Erde, Mond und Mars (VERARBEITUNGSPLAN.md, Abschnitt 4).
Alle Teams benutzen diese Funktionen, damit Neigung und Relief auf allen Koerpern gleich berechnet werden.
Aenderungen nur nach Absprache im Team.

Festlegungen:
  Pixelgroesse   Mond-Vergleiche 100 m, Mars-Vergleiche 463 m (MOLA). Das DEM wird vorher auf diese
                 Pixelgroesse gebracht (resample).
  Neigung        zentrale Differenzen (numpy.gradient) auf dem neu abgetasteten DEM, in Grad.
  slope_p50/p90  Median und 90-%-Perzentil der Neigung aller Pixel im Gebiet.
  relief         Gebiet in 5 x 5 km grosse Fenster teilen, je Fenster Hoehe P95 - P5, davon der Median.
                 Auf der Erde ist das Gebiet eine 0,05-Grad-Zelle (ca. 5 km), also genau ein Fenster.

Eingabe: DEM als 2D-Array in Metern, NaN = keine Daten, mit Pixelabstand in Metern (dx Ost-West, dy Nord-Sued).
Fuer Gitter in Breite/Laenge liefert pixel_size_latlon() die Abstaende (dx haengt von der Breite ab).

Beispiel (Mars, MOLA-Ausschnitt um Jezero):
    from common.terrain import terrain_stats
    stats = terrain_stats(dem_m, dx=463.0, dy=463.0, pixel_m=463.0)
    # {'slope_p50': ..., 'slope_p90': ..., 'relief': ..., 'n_pixels': ..., 'n_windows': ...}

Selbsttest: python common/terrain.py
"""

import numpy as np

RADIUS_M = {"Earth": 6_371_000.0, "Moon": 1_737_400.0, "Mars": 3_389_500.0}
PIXEL_M = {"Moon": 100.0, "Mars": 463.0}   # Festlegung aus dem Plan
WINDOW_M = 5_000.0                          # Relief-Fenster


def pixel_size_latlon(lat_deg, dlat_deg, dlon_deg, body):
    """Pixelabstand in Metern fuer ein Gitter in Breite/Laenge. lat_deg: Breite je Zeile (Array)."""
    r = RADIUS_M[body]
    dy = np.radians(abs(dlat_deg)) * r
    dx = np.radians(abs(dlon_deg)) * r * np.cos(np.radians(np.asarray(lat_deg, float)))
    return dx, dy


def resample(dem, dx, dy, pixel_m):
    """
    Bringt das DEM auf quadratische Pixel der Groesse pixel_m (Blockmittel beim Vergroebern, bilinear beim Verfeinern).
    dx darf ein Array je Zeile sein (Breite/Laenge-Gitter); dann wird zeilenweise in Ost-West-Richtung abgetastet.
    """
    from scipy.ndimage import zoom

    dem = np.asarray(dem, float)
    dx = np.broadcast_to(np.asarray(dx, float).reshape(-1, 1) if np.ndim(dx) else dx, (dem.shape[0], 1))
    # Nord-Sued
    fy = dy / pixel_m
    out = _scale_axis(dem, fy, axis=0, zoom=zoom)
    # Ost-West, je Zeile eigener Faktor (Breite/Laenge-Gitter); Zeilen gleicher Laenge erzwingen
    rows_dx = np.interp(np.linspace(0, dem.shape[0] - 1, out.shape[0]), np.arange(dem.shape[0]), dx[:, 0])
    width_m = np.nanmean(rows_dx) * dem.shape[1]
    nx = max(int(round(width_m / pixel_m)), 2)
    res = np.empty((out.shape[0], nx))
    for i in range(out.shape[0]):
        src_x = np.arange(out.shape[1]) * rows_dx[i]
        dst_x = (np.arange(nx) + 0.5) * pixel_m
        row = out[i]
        k = int(round(pixel_m / rows_dx[i]))
        if k > 1:  # beim Vergroebern erst ueber die Zielpixelbreite mitteln, sonst nur abgetastet (Rauschen)
            row = _box(row[None, :], k, axis=1)[0]
        ok = ~np.isnan(row)
        # Zielpixel am Rand ragen bis zu einem Pixel ueber den letzten Messwert hinaus: Randwert verwenden
        # (frueher NaN, dadurch fehlten Randzellen jeder Kachel; Aenderung 14.11. 19:00)
        res[i] = np.interp(dst_x, src_x[ok], row[ok]) if ok.sum() > 1 else np.nan
    return res


def _box(a, size, axis):
    """Gleitendes Mittel ueber `size` Pixel entlang einer Achse, NaN-tolerant."""
    from scipy.ndimage import uniform_filter1d

    valid = np.isfinite(a)
    num = uniform_filter1d(np.where(valid, a, 0.0), size, axis=axis, mode="nearest")
    den = uniform_filter1d(valid.astype(float), size, axis=axis, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def _scale_axis(a, f, axis, zoom):
    """Skaliert eine Achse um Faktor f (f < 1: vergroebern per Blockmittel, f > 1: bilinear verfeinern)."""
    if abs(f - 1) < 1e-6:
        return a
    if f < 1:
        k = int(round(1 / f))
        if k > 1 and abs(1 / f - k) < 0.05:  # ganzzahliger Faktor: exaktes Blockmittel
            n = (a.shape[axis] // k) * k
            a = np.take(a, np.arange(n), axis=axis)
            shp = list(a.shape)
            shp[axis:axis + 1] = [n // k, k]
            with np.errstate(invalid="ignore"):
                return np.nanmean(a.reshape(shp), axis=axis + 1)
    if f < 1:  # nicht ganzzahlig vergroebern: erst mitteln, dann abtasten
        a = _box(a, int(round(1 / f)), axis)
    factors = [1.0, 1.0]
    factors[axis] = f
    filled = np.where(np.isnan(a), np.nanmean(a), a)
    out = zoom(filled, factors, order=1)
    mask = zoom(np.isnan(a).astype(float), factors, order=0) > 0.5
    out[mask] = np.nan
    return out


def slope_deg(dem, pixel_m):
    """Neigung in Grad auf einem DEM mit quadratischen Pixeln (zentrale Differenzen)."""
    gy, gx = np.gradient(np.asarray(dem, float), pixel_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def terrain_stats(dem, dx, dy, pixel_m, window_m=WINDOW_M):
    """
    Gelaendekennwerte eines Gebiets nach der Festlegung im Plan.
    dem: Ausschnitt (Zielpolygon bzw. Erdzelle), Meter. dx/dy: Pixelabstand des Eingangs-DEM in Metern.
    pixel_m: Ziel-Pixelgroesse (100 Mond, 463 Mars). Rueckgabe: dict.
    """
    z = resample(dem, dx, dy, pixel_m)
    s = slope_deg(z, pixel_m)
    s = s[~np.isnan(s)]
    w = max(int(round(window_m / pixel_m)), 2)
    reliefs = []
    for i in range(0, z.shape[0] - w + 1, w):
        for j in range(0, z.shape[1] - w + 1, w):
            win = z[i:i + w, j:j + w]
            if np.isfinite(win).mean() >= 0.5:
                p5, p95 = np.nanpercentile(win, [5, 95])
                reliefs.append(p95 - p5)
    if not reliefs and np.isfinite(z).any():  # Gebiet kleiner als ein Fenster: ganzes Gebiet nehmen
        p5, p95 = np.nanpercentile(z, [5, 95])
        reliefs.append(p95 - p5)
    return dict(
        slope_p50=float(np.percentile(s, 50)) if s.size else np.nan,
        slope_p90=float(np.percentile(s, 90)) if s.size else np.nan,
        relief=float(np.median(reliefs)) if reliefs else np.nan,
        n_pixels=int(s.size),
        n_windows=len(reliefs),
        pixel_m=pixel_m,
    )


if __name__ == "__main__":
    # Selbsttest 1: schiefe Ebene mit 10 Grad, 20 x 20 km, Eingang 50-m-Pixel, Ziel 463 m
    n, px = 400, 50.0
    x = np.arange(n) * px
    plane = np.tan(np.radians(10)) * x[None, :] * np.ones((n, 1))
    st = terrain_stats(plane, dx=px, dy=px, pixel_m=463.0)
    print("Ebene 10 Grad   ", {k: round(v, 2) if isinstance(v, float) else v for k, v in st.items()})
    assert abs(st["slope_p50"] - 10) < 0.2, st
    # Relief einer Ebene im 5-km-Fenster: tan(10)*5 km * 0,9 (P5..P95) ~ 790 m
    assert 700 < st["relief"] < 900, st

    # Selbsttest 2: flache Flaeche mit Rauschen -> Neigung nahe 0, Relief klein
    rng = np.random.default_rng(0)
    flat = rng.normal(0, 0.5, (400, 400))
    st = terrain_stats(flat, dx=px, dy=px, pixel_m=100.0)
    print("flach + Rauschen", {k: round(v, 2) if isinstance(v, float) else v for k, v in st.items()})
    assert st["slope_p90"] < 1 and st["relief"] < 2, st

    # Selbsttest 3: Breite/Laenge-Gitter (Mars, 1/128 Grad) bei 60 Grad Breite, Ebene 5 Grad nach Osten
    lat = np.linspace(60.5, 59.5, 128)
    dx, dy = pixel_size_latlon(lat, 1 / 128, 1 / 128, "Mars")
    xs = np.cumsum(np.ones((128, 128)) * dx[:, None], axis=1)
    dem = np.tan(np.radians(5)) * xs
    st = terrain_stats(dem, dx=dx, dy=dy, pixel_m=463.0)
    print("Mars 60 Grad 5° ", {k: round(v, 2) if isinstance(v, float) else v for k, v in st.items()})
    assert abs(st["slope_p50"] - 5) < 0.3, st

    # Selbsttest 4: Vergroebern muss mitteln. Ebene 3 Grad + kleinraeumiges Rauschen (90-m-Pixel, Ziel 463 m,
    # krummer Faktor). Ohne Mittelung bliebe das Rauschen in der Neigung stehen.
    n, px = 600, 90.0
    x = np.arange(n) * px
    noisy = np.tan(np.radians(3)) * x[None, :] + rng.normal(0, 30, (n, n))
    st = terrain_stats(noisy, dx=93.0, dy=px, pixel_m=463.0)
    print("Rauschen 463 m  ", {k: round(v, 2) if isinstance(v, float) else v for k, v in st.items()})
    assert abs(st["slope_p50"] - 3) < 0.5, st
    print("Selbsttest bestanden")
