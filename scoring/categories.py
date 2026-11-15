"""
Analog-Kategorien fuer den Analog Finder. Eine Definition fuer Scoring, Auswertung und Web-Karte.

Drei Ebenen:

1. UMGEBUNGSKLASSEN  Was fuer ein Ort ist das auf der Erde? (genau eine Klasse pro Zelle, nach Prioritaet)
                     plus FLAGS fuer Zusatzeigenschaften (Staubquelle, sturmreich, landefreundlich, ...).
2. DIMENSIONEN       Die Analog-Dimensionen aus der Aufgabenstellung (Thermik, Trockenheit, Staub & Wind, ...).
                     Jede Zelle bekommt pro Ziel und Dimension einen Wert 0..1.
3. ZIELE             Mond-Suedpol, Mars aequatoriale Landestellen, Mars Eis-Mittelbreiten.
                     Jedes Ziel gewichtet die Dimensionen anders und nennt die Grenzen der Analogie.

Bewertungsprinzip: Die Erde erreicht Mond- und Marswerte fast nie (Mars: 6 hPa, Mond: Vakuum).
Deshalb wird meist relativ zur Erde bewertet: "wie weit geht dieser Ort in Richtung Ziel, verglichen mit
allen Landzellen der Erde" (Perzentil-Rang, nach Zellflaeche gewichtet). Nur wo die Erde echte Zielwerte erreicht (z. B. Albedo),
wird gegen den Zielwert selbst gemessen.

Benutzung:
    import pandas as pd
    from scoring.categories import classify, flags, score
    df = pd.read_parquet("data/earth/earth_features_005deg.parquet")
    df["env_class"] = classify(df)
    df = df.join(flags(df))
    s = score(df, "mars_aequatorial")     # Spalten: dim_<dimension>, total, best_dim, worst_dim
    idx = top_sites(df, s["total"], n=20, min_km=200)   # raeumlich verteilte Bestenliste
    known = mark_known(df.loc[idx])                     # Name eines bekannten Analogs oder None = neu

Die Testorte (TEST_SITES) pruefen nur, ob die Klassenregeln richtig greifen; die bekannten Analoga
(KNOWN_ANALOGS) werden nur markiert. Beides beeinflusst die Bewertung nicht, gesucht wird global.

Selbsttest an bekannten Orten:  python scoring/categories.py
"""

import numpy as np
import pandas as pd

# =====================================================================================================
# 1. UMGEBUNGSKLASSEN
# =====================================================================================================
# Reihenfolge = Prioritaet: die erste zutreffende Regel gewinnt.
# Schwellen sind erste Festlegungen und werden an den Testorten (TEST_SITES) ueberprueft.


def _c(df, col, default=np.nan):
    """Spalte oder NaN-Spalte, falls sie (noch) fehlt."""
    return df[col] if col in df else pd.Series(default, index=df.index, dtype="float32")


def _albedo(df):
    """Schneefreie Albedo, ersatzweise Jahresmittel."""
    return _c(df, "albedo_snowfree").fillna(_c(df, "albedo_sw_mean"))


def _pressure(df):
    """Luftdruck aus MERRA-2, ersatzweise aus der Hoehe geschaetzt."""
    return _c(df, "PS_hpa").fillna(_c(df, "pressure_est_hpa"))


def _barren(df):
    """
    Vegetationsarm (Plan, Korrektur 4): NDVI-Jahresmaximum < 0,15 ODER MODIS-Klasse "barren" >= 50 %.
    Nicht das NDVI-Mittel: heller nackter Boden erreicht NDVI um 0,12 (Atacama-Kern 0,124), und Schneemonate
    druecken das Mittel kuenstlich nach unten.
    """
    peak = _c(df, "ndvi_peak_mean")
    return (peak < 0.15) | (_c(df, "barren_pct") >= 50)


def _arid(df, mm):
    p = _c(df, "precip_mm_yr")
    return p < mm


