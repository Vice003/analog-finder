"""
Flags (categories.FLAGS) for every cell of the candidate pool (results/pool.npz), so that the web app can filter
in-browser rankings by property.

The flags are computed on the FULL 0.05 degree Earth table (the "staubquelle" rule uses a quantile over all land
cells), then looked up per pool cell by grid index. Result: one uint16 bitmask per pool cell, bit i = i-th key of
FLAGS.

  python scoring/pool_flags.py  -> results/pool_flags.npz  {"<target>": uint16[n_pool], "_flags": flag ids}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "data" / "earth" / "earth_features_005deg.parquet"
RES = 0.05
NX = int(round(360 / RES))

# every column the FLAGS rules read (directly or via _albedo, _pressure, _barren)
COLS = ["lat", "lon", "DUEM_mean", "dust_storm_days", "wind_storm_days", "SPEED_mean", "freeze_thaw_months",
        "lst_abs_min", "PS_hpa", "pressure_est_hpa", "albedo_snowfree", "albedo_sw_mean", "ndvi_peak_mean",
        "barren_pct", "flat_frac", "slope_p90"]


def grid_index(lat, lon):
    iy = np.round((90 - np.asarray(lat, float)) / RES - 0.5).astype(np.int64)
    ix = np.round((np.asarray(lon, float) + 180) / RES - 0.5).astype(np.int64)
    return iy * NX + ix


def main():
    import sys
    sys.path.insert(0, str(ROOT / "scoring"))
    from categories import FLAGS, flags

    have = set(pq.read_schema(TABLE).names)
    cols = [c for c in COLS if c in have]
    missing = [c for c in COLS if c not in have]
    if missing:
        print("Missing columns (rules fall back to NaN):", missing)
    df = pd.read_parquet(TABLE, columns=cols)
    print(f"Table: {len(df):,} cells, {len(cols)} columns")
    F = flags(df)
    ids = list(FLAGS)
    assert len(ids) <= 16
    mask = np.zeros(len(df), np.uint16)
    for b, k in enumerate(ids):
        mask |= (F[f"flag_{k}"].to_numpy(bool).astype(np.uint16) << b)
    gi = grid_index(df["lat"].to_numpy(), df["lon"].to_numpy())
    del df, F
    order = np.argsort(gi)
    gi_sorted = gi[order]
    assert (np.diff(gi_sorted) > 0).all(), "duplicate grid cells in table"

    Z = np.load(ROOT / "results" / "pool.npz")
    targets = sorted({k.split("/")[0] for k in Z.files if "/" in k and k.endswith("/lat")})
    out = {"_flags": np.array(ids)}
    n_all = n_hit = 0
    counts = np.zeros(len(ids), np.int64)
    for tid in targets:
        g = grid_index(Z[f"{tid}/lat"], Z[f"{tid}/lon"])
        pos = np.clip(np.searchsorted(gi_sorted, g), 0, len(gi_sorted) - 1)
        hit = gi_sorted[pos] == g
        m = np.where(hit, mask[order[pos]], 0).astype(np.uint16)
        out[tid] = m
        n_all += len(g)
        n_hit += int(hit.sum())
        counts += np.array([int((m >> b & 1).sum()) for b in range(len(ids))], np.int64)
        if not hit.all():
            print(f"  {tid}: {int((~hit).sum())} of {len(g)} pool cells not found in table")
    print(f"Matched {n_hit:,} of {n_all:,} pool cells ({n_hit / n_all:.2%}) over {len(targets)} targets")
    for k, c in zip(ids, counts):
        print(f"  {k:20s} {c:6d} ({c / n_all:.1%})")
    p = ROOT / "results" / "pool_flags.npz"
    np.savez_compressed(p, **out)
    print("->", p)


if __name__ == "__main__":
    main()
