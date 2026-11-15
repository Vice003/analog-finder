"""
Re-applies the list of known analogs (categories.KNOWN_ANALOGS) to the results without re-running the scoring:
known_analog of every list site in results/top_sites.json, n_new_in_top per target, and the known index of every
pool cell in results/pool.npz. Needed after adding entries to KNOWN_ANALOGS (the label depends only on location).

  python scoring/relabel_known.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scoring"))
from categories import KNOWN_ANALOGS, mark_known  # noqa: E402


def main():
    names = [k[0] for k in KNOWN_ANALOGS]
    rp = ROOT / "results" / "top_sites.json"
    R = json.load(open(rp, encoding="utf-8"))
    changed = 0
    for tid, t in R["targets"].items():
        for lst in ("top", "excl_china", "by_continent", "by_continent_excl_china"):
            xs = t.get(lst, [])
            if not xs:
                continue
            kn = mark_known(pd.DataFrame({"lat": [x["lat"] for x in xs], "lon": [x["lon"] for x in xs]}))
            for x, k in zip(xs, kn):
                k = k if isinstance(k, str) else None
                if k != x.get("known_analog"):
                    changed += 1
                x["known_analog"] = k
        t["n_new_in_top"] = sum(x["known_analog"] is None for x in t["top"])
    json.dump(R, open(rp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    zp = ROOT / "results" / "pool.npz"
    Z = dict(np.load(zp))
    Z["_known"] = np.array(names)
    for tid in R["targets"]:
        if f"{tid}/lat" not in Z:
            continue
        kn = mark_known(pd.DataFrame({"lat": Z[f"{tid}/lat"].astype(float), "lon": Z[f"{tid}/lon"].astype(float)}))
        Z[f"{tid}/known"] = np.array([names.index(k) if isinstance(k, str) else -1 for k in kn], np.int16)
    np.savez_compressed(zp, **Z)
    print(f"{changed} Listen-Eintraege neu markiert; Pool aktualisiert ({len(names)} bekannte Analoga)")


if __name__ == "__main__":
    main()
