"""
"What makes this terrain special": 2-5 short statements per Earth site, generated only from its measured values.

Inputs per site and target: the feature list of the target (key, method, target value, direction, target percentile)
and the site's values per feature (Earth value, match score, Earth percentile), its environment class and flags.
Every statement names its value and, where it helps, how it compares with Earth's land or with the target.
The web app (template.html, function highlightsJS) mirrors these rules for candidate-pool sites.

  highlights(fm, fv, env_class, flags, lang="en") -> list of str
    fm: [{k, m, tv, tp, dir}]   (method "direct" / "quantile" / "direction")
    fv: [[earth_value, score, earth_pct], ...] aligned with fm
"""

CLASS_WHY = {
    "en": {"salzpfanne": "Salt flat: chloride and sulfate deposits like those found on Mars.",
           "duenenfeld": "Dune field: wind-blown sand, as in the Martian dunes Curiosity crossed in Gale crater.",
           "dunkel_vulkanisch": "Dark bare rock (basalt, lava): the rock type of Mars's plains and the lunar maria.",
           "kalte_polarwueste": "Ice-free cold polar desert: cold, dry regolith, the closest Earth gets to lunar polar or Martian mid-latitude ground.",
           "hochplateau": "Arid high plateau: thin air, strong UV and large temperature swings, as on Mars.",
           "hyperarid": "Hyperarid desert: dryness and oxidised soil at the limit of life, like Martian soil.",
           "raues_gebirge": "Barren steep terrain: like crater rims and canyon walls on Mars or at the lunar south pole.",
           "aride_wueste": "Arid desert: a general desert analog for testing rovers and instruments.",
           "kein_analog": "Bare ground that is wetter or milder than the classic analog landscapes."},
    "de": {"salzpfanne": "Salzpfanne: Chlorid- und Sulfatablagerungen wie auf dem Mars.",
           "duenenfeld": "Dünenfeld: Flugsand wie in den Marsdünen, die Curiosity im Gale-Krater durchquert hat.",
           "dunkel_vulkanisch": "Dunkles, kahles Gestein (Basalt, Lava): das Gestein der Mars-Ebenen und der Mond-Maria.",
           "kalte_polarwueste": "Eisfreie kalte Polarwüste: kalter, trockener Boden, so nah am Regolith der Mondpole oder der Mars-Mittelbreiten, wie es auf der Erde geht.",
           "hochplateau": "Arides Hochplateau: dünne Luft, starke UV-Strahlung und große Temperaturwechsel wie auf dem Mars.",
           "hyperarid": "Hyperaride Wüste: Trockenheit und oxidierter Boden an der Grenze des Lebens, wie der Marsboden.",
           "raues_gebirge": "Kahles Steilgelände: wie Kraterränder und Canyonwände auf dem Mars oder am Mond-Südpol.",
           "aride_wueste": "Aride Wüste: allgemeines Wüstenanalog für Tests von Rovern und Instrumenten.",
           "kein_analog": "Kahler Boden, der feuchter oder milder ist als die klassischen Analog-Landschaften."},
}
T = {
    "en": dict(
        flat="Very flat: median slope {v:.1f}°, 90 % of slopes under {p90:.1f}°",
        rugged="Rugged terrain: median slope {v:.1f}°, relief {rel:.0f} m within 5 km",
        moderate="Moderate terrain: median slope {v:.1f}°, relief {rel:.0f} m within 5 km",
        like_target=" (target {tv:.1f}°, almost the same)", vs_target=" (target {tv:.1f}°)",
        dry="Hyperarid: {v:.0f} mm of precipitation a year, drier than {s:.0f} % of Earth's land",
        dry2="Very dry: {v:.0f} mm of precipitation a year, drier than {s:.0f} % of Earth's land",
        high="High altitude: air pressure {v:.0f} hPa, lower than {s:.0f} % of Earth's land",
        cold="Cold: mean ground temperature {c:.0f} °C, colder than {s:.0f} % of Earth's land",
        swing="Large day-night swings: {v:.0f} K, more than {s:.0f} % of Earth's land",
        bright="Bright surface: brighter than {s:.0f} % of Earth's bare land",
        dark="Dark surface: darker than {s:.0f} % of Earth's bare land",
        rank_match=" (the target ranks similarly on its own body)",
        loose="Loose, fine material: lower thermal inertia than {s:.0f} % of Earth's bare land (dust, sand)",
        rocky="Rocky or crusted ground: higher thermal inertia than {s:.0f} % of Earth's bare land",
        dusty="Frequent dust storms: {v:.0f} days a year with dust optical depth above 1",
        lowsun="Low sun: it never rises higher than {v:.0f}° above the horizon",
        calm="Calm air: mean wind {v:.1f} m/s, calmer than {s:.0f} % of Earth's land",
        f_landing="Landing-friendly: at least 80 % of the area is flatter than 5°",
        f_freeze="Freeze-thaw cycles in at least 3 months a year",
        f_source="Active dust source: dust emission among the top 5 % of Earth's land"),
    "de": dict(
        flat="Sehr flach: Neigung im Median {v:.1f}°, 90 % der Hänge unter {p90:.1f}°",
        rugged="Zerklüftetes Gelände: Neigung im Median {v:.1f}°, Relief {rel:.0f} m auf 5 km",
        moderate="Mäßig bewegtes Gelände: Neigung im Median {v:.1f}°, Relief {rel:.0f} m auf 5 km",
        like_target=" (Ziel {tv:.1f}°, fast gleich)", vs_target=" (Ziel {tv:.1f}°)",
        dry="Hyperarid: {v:.0f} mm Niederschlag im Jahr, trockener als {s:.0f} % des Erdlands",
        dry2="Sehr trocken: {v:.0f} mm Niederschlag im Jahr, trockener als {s:.0f} % des Erdlands",
        high="Große Höhe: Luftdruck {v:.0f} hPa, niedriger als bei {s:.0f} % des Erdlands",
        cold="Kalt: Bodentemperatur im Mittel {c:.0f} °C, kälter als {s:.0f} % des Erdlands",
        swing="Große Tag-Nacht-Unterschiede: {v:.0f} K, mehr als bei {s:.0f} % des Erdlands",
        bright="Helle Oberfläche: heller als {s:.0f} % des kahlen Erdlands",
        dark="Dunkle Oberfläche: dunkler als {s:.0f} % des kahlen Erdlands",
        rank_match=" (das Ziel steht auf seinem Körper ähnlich)",
        loose="Lockeres, feines Material: geringere thermische Trägheit als {s:.0f} % des kahlen Erdlands (Staub, Sand)",
        rocky="Felsiger oder verkrusteter Boden: höhere thermische Trägheit als {s:.0f} % des kahlen Erdlands",
        dusty="Häufige Staubstürme: {v:.0f} Tage im Jahr mit Staubtrübung über 1",
        lowsun="Tiefe Sonne: Sie steht nie höher als {v:.0f}° über dem Horizont",
        calm="Ruhige Luft: mittlerer Wind {v:.1f} m/s, ruhiger als bei {s:.0f} % des Erdlands",
        f_landing="Landefreundlich: mindestens 80 % der Fläche flacher als 5°",
        f_freeze="Frost-Tau-Wechsel in mindestens 3 Monaten im Jahr",
        f_source="Aktive Staubquelle: Staubemission unter den obersten 5 % des Erdlands"),
}