ENV_CLASSES = [
    dict(
        id="eisschild", name="Eisschild & Gletscher",
        desc="Ganzjaehrig von Schnee oder Eis bedeckt.",
        analog="Mars-Polkappen, Eis in lunaren Kaeltefallen (nur als Eis-Prozess, nicht als Gelaende).",
        # MODIS verwechselt helle Salzpfannen mit Schnee/Eis -> zusaetzlich: auch der waermste Monat
        # bleibt nahe 0 Grad C (Salar de Uyuni erreicht tagsueber ueber 300 K)
        # (fehlt die Temperatur noch, wird diese Bedingung nicht geprueft)
        rule=lambda d: ((_c(d, "snow_perm_frac") >= 0.8) | (_c(d, "snow_ice_pct") >= 60))
        & (_c(d, "lst_warm_mean").fillna(_c(d, "lst_day_mean")).fillna(0) < 280),
    ),
    dict(
        id="salzpfanne", name="Salzpfanne / Evaporit",
        desc="Sehr flach, hell, vegetationslos: ausgetrocknete Salzseen.",
        analog="Chlorid- und Sulfatablagerungen auf dem Mars (z. B. Meridiani, Terra Sirenum).",
        # topfeben: Relief < 25 m und Hoehen-Standardabweichung < 5 m (Duenenfelder sind zwar hell und im
        # Mittel flach, haben aber Dutzende Meter Relief)
        # Schnee wird ueber die Temperatur ausgeschlossen, nicht ueber MODIS-Schnee: MOD10 haelt Salz ebenfalls
        # fuer Schnee (Uyuni: 97 % "Dauerschnee"). Relief grosszuegig, weil einzelne Inseln es hochtreiben.
        rule=lambda d: (_albedo(d) > 0.35) & (_c(d, "flat_frac") >= 0.95) & (_c(d, "relief") < 100)
        & (_c(d, "elev_std") < 5) & _barren(d) & (_c(d, "lst_warm_mean").fillna(999) > 280),
    ),
    dict(
        id="duenenfeld", name="Duenenfeld / Sandmeer",
        desc="Vegetationsloser Flugsand: geringe thermische Traegheit, mittlere Albedo, trocken.",
        analog="Marsduenen und aeolische Prozesse (z. B. Bagnold-Duenen im Gale-Krater).",
        # keine Bedingung an die Flachheit: Riesenduenen (Namib, bis 300 m) haben viel Relief.
        # Felsplateaus mit aehnlicher Traegheit (Tibesti, Albedo 0,21) fallen ueber die Albedo-Untergrenze heraus.
        rule=lambda d: _barren(d) & (_c(d, "barren_pct") >= 80) & _albedo(d).between(0.25, 0.45)
        & (_c(d, "ati") < 0.026) & _arid(d, 150),
    ),
    dict(
        id="dunkel_vulkanisch", name="Dunkles, vegetationsloses Gestein",
        desc="Schneefreie Albedo < 0,15 ohne Vegetation: Basalt, Lavafelder, vulkanische Asche.",
        analog="Basaltische Ebenen auf Mars und Mond-Maria; Lavaroehren-Gebiete.",
        rule=lambda d: _barren(d) & (_albedo(d) < 0.15) & (_c(d, "water_pct").fillna(0) < 30),
    ),
    dict(
        id="kalte_polarwueste", name="Eisfreie kalte Polarwueste",
        desc="Kalt, trocken, kaum Vegetation, im Sommer schneefrei.",
        analog="Mars-Mittelbreiten mit Bodeneis; Regolith der lunaren Polregionen.",
        # kein Dauereis (< 80 % der Monate, wie Eisschild-Regel): arktischer Winterschnee liegt ~7 Monate.
        # 400 mm, weil MERRA-2 (55 km) in Kuestennaehe zu viel Niederschlag zeigt (Haughton 309 mm).
        rule=lambda d: (_c(d, "lst_mean") < 263) & _barren(d) & (_c(d, "snow_perm_frac") < 0.8)
        & (_arid(d, 400) | _c(d, "precip_mm_yr").isna()),
    ),
    dict(
        id="hochplateau", name="Arides Hochplateau",
        desc="Ueber 3000 m, trocken und karg: niedriger Druck, starker Tagesgang, hohe UV-Strahlung.",
        analog="Mars: duenne Atmosphaere, starke Temperaturwechsel, UV (z. B. Altiplano, Chang Tang).",
        rule=lambda d: (_c(d, "elev_mean") > 3000) & _barren(d) & _arid(d, 400),
    ),
    dict(
        id="hyperarid", name="Hyperaride Wueste",
        desc="Unter 50 mm Niederschlag im Jahr, praktisch vegetationslos.",
        analog="Trockenheit und Oxidation des Marsbodens; Grenze des Lebens (z. B. Atacama-Kern).",
        rule=lambda d: _arid(d, 50) & _barren(d),
    ),
    dict(
        id="raues_gebirge", name="Vegetationsarmes Steilrelief",
        desc="Mittlere Hangneigung > 15 Grad ohne nennenswerte Vegetation.",
        analog="Kraterraender, Canyonwaende (Valles Marineris), Kraterraender am Mond-Suedpol.",
        rule=lambda d: (_c(d, "slope_mean") > 15) & _barren(d),
    ),
    dict(
        id="aride_wueste", name="Aride Wueste / Halbwueste",
        desc="Unter 250 mm Niederschlag und vegetationsarm, ohne die Merkmale oben.",
        analog="Allgemeines Wuestenanalog fuer Geraetetests und Mobilitaet.",
        rule=lambda d: _barren(d) & (_arid(d, 250) | _c(d, "precip_mm_yr").isna()),
    ),
    dict(
        id="kein_analog", name="Kein Analog (Vegetation, Wasser)",
        desc="Bewachsen, feucht oder ueberwiegend Wasser.",
        analog="-",
        rule=lambda d: pd.Series(True, index=d.index),
    ),
]
ENV_IDS = [c["id"] for c in ENV_CLASSES]

# Offengelegte Bedingungen je Klasse, damit jede Einstufung nachvollziehbar ist (Frontend: "Why this class").
# Muss mit den Regeln oben uebereinstimmen. Je Bedingung: (Text, Spalte, Vergleich, Schwelle, Einheit).
# "barren" ist die Kahl-Regel: NDVI-Jahresmaximum < 0,15 ODER MODIS-Klasse "barren" >= 50 %.
BARREN = [("vegetation-free: NDVI yearly peak < 0.15", "ndvi_peak_mean", "<", 0.15, ""),
          ("or MODIS land cover 'barren' >= 50 %", "barren_pct", ">=", 50, "%")]
