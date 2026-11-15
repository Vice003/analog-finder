"""
Land zu einer Erdkoordinate, nur zur Beschriftung der Ergebnisse (keine Analysedaten).

Quelle: Natural Earth 1:50m Admin 0 Countries (gemeinfrei), https://www.naturalearthdata.com
Datei:  ne_50m_admin_0_countries.shp, Standardordner data/ref/ (nicht im Repo, ca. 2,5 MB), herunterladen mit
        https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/50m_cultural/ne_50m_admin_0_countries.{shp,shx,dbf,prj,cpg}

Natural Earth zeichnet De-facto-Grenzen. Umstrittene Gebiete (z. B. Aksai Chin, Westsahara) erscheinen dort unter
einem Land; das Ergebnis ist deshalb keine politische Aussage.

    from countries import CountryLookup
    cl = CountryLookup()
    cl.lookup(36.5, 77.1)   # -> ("China", "CHN")
"""

from pathlib import Path

import numpy as np

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "ref" / "ne_50m_admin_0_countries"
DISPUTED = Path(__file__).resolve().parent.parent / "data" / "ref" / "ne_50m_admin_0_breakaway_disputed_areas"


class CountryLookup:
    def __init__(self, path=DEFAULT, disputed=DISPUTED, max_km=30.0, lang="de"):
        self.lang = lang
        import shapefile
        from shapely.geometry import shape
        from shapely import STRtree

        # umstrittene Gebiete (Natural Earth "breakaway / disputed areas"), z. B. Aksai Chin
        self.disp_geoms, self.disp_names = [], []
        if Path(str(disputed) + ".shp").exists():
            rd = shapefile.Reader(str(disputed), encoding="utf-8")
            fd = [f[0] for f in rd.fields[1:]]
            for sr in rd.iterShapeRecords():
                rec = dict(zip(fd, sr.record))
                self.disp_geoms.append(shape(sr.shape.__geo_interface__))
                self.disp_names.append((rec.get("NAME_DE") if lang == "de" else rec.get("BRK_NAME")) or rec.get("BRK_NAME") or rec.get("NAME"))
        self.disp_tree = STRtree(self.disp_geoms) if self.disp_geoms else None

        r = shapefile.Reader(str(path), encoding="utf-8")
        fields = [f[0] for f in r.fields[1:]]
        self.geoms, self.names = [], []
        for sr in r.iterShapeRecords():
            rec = dict(zip(fields, sr.record))
            self.geoms.append(shape(sr.shape.__geo_interface__))
            iso = rec.get("ISO_A3")
            if iso in (None, "", "-99"):
                iso = rec.get("ADM0_A3") or ""
            self.names.append(((rec.get("NAME_DE") if lang == "de" else rec.get("NAME")) or rec.get("NAME"), iso))
        self.tree = STRtree(self.geoms)
        self.max_deg = max_km / 111.0

    def disputed(self, lat, lon):
        """Name des umstrittenen Gebiets oder None."""
        from shapely.geometry import Point

        if self.disp_tree is None:
            return None
        hit = self.disp_tree.query(Point(float(lon), float(lat)), predicate="within")
        return self.disp_names[int(hit[0])] if len(hit) else None

    def label(self, lat, lon):
        """Text fuer Ergebnisse, z. B. 'Chile' oder 'Aksai Chin (umstritten; verwaltet: Volksrepublik China)'."""
        name, iso = self.lookup(lat, lon)
        d = self.disputed(lat, lon)
        if d:
            if self.lang == "de":
                return (f"{d} (umstritten; verwaltet: {name})" if name else f"{d} (umstritten)"), iso
            return (f"{d} (disputed; administered by {name})" if name else f"{d} (disputed)"), iso
        return name, iso

    def lookup(self, lat, lon):
        """(Landesname deutsch, ISO-A3) oder (None, None), falls kein Land innerhalb max_km."""
        from shapely.geometry import Point

        p = Point(float(lon), float(lat))
        hit = self.tree.query(p, predicate="within")
        if len(hit):
            return self.names[int(hit[0])]
        i = self.tree.nearest(p)
        # Abstand in Grad, Laenge mit cos(Breite) gestaucht: grobe, fuer Kuestenzellen ausreichende Naeherung
        d = self.geoms[int(i)].distance(p) * max(np.cos(np.radians(lat)), 0.2)
        return self.names[int(i)] if d <= self.max_deg else (None, None)


if __name__ == "__main__":
    cl = CountryLookup()
    for la, lo in [(36.98, 88.42), (81.88, -79.03), (-24.1, -70.0), (38.88, 93.72), (35.6, 79.4), (-77.5, 161.7), (52.5, 13.4)]:
        print(la, lo, cl.label(la, lo))
