"""
Bewertet Erdzellen gegen die gemessenen Zielsignaturen aus planetary/targets.json
(Spezifikation: planetary/ZIELSIGNATUREN.md).

Je Merkmal eine von drei Methoden:
  direct     S = 1 - |Erdwert - Zielwert| / Spanne, Spanne = Abstand vom Zielwert zur unaehnlichsten Erde
             (2.-98. Perzentil, flaechengewichtet). Wie scripts/rank.py im Team-Repo.
  quantile   dasselbe auf Perzentilen: Erd-Perzentil gegen body_percentile des Ziels.
  direction  flaechengewichtetes Perzentil in Richtung des Zielwerts (die Erde erreicht ihn nie).
Merkmale ohne Zielwert (null) oder ohne passendes Erdmerkmal werden uebersprungen und gemeldet.

Benutzung:
    from scoring.target_scoring import load_targets, score_target
    T = load_targets("planetary/targets.json")
    s = score_target(df, T["jezero"])       # dim_*, feat_*, total, coverage, best_dim, worst_dim

Aufruf:  python scoring/target_scoring.py [pfad/targets.json] [tabelle.parquet]
         ohne Pfad: ../planetary/targets.json, ersatzweise die Vorlage daneben
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categories import TARGETS as PROFILES, _weighted_pct, classify, mark_known, top_sites, ENV_CLASSES, KNOWN_ANALOGS  # noqa: E402

def profile_for(target):
    """Gewichtsprofil aus categories.py nach Koerper und Kategorie (freie Ziel-IDs, Aenderung 14.11. 18:30)."""
    if target.get("body") == "Moon":
        return "mond_suedpol"
    cat = (target.get("category") or "").lower()
    icy = "ice" in cat or "eis" in cat or abs(target.get("center_lat") or 0) >= 35
    return "mars_eis_mittelbreiten" if icy else "mars_aequatorial"

# Merkmal -> (Methode, Dimension, Erdspalte bzw. Funktion)
FEATURES = {
    "slope_p50":         ("direct",    "gelaende",    "baseline"),
    "slope_p90":         ("direct",    "gelaende",    "baseline"),
    "relief":            ("direct",    "gelaende",    "baseline"),
    # Albedo immer als Rang: LOLA 1064 nm bzw. OMEGA 1,08 um gegen MODIS breitbandig (verschiedene Groessen)
    "albedo":            ("quantile",  "oberflaeche", lambda d: d["albedo_snowfree"].fillna(d["albedo_sw_mean"])
                          if "albedo_snowfree" in d else d.get("albedo_sw_mean")),
    "thermal_inertia":   ("quantile",  "oberflaeche", "ati"),
    "dust_opacity":      ("quantile",  "staub_wind",  "DUEXTTAU_mean"),
    "dust_storm_days":   ("quantile",  "staub_wind",  "dust_storm_days"),
    "wind_mean":         ("direction", "staub_wind",  "SPEED_mean"),
    "surface_temp_mean": ("direction", "thermik",     "lst_mean"),
    "surface_temp_min":  ("direction", "thermik",     "lst_cold_mean"),
    "diurnal_range":     ("direction", "thermik",     "lst_diurnal_mean"),
    "pressure":          ("direction", "atmosphaere", lambda d: d["PS_hpa"] if "PS_hpa" in d else d.get("pressure_est_hpa")),
    "humidity":          ("direction", "atmosphaere", "QV2M_gkg"),
    "precip":            ("direction", "trockenheit", "precip_mm_yr"),
    "ndvi":              ("direction", "leben",       "ndvi_mean"),
    # wie scripts/pipeline.py: Eis-Proxy aus der Jahresmitteltemperatur (hier Oberflaeche statt Luft)
    "ground_ice":        ("direction", "eis_wasser",  lambda d: ((272.15 - d["lst_mean"]) / 7).clip(0, 1)
                          if "lst_mean" in d else None),
    # hoechster Sonnenstand aus Breite und Achsneigung. Methode Richtung (Plan, Korrektur 15):
    # die Erde erreicht die ca. 1,5 Grad am Mond-Suedpol nie (Minimum ca. 23,4 Grad an den Polen)
    "sun_elevation_max": ("direction", "beleuchtung", lambda d: np.minimum(90, 90 - d["lat"].abs() + 23.44)),
}
# Verlaesslichkeit als Gewicht (Skala aus docs/official_sources_audit.md, Branch Mars_and_Moon):
# Gewicht je Merkmal = Note des Zielwerts (reliability in targets.json) x Note des Erd-Gegenstuecks (unten).
MIN_COVERAGE = 0.8  # Anteil des Zielgewichts, den eine Erdzelle belegen muss, um ins Ranking zu kommen
REL_WEIGHT = {"A": 1.0, "B": 0.7, "C": 0.4}
REL_DEFAULT = "B"  # Zielwert ohne Angabe
EARTH_RELIABILITY = {  # Erdseite, nach Abschnitt 5 des Audits
    "slope_p50": "A", "slope_p90": "A", "relief": "A", "albedo": "A", "thermal_inertia": "B",
    "dust_opacity": "A", "dust_storm_days": "B", "wind_mean": "A", "surface_temp_mean": "A",
    "surface_temp_min": "A", "diurnal_range": "A", "pressure": "A", "humidity": "A", "precip": "A",
    "ndvi": "A", "ground_ice": "C",  # Temperatur-Proxy, bis die ESA-CCI-Permafrostkarte eingebaut ist
    "sun_elevation_max": "A",
}
# Gelaende: Erdspalte nach Pixelgroesse (Plan, Abschnitt 4), berechnet mit common/terrain.py
# durch earth/dem_baselines.py (100 m und 463 m). Fehlen die Spalten, wird das Merkmal uebersprungen.
TERRAIN_COLS = {
    ("slope_p50", 100): "slope_p50_100m", ("slope_p90", 100): "slope_p90_100m", ("relief", 100): "relief_100m",
    ("slope_p50", 463): "slope_p50_463m", ("slope_p90", 463): "slope_p90_463m", ("relief", 463): "relief_463m",
}
EXCLUDED_LC = {1, 2, 3, 4, 5, 12, 13, 14}  # Wald, Acker, Siedlung, Acker-Mosaik (IGBP), wie scripts/modis_landcover.py


def ranking_mask(df):
    """
    Zellen, die ins Ranking duerfen (Plan, Abschnitt 5 und Korrektur 8): kein Wasser (> 50 %), kein Eisschild,
    keine Zelle mit Wald/Acker/Siedlung als Hauptklasse.
    """
    c = lambda k: df[k] if k in df else pd.Series(np.nan, index=df.index)
    water = c("water_pct") > 50
    # Eis nur, wo es auch im waermsten Monat kalt bleibt: MODIS haelt Salzpfannen fuer Schnee (Uyuni)
    ice = ((c("snow_perm_frac") >= 0.8) | (c("snow_ice_pct") >= 60)) & (c("lst_warm_mean").fillna(0) < 280)
    lc = c("landcover").isin(EXCLUDED_LC)
    return ~(water | ice | lc)


def reference_mask(df):
    """Erd-Referenz fuer den Rang-Abgleich (Korrektur 7): vegetationsfreies, eisfreies Land."""
    from categories import _barren
    return ranking_mask(df) & _barren(df).fillna(False)


def load_targets(path):
    data = json.load(open(path, encoding="utf-8"))
    out = {}
    for tid, t in data["targets"].items():
        t = dict(t, id=tid)
        out[tid] = t
    return out


def _earth_values(df, key, feat):
    how = FEATURES[key][2]
    if how == "baseline":
        col = TERRAIN_COLS.get((key, int(feat.get("pixel_m") or 0)))  # Schema 2: pixel_m (100 Mond, 463 Mars)
        return (df[col] if col in df else None), col
    if callable(how):
        v = how(df)
        return (None if v is None else pd.Series(np.asarray(v, dtype="float64"), index=df.index)), "berechnet"
    return (df[how] if how in df else None), how


def _wquantile(x, w, qs):
    ok = x.notna().to_numpy()
    v, ww = x.to_numpy(dtype=np.float64)[ok], w.to_numpy(dtype=np.float64)[ok]  # 64 Bit, siehe _weighted_pct
    o = np.argsort(v)
    cw = np.cumsum(ww[o]); cw /= cw[-1]
    return [v[o][min(np.searchsorted(cw, q), len(v) - 1)] for q in qs]


def score_target(df, target, verbose=True):
    """Bewertung aller Zeilen von df fuer ein Ziel aus targets.json."""
    w = pd.Series(np.cos(np.radians(df["lat"].to_numpy())), index=df.index)
    prof = PROFILES[profile_for(target)]
    ref = reference_mask(df)
    # Ranking nur ueber vegetationsfreies Land (Kahl-Regel aus categories.py): sonst kamen fuer die Mond-Ziele
    # spaerlich bewachsene Tundrazellen nach oben (Stand 15.11.: 89 von 260 Mond-Treffern)
    rank_ok = ref
    out = pd.DataFrame(index=df.index)
    used, skipped, meta = [], [], []
    dims = {}
    for key, feat in target["features"].items():
        if key not in FEATURES:
            skipped.append((key, "unbekanntes Merkmal"))
            continue
        tv = feat.get("value")
        if tv is None:
            skipped.append((key, "kein Zielwert"))
            continue
        method, dim, _ = FEATURES[key]
        x, col = _earth_values(df, key, feat)
        if x is None:
            skipped.append((key, f"Erdmerkmal fehlt ({col})"))
            continue
        x = x.astype("float64")
        info = dict(key=key, method=method, dim=dim, col=col, target=tv, unit=feat.get("unit"),
                    body_percentile=feat.get("body_percentile"))
        pe = None
        if method == "direct":
            p2, p98 = _wquantile(x, w, [0.02, 0.98])
            span = max(abs(p2 - tv), abs(p98 - tv)) or 1e-9
            s = (1 - (x - tv).abs() / span).clip(0, 1)
            info["span"] = float(span)
        elif method == "quantile":
            bp = feat.get("body_percentile")
            if bp is None:
                skipped.append((key, "body_percentile fehlt"))
                continue
            # Perzentil relativ zur Erd-Referenz (vegetations- und eisfreies Land), flaechengewichtet
            xr, wr = x[ref & x.notna()], w[ref & x.notna()]
            if len(xr) < 100:
                skipped.append((key, "zu wenig Referenzzellen"))
                continue
            o = np.argsort(xr.to_numpy())
            xs, cw = xr.to_numpy(dtype=np.float64)[o], np.cumsum(wr.to_numpy(dtype=np.float64)[o])
            pe = pd.Series(np.interp(x.to_numpy(), xs, cw / cw[-1]), index=x.index).where(x.notna())
            s = (1 - (pe - bp).abs() / max(bp, 1 - bp)).clip(0, 1)
        else:  # direction
            med = _wquantile(x, w, [0.5])[0]
            pe = _weighted_pct(x, w)
            s = pe if tv > med else 1 - pe
            info["direction"] = "higher" if tv > med else "lower"
        out[f"feat_{key}"] = s
        if pe is not None:
            out[f"pct_{key}"] = pe.astype("float32")  # Rang des Erdwerts auf der Erde (fuer die Erklaerung)
        rel_t = feat.get("reliability") or REL_DEFAULT
        wgt = REL_WEIGHT.get(rel_t, REL_WEIGHT[REL_DEFAULT]) * REL_WEIGHT[EARTH_RELIABILITY.get(key, "B")]
        dims.setdefault(dim, []).append((s, wgt))
        used.append((key, method, f"{col}, Gewicht {wgt:.2f} (Ziel {rel_t}, Erde {EARTH_RELIABILITY.get(key, 'B')})"))
        info.update(weight=float(wgt), rel_target=rel_t, rel_earth=EARTH_RELIABILITY.get(key, "B"))
        meta.append(info)

    conf = {}
    for dim, parts in dims.items():  # gewichtetes Mittel der Merkmale, fehlende Werte zaehlen nicht
        num = sum(s.fillna(0) * w for s, w in parts)
        den = sum(s.notna() * w for s, w in parts)
        n_av = sum(s.notna().astype(float) for s, w in parts)
        out[f"dim_{dim}"] = num / den.replace(0, np.nan)
        # Konfidenz der Dimension = mittleres Verlaesslichkeitsgewicht ihrer vorhandenen Merkmale
        conf[dim] = (den / n_av.replace(0, np.nan)).fillna(0)
        out[f"conf_{dim}"] = conf[dim]
    weights = {d: prof["weights"].get(d, 0) for d in dims if prof["weights"].get(d, 0) > 0}
    if weights:
        S = out[[f"dim_{d}" for d in weights]]
        S.columns = list(weights)
        W = pd.Series(weights)
        avail = S.notna()
        # Dimensionsgewicht x Konfidenz: unsichere Dimensionen (z. B. nur Note-C-Merkmale) zaehlen weniger
        WC = pd.DataFrame({d: W[d] * conf[d] for d in weights})
        out["total"] = (S.fillna(0) * WC).sum(axis=1) / (avail * WC).sum(axis=1).replace(0, np.nan)
        # Mindestabdeckung: mindestens MIN_COVERAGE des Gewichts der Dimensionen, fuer die das Ziel Werte hat,
        # muss die Erdzelle belegen. Sonst wuerden fehlende Dimensionen einfach weggelassen und Zellen mit Luecken
        # nach oben rutschen ("Bestnote durch Weglassen").
        out["coverage_target"] = (avail * W).sum(axis=1) / W.sum()
        full = out["coverage_target"] >= MIN_COVERAGE
        out["total"] = out["total"].where(rank_ok & full)  # Wasser, Eis, Wald/Acker/Siedlung, Luecken nicht ins Ranking
        out["in_ranking"] = rank_ok & full
        out["coverage"] = (avail * W).sum(axis=1) / sum(v for v in prof["weights"].values() if v > 0)
        arr = S.to_numpy(dtype="float64")
        has = avail.any(axis=1).to_numpy()
        names = np.array(list(weights), dtype=object)
        best = np.full(len(S), None, dtype=object); worst = best.copy()
        if has.any():
            best[has] = names[np.nanargmax(arr[has], axis=1)]
            worst[has] = names[np.nanargmin(arr[has], axis=1)]
        out["best_dim"], out["worst_dim"] = best, worst
    else:
        out["total"] = np.nan; out["coverage"] = 0.0; out["best_dim"] = None; out["worst_dim"] = None

    out.attrs["features"] = meta
    if verbose:
        print(f"\n{target['id']} ({target.get('body')}): {len(used)} Merkmale bewertet, {len(skipped)} uebersprungen")
        for k, m, c in used:
            print(f"   + {k:18s} {m:9s} <- {c}")
        for k, why in skipped:
            print(f"   - {k:18s} {why}")
    return out


def country_raster(df, field="ISO_A3"):
    """ISO-A3 (oder ein anderes Natural-Earth-Feld, z. B. CONTINENT) je Zeile von df ueber die gerasterten
    Grenzen (0,05 Grad); leer = kein Land."""
    import shapefile
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    path = Path(__file__).resolve().parent.parent / "data" / "ref" / "ne_50m_admin_0_countries"
    r = shapefile.Reader(str(path), encoding="utf-8")
    fields = [f[0] for f in r.fields[1:]]
    isos, shapes = [""], []
    for n, sr in enumerate(r.iterShapeRecords(), 1):
        rec = dict(zip(fields, sr.record))
        iso = rec.get(field)
        isos.append(iso if iso not in (None, "", "-99") else (rec.get("ADM0_A3") or "") if field == "ISO_A3" else (iso or ""))
        shapes.append((sr.shape.__geo_interface__, n))
    grid = rasterize(shapes, out_shape=(3600, 7200), transform=from_origin(-180, 90, 0.05, 0.05), fill=0, dtype="int32")
    iy = np.clip(((90 - df["lat"].to_numpy()) / 0.05).astype(int), 0, 3599)
    ix = np.clip(((df["lon"].to_numpy() + 180) / 0.05).astype(int), 0, 7199)
    return pd.Series(np.array(isos, dtype=object)[grid[iy, ix]], index=df.index)


# Kandidatenpool fuer die Neu-Gewichtung in der Web-App: die besten Zellen nach Gesamtwert, je Dimension, je
# Kontinent, je Umgebungsklasse und ausserhalb Chinas, mit allen Teilnoten. Die App rechnet daraus im Browser neu.
POOL_DIMS = ["gelaende", "oberflaeche", "thermik", "trockenheit", "atmosphaere", "staub_wind", "eis_wasser", "leben",
             "beleuchtung"]


def export_pool(df, s, fmeta, t, iso_cell, cont_cell, continents, china, n_top=600, n_dim=80, n_cont=25, n_cls=30,
                n_excl=200):
    from categories import ENV_CLASSES, KNOWN_ANALOGS
    tot = s["total"]
    ok = tot.notna()
    pick = set(tot[ok].nlargest(n_top).index)
    for d in POOL_DIMS:
        c = f"dim_{d}"
        if c in s:
            key = pd.DataFrame({"d": s.loc[ok, c], "t": tot[ok]}).dropna()
            pick |= set(key.sort_values(["d", "t"], ascending=False).index[:n_dim])
    for c in continents:
        pick |= set(tot[ok & (cont_cell == c)].nlargest(n_cont).index)
    for c in ENV_CLASSES:
        pick |= set(tot[ok & (df["env_class"] == c["id"])].nlargest(n_cls).index)
    pick |= set(tot[ok & ~iso_cell.isin(china)].nlargest(n_excl).index)
    idx = tot.loc[list(pick)].sort_values(ascending=False).index
    sub = s.loc[idx]
    q8 = lambda x: np.where(np.isfinite(x), np.clip(np.round(x * 254), 0, 254), 255).astype(np.uint8)
    dims = np.stack([q8(sub[f"dim_{d}"].to_numpy(dtype=float)) if f"dim_{d}" in sub else np.full(len(sub), 255, np.uint8)
                     for d in POOL_DIMS], axis=1)
    conf = np.stack([q8(sub[f"conf_{d}"].to_numpy(dtype=float)) if f"conf_{d}" in sub else np.full(len(sub), 255, np.uint8)
                     for d in POOL_DIMS], axis=1)
    fkeys = [m["key"] for m in fmeta]
    fs = np.stack([q8(sub[f"feat_{k}"].to_numpy(dtype=float)) for k in fkeys], axis=1) if fkeys else np.zeros((len(sub), 0), np.uint8)
    fv = np.stack([_earth_values(df.loc[idx], k, t["features"][k])[0].to_numpy(dtype=float) for k in fkeys], axis=1).astype(np.float16) \
        if fkeys else np.zeros((len(sub), 0), np.float16)
    cls_ids = [c["id"] for c in ENV_CLASSES]
    known = mark_known(df.loc[idx, ["lat", "lon"]])
    kn_names = [k[0] for k in KNOWN_ANALOGS]
    rank = tot.rank(ascending=False, method="min")
    return dict(lat=df.loc[idx, "lat"].to_numpy(np.float32), lon=df.loc[idx, "lon"].to_numpy(np.float32),
                total=tot.loc[idx].to_numpy(np.float32), rank=rank.loc[idx].to_numpy(np.int32),
                cov=q8(sub["coverage_target"].to_numpy(dtype=float)), dims=dims, conf=conf, fs=fs, fv=fv,
                fkeys=np.array(fkeys), cls=np.array([cls_ids.index(str(c)) for c in df.loc[idx, "env_class"]], np.uint8),
                iso=np.array([str(x) for x in iso_cell.loc[idx]]),
                cont=np.array([continents.index(c) if c in continents else 255 for c in cont_cell.loc[idx]], np.uint8),
                known=np.array([kn_names.index(k) if isinstance(k, str) and k in kn_names else -1 for k in known], np.int16),
                nranked=np.array(int(ok.sum())))


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    # Standard: ausgefuellte Datei im Repo (planetary/targets.json), sonst die Vorlage
    candidates = [here / "planetary" / "targets.json", here.parent / "planetary" / "targets.json", here.parent / "planetary" / "targets_template.json",
                  here / "schnittstelle" / "targets_template.json"]
    tpath = Path(sys.argv[1]) if len(sys.argv) > 1 else next(p for p in candidates if p.exists())
    table = here / "data" / "earth" / (sys.argv[2] if len(sys.argv) > 2 else "earth_features_025deg.parquet")
    df = pd.read_parquet(table)
    df["env_class"] = classify(df)
    names = {c["id"]: c["name"] for c in ENV_CLASSES}
    T = load_targets(tpath)
    print(f"Zielsignaturen: {tpath}\nErdtabelle:     {table.name} ({len(df):,} Zellen)")
    from categories import flags as _flags
    try:  # Land nur zur Beschriftung (Natural Earth, data/ref/); fehlt die Datei, bleibt das Feld leer
        from countries import CountryLookup
        _cl = CountryLookup()
    except Exception as e:
        print("Hinweis: keine Laenderzuordnung:", e)
        _cl = None
    N_TOP = 20
    EXCLUDE = {"china": {"CHN", "HKG", "MAC"}}  # Option im Frontend: China inkl. verwalteter Gebiete (Aksai Chin)
    from categories import explain_class_full
    iso_cell = country_raster(df)  # ISO-A3 je Zelle (Natural Earth, gerastert)
    cont_cell = country_raster(df, "CONTINENT")
    CONTINENTS = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania", "Antarctica"]
    w_area = pd.Series(np.cos(np.radians(df["lat"].to_numpy(dtype=np.float64))), index=df.index)
    results, rows, pools = {}, [], {}
    for tid, t in T.items():
        s = score_target(df, t)
        if s["total"].notna().sum() == 0:
            continue
        fmeta = s.attrs.get("features", [])
        dimcols = [c for c in s.columns if c.startswith("dim_")]
        tot = s["total"]
        pct = _weighted_pct(tot, w_area)  # Rang unter allen bewerteten Landzellen, fuer "besser als x %"
        # Platz unter allen bewerteten Zellen (1 = beste Zelle der Erde), ungewichtet, Gleichstand = gleicher Platz
        cell_rank = tot.rank(ascending=False, method="min")
        n_ranked = int(tot.notna().sum())

        def site_list(total, label, n=N_TOP):
            idx = top_sites(df, total, n=n, min_km=200)
            top = df.loc[idx].join(s.loc[idx, ["total", "coverage", "coverage_target", "best_dim", "worst_dim"] + dimcols],
                                   rsuffix="_s")
            known = mark_known(top[["lat", "lon"]])
            fl = _flags(df.loc[idx])
            out_sites = []
            for rank, (i, r) in enumerate(top.iterrows(), 1):
                kn = known[i] if isinstance(known[i], str) else None
                country, iso = _cl.label(r.lat, r.lon) if _cl else (None, None)
                # Aufschluesselung je Merkmal: Zielwert, Erdwert, Methode, Teilnote, Gewicht, Rang auf der Erde
                feats = []
                for m in fmeta:
                    ev, _c = _earth_values(df.loc[[i]], m["key"], t["features"][m["key"]])
                    ev = None if ev is None or pd.isna(ev.iloc[0]) else float(ev.iloc[0])
                    sc = s.at[i, f"feat_{m['key']}"]
                    pc = s.at[i, f"pct_{m['key']}"] if f"pct_{m['key']}" in s else np.nan
                    feats.append(dict(key=m["key"], dim=m["dim"], method=m["method"], target=m["target"], unit=m["unit"],
                                      earth=None if ev is None else round(ev, 4),
                                      score=None if pd.isna(sc) else round(float(sc), 3),
                                      earth_pct=None if pd.isna(pc) else round(float(pc), 3),
                                      target_pct=m.get("body_percentile"), direction=m.get("direction"),
                                      weight=round(m["weight"], 2), rel_target=m["rel_target"], rel_earth=m["rel_earth"]))
                site = dict(rank=rank, lat=round(float(r.lat), 3), lon=round(float(r.lon), 3), country=country,
                            country_iso=iso, continent=str(cont_cell[i]) or None, score=round(float(r.total), 4),
                            better_than_pct=round(float(pct[i]) * 100, 4), cell_rank=int(cell_rank[i]),
                            n_ranked=n_ranked, coverage=round(float(r.coverage_target), 3),
                            env_class=str(r.env_class), env_class_name=names[r.env_class],
                            env_reason=explain_class_full(df.loc[i], str(r.env_class)),
                            best_dim=r.best_dim, worst_dim=r.worst_dim, known_analog=kn,
                            flags=[k[5:] for k in fl.columns if bool(fl.at[i, k])],
                            dims={c[4:]: (None if pd.isna(r[c]) else round(float(r[c]), 3)) for c in dimcols},
                            features=feats)
                out_sites.append(site)
                if label == "all" and rank <= 10:
                    print(f"     {r.lat:7.2f} {r.lon:8.2f}  {r.total:.2f}  {names[r.env_class]:30.30s}  {country or '':22.22s} "
                          f"passt: {r.best_dim:11s} bricht: {r.worst_dim:11s}  {('bekannt: ' + kn) if kn else 'NEU'}")
            return out_sites

        print(f"   Top 10 (Datenabdeckung {s['coverage'].mean():.0%}):")
        sites = site_list(tot, "all")
        lists = {"all": sites}
        for name, isos in EXCLUDE.items():
            lists[f"excl_{name}"] = site_list(tot.where(~iso_cell.isin(isos)), name)

        # bester Ort je Kontinent (gegen die Ballung in einer Region), nach Zellplatz sortiert
        def by_continent(total):
            out_c = []
            for c in CONTINENTS:
                tc = total.where(cont_cell == c)
                if tc.notna().any():
                    out_c += site_list(tc, "cont", n=1)
            out_c.sort(key=lambda x: x["cell_rank"])
            for k, x in enumerate(out_c, 1):
                x["rank"] = k
            return out_c
        lists["by_continent"] = by_continent(tot)
        for name, isos in EXCLUDE.items():
            lists[f"by_continent_excl_{name}"] = by_continent(tot.where(~iso_cell.isin(isos)))
        for x in sites:
            rows.append(dict(target=tid, body=t.get("body"), target_name=t.get("name"),
                             **{k: v for k, v in x.items() if k not in ("dims", "flags", "features", "env_reason")},
                             flags=";".join(x["flags"])))
        pools[tid] = export_pool(df, s, fmeta, t, iso_cell, cont_cell, CONTINENTS, EXCLUDE["china"])
        results[tid] = dict(name=t.get("name"), body=t.get("body"), category=t.get("category"),
                            coord_quality=t.get("coord_quality"), center_lat=t.get("center_lat"),
                            center_lon=t.get("center_lon"), mean_coverage=round(float(s["coverage"].mean()), 3),
                            n_new_in_top=sum(x["known_analog"] is None for x in sites), top=sites,
                            **{k: v for k, v in lists.items() if k != "all"},
                            features_used=[{k: v for k, v in m.items()} for m in fmeta])
    out_dir = here / "results"
    out_dir.mkdir(exist_ok=True)
    meta = dict(earth_table=table.name, earth_cells=int(len(df)), targets_file=str(tpath.name), n_top=N_TOP,
                min_separation_km=200, note="Gesamtwert nur zum Sortieren; gezeigt wird das Profil (dims). "
                                            "known_analog = innerhalb des Radius eines bekannten Analogs, sonst neu.")
    flat = {"_dims": np.array(POOL_DIMS), "_classes": np.array([c["id"] for c in ENV_CLASSES]),
            "_continents": np.array(CONTINENTS), "_known": np.array([k[0] for k in KNOWN_ANALOGS])}
    for tid, pdat in pools.items():
        flat.update({f"{tid}/{k}": v for k, v in pdat.items()})
    np.savez_compressed(out_dir / "pool.npz", **flat)
    print(f"Pool: {out_dir / 'pool.npz'} ({sum(len(p['lat']) for p in pools.values()):,} Zellen)")
    json.dump(dict(meta=meta, targets=results), open(out_dir / "top_sites.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    pd.DataFrame(rows).to_csv(out_dir / "top_sites.csv", index=False)
    import augment_pool
    augment_pool.main()
    print(f"\nErgebnisse: {out_dir / 'top_sites.json'}, {out_dir / 'top_sites.csv'}")