CLASS_RULES = {
    "eisschild": [("permanent snow in >= 80 % of months", "snow_perm_frac", ">=", 0.8, ""),
                  ("or MODIS snow/ice >= 60 %", "snow_ice_pct", ">=", 60, "%"),
                  ("and warmest month < 280 K", "lst_warm_mean", "<", 280, "K")],
    "salzpfanne": [("snow-free albedo > 0.35", "albedo_snowfree", ">", 0.35, ""),
                   ("flat: >= 95 % of area below 5 deg", "flat_frac", ">=", 0.95, ""),
                   ("relief < 100 m", "relief", "<", 100, "m"),
                   ("elevation spread < 5 m", "elev_std", "<", 5, "m"),
                   ("warmest month > 280 K (not snow)", "lst_warm_mean", ">", 280, "K")] + BARREN,
    "duenenfeld": [("MODIS 'barren' >= 80 %", "barren_pct", ">=", 80, "%"),
                   ("albedo 0.25 to 0.45", "albedo_snowfree", "between", (0.25, 0.45), ""),
                   ("loose ground: apparent thermal inertia < 0.026", "ati", "<", 0.026, "1/K"),
                   ("precipitation < 150 mm/yr", "precip_mm_yr", "<", 150, "mm/yr")] + BARREN,
    "dunkel_vulkanisch": [("snow-free albedo < 0.15", "albedo_snowfree", "<", 0.15, ""),
                          ("water < 30 %", "water_pct", "<", 30, "%")] + BARREN,
    "kalte_polarwueste": [("mean surface temperature < 263 K", "lst_mean", "<", 263, "K"),
                          ("not permanent snow (< 80 % of months)", "snow_perm_frac", "<", 0.8, ""),
                          ("precipitation < 400 mm/yr", "precip_mm_yr", "<", 400, "mm/yr")] + BARREN,
    "hochplateau": [("elevation > 3000 m", "elev_mean", ">", 3000, "m"),
                    ("precipitation < 400 mm/yr", "precip_mm_yr", "<", 400, "mm/yr")] + BARREN,
    "hyperarid": [("precipitation < 50 mm/yr", "precip_mm_yr", "<", 50, "mm/yr")] + BARREN,
    "raues_gebirge": [("mean slope > 15 deg", "slope_mean", ">", 15, "deg")] + BARREN,
    "aride_wueste": [("precipitation < 250 mm/yr", "precip_mm_yr", "<", 250, "mm/yr")] + BARREN,
    "kein_analog": [("none of the rules above applies (vegetated, wet or icy)", None, None, None, "")],
}


def explain_class(row, cls):
    """Bedingungen der Klasse mit dem Wert dieses Orts: [{text, value, unit, ok}]."""
    out = []
    for text, col, op, thr, unit in CLASS_RULES.get(cls, []):
        v = None if col is None or col not in row or pd.isna(row[col]) else float(row[col])
        ok = None
        if v is not None:
            ok = {"<": v < thr if op == "<" else None, ">": v > thr if op == ">" else None}.get(op)
            if op == ">=":
                ok = v >= thr
            elif op == "between":
                ok = thr[0] <= v <= thr[1]
        out.append(dict(text=text, value=None if v is None else round(v, 4), unit=unit, ok=ok))
    return out


def _rule_groups(row, cls):
    """Bedingungen als Gruppen: eine Zeile, die mit 'or ' beginnt, gehoert zur vorherigen (Gruppe ok, wenn eine ok)."""
    groups = []
    for r in explain_class(row, cls):
        if r["text"].startswith("or ") and groups:
            groups[-1].append(r)
        else:
            groups.append([r])
    return groups


def explain_class_full(row, cls):
    """
    Begruendung der Klasse: ihre Bedingungen mit den Werten des Orts, und fuer jede vorher gepruefte Klasse
    die erste Bedingung, an der der Ort scheiterte (Klassifikation = erste zutreffende Klasse in ENV_IDS-Reihenfolge).
    """
    not_ = []
    for c in ENV_IDS:
        if c == cls or c == "kein_analog":
            break
        for g in _rule_groups(row, c):
            if not any(r["ok"] for r in g):
                not_.append(dict(cls=c, failed=g))
                break
    return dict(rules=explain_class(row, cls), not_=not_)


def classify(df):
    """Eine Umgebungsklasse pro Zeile (erste zutreffende Regel). Rueckgabe: kategoriale Serie."""
    out = pd.Series("kein_analog", index=df.index, dtype=object)
    todo = pd.Series(True, index=df.index)
    for c in ENV_CLASSES:
        hit = c["rule"](df).fillna(False).astype(bool) & todo
        out[hit] = c["id"]
        todo &= ~hit
    return pd.Categorical(out, categories=ENV_IDS)


