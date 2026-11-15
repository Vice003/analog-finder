"""
Area-weighted percentile of a target value on its own body (Moon, Mars, Earth).
Needed for every feature with method "quantile" (planetary/ZIELSIGNATUREN.md, field `body_percentile`).
Shared code (VERARBEITUNGSPLAN.md): every team uses this function so the percentile is computed the same way.

Question it answers: "Which fraction of the body's surface has a LOWER value than the target site?"
Example: body_percentile = 0.40 means 40 % of the Mars surface has lower thermal inertia than Jezero.

Inputs
  values   global map as 2D array (NaN = no data)
  weights  pixel area. For lat/lon grids use latlon_weights(); for equal-area grids use 1;
           for polar stereographic grids pass the pixel area map of the projection.
  target   the target site value (median over the site polygon, the same number as `value` in targets.json)

Example (TES thermal inertia, global lat/lon grid with 20 pixels per degree):
    from common.body_percentile import body_percentile, latlon_weights
    w = latlon_weights(ti.shape[0])                 # rows from +90 to -90
    p = body_percentile(ti, w, target=ti_jezero)    # -> e.g. 0.41

Self-test: python common/body_percentile.py
"""

import numpy as np


def latlon_weights(n_rows, lat_top=90.0, lat_bottom=-90.0):
    """Area weight per row for a regular lat/lon grid (cos of the row-centre latitude), shape (n_rows, 1)."""
    edges = np.linspace(lat_top, lat_bottom, n_rows + 1)
    centres = (edges[:-1] + edges[1:]) / 2
    return np.cos(np.radians(centres)).reshape(-1, 1)


def body_percentile(values, weights, target):
    """Area-weighted share of valid pixels with a value below `target`, 0..1. Ties count half."""
    v = np.asarray(values, float)
    w = np.broadcast_to(np.asarray(weights, float), v.shape)
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if not ok.any():
        raise ValueError("no valid pixels")
    v, w = v[ok], w[ok]
    below = w[v < target].sum()
    equal = w[v == target].sum()
    return float((below + equal / 2) / w.sum())


if __name__ == "__main__":
    # 1) uniform weights: 0..99 -> value 25 has 25 below and one tie -> 0.255
    a = np.arange(100, dtype=float).reshape(10, 10)
    p = body_percentile(a, 1.0, 25)
    print("uniform        ", round(p, 3))
    assert abs(p - 0.255) < 1e-9

    # 2) lat/lon weighting: high values only near the poles must count little
    n = 180
    grid = np.zeros((n, 360))
    grid[:10] = 10      # polar rows (80-90 N) with high values
    w = latlon_weights(n)
    p_unweighted = body_percentile(grid, 1.0, 5)
    p_weighted = body_percentile(grid, w, 5)
    print("polar cap      ", "unweighted", round(p_unweighted, 3), "weighted", round(p_weighted, 3))
    # area of the cap 80-90 N is (1 - sin 80) / 2 = 0.76 % of the sphere -> 99.2 % of the area lies below 5
    assert abs(p_weighted - (1 - (1 - np.sin(np.radians(80))) / 2)) < 2e-3 and p_weighted > p_unweighted

    # 3) NaN is ignored
    b = a.copy(); b[0, :] = np.nan
    print("with NaN       ", round(body_percentile(b, 1.0, 50), 3))
    print("self-test passed")