def pc(x):
    """Share as a whole percentage, rounded down and capped at 99 (never 'more than 100 %')."""
    return min(int(x * 100), 99)


def highlights(fm, fv, env_class=None, flags=(), lang="en", max_items=4):
    t = T[lang]
    by = {}
    for m, v in zip(fm, fv or []):
        if v and v[0] is not None:
            by[m["k"]] = (m, v[0], v[1], v[2])
    out = []  # (strength, text)
    if "slope_p50" in by:
        m, v, sc, _ = by["slope_p50"]
        p90 = by.get("slope_p90", (None, v))[1]
        rel = by.get("relief", (None, 0))[1] or 0
        key = "flat" if v < 2 else ("rugged" if v > 10 or rel > 400 else "moderate")
        txt = t[key].format(v=v, p90=p90, rel=rel)
        if m.get("tv") is not None:
            txt += (t["like_target"] if sc is not None and sc >= 0.9 else t["vs_target"]).format(tv=m["tv"])
        out.append((2.0, txt))  # terrain always first: it is what the site profile shows
    def share(k):  # share of Earth's land that is further from the target than this site
        m, v, sc, ep = by[k]
        if ep is None:
            return None, v, m
        return ((1 - ep) if m.get("dir") == "lower" else ep), v, m
    if "precip" in by:
        s, v, _ = share("precip")
        if s is not None and s >= 0.8:
            out.append((s, (t["dry"] if v < 50 else t["dry2"]).format(v=v, s=pc(s))))
    if "pressure" in by:
        s, v, m = share("pressure")
        if s is not None and s >= 0.8 and m.get("dir") == "lower":
            out.append((s, t["high"].format(v=v, s=pc(s))))
    if "surface_temp_mean" in by:
        s, v, m = share("surface_temp_mean")
        if s is not None and s >= 0.8 and m.get("dir") == "lower":
            out.append((s, t["cold"].format(c=v - 273.15, s=pc(s))))
    if "diurnal_range" in by:
        s, v, m = share("diurnal_range")
        if s is not None and s >= 0.8 and m.get("dir") == "higher":
            out.append((s - 0.02, t["swing"].format(v=v, s=pc(s))))
    if "wind_mean" in by:
        s, v, m = share("wind_mean")
        if s is not None and s >= 0.85 and m.get("dir") == "lower":
            out.append((s - 0.05, t["calm"].format(v=v, s=pc(s))))
    for k in ("albedo", "thermal_inertia"):
        if k in by and by[k][3] is not None:
            m, v, sc, ep = by[k]
            tp = m.get("tp")
            match = tp is not None and abs(ep - tp) <= 0.1
            if k == "albedo" and (ep >= 0.8 or ep <= 0.2):
                txt = (t["bright"].format(s=pc(ep)) if ep >= 0.8 else t["dark"].format(s=pc(1 - ep)))
                out.append((max(ep, 1 - ep) - 0.05, txt + (t["rank_match"] if match else "")))
            if k == "thermal_inertia" and (ep >= 0.75 or ep <= 0.25):
                txt = (t["rocky"].format(s=pc(ep)) if ep >= 0.75 else t["loose"].format(s=pc(1 - ep)))
                out.append((max(ep, 1 - ep) - 0.05, txt + (t["rank_match"] if match else "")))
    if "dust_storm_days" in by and (by["dust_storm_days"][1] or 0) >= 10:
        out.append((0.85, t["dusty"].format(v=by["dust_storm_days"][1])))
    if "sun_elevation_max" in by and by["sun_elevation_max"][1] < 35:
        out.append((0.8, t["lowsun"].format(v=by["sun_elevation_max"][1])))
    fl = set(flags or ())
    if "landefreundlich" in fl and not any("flat" in x[1].lower() or "flach" in x[1].lower() for x in out):
        out.append((0.75, t["f_landing"]))
    if "frost_tau" in fl:
        out.append((0.7, t["f_freeze"]))
    if "staubquelle" in fl:
        out.append((0.72, t["f_source"]))
    out.sort(key=lambda x: -x[0])
    items = [x[1] for x in out[:max_items]]
    if lang == "de":  # Dezimalkomma
        import re
        items = [re.sub(r"(\d)\.(\d)", r"\1,\2", x) for x in items]
    why = CLASS_WHY[lang].get(env_class or "")
    if why:
        items.append(why)
    return items