# Zusatzeigenschaften (mehrere pro Zelle moeglich)
FLAGS = {
    "staubquelle": ("Aktive Staubquelle (Staubemission im obersten 5 % der Landflaechen)",
                    lambda d: _c(d, "DUEM_mean") > _c(d, "DUEM_mean").quantile(0.95)),
    "staubsturmreich": ("Mindestens 10 Staubsturmtage pro Jahr (Staub-AOD > 1)",
                        lambda d: _c(d, "dust_storm_days") >= 10),
    "windsturmreich": ("Mindestens 5 Sturmtage pro Jahr (Wind > 17 m/s)",
                       lambda d: _c(d, "wind_storm_days") >= 5),
    "windstill": ("Kaum Wind und keine Stuerme: stabile Bedingungen wie auf dem Mond",
                  lambda d: (_c(d, "SPEED_mean") < 3) & (_c(d, "wind_storm_days").fillna(0) < 0.5)),
    "frost_tau": ("Mindestens 3 Monate pro Jahr mit Frost-Tau-Wechsel",
                  lambda d: _c(d, "freeze_thaw_months") >= 3),
    "extrem_kalt": ("Kaeltester Monat nachts unter 220 K (-53 Grad C)",
                    lambda d: _c(d, "lst_abs_min") < 220),
    "niedriger_druck": ("Luftdruck unter 700 hPa (etwa ab 3000 m)",
                        lambda d: _pressure(d) < 700),
    "dunkle_oberflaeche": ("Schneefreie Albedo unter 0,15 bei vegetationsarmer Flaeche (Basalt, Lava, Asche)",
                           lambda d: (_albedo(d) < 0.15) & _barren(d)),
    "landefreundlich": ("Mindestens 80 % der Flaeche unter 5 Grad Neigung, 90-%-Neigung unter 8 Grad",
                        lambda d: (_c(d, "flat_frac") >= 0.8) & (_c(d, "slope_p90") < 8)),
    "polar": ("Polarkreis: Polartag/-nacht, flacher Sonnenstand wie am Mond-Suedpol",
              lambda d: d["lat"].abs() >= 66.56),
}


def flags(df):
    """Boolesche Spalte flag_<name> pro Zusatzeigenschaft."""
    return pd.DataFrame({f"flag_{k}": rule(df).fillna(False).astype(bool) for k, (_, rule) in FLAGS.items()},
                        index=df.index)


# =====================================================================================================
# 2. DIMENSIONEN
# =====================================================================================================
DIMENSIONS = {
    "thermik":      ("Temperatur & Extreme", "Mittlere Temperatur, Tagesgang, Jahresgang, Kaelteextreme"),
    "trockenheit":  ("Trockenheit", "Niederschlag, Trockenmonate, Luftfeuchte"),
    "staub_wind":   ("Staub, Wind & Stuerme", "Staubtruebung, Staubsturm- und Sturmtage, Staubemission, Wind"),
    "gelaende":     ("Gelaende & Landung", "Hangneigung, landefreundliche Flaeche, Relief"),
    "oberflaeche":  ("Oberflaechenmaterial", "Albedo, thermische Traegheit (Staub/Sand/Fels), Vegetationsfreiheit"),
    "eis_wasser":   ("Eis & Wasser-Ressourcen", "Dauerschnee/Eis, Frost-Tau, Kaelte als Konservierung von Eis"),
    "leben":        ("Biologie & Bewohnbarkeit", "Je weniger Vegetation, desto naeher an der Grenze des Lebens"),
    "atmosphaere":  ("Atmosphaere", "Luftdruck und Wasserdampf"),
    "beleuchtung":  ("Beleuchtung", "Sonnenstand und Polartag/-nacht (Breitengrad)"),
}

# Merkmal: (Spalte, Modus, Parameter, Gewicht)
#   "low"    je niedriger, desto besser (Perzentil-Rang unter allen Landzellen)
#   "high"   je hoeher, desto besser
#   "target" Glockenkurve um Zielwert: Parameter = (Zielwert, Toleranz)
# Fehlende Spalten werden uebersprungen; eine Dimension ohne verfuegbare Spalte bekommt NaN.

