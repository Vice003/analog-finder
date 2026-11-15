"""
Robustness of the top sites: how often does a site stay in the top 20 when the dimension weights change?

For each target, N random weightings are drawn: every dimension weight of the target profile is multiplied by a
factor drawn uniformly from [1 - SPREAD, 1 + SPREAD]. For each draw the top 20 (at least 200 km apart) is rebuilt
from the candidate pool (results/pool.npz), exactly as the web app does. A site counts as "kept" in a draw if the
top 20 of that draw contains it or a site within KEEP_KM of it (neighbouring cells of one area swap places easily).

  python scoring/robustness.py   -> results/robustness.json  {target: {"lat,lon": share 0..1}}
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
N_DRAWS, SPREAD, N_TOP, MIN_KM, KEEP_KM, SEED = 1000, 0.5, 20, 200.0, 50.0, 42


def haversine_matrix(lat, lon):
    la, lo = np.radians(lat)[:, None], np.radians(lon)[:, None]
    a = np.sin((la - la.T) / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin((lo - lo.T) / 2) ** 2
    return 12742.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def top_sites(order, dist, n=N_TOP, min_km=MIN_KM):
    picked = []
    for j in order:
        if all(dist[j, k] >= min_km for k in picked):
            picked.append(j)
            if len(picked) == n:
                break
    return picked


def main():
    import sys
    sys.path.insert(0, str(ROOT / "scoring"))
    from target_scoring import load_targets, profile_for, POOL_DIMS
    from categories import TARGETS as PROFILES
    Z = np.load(ROOT / "results" / "pool.npz")
    R = json.load(open(ROOT / "results" / "top_sites.json", encoding="utf-8"))
    tpath = ROOT.parent / "NASA-Challenge" / "planetary" / "targets.json"
    if not tpath.exists():
        tpath = ROOT / "planetary" / "targets.json"
    T = load_targets(tpath)
    rng = np.random.default_rng(SEED)
    out = {}
    for tid in R["targets"]:
        if f"{tid}/lat" not in Z.files:
            continue
        lat, lon = Z[f"{tid}/lat"].astype(float), Z[f"{tid}/lon"].astype(float)
        dims = Z[f"{tid}/dims"].astype(float)
        conf = Z[f"{tid}/conf"].astype(float)
        avail = (dims != 255) & (conf != 255)
        D, C = np.where(avail, dims / 254, 0), np.where(avail, conf / 254, 0)
        w0 = np.array([PROFILES[profile_for(T[tid])]["weights"].get(d, 0) for d in POOL_DIMS], float)
        dist = haversine_matrix(lat, lon)
        near = dist < KEEP_KM
        kept = np.zeros(len(lat))
        for _ in range(N_DRAWS):
            w = w0 * rng.uniform(1 - SPREAD, 1 + SPREAD, size=len(w0))
            wc = C * w  # cells x dims
            den = wc.sum(1)
            score = np.where(den > 0, (wc * D).sum(1) / np.where(den > 0, den, 1), -1)
            picked = top_sites(np.argsort(-score), dist)
            kept += near[:, picked].any(axis=1)
        share = kept / N_DRAWS
        key = lambda a, b: f"{a:.3f},{b:.3f}"
        idx = {key(a, b): i for i, (a, b) in enumerate(zip(lat, lon))}
        res = {}
        lists = [R["targets"][tid].get(k, []) for k in ("top", "excl_china", "by_continent", "by_continent_excl_china")]
        for x in (x for lst in lists for x in lst):
            k = key(x["lat"], x["lon"])
            if k in idx:
                res[k] = round(float(share[idx[k]]), 3)
        out[tid] = res
        top = R["targets"][tid]["top"]
        print(f"{tid:26s} Top 5 robust: " + ", ".join(f"{res.get(key(x['lat'], x['lon']), float('nan')):.0%}" for x in top[:5]))
    p = ROOT / "results" / "robustness.json"
    json.dump(dict(meta=dict(draws=N_DRAWS, spread=SPREAD, n_top=N_TOP, min_km=MIN_KM, keep_km=KEEP_KM, seed=SEED),
                   targets=out), open(p, "w", encoding="utf-8"), indent=1)
    print("->", p)


if __name__ == "__main__":
    main()
