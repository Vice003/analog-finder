"""
Adds every site of the precomputed lists (top 20, without China, best per continent) to the candidate pool
(results/pool.npz) if it is missing. Because of the 200 km rule, a list site can have cell rank 1,000+ and so fall
outside the pool's top 600; without it, a class filter in the web app would drop a site that is in the default list.

Dimension scores, feature scores and Earth values come from results/top_sites.json. The dimension confidence is not
stored there; the median confidence of the pool cells for that dimension is used (it only varies where features
are missing). Idempotent: sites already in the pool are skipped.

  python scoring/augment_pool.py
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def main():
    import sys
    sys.path.insert(0, str(ROOT / "scoring"))
    from categories import ENV_CLASSES, KNOWN_ANALOGS
    p = ROOT / "results" / "pool.npz"
    Z = dict(np.load(p))
    R = json.load(open(ROOT / "results" / "top_sites.json", encoding="utf-8"))
    dims_order = Z["_dims"].tolist()
    continents = Z["_continents"].tolist()
    cls_ids = [c["id"] for c in ENV_CLASSES]
    kn_names = [k[0] for k in KNOWN_ANALOGS]
    added = 0
    for tid, t in R["targets"].items():
        if f"{tid}/lat" not in Z:
            continue
        g = lambda k: Z[f"{tid}/{k}"]
        key = lambda a, b: f"{float(a):.3f},{float(b):.3f}"
        have = {key(a, b) for a, b in zip(g("lat"), g("lon"))}
        fkeys = g("fkeys").tolist()
        conf_med = np.array([np.median(c[c != 255]) if (c != 255).any() else 255 for c in g("conf").T], np.uint8)
        rows = []
        for lst in ("top", "excl_china", "by_continent", "by_continent_excl_china"):
            for x in t.get(lst, []):
                k = key(x["lat"], x["lon"])
                if k in have:
                    continue
                have.add(k)
                rows.append(x)
        if not rows:
            continue
        q8 = lambda v: 255 if v is None else int(np.clip(round(v * 254), 0, 254))
        new = dict(
            lat=np.array([x["lat"] for x in rows], np.float32), lon=np.array([x["lon"] for x in rows], np.float32),
            total=np.array([x["score"] for x in rows], np.float32), rank=np.array([x["cell_rank"] for x in rows], np.int32),
            cov=np.array([q8(x["coverage"]) for x in rows], np.uint8),
            dims=np.array([[q8(x["dims"].get(d)) for d in dims_order] for x in rows], np.uint8),
            conf=np.array([[conf_med[i] if x["dims"].get(d) is not None else 255 for i, d in enumerate(dims_order)] for x in rows], np.uint8),
            fs=np.array([[q8({f["key"]: f["score"] for f in x["features"]}.get(k)) for k in fkeys] for x in rows], np.uint8).reshape(len(rows), len(fkeys)),
            fv=np.array([[np.nan if {f["key"]: f["earth"] for f in x["features"]}.get(k) is None else {f["key"]: f["earth"] for f in x["features"]}[k]
                          for k in fkeys] for x in rows], np.float16).reshape(len(rows), len(fkeys)),
            cls=np.array([cls_ids.index(x["env_class"]) for x in rows], np.uint8),
            iso=np.array([x.get("country_iso") or "" for x in rows]),
            cont=np.array([continents.index(x["continent"]) if x.get("continent") in continents else 255 for x in rows], np.uint8),
            known=np.array([kn_names.index(x["known_analog"]) if x.get("known_analog") in kn_names else -1 for x in rows], np.int16))
        for k, v in new.items():
            Z[f"{tid}/{k}"] = np.concatenate([Z[f"{tid}/{k}"], v])
        added += len(rows)
        print(f"{tid:26s} +{len(rows)}")
    np.savez_compressed(p, **Z)
    print(f"{added} Listen-Orte ergaenzt -> {p}")


if __name__ == "__main__":
    main()