# =====================================================================================================
# 3. ZIELE
# =====================================================================================================
TARGETS = {
    "mond_suedpol": dict(
        name="Mond-Suedpol (dauerhafte Basis)",
        desc="Artemis-Regionen um den Shackleton-Krater: beleuchtete Kraterraender neben dauerhaft "
             "beschatteten Kaeltefallen mit Wassereis. Kein Wetter, kein Wind, feiner Regolith.",
        reference={
            "Oberflaechentemperatur Kraterrand": "ca. 200-250 K (Diviner)",
            "Dauerschatten-Kaeltefallen": "25-110 K",
            "Atmosphaere": "praktisch Vakuum",
            "Albedo Hochland": "ca. 0,15-0,3",
            "Regolith": "sehr feinkoernig, sehr niedrige thermische Traegheit",
            "Sonnenstand": "maximal ca. 1,5 Grad ueber dem Horizont",
        },
        weights=dict(thermik=1.5, trockenheit=1.0, staub_wind=1.0, gelaende=1.0, oberflaeche=1.0,
                     eis_wasser=1.5, leben=0.5, atmosphaere=0.5, beleuchtung=1.5),
        features=dict(
            thermik=[("lst_mean", "low", None, 2), ("lst_abs_min", "low", None, 1),
                     ("lst_diurnal_mean", "low", None, 0.5)],
            trockenheit=[("precip_mm_yr", "low", None, 1), ("QV2M_gkg", "low", None, 1), ("TQV_mm", "low", None, 1)],
            # Mond: kein Wetter -> Windstille und fehlende Stuerme sind hier das Analog
            staub_wind=[("SPEED_mean", "low", None, 1), ("wind_storm_days", "low", None, 1),
                        ("dust_event_days", "low", None, 0.5)],
            # Basis auf Kraterrand: flache Stellen in stark reliefiertem Umfeld
            gelaende=[("flat_frac", "high", None, 1), ("relief", "high", None, 1)],
            oberflaeche=[("albedo_snowfree", "target", (0.22, 0.08), 1), ("ati", "low", None, 1),
                         ("barren_pct", "high", None, 1)],
            eis_wasser=[("snow_perm_frac", "high", None, 1), ("snow_ice_pct", "high", None, 0.5),
                        ("lst_cold_mean", "low", None, 1)],
            leben=[("ndvi_mean", "low", None, 1)],
            atmosphaere=[("PS_hpa", "low", None, 1), ("TQV_mm", "low", None, 0.5)],
            beleuchtung=[("abs_lat", "high", None, 1)],
        ),
        limits=["Vakuum statt Atmosphaere", "Ein Sechstel der Erdschwerkraft",
                "Kosmische und solare Strahlung ohne Magnetfeld und Atmosphaere",
                "Dauerschatten-Temperaturen unter 110 K gibt es auf der Erde nicht",
                "Elektrostatisch geladener, scharfkantiger Regolith statt verwittertem Boden"],
    ),
    "mars_aequatorial": dict(
        name="Mars, aequatoriale Lande- und Erkundungsorte",
        desc="Robotische Landestellen wie Jezero, Gale, Meridiani: hyperarid, staubig, grosse "
             "Tag-Nacht-Wechsel, Sedimente, Tone und Sulfate, flache Landeellipsen.",
        reference={
            "Mittlere Oberflaechentemperatur": "ca. 210 K",
            "Tag-Nacht-Spanne": "ca. 60-100 K",
            "Luftdruck": "ca. 6 hPa",
            "Albedo": "0,1-0,15 (dunkle Regionen) bis 0,25-0,3 (helle, staubige Regionen)",
            "Staub": "regionale und globale Staubstuerme, Staubteufel",
            "Landeellipse": "Hangneigungen meist unter 15 Grad",
        },
        weights=dict(thermik=1.0, trockenheit=1.5, staub_wind=1.5, gelaende=1.0, oberflaeche=1.5,
                     eis_wasser=0.25, leben=1.0, atmosphaere=1.0, beleuchtung=0.0),
        features=dict(
            thermik=[("lst_diurnal_mean", "high", None, 2), ("lst_mean", "low", None, 1),
                     ("lst_seasonal_amp", "high", None, 0.5)],
            trockenheit=[("precip_mm_yr", "low", None, 2), ("precip_min_year_mm", "low", None, 1),
                         ("dry_month_frac", "high", None, 1), ("QV2M_gkg", "low", None, 1)],
            staub_wind=[("DUEXTTAU_mean", "high", None, 1), ("dust_event_days", "high", None, 1),
                        ("dust_storm_days", "high", None, 1), ("DUEM_mean", "high", None, 1),
                        ("SPEED_mean", "high", None, 0.5)],
            gelaende=[("flat_frac", "high", None, 1), ("slope_p90", "low", None, 1)],
            oberflaeche=[("albedo_snowfree", "target", (0.20, 0.08), 1), ("barren_pct", "high", None, 1),
                         ("ati", "low", None, 0.5)],
            eis_wasser=[("freeze_thaw_months", "high", None, 1)],
            leben=[("ndvi_mean", "low", None, 1), ("ndvi_peak_mean", "low", None, 1)],
            atmosphaere=[("PS_hpa", "low", None, 1), ("TQV_mm", "low", None, 1)],
            beleuchtung=[],
        ),
        limits=["Luftdruck rund 150-mal niedriger, CO2-Atmosphaere", "Gut ein Drittel der Erdschwerkraft",
                "Hohe UV- und Teilchenstrahlung an der Oberflaeche",
                "Kein fluessiges Wasser an der Oberflaeche, Perchlorate im Boden",
                "Mars-Mitteltemperaturen um 210 K erreicht die Erde nur in Polargebieten"],
    ),
    "mars_eis_mittelbreiten": dict(
        name="Mars, eisreiche Mittelbreiten (bemannte Landung)",
        desc="Kandidaten fuer bemannte Landungen wie Arcadia oder Utopia Planitia (ca. 30-50 Grad N): "
             "flach, kalt, oberflaechennahes Bodeneis als Wasserquelle.",
        reference={
            "Oberflaechentemperatur": "ca. 180-230 K",
            "Bodeneis": "wenige Zentimeter bis Meter unter der Oberflaeche",
            "Gelaende": "sehr flache Ebenen",
            "Luftdruck": "ca. 6-8 hPa",
        },
        weights=dict(thermik=1.5, trockenheit=1.0, staub_wind=0.5, gelaende=1.5, oberflaeche=0.75,
                     eis_wasser=2.0, leben=1.0, atmosphaere=0.5, beleuchtung=0.0),
        features=dict(
            thermik=[("lst_mean", "low", None, 2), ("lst_cold_mean", "low", None, 1),
                     ("lst_seasonal_amp", "high", None, 0.5)],
            trockenheit=[("precip_mm_yr", "low", None, 1), ("QV2M_gkg", "low", None, 1)],
            staub_wind=[("DUEXTTAU_mean", "high", None, 1), ("SPEED_mean", "high", None, 0.5)],
            gelaende=[("flat_frac", "high", None, 2), ("slope_p90", "low", None, 1), ("relief", "low", None, 0.5)],
            oberflaeche=[("barren_pct", "high", None, 1), ("albedo_snowfree", "target", (0.20, 0.08), 0.5)],
            # Bodeneis unter eisfreier Oberflaeche: kalt + Frost-Tau, aber kein Eisschild
            eis_wasser=[("freeze_thaw_months", "high", None, 1), ("lst_cold_mean", "low", None, 1),
                        ("snow_perm_frac", "target", (0.2, 0.3), 1), ("permafrost_frac", "high", None, 2)],
            leben=[("ndvi_mean", "low", None, 1)],
            atmosphaere=[("PS_hpa", "low", None, 1)],
            beleuchtung=[],
        ),
        limits=["Luftdruck rund 150-mal niedriger", "Gut ein Drittel der Erdschwerkraft",
                "Strahlung an der Oberflaeche", "Marsboden-Eis sublimiert statt zu tauen"],
    ),
}


# =====================================================================================================
# Bewertung
# =====================================================================================================
def _weighted_pct(x, w):
    """Flaechengewichteter Perzentil-Rang (0..1). Ohne Gewichtung waeren Polargebiete ueberrepraesentiert,
    weil 0,05-Grad-Zellen zu den Polen hin kleiner und damit zahlreicher werden."""
    ok = x.notna().to_numpy()
    # 64 Bit: bei Millionen Zellen summieren sich 32-Bit-Rundungsfehler sonst auf ~1 % (Perzentile > 100 %)
    v, ww = x.to_numpy(dtype=np.float64)[ok], w.to_numpy(dtype=np.float64)[ok]
    o = np.argsort(v, kind="mergesort")
    cw = np.cumsum(ww[o]) - ww[o] / 2  # Mittelpunkt der eigenen Gewichtsstufe
    r = np.empty(v.size)
    r[o] = cw / ww.sum()
    out = pd.Series(np.nan, index=x.index)
    out[ok] = r
    return out


def _feature_score(x, mode, param, w):
    """Wert 0..1 fuer ein Merkmal: flaechengewichteter Perzentil-Rang oder Glockenkurve um einen Zielwert."""
    if mode == "target":
        v, tol = param
        return np.exp(-(((x - v) / tol) ** 2))
    r = _weighted_pct(x, w)
    return r if mode == "high" else 1 - r


def score(df, target):
    """
    Bewertet jede Zeile fuer ein Ziel. Rueckgabe-Spalten:
      dim_<dimension>   0..1 je Dimension (NaN, wenn keine Daten)
      total             gewichtetes Mittel der verfuegbaren Dimensionen
      best_dim          staerkste Dimension (was passt)
      worst_dim         schwaechste Dimension (wo die Analogie bricht)
      coverage          Anteil der Dimensionsgewichte mit Daten
    """
    t = TARGETS[target]
    d = df.copy()
    d["abs_lat"] = d["lat"].abs()
    if "PS_hpa" not in d and "pressure_est_hpa" in d:
        d["PS_hpa"] = d["pressure_est_hpa"]
    if "albedo_snowfree" in d and "albedo_sw_mean" in d:
        d["albedo_snowfree"] = d["albedo_snowfree"].fillna(d["albedo_sw_mean"])

    out = pd.DataFrame(index=df.index)
    area_w = pd.Series(np.cos(np.radians(d["lat"].to_numpy())), index=d.index)  # Zellflaeche ~ cos(Breite)
    for dim, feats in t["features"].items():
        num = pd.Series(0.0, index=d.index)
        den = pd.Series(0.0, index=d.index)
        for col, mode, param, w in feats:
            if col not in d:
                continue
            s = _feature_score(d[col].astype("float64"), mode, param, area_w)
            num += s.fillna(0) * w
            den += s.notna() * w  # fehlt ein Wert, zaehlen die uebrigen Merkmale der Dimension
        out[f"dim_{dim}"] = num / den.replace(0, np.nan)

    dims = [k for k in t["features"] if t["weights"].get(k, 0) > 0]
    W = pd.Series({k: t["weights"][k] for k in dims})
    S = out[[f"dim_{k}" for k in dims]]
    S.columns = dims
    avail = S.notna()
    out["total"] = (S.fillna(0) * W).sum(axis=1) / (avail * W).sum(axis=1).replace(0, np.nan)
    out["coverage"] = (avail * W).sum(axis=1) / W.sum()
    has = avail.any(axis=1)
    arr = S.to_numpy(dtype="float64")
    best = np.full(len(S), None, dtype=object)
    worst = np.full(len(S), None, dtype=object)
    if has.any():
        sub = arr[has.to_numpy()]
        best[has.to_numpy()] = np.array(dims, dtype=object)[np.nanargmax(sub, axis=1)]
        worst[has.to_numpy()] = np.array(dims, dtype=object)[np.nanargmin(sub, axis=1)]
    out["best_dim"], out["worst_dim"] = best, worst
    return out


def missing_columns(df):
    """Welche in den Zielprofilen benutzten Spalten fehlen in df noch?"""
    used = {c for t in TARGETS.values() for fs in t["features"].values() for c, *_ in fs}
    return sorted(used - set(df.columns) - {"abs_lat"})


# =====================================================================================================
# Testorte: bekannte Analoga und erwartete Klasse (zum Ueberpruefen der Schwellen)
# =====================================================================================================
TEST_SITES = [
    ("Dome C, Antarktis", -75.10, 123.35, "eisschild"),
    # Dry Valleys: bei 5 km nicht aufloesbar, MOD10CM meldet in allen 600 Zellen 100 % Dauerschnee (Datengrenze)
    ("McMurdo Dry Valleys (nur Hinweis)", -77.55, 161.70, None),
    ("Haughton-Krater, Devon Island", 75.38, -89.68, "kalte_polarwueste"),
    ("Atacama, Yungay", -24.08, -70.00, "hyperarid"),
    ("Rub al-Chali", 20.00, 50.00, "duenenfeld"),
    ("Namib-Sandmeer", -24.50, 15.30, "duenenfeld"),
    ("Taklamakan", 39.00, 83.00, "duenenfeld"),
    ("Salar de Uyuni", -20.20, -67.60, "salzpfanne"),
    ("Odadahraun, Island", 65.00, -16.60, "dunkel_vulkanisch"),
    ("Harrat Khaybar, Saudi-Arabien", 25.50, 39.90, "dunkel_vulkanisch"),
    ("Mauna Loa, Gipfellava", 19.47, -155.59, "dunkel_vulkanisch"),  # Ka'u-Zelle mischt Lava und Regenwald
    ("Chang Tang, Tibet", 34.50, 85.00, "hochplateau"),
    ("Hajar-Gebirge, Oman", 23.25, 57.25, "raues_gebirge"),  # alter Tibesti-Punkt lag auf einem Plateau (4,8 Grad)
    ("Death Valley", 36.50, -116.90, "aride_wueste"),
    ("Bodele-Senke (Staubquelle)", 16.80, 17.80, None),
    ("Berlin (Gegenprobe)", 52.52, 13.40, "kein_analog"),
]


# =====================================================================================================
# Bekannte Analog-Orte: werden NICHT bevorzugt, nur markiert ("bekannt" vs. "neu").
# Die Aufgabenstellung fragt ausdruecklich nach bisher wenig beachteten Orten; diese Liste macht sichtbar,
# welche Treffer bereits etablierte Analoga sind. Koordinaten und Radien sind Naeherungen (Zentrum des
# Gebiets, Radius in km). Grundlage: haeufig genutzte Feldstandorte aus NASA-/ESA-Analogmissionen und
# Literatur (u. a. ESA Catalogue of Planetary Analogues). Erweiterbar.
# =====================================================================================================
KNOWN_ANALOGS = [
    # Name, Breite, Laenge, Radius km, wofuer bekannt
    ("Atacama-Wueste (Yungay, Kern)", -24.1, -70.0, 250, "Mars: Hyperariditaet, Lebensgrenze"),
    ("Altiplano / Licancabur", -22.8, -67.9, 120, "Mars: Hochgebirgsseen, UV"),
    # ergaenzt nach Literaturpruefung 15.11. (results/novelty_check.json)
    ("Salar de Uyuni / Sur Lipez", -20.2, -67.6, 120, "Mars: Salzkrusten, Evaporite im Hochland"),
    ("Borup Fiord Pass (Ellesmere)", 80.8, -81.6, 120, "Mars/Europa: Schwefelquellen, kalte Polarwueste"),
    ("McMurdo Dry Valleys", -77.5, 161.8, 120, "Mars: kalte Polarwueste"),
    ("Dome C / Concordia", -75.1, 123.3, 100, "Isolation, Kaelte"),
    ("Haughton-Krater / Devon Island", 75.4, -89.7, 150, "Mars/Mond: Impaktkrater, polare Wueste"),
    ("Axel Heiberg Island", 79.4, -90.8, 120, "Mars: Permafrost, kalte Quellen"),
    ("Svalbard (AMASE)", 79.4, 13.3, 150, "Mars: Vulkanismus im Permafrost"),
    ("Island, Hochland", 64.8, -17.5, 200, "Mars/Mond: Basalt, Vulkanismus, Gletscher"),
    ("Death Valley", 36.5, -116.9, 100, "Mars: Salzpfannen, Wueste"),
    ("Mojave-Wueste", 35.0, -116.0, 200, "Mars: Rover-Tests"),
    ("Utah, MDRS Hanksville", 38.4, -110.8, 80, "Mars: Habitat-Simulation"),
    ("Meteor Crater / Black Point (Desert RATS)", 35.2, -111.3, 80, "Mond: Krater, Lavafelder"),
    ("Hawaii (Mauna Kea, HI-SEAS, PISCES)", 19.6, -155.5, 120, "Mond/Mars: Basalt, Habitat"),
    ("Lanzarote (PANGAEA)", 29.0, -13.6, 60, "Mond/Mars: Vulkanismus, Lavaroehren"),
    ("Rio Tinto", 37.7, -6.6, 50, "Mars: saure Gewaesser, Eisenminerale"),
    ("Ries-Krater", 48.9, 10.6, 30, "Mond/Mars: Impaktkrater"),
    ("Sudbury", 46.6, -81.2, 60, "Mond: Impaktkrater"),
    ("Mistastin-Krater", 55.9, -63.3, 30, "Mond: Anorthosit, Impakt"),
    ("Qaidam-Becken", 37.5, 94.0, 300, "Mars: Evaporite, Yardangs"),
    ("Danakil / Dallol", 14.2, 40.3, 100, "Mars: Extremophile, Salz"),
    ("Pilbara", -21.0, 119.5, 200, "Mars: fruehes Leben"),
    ("Namib-Wueste", -24.0, 15.5, 200, "Mars: Duenen, Nebelwueste"),
    ("Dhofar, Oman (AMADEE-18)", 18.6, 53.8, 100, "Mars: Feldsimulation"),
    ("Negev / Ramon-Krater (D-MARS)", 30.6, 34.8, 50, "Mars: Feldsimulation"),
    ("Wadi Rum", 29.6, 35.4, 50, "Mars: Sandsteinlandschaft"),
    ("Lonar-Krater", 19.98, 76.51, 20, "Mars/Mond: Basalt-Impaktkrater"),
    ("Pavilion Lake", 50.86, -121.74, 20, "Mars: Mikrobialithen"),
]


def _haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def mark_known(df):
    """Name des naechstgelegenen bekannten Analogs innerhalb seines Radius, sonst None ("neu")."""
    out = pd.Series(None, index=df.index, dtype=object)
    best = pd.Series(np.inf, index=df.index)
    for name, la, lo, r, _ in KNOWN_ANALOGS:
        near = (df["lat"] - la).abs() < r / 111 + 0.5  # Vorauswahl, spart Rechenzeit
        if not near.any():
            continue
        d = pd.Series(_haversine_km(df.loc[near, "lat"].to_numpy(), df.loc[near, "lon"].to_numpy(), la, lo),
                      index=df.index[near])
        hit = (d <= r) & (d < best[near])
        out[hit[hit].index] = name
        best[hit[hit].index] = d[hit]
    return out


def top_sites(df, total, n=20, min_km=200, pool=200_000):
    """
    Beste n Zellen mit mindestens min_km Abstand untereinander, damit nicht 20 Nachbarzellen derselben
    Region die Liste fuellen. Rueckgabe: Indizes in Rangfolge.
    """
    cand = total.dropna().nlargest(pool)
    lat, lon = df.loc[cand.index, "lat"].to_numpy(), df.loc[cand.index, "lon"].to_numpy()
    chosen = []
    for k in range(len(cand)):
        if chosen and (_haversine_km(lat[k], lon[k], lat[chosen], lon[chosen]) < min_km).any():
            continue
        chosen.append(k)
        if len(chosen) == n:
            break
    return cand.index[chosen]


def nearest(df, lat, lon):
    i = ((df["lat"] - lat).abs() + ((df["lon"] - lon + 180) % 360 - 180).abs()).idxmin()
    return df.loc[i]


if __name__ == "__main__":
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "earth" / (
        sys.argv[1] if len(sys.argv) > 1 else "earth_features_005deg.parquet")
    df = pd.read_parquet(path)
    miss = missing_columns(df)
    if miss:
        print("Hinweis, Spalten fehlen noch (werden uebersprungen):", ", ".join(miss))
    df["env_class"] = classify(df)
    F = flags(df)
    names = {c["id"]: c["name"] for c in ENV_CLASSES}

    print("\nUmgebungsklassen (Anteil der Landzellen):")
    print((df["env_class"].value_counts(normalize=True) * 100).round(1).to_string())

    print("\nTestorte:")
    ok = 0
    for name, la, lo, exp in TEST_SITES:
        i = nearest(df, la, lo).name
        got = df.at[i, "env_class"]
        fl = [k for k in FLAGS if F.at[i, f"flag_{k}"]]
        mark = "  " if exp is None else ("OK" if got == exp else "--")
        ok += exp is not None and got == exp
        print(f" {mark} {name:32s} -> {names[got]:34s} {('erwartet: ' + names[exp]) if exp and got != exp else ''}"
              f"  [{', '.join(fl)}]")
    n_exp = sum(e is not None for *_, e in TEST_SITES)
    print(f"\n{ok}/{n_exp} Testorte wie erwartet klassifiziert")

    N = 15
    for t in TARGETS:
        s = score(df, t)
        idx = top_sites(df, s["total"], n=N, min_km=200)
        top = df.loc[idx].join(s.loc[idx])
        top["known"] = mark_known(top)
        top["known"] = top["known"].where(top["known"].notna(), None)
        n_new = top["known"].isna().sum()
        print(f"\nTop {N} fuer {TARGETS[t]['name']}  (mind. 200 km Abstand, Datenabdeckung {s['coverage'].mean():.0%}, "
              f"{n_new} neu / {N - n_new} bekannt)")
        for _, r in top.iterrows():
            tag = f"bekannt: {r.known}" if isinstance(r.known, str) else "NEU"
            print(f"   {r.lat:7.2f} {r.lon:8.2f}  {r.total:.2f}  {names[r.env_class]:30.30s}  "
                  f"passt: {r.best_dim:11s} bricht: {r.worst_dim:11s}  {tag}")
