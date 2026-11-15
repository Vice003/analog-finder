"""
Glossary for all pages (German project/results pages, English web app).

Hand-written entries explain general terms; classes, flags, profile weights and known analogs are generated from
scoring/categories.py and scoring/target_scoring.py, so the glossary always matches the code.

  entries(lang) -> list of dict(id, group, title, html)
  GROUPS[lang]  -> ordered group names
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scoring"))
from categories import CLASS_RULES, ENV_CLASSES, FLAGS, KNOWN_ANALOGS, TARGETS as PROFILES  # noqa: E402
from target_scoring import EARTH_RELIABILITY, FEATURES, MIN_COVERAGE, REL_WEIGHT  # noqa: E402

esc = html.escape
GROUPS = {
    "de": ["Grundbegriffe", "Bewertung", "Umgebungsklassen", "Zusatzeigenschaften", "Merkmale", "Zielorte", "Daten",
           "Projektseite"],
    "en": ["Basics", "Scoring", "Environment classes", "Flags", "Features", "Target sites", "Data", "Project page"],
}
G = {k: dict(zip(GROUPS["de"], GROUPS[k])) for k in GROUPS}  # German group name -> group name in lang

# (id, group (de), title de, text de, title en, text en). Text is HTML; {g:id} links to another entry.
HAND = [
    # ---------------------------------------------------------------- Grundbegriffe
    ("ziel", "Grundbegriffe", "Ziel (Zielort)",
     "Ein Landeplatz oder Basis-Kandidat auf Mars oder Mond, zu dem Erd-Analoga gesucht werden: 14 auf dem Mars, 13 am Mond-Südpol, aus der Ortsliste des Mond/Mars-Teams. Jedes Ziel ist ein {g:zielquadrat} mit Werten für die {g:merkmal|Merkmale}.",
     "Target site",
     "A landing site or base candidate on Mars or the Moon for which Earth analogs are sought: 14 on Mars, 13 at the lunar south pole, from the Moon/Mars team's site list. Each target is a {g:zielquadrat|box} with values for the {g:merkmal|features}."),
    ("zelle", "Grundbegriffe", "Erdzelle",
     "Ein Rasterfeld von 0,05° × 0,05° auf der Erde, am Äquator etwa 5,5 × 5,5 km, zu den Polen hin schmaler. Die Erde hat 8,9 Millionen solcher Landzellen. Für jede Zelle liegen Mittelwerte aus 2003–2024 vor.",
     "Earth cell",
     "A 0.05° × 0.05° grid cell on Earth, about 5.5 × 5.5 km at the equator and narrower towards the poles. Earth has 8.9 million such land cells, each with averages over 2003–2024."),
    ("bewertet", "Grundbegriffe", "Bewertete Zellen",
     "Die Zellen, die ins Ranking kommen: nur {g:vegetationsfrei|vegetationsfreies} Land, ohne {g:masken|ausgeschlossene Flächen} und mit genug Daten ({g:mindestabdeckung}). Das sind je Ziel rund 840.000 der 8,9 Millionen Landzellen.",
     "Ranked cells",
     "The cells that enter the ranking: only {g:vegetationsfrei|vegetation-free} land, without {g:masken|masked areas}, with enough data ({g:mindestabdeckung|minimum coverage}). About 840,000 of the 8.9 million land cells per target."),
    ("vegetationsfrei", "Grundbegriffe", "Vegetationsfrei (Kahl-Regel)",
     "Eine Zelle gilt als vegetationsfrei, wenn ihr NDVI-Jahresmaximum unter 0,15 liegt <i>oder</i> MODIS mindestens 50 % ihrer Fläche als „barren“ (kahl) einstuft. Das Jahresmaximum statt des Mittels, damit heller Wüstenboden (Atacama, NDVI 0,12) nicht als bewachsen gilt.",
     "Vegetation-free",
     "A cell counts as vegetation-free if its yearly NDVI peak is below 0.15 <i>or</i> MODIS classes at least 50 % of it as ‘barren’. The yearly peak rather than the mean, so bright desert soil (Atacama, NDVI 0.12) is not taken for vegetation."),
    ("masken", "Grundbegriffe", "Ausgeschlossene Flächen",
     "Nicht bewertet werden: Zellen mit über 50 % Wasser; Eisschilde und Gletscher (Dauerschnee, der auch im wärmsten Monat unter 280 K bleibt); Wald, Acker und Siedlung als Hauptklasse (MODIS-Landbedeckung); alles, was nicht {g:vegetationsfrei} ist.",
     "Masked areas",
     "Not ranked: cells over 50 % water; ice sheets and glaciers (permanent snow that stays below 280 K even in the warmest month); forest, cropland and settlements as the main land cover (MODIS); everything that is not {g:vegetationsfrei|vegetation-free}."),
    ("platz", "Grundbegriffe", "Platz auf der Erde (Zellplatz)",
     "Rang einer Zelle unter allen {g:bewertet|bewerteten Zellen}, sortiert nach dem {g:gesamtwert}. Platz 1 ist die ähnlichste Zelle der Erde. „Platz 105 von 837.533“ heißt: 104 Zellen passen besser, und die Zelle gehört zu den besten 0,013 %. In den Listen springen die Plätze, weil Nachbarzellen eines besseren Orts übersprungen werden ({g:top20}).",
     "Rank on Earth",
     "Place of a cell among all {g:bewertet|ranked cells}, sorted by the {g:gesamtwert|overall score}. Rank 1 is the best-matching cell on Earth. ‘#105 of 837,533’ means 104 cells match better and the cell is in the best 0.013 %. Ranks jump in the lists because cells next to a better site are skipped ({g:top20|Top 20})."),
    ("top20", "Grundbegriffe", "Top 20 (mindestens 200 km Abstand)",
     "Die 20 besten Orte je Ziel. Damit nicht 20 Nachbarzellen derselben Gegend die Liste füllen, muss jeder Ort mindestens 200 km von allen besseren entfernt sein. Deshalb ist Ort Nr. 4 der Liste oft Zellplatz 15 oder 30.",
     "Top 20 (at least 200 km apart)",
     "The 20 best sites per target. So that 20 neighbouring cells of one area do not fill the list, each site must be at least 200 km from every better one. That is why site no. 4 in the list is often cell rank 15 or 30."),
    ("kontinent", "Grundbegriffe", "Bester Ort je Kontinent",
     "Für jedes Ziel die beste Zelle auf jedem Kontinent (Kontinente laut Natural Earth), sortiert nach {g:platz|Zellplatz}. Zeigt, wie weit die beste Alternative außerhalb der führenden Region zurückliegt. In der Zusammenfassung steht je Kontinent der <b>Median über alle Ziele eines Körpers</b>: „Mars: Südamerika 105“ heißt, für ein typisches Mars-Ziel liegt der beste Ort in Südamerika auf Platz 105.",
     "Best site per continent",
     "For each target, the best cell on every continent (continents as in Natural Earth), sorted by {g:platz|rank on Earth}. Shows how far the best alternative outside the leading region falls behind. Summaries give the <b>median over all targets of one body</b> per continent: ‘Mars: South America 105’ means that for a typical Mars target the best South American site is rank 105."),
    ("ohne_china", "Grundbegriffe", "Ohne China",
     "Option für Missionen, bei denen Feldarbeit in China nicht möglich ist. Entfernt alle Zellen innerhalb der De-facto-Grenzen der Volksrepublik China (laut Natural Earth, also einschließlich von China verwalteter umstrittener Gebiete wie Aksai Chin) sowie Hongkong und Macau, und sortiert die Liste neu. Taiwan wird nicht entfernt. Die Bewertung selbst ändert sich nicht.",
     "Exclude China",
     "Option for missions where fieldwork in China is not possible. Removes all cells inside the People's Republic of China's de-facto borders (Natural Earth, so including disputed areas China administers such as Aksai Chin) and Hong Kong and Macau, then re-ranks the list. Taiwan is not removed. The scores themselves do not change."),
    ("bekannt", "Grundbegriffe", "Bekanntes Analog / neu",
     "„Bekannt“: Der Ort liegt im Radius eines etablierten Analog-Standorts aus der Literatur (Liste unter {g:analoga|Bekannte Analoga}). „Neu“: kein bekannter Standort in der Nähe. Das Verfahren kennt diese Liste beim Bewerten nicht; sie dient nur zur Markierung.",
     "Known analog / new",
     "‘Known’: the site lies within the radius of an established analog site from the literature (list under {g:analoga|known analogs}). ‘New’: no known site nearby. The method does not see this list while scoring; it is only used for the label."),
    ("positivkontrolle", "Grundbegriffe", "Positivkontrolle",
     "Prüfung, ob das Verfahren Sinnvolles findet: Etablierte Analoga (Qaidam-Becken, Atacama, Altiplano, Axel Heiberg, Haughton-Krater) tauchen in den Listen auf, obwohl das Verfahren sie nicht kennt. Die Zahl in Klammern ist die Anzahl der Treffer im Radius des jeweiligen Standorts.",
     "Positive control",
     "A check that the method finds sensible places: established analogs (Qaidam Basin, Atacama, Altiplano, Axel Heiberg, Haughton crater) appear in the lists although the method does not know them. The number in brackets is the count of hits within that site's radius."),
    ("heatmap", "Grundbegriffe", "Ähnlichkeitskarte",
     "Die farbige Weltkarte in der Web-App: jede {g:bewertet|bewertete Zelle} nach ihrem Rang eingefärbt, flächengewichtet. Gezeigt werden nur die besten 35 % (ab dem 65. Perzentil), je heller, desto ähnlicher. Die Karte nutzt das gröbere 0,25°-Raster, die Listen das feine 0,05°-Raster.",
     "Similarity map",
     "The coloured world map in the web app: every {g:bewertet|ranked cell} coloured by its rank, area-weighted. Only the best 35 % are shown (from the 65th percentile), brighter is more similar. The map uses the coarser 0.25° grid; the lists use the fine 0.05° grid."),
    ("land", "Grundbegriffe", "Land und umstrittene Gebiete",
     "Ländernamen aus Natural Earth 1:50m (gemeinfrei), nur zur Beschriftung und für den Filter {g:ohne_china}. Natural Earth zeichnet De-facto-Grenzen; umstrittene Gebiete sind gekennzeichnet, z. B. „Aksai Chin (umstritten; verwaltet: Volksrepublik China)“.",
     "Country and disputed areas",
     "Country names from Natural Earth 1:50m (public domain), only for labels and the {g:ohne_china|Exclude China} filter. Natural Earth draws de-facto borders; disputed areas are marked, e.g. ‘Aksai Chin (disputed; administered by China)’."),
    # ---------------------------------------------------------------- Bewertung
    ("merkmal", "Bewertung", "Merkmal",
     "Eine messbare Größe, die Ziel und Erdzelle gemeinsam haben, z. B. Hangneigung, Albedo oder Niederschlag. Liste unter {g:merkmale|Merkmale}. Jedes Merkmal gehört zu einer {g:dimension} und wird mit einer von drei Methoden verglichen ({g:methode_direkt}, {g:methode_rang}, {g:methode_richtung}).",
     "Feature",
     "A measurable quantity that target and Earth cell share, e.g. slope, albedo or precipitation (list under {g:merkmale|features}). Each feature belongs to a {g:dimension} and is compared with one of three methods ({g:methode_direkt|value against value}, {g:methode_rang|rank against rank}, {g:methode_richtung|beyond Earth's range})."),
    ("dimension", "Bewertung", "Dimension",
     "Eine Gruppe von Merkmalen, die zusammen eine Eigenschaft beschreiben, z. B. „Gelände“ aus mittlerer und steiler Neigung und Relief. Die Note einer Dimension ist das gewichtete Mittel ihrer {g:teilnote|Teilnoten}. Neun Dimensionen: Gelände, Oberflächenmaterial, Temperatur, Trockenheit, Atmosphäre, Staub & Wind, Eis & Wasser, Vegetation, Beleuchtung.",
     "Dimension",
     "A group of features describing one property, e.g. ‘Terrain’ from median and steep slope and relief. A dimension's score is the weighted mean of its {g:teilnote|match scores}. Nine dimensions: terrain, surface material, temperature, dryness, atmosphere, dust & wind, ice & water, vegetation, sunlight."),
    ("teilnote", "Bewertung", "Teilnote (Match)",
     "Wie gut eine Erdzelle bei einem Merkmal zum Ziel passt, von 0 bis 1. 1 heißt: so nah, wie es auf der Erde geht. Wie sie berechnet wird, hängt von der Methode ab ({g:methode_direkt}, {g:methode_rang}, {g:methode_richtung}).",
     "Match score",
     "How well an Earth cell matches the target for one feature, from 0 to 1; 1 means as close as Earth gets. How it is computed depends on the method ({g:methode_direkt|value against value}, {g:methode_rang|rank against rank}, {g:methode_richtung|beyond Earth's range})."),
    ("methode_direkt", "Bewertung", "Wert gegen Wert",
     "Für dieselbe Größe, mit derselben Methode gemessen (Gelände: Neigung und Relief aus Höhenmodellen mit demselben Code). Teilnote = 1 − |Erdwert − Zielwert| / Spanne, wobei die Spanne der größere Abstand des Zielwerts zum 2. oder 98. Perzentil der Erde ist.",
     "Value against value",
     "For the same quantity measured the same way (terrain: slope and relief from elevation models with the same code). Match = 1 − |Earth value − target value| / span, where span is the larger distance of the target value to Earth's 2nd or 98th percentile."),
    ("methode_rang", "Bewertung", "Rang gegen Rang",
     "Für Größen, die auf Ziel und Erde mit verschiedenen Instrumenten gemessen werden (Albedo, thermische Trägheit). Verglichen wird nicht der Wert, sondern die Stellung auf dem eigenen Körper: Ein Ort, der heller ist als 41 % des Mars, passt zu Erdland, das heller ist als 41 % des kahlen Erdlands. Siehe {g:koerper_perzentil}.",
     "Rank against rank",
     "For quantities measured with different instruments on target and Earth (albedo, thermal inertia). Not the value is compared but the standing on its own body: a site brighter than 41 % of Mars matches Earth land brighter than 41 % of Earth's bare land. See {g:koerper_perzentil|body percentile}."),
    ("methode_richtung", "Bewertung", "Richtung („jenseits der Erde“)",
     "Für Werte, die die Erde nie erreicht: Vakuum, 6 hPa Luftdruck, −170 °C, kein Niederschlag, Sonne knapp über dem Horizont. Teilnote = Anteil des Erdlands, das weiter vom Ziel entfernt ist: „niedriger als 91 % des Erdlands“ ergibt 0,91. Je näher an den Zielwert, desto besser.",
     "Beyond Earth's range",
     "For values Earth never reaches: vacuum, 6 hPa air pressure, −170 °C, no precipitation, the Sun just above the horizon. Match = share of Earth's land that is further from the target: ‘lower than 91 % of Earth's land’ gives 0.91. The closer to the target value, the better."),
    ("koerper_perzentil", "Bewertung", "Körper-Perzentil",
     "Der Anteil der Oberfläche eines Himmelskörpers mit kleinerem Wert, flächengewichtet. Beispiel: Jezero hat eine thermische Trägheit von 304 TIU, das ist mehr als bei 89 % der Marsoberfläche (Perzentil 0,89). Auf der Erde wird gegen kahles, eisfreies Land gerechnet (Datei common/body_percentile.py).",
     "Body percentile",
     "Share of a body's surface with a lower value, area-weighted. Example: Jezero has a thermal inertia of 304 TIU, more than 89 % of Mars's surface (percentile 0.89). On Earth the reference is bare, ice-free land (common/body_percentile.py)."),
    ("verlaesslichkeit", "Bewertung", "Verlässlichkeit A / B / C",
     "Note für jeden Zielwert und jedes Erd-Merkmal: <b>A</b> direkte Messung, <b>B</b> grob aufgelöst oder abgeleitet, <b>C</b> grobe Schätzung. Daraus ergibt sich das {g:gewicht}: A = 1, B = 0,7, C = 0,4, multipliziert für Ziel und Erde. Ein Merkmal mit Ziel C und Erde C zählt also nur 0,16.",
     "Reliability grade A / B / C",
     "Grade for every target value and Earth feature: <b>A</b> direct measurement, <b>B</b> coarse or derived, <b>C</b> rough estimate. It sets the {g:gewicht|weight}: A = 1, B = 0.7, C = 0.4, multiplied for target and Earth. A feature graded C on the target and C on Earth counts only 0.16."),
    ("gewicht", "Bewertung", "Gewicht",
     "Wie stark ein Merkmal in seine {g:dimension} eingeht: Verlässlichkeit des Zielwerts × Verlässlichkeit des Erd-Merkmals (siehe {g:verlaesslichkeit}). In der Web-App steht es im Hinweis über dem Balken jeder Teilnote.",
     "Weight",
     "How much a feature counts within its {g:dimension}: reliability of the target value × reliability of the Earth feature (see {g:verlaesslichkeit|reliability grade}). In the web app it is shown when hovering a match bar."),
    ("konfidenz", "Bewertung", "Konfidenz einer Dimension",
     "Das mittlere {g:gewicht} der vorhandenen Merkmale einer Dimension. Dimensionen aus unsicheren Werten (z. B. nur Note C) zählen im {g:gesamtwert} entsprechend weniger.",
     "Dimension confidence",
     "The mean {g:gewicht|weight} of a dimension's available features. Dimensions built from uncertain values (e.g. only grade C) count correspondingly less in the {g:gesamtwert|overall score}."),
    ("gesamtwert", "Bewertung", "Gesamtwert",
     "Eine Zahl von 0 bis 1 je Zelle, nur zum Sortieren: gewichtetes Mittel der Dimensionsnoten, Gewicht = Dimensionsgewicht des {g:profil|Profils} × {g:konfidenz}. Er bestimmt den {g:platz}. Aussagekräftiger als die Zahl ist das Profil der Dimensionen.",
     "Overall score",
     "A number from 0 to 1 per cell, used only for sorting: weighted mean of the dimension scores, weight = the {g:profil|profile}'s dimension weight × {g:konfidenz|confidence}. It sets the {g:platz|rank on Earth}. The profile of dimensions says more than the number."),
    ("profil", "Bewertung", "Profil (Gewichte je Zieltyp)",
     "Jedes Ziel gehört zu einem von drei Profilen; das Profil legt fest, wie stark jede {g:dimension} im {g:gesamtwert} zählt (0 = gar nicht). Tabelle unten.",
     "Target profile (weights)",
     "Each target belongs to one of three profiles; the profile sets how much each {g:dimension} counts in the {g:gesamtwert|overall score} (0 = not at all). Table below."),
    ("abdeckung", "Bewertung", "Datenabdeckung („of the profile has data“)",
     "Anteil des Profilgewichts, für das die Erdzelle Werte hat. 100 % heißt: Für jede gewichtete Dimension liegen Daten vor.",
     "Profile with data",
     "Share of the profile's weight for which the Earth cell has values; 100 % means data for every weighted dimension."),
    ("mindestabdeckung", "Bewertung", "Mindestabdeckung 80 %",
     f"Eine Zelle kommt nur ins Ranking, wenn sie mindestens {MIN_COVERAGE:.0%} des Gewichts der Dimensionen belegt, für die das Ziel Werte hat. Sonst kämen Zellen mit Datenlücken nach oben, weil fehlende Dimensionen einfach weggelassen würden.".replace(".", ",", 0),
     "Minimum coverage 80 %",
     f"A cell only enters the ranking if it covers at least {MIN_COVERAGE:.0%} of the weight of the dimensions the target has values for. Otherwise cells with data gaps would rise, because missing dimensions would simply be left out."),
    ("eigene_gewichtung", "Bewertung", "Eigene Gewichtung und Klassenfilter (Web-App)",
     "In der Web-App lässt sich die Rangliste anpassen: <b>Environment</b> blendet {g:klasse|Umgebungsklassen} aus, <b>Most important</b> macht eine {g:dimension} dreimal so wichtig wie die stärkste Dimension des {g:profil|Profils}, <b>Adjust weights</b> stellt jede Dimension einzeln ein (0 = ignorieren). Die Liste wird dann im Browser aus dem {g:kandidatenpool} neu berechnet, wieder mit mindestens 200 km Abstand. Mit eigener Gewichtung gibt es keinen {g:platz} auf der ganzen Erde, deshalb zeigt die Liste dann den eigenen Gesamtwert (0 bis 1). Die {g:heatmap|Ähnlichkeitskarte} bleibt bei der Standardgewichtung.",
     "Custom weights and class filter (web app)",
     "The ranking can be adjusted in the web app: <b>Environment</b> hides {g:klasse|environment classes}, <b>Most important</b> makes one {g:dimension} three times as important as the profile's strongest dimension, <b>Adjust weights</b> sets each dimension separately (0 = ignore). The list is then recomputed in the browser from the {g:kandidatenpool|candidate pool}, again at least 200 km apart. With custom weights there is no {g:platz|rank on Earth}, so the list shows the custom overall score (0 to 1). The {g:heatmap|similarity map} keeps the default weighting."),
    ("kandidatenpool", "Bewertung", "Kandidatenpool",
     "Je Ziel rund 1.300 Erdzellen mit allen Teilnoten, die das Scoring für die Web-App mitliefert: die besten 600 nach Gesamtwert, je Dimension die besten 80, je Kontinent die besten 25, je Umgebungsklasse die besten 30 und die besten 200 außerhalb Chinas. Aus ihnen berechnet die App eigene Gewichtungen und Filter, ohne die 8,9 Millionen Zellen laden zu müssen. Für extreme Gewichtungen kann eine Zelle außerhalb des Pools fehlen; für Regler zwischen 0 und dem Dreifachen ist der Pool groß genug.",
     "Candidate pool",
     "About 1,300 Earth cells per target with all match scores, exported by the scoring for the web app: the best 600 overall, the best 80 per dimension, 25 per continent, 30 per environment class and the best 200 outside China. The app computes custom weights and filters from them without loading 8.9 million cells. With extreme weights a cell outside the pool can be missing; for sliders between 0 and three times the default the pool is large enough."),
    ("robustheit", "Bewertung", "Robustheit",
     "Wie oft ein Ort in den {g:top20} bleibt, wenn sich die Gewichte ändern: 1.000 zufällige Gewichtungen, jedes Dimensionsgewicht des {g:profil|Profils} mit einem Faktor zwischen 0,5 und 1,5 multipliziert; je Gewichtung wird die Top-20-Liste aus dem {g:kandidatenpool} neu gebildet. Gezählt wird, ob der Ort oder ein Ort im Umkreis von 50 km darin vorkommt. 94 % heißt: Der Treffer hängt kaum an der genauen Gewichtung. Unter 50 % heißt: Er steht nur bei bestimmten Gewichtungen oben.",
     "Robustness",
     "How often a site stays in the {g:top20|top 20} when the weights change: 1,000 random weightings, each dimension weight of the {g:profil|profile} multiplied by a factor between 0.5 and 1.5; for each one the top 20 is rebuilt from the {g:kandidatenpool|candidate pool}. It counts whether the site or a site within 50 km is in it. 94 % means the match hardly depends on the exact weighting; below 50 % means it only comes out on top under some weightings."),
    ("steckbrief", "Bewertung", "Steckbrief (Site profile)",
     "Genauerer Blick auf die besten Orte (alle verschiedenen Orte unter den Top 3 jedes Ziels, dazu der beste ohne China und die besten drei Kontinent-Sieger): Satellitenbild (Landsat-WELD-Jahresmosaik der NASA, 30 m), Geländeschummerung aus dem Copernicus-Höhenmodell mit 90 m und die Neigungsverteilung der 5-km-Zelle gegen ihre Umgebung (20 × 20 km). Daran sieht man, ob die Zelle einheitlich ist oder ob ihr Mittelwert Steilhänge und Ebenen mischt.",
     "Site profile",
     "A closer look at the best sites (all distinct sites among the top 3 of each target, plus the best without China and the best three continent winners): satellite image (NASA Landsat WELD annual mosaic, 30 m), hillshade from the Copernicus DEM at 90 m and the slope distribution of the 5 km cell against its surroundings (20 × 20 km). It shows whether the cell is uniform or whether its average mixes cliffs and plains."),
    ("passt_bricht", "Bewertung", "Stärkste / schwächste Dimension",
     "Die {g:dimension} mit der höchsten bzw. niedrigsten Note für diesen Ort: wo die Analogie am besten trägt („passt“, „Strongest“) und wo sie bricht („bricht“, „Weakest“).",
     "Strongest / weakest dimension",
     "The {g:dimension} with the highest or lowest score at this site: where the analogy holds best (‘Strongest’) and where it breaks (‘Weakest’)."),
    ("klasse", "Umgebungsklassen", "Umgebungsklasse",
     "Eine Einordnung jeder Erdzelle in eine von zehn Landschaftstypen nach festen Regeln. Die Klassen werden <b>in fester Reihenfolge</b> geprüft (wie unten aufgeführt); die erste, deren Regeln alle zutreffen, gewinnt. Eine Regel mit „oder“ ist eine Alternative zur Zeile davor. Die Klasse fließt nicht in den Gesamtwert ein; sie beschreibt den Ort.",
     "Environment class",
     "Every Earth cell is put into one of ten landscape types by fixed rules. Classes are tested <b>in a fixed order</b> (as listed below); the first whose rules all hold wins. A rule starting with ‘or’ is an alternative to the line above. The class does not enter the overall score; it describes the site."),
    ("flag", "Zusatzeigenschaften", "Zusatzeigenschaft",
     "Merkmale, die zusätzlich zur Klasse am Ort stehen; ein Ort kann mehrere haben. Sie fließen nicht in den Gesamtwert ein.",
     "Flag",
     "Properties shown in addition to the class; a site can have several. They do not enter the overall score."),
    ("merkmale", "Merkmale", "Merkmale im Überblick",
     "Die Größen, die Ziel und Erde vergleichbar machen. Je Merkmal: was es misst, woher die Erdwerte und die Zielwerte kommen, mit welcher Methode verglichen wird. Einheiten: K Kelvin (0 °C = 273,15 K), hPa Hektopascal, TIU = J m⁻² K⁻¹ s⁻½.",
     "Features at a glance",
     "The quantities that make target and Earth comparable. For each: what it measures, where Earth and target values come from, which method compares them. Units: K kelvin (0 °C = 273.15 K), hPa hectopascal, TIU = J m⁻² K⁻¹ s⁻½."),
    # ---------------------------------------------------------------- Zielorte
    ("zielquadrat", "Zielorte", "Zielquadrat",
     "Jedes Ziel ist ein Quadrat um die Koordinate der Ortsliste: 10 × 10 km auf dem Mars, 15 × 15 km am Mond. Die Zielwerte sind Mediane (bzw. Statistiken) über dieses Quadrat.",
     "Target box",
     "Each target is a square around the site list's coordinate: 10 × 10 km on Mars, 15 × 15 km on the Moon. Target values are medians (or statistics) over this square."),
    ("artemis", "Zielorte", "Artemis-Regionen und Kraterrand",
     "Die NASA-Kandidatenregionen für Artemis III sind beleuchtete Flächen am Rand von Kratern. Die Ortsliste nennt oft den Kratermittelpunkt, der im Dauerschatten liegt. Deshalb wird das Zielquadrat auf den hellsten Ausschnitt (mittlere LOLA-Sonnensichtbarkeit) in der Nähe gelegt: innerhalb 12 km, bei Kraterregionen (Haworth, Nobile, de Gerlache, Faustini, Slater) innerhalb Kraterradius + 10 km.",
     "Artemis regions and crater rims",
     "NASA's Artemis III candidate regions are sunlit areas on crater rims. The site list often gives the crater centre, which lies in permanent shadow. So the target box is placed on the best-lit square nearby (mean LOLA sun visibility): within 12 km, for crater regions (Haworth, Nobile, de Gerlache, Faustini, Slater) within crater radius + 10 km."),
    ("koordinaten", "Zielorte", "Koordinatenqualität",
     "„verified“: genaue, veröffentlichte Koordinate (z. B. Curiosity-Landestelle Bradbury Landing). „approx.“: Näherung (gerundet oder Regionsmitte). „unverified“: Quelle unsicher. Angezeigt in der Zielliste der Web-App.",
     "Coordinate quality",
     "‘verified’: exact published coordinate (e.g. Curiosity's Bradbury Landing). ‘approx.’: approximate (rounded or region centre). ‘unverified’: uncertain source. Shown in the web app's target list."),
    ("psr", "Zielorte", "Dauerschatten (PSR)",
     "Permanently shadowed region: Krater am Mondpol, deren Boden nie Sonne bekommt (unter 110 K, teils unter 40 K). Dort ist Wassereis stabil. Ziele: Shackleton-Krater, Cabeus. Kein Ort der Erde ist so kalt.",
     "Permanently shadowed region (PSR)",
     "Craters at the lunar poles whose floors never see the Sun (below 110 K, partly below 40 K), where water ice is stable. Targets: Shackleton crater, Cabeus. No place on Earth is that cold."),
    # ---------------------------------------------------------------- Daten
    ("modis", "Daten", "MODIS (NASA)",
     "Instrument auf den NASA-Satelliten Terra und Aqua. Genutzt: Oberflächentemperatur zu vier Tageszeiten (MOD11C3/MYD11C3), Albedo auch schneefrei (MCD43C3), Landbedeckung (MCD12C1), Vegetationsindex NDVI (MOD13C2), Schnee (MOD10CM). 0,05°, 2003–2024.",
     "MODIS (NASA)",
     "Instrument on NASA's Terra and Aqua satellites. Used: surface temperature at four times of day (MOD11C3/MYD11C3), albedo incl. snow-free (MCD43C3), land cover (MCD12C1), vegetation index NDVI (MOD13C2), snow (MOD10CM). 0.05°, 2003–2024."),
    ("merra2", "Daten", "MERRA-2 (NASA)",
     "Atmosphären-Reanalyse der NASA (ca. 55 km Raster): Staubtrübung, Staubemission, Staubsturm- und Sturmtage, Wind, Luftdruck, Feuchte, Niederschlag (PRECTOTCORR). Regional, nicht lokal: Gebirge und Täler in einer Rasterzelle haben denselben Wert.",
     "MERRA-2 (NASA)",
     "NASA atmospheric reanalysis (about 55 km grid): dust optical depth, dust emission, dust-storm and gale days, wind, pressure, humidity, precipitation (PRECTOTCORR). Regional, not local: mountains and valleys in one grid cell share a value."),
    ("copernicus", "Daten", "Copernicus DEM GLO-90 (ESA)",
     "Globales Höhenmodell mit 90 m Pixeln. Daraus Hangneigung und Relief der Erdzellen, vergröbert auf 100 m bzw. 463 m wie die Ziele.",
     "Copernicus DEM GLO-90 (ESA)",
     "Global elevation model with 90 m pixels; gives slope and relief of the Earth cells, coarsened to 100 m or 463 m like the targets."),
    ("mola", "Daten", "MOLA (NASA, Mars)",
     "Laser-Höhenmesser des Mars Global Surveyor. Mosaik mit 463 m Pixeln (USGS) für das Gelände der Mars-Ziele; die Kartendarstellung in der App nutzt das MEGDR-Produkt mit 4 Pixeln pro Grad (NASA PDS).",
     "MOLA (NASA, Mars)",
     "Mars Global Surveyor's laser altimeter. 463 m mosaic (USGS) for the Mars targets' terrain; the app's Mars map uses the MEGDR product at 4 pixels per degree (NASA PDS)."),
    ("lola", "Daten", "LOLA (NASA, Mond)",
     "Laser-Höhenmesser des Lunar Reconnaissance Orbiter. Polares Höhenmodell LDEM_80S_80M (80 m) für das Gelände der Mond-Ziele und die Mondkarte; Sonnensichtbarkeit für die Lage der {g:artemis|Artemis-Regionen}.",
     "LOLA (NASA, Moon)",
     "Lunar Reconnaissance Orbiter's laser altimeter. Polar elevation model LDEM_80S_80M (80 m) for the Moon targets' terrain and the Moon map; sun visibility for placing the {g:artemis|Artemis regions}."),
    ("tes", "Daten", "TES (NASA, Mars)",
     "Thermal Emission Spectrometer des Mars Global Surveyor: thermische Trägheit nachts (Putzig & Mellon 2007, NASA PDS, 3 km) und Lambert-Albedo (USGS-Mosaik, 7,4 km).",
     "TES (NASA, Mars)",
     "Mars Global Surveyor's Thermal Emission Spectrometer: night-time thermal inertia (Putzig & Mellon 2007, NASA PDS, 3 km) and Lambert albedo (USGS mosaic, 7.4 km)."),
    ("diviner", "Daten", "Diviner (NASA, Mond)",
     "Radiometer des Lunar Reconnaissance Orbiter. Polar Resource Product: Oberflächentemperaturen und Tiefe, in der Wassereis stabil ist, als 240-m-Raster für 85–90° S (aufbereitet vom Mond/Mars-Team).",
     "Diviner (NASA, Moon)",
     "Lunar Reconnaissance Orbiter's radiometer. Polar Resource Product: surface temperatures and the depth at which water ice is stable, as a 240 m grid for 85–90° S (prepared by the Moon/Mars team)."),
    ("natural_earth", "Daten", "Natural Earth",
     "Gemeinfreie Ländergrenzen und Kontinente (1:50m, 1:110m). Nur Beschriftung, Filter {g:ohne_china} und Grundkarte; keine Messdaten.",
     "Natural Earth",
     "Public-domain country borders and continents (1:50m, 1:110m). Only labels, the {g:ohne_china|Exclude China} filter and the base map; no measurements."),
    # ---------------------------------------------------------------- Projektseite
    ("meilensteine", "Projektseite", "Meilensteine",
     "M1 (Sa 20:00) Erddaten und Schnittstelle, M2 (So 13:00) Ergebnisse vollständig und Web-App, M3 (So 22:00) Story, Demo und Einreichung vorbereitet, Abgabe So 23:59. Der Countdown zählt bis zur Abgabe.",
     "Milestones",
     "M1 (Sat 20:00) Earth data and interface, M2 (Sun 13:00) results complete and web app, M3 (Sun 22:00) story, demo and submission ready, deadline Sun 23:59."),
    ("todo", "Projektseite", "To-do-Liste",
     "Gemeinsame Aufgabenliste auf der Projektseite. Jede Aufgabe hat eine <b>Gruppe</b> (Abgabe, Daten & Methode, Optional, Erledigt oder eine eigene, über „Neue Gruppe …“ angelegt) und eine <b>Priorität</b> (hoch, mittel, niedrig). Sortieren lässt sich nach Gruppe (innerhalb: offen vor erledigt, dann nach Priorität) oder nach Priorität (erledigte Aufgaben gesammelt am Ende); „Erledigte ausblenden“ blendet abgehakte aus. Ansehen kann jeder; Ändern verlangt den {g:teamlogin}.",
     "To-do list",
     "Shared task list on the project page. Each task has a <b>group</b> (submission, data & method, optional, done, or a custom one) and a <b>priority</b> (high, medium, low); the list can be sorted by group or by priority. Anyone can view it; changes need the {g:teamlogin|team login}."),
    ("teamlogin", "Projektseite", "Team-Login",
     "Benutzername und Passwort, die der Browser beim ersten Ändern der To-do-Liste abfragt (HTTP Basic Auth). Zugänge legt Vicente auf dem Server an. Die Seite läuft ohne HTTPS: ein eigenes Passwort verwenden, das sonst nirgends genutzt wird.",
     "Team login",
     "User name and password the browser asks for the first time the to-do list is changed (HTTP basic auth). Vicente creates the accounts on the server. The page has no HTTPS: use a password not used anywhere else."),
]

# features: (key, title de, text de, title en, text en, unit hint)
FEAT_TXT = {
    "slope_p50": ("Hangneigung, Median", "Mittlere Steilheit des Geländes im Zielquadrat bzw. in der Erdzelle, berechnet aus dem Höhenmodell, das vorher auf die Pixelgröße des Ziels vergröbert wird (100 m Mond, 463 m Mars). Erde: Copernicus GLO-90; Mars: MOLA; Mond: LOLA; überall derselbe Code (common/terrain.py).",
                  "Slope, median", "Typical steepness of the ground in the target box or Earth cell, from the elevation model coarsened to the target's pixel size first (100 m Moon, 463 m Mars). Earth: Copernicus GLO-90; Mars: MOLA; Moon: LOLA; the same code everywhere (common/terrain.py)."),
    "slope_p90": ("Hangneigung, 90. Perzentil", "Wie steil die steilsten 10 % der Fläche sind: Maß für Hindernisse bei Landung und Fahrt. Berechnung wie beim Median.",
                  "Slope, 90th percentile", "How steep the steepest 10 % of the area are: a measure of obstacles for landing and driving. Computed like the median."),
    "relief": ("Relief (P95−P5, 5 km)", "Höhenspanne zwischen dem 5. und 95. Perzentil der Höhe in 5-km-Fenstern: wie hügelig oder zerklüftet die Gegend ist.",
               "Relief (P95−P5, 5 km)", "Elevation span between the 5th and 95th percentile within 5 km windows: how hilly or rugged the area is."),
    "albedo": ("Albedo", "Anteil des reflektierten Sonnenlichts (0 schwarz, 1 weiß). Erde: MODIS, schneefrei; Mars: TES-Lambert-Albedo. Verglichen über den {g:methode_rang|Rang}, weil die Instrumente verschiedene Wellenlängen messen.",
               "Albedo", "Share of sunlight reflected (0 black, 1 white). Earth: MODIS, snow-free; Mars: TES Lambert albedo. Compared by {g:methode_rang|rank} because the instruments measure different wavelengths."),
    "thermal_inertia": ("Thermische Trägheit", "Wie träge eine Oberfläche ihre Temperatur ändert: Staub und Sand niedrig, Fels hoch. Mars: TES, nachts (TIU). Erde: scheinbare thermische Trägheit ATI = (1 − Albedo) / Tagesgang der Temperatur (1/K). Verglichen über den {g:methode_rang|Rang}.",
                        "Thermal inertia", "How slowly a surface changes temperature: dust and sand low, rock high. Mars: TES, night-time (TIU). Earth: apparent thermal inertia ATI = (1 − albedo) / day-night temperature range (1/K). Compared by {g:methode_rang|rank}."),
    "dust_opacity": ("Staubtrübung", "Wie stark Staub in der Luft das Licht schwächt (optische Dicke, AOD). Erde: MERRA-2. Für den Mars noch kein Zielwert.",
                     "Dust opacity", "How much airborne dust dims the light (optical depth, AOD). Earth: MERRA-2. No Mars target value yet."),
    "dust_storm_days": ("Staubsturmtage", "Tage pro Jahr mit Staub-AOD über 1,0 (MERRA-2, Tageswerte 2003–2024).",
                        "Dust storm days", "Days per year with dust AOD above 1.0 (MERRA-2, daily values 2003–2024)."),
    "wind_mean": ("Mittlerer Wind", "Mittlere Windgeschwindigkeit am Boden (MERRA-2), m/s. Mond: 0 (kein Wind).",
                  "Mean wind", "Mean surface wind speed (MERRA-2), m/s. Moon: 0 (no wind)."),
    "surface_temp_mean": ("Mittlere Oberflächentemperatur", "Mittel der Bodentemperatur aus vier MODIS-Überflügen pro Tag, 2003–2024 (K). Mond: Diviner; Mars: Schätzwert (Note C).",
                          "Mean surface temperature", "Mean ground temperature from four MODIS overpasses per day, 2003–2024 (K). Moon: Diviner; Mars: estimate (grade C)."),
    "surface_temp_min": ("Kältester Monat", "Mittlere nächtliche Bodentemperatur im kältesten Monat (MODIS, K).",
                         "Coldest month", "Mean night-time ground temperature in the coldest month (MODIS, K)."),
    "diurnal_range": ("Tagesgang", "Unterschied zwischen wärmster und kältester der vier täglichen MODIS-Messungen, gemittelt (K). Mars: Schätzwert (Note C).",
                      "Day-night range", "Difference between the warmest and coldest of the four daily MODIS measurements, averaged (K). Mars: estimate (grade C)."),
    "pressure": ("Luftdruck", "Bodenluftdruck (MERRA-2, hPa). Mars: grobe Schätzung aus der MOLA-Höhe (6,1 hPa · e^(−Höhe/11,1 km), Note C); Mond: Vakuum.",
                 "Surface pressure", "Surface air pressure (MERRA-2, hPa). Mars: rough estimate from MOLA elevation (6.1 hPa · e^(−height/11.1 km), grade C); Moon: vacuum."),
    "humidity": ("Luftfeuchte", "Spezifische Feuchte in 2 m Höhe (MERRA-2, g Wasserdampf pro kg Luft).",
                 "Humidity", "Specific humidity at 2 m (MERRA-2, g of water vapour per kg of air)."),
    "precip": ("Niederschlag", "Jahresniederschlag (MERRA-2 PRECTOTCORR, mm/Jahr). Mars und Mond: 0.",
               "Precipitation", "Yearly precipitation (MERRA-2 PRECTOTCORR, mm/yr). Mars and Moon: 0."),
    "ndvi": ("Vegetationsindex (NDVI)", "Wie grün eine Fläche ist (MODIS, Jahresmittel): unter 0,1 kahl, über 0,3 deutlich bewachsen. Mars und Mond: 0.",
             "Vegetation (NDVI)", "How green an area is (MODIS, yearly mean): below 0.1 bare, above 0.3 clearly vegetated. Mars and Moon: 0."),
    "ground_ice": ("Bodeneis", "Mond: Anteil der Fläche, auf der Wassereis in höchstens 1 m Tiefe stabil ist (Diviner). Erde: grobe Näherung aus der Jahresmitteltemperatur ((272,15 K − T) / 7, auf 0–1 begrenzt, Note C). Mars: Schätzwert.",
                   "Ground ice", "Moon: share of the area where water ice is stable within 1 m depth (Diviner). Earth: rough proxy from mean yearly temperature ((272.15 K − T) / 7, limited to 0–1, grade C). Mars: estimate."),
    "sun_elevation_max": ("Höchster Sonnenstand", "Größte Höhe der Sonne über dem Horizont im Jahr: 90° − |Breite| + Achsneigung (Erde 23,44°, Mars 25,19°, Mond 1,54°). Am Mond-Südpol nur wenige Grad, auf der Erde nie unter 23,4°.",
                          "Highest sun elevation", "Highest elevation of the Sun above the horizon over the year: 90° − |latitude| + axial tilt (Earth 23.44°, Mars 25.19°, Moon 1.54°). Only a few degrees at the lunar south pole, never below 23.4° on Earth."),
}
METHOD_NAME = {"de": {"direct": "Wert gegen Wert", "quantile": "Rang gegen Rang", "direction": "Richtung"},
               "en": {"direct": "value against value", "quantile": "rank against rank", "direction": "beyond Earth's range"}}
METHOD_ID = {"direct": "methode_direkt", "quantile": "methode_rang", "direction": "methode_richtung"}
DIM_NAME = {"de": {"gelaende": "Gelände", "oberflaeche": "Oberflächenmaterial", "thermik": "Temperatur", "trockenheit": "Trockenheit",
                   "atmosphaere": "Atmosphäre", "staub_wind": "Staub & Wind", "eis_wasser": "Eis & Wasser", "leben": "Vegetation",
                   "beleuchtung": "Beleuchtung"},
            "en": {"gelaende": "Terrain", "oberflaeche": "Surface material", "thermik": "Temperature", "trockenheit": "Dryness",
                   "atmosphaere": "Atmosphere", "staub_wind": "Dust & wind", "eis_wasser": "Ice & water", "leben": "Vegetation",
                   "beleuchtung": "Sunlight"}}
CLASS_EN = {"eisschild": ("Ice sheet & glacier", "Snow or ice all year.", "Mars polar caps, ice in lunar cold traps (as an ice process, not as terrain)."),
            "salzpfanne": ("Salt flat / evaporite", "Very flat, bright, vegetation-free: dried-out salt lakes.", "Chloride and sulfate deposits on Mars (e.g. Meridiani, Terra Sirenum)."),
            "duenenfeld": ("Dune field / sand sea", "Vegetation-free wind-blown sand: low thermal inertia, medium albedo, dry.", "Martian dunes and wind processes (e.g. Bagnold dunes in Gale crater)."),
            "dunkel_vulkanisch": ("Dark bare rock (basalt, lava)", "Snow-free albedo below 0.15 without vegetation: basalt, lava fields, volcanic ash.", "Basaltic plains on Mars and lunar maria; lava-tube regions."),
            "kalte_polarwueste": ("Ice-free cold polar desert", "Cold, dry, hardly any vegetation, snow-free in summer.", "Martian mid-latitudes with ground ice; regolith of the lunar polar regions."),
            "hochplateau": ("Arid high plateau", "Above 3000 m, dry and barren: low pressure, large day-night range, strong UV.", "Mars: thin air, strong temperature swings, UV (e.g. Altiplano, Chang Tang)."),
            "hyperarid": ("Hyperarid desert", "Below 50 mm of precipitation a year, practically vegetation-free.", "Dryness and oxidation of Martian soil; the limit of life (e.g. Atacama core)."),
            "raues_gebirge": ("Barren steep terrain", "Mean slope above 15° without notable vegetation.", "Crater rims, canyon walls (Valles Marineris), crater rims at the lunar south pole."),
            "aride_wueste": ("Arid desert / semi-desert", "Below 250 mm of precipitation and sparse vegetation, without the properties above.", "General desert analog for instrument tests and mobility."),
            "kein_analog": ("Bare, but no class matched", "Among the ranked (vegetation-free) sites: bare ground that fits none of the classes above, mostly because it is wetter (e.g. over 400 mm of precipitation) or milder. Elsewhere: vegetated, wet or mostly water.", "–")}
FLAG_EN = {"staubquelle": ("Dust source", "Dust emission in the top 5 % of land areas (MERRA-2)."),
           "staubsturmreich": ("Frequent dust storms", "At least 10 dust-storm days a year (dust AOD above 1)."),
           "windsturmreich": ("Frequent gales", "At least 5 gale days a year (wind above 17 m/s)."),
           "windstill": ("Calm", "Little wind and no storms (mean wind below 3 m/s): stable conditions as on the Moon."),
           "frost_tau": ("Freeze-thaw", "At least 3 months a year with freeze-thaw cycles."),
           "extrem_kalt": ("Extreme cold", "Coldest month below 220 K (−53 °C) at night."),
           "niedriger_druck": ("Low pressure", "Air pressure below 700 hPa (roughly above 3000 m)."),
           "dunkle_oberflaeche": ("Dark surface", "Snow-free albedo below 0.15 on vegetation-free ground (basalt, lava, ash)."),
           "landefreundlich": ("Landing-friendly", "At least 80 % of the area below 5° slope, 90th-percentile slope below 8°."),
           "polar": ("Polar light", "Inside the polar circle: polar day and night, low sun as at the lunar south pole.")}
CLASS_DE_FIX = {"Duenenfeld": "Dünenfeld", "Polarwueste": "Polarwüste", "Wueste": "Wüste", "Halbwueste": "Halbwüste",
                "Gelaende": "Gelände", "Oberflaeche": "Oberfläche", "Kaelte": "Kälte", "Traegheit": "Trägheit", "ae": "ä"}


def de_text(s):
    """Umlaute in den ASCII-Texten aus categories.py wiederherstellen (nur bekannte Muster)."""
    for a, b in [("Duenen", "Dünen"), ("wueste", "wüste"), ("Wueste", "Wüste"), ("ueber", "über"), ("Ueber", "Über"),
                 ("Gelaende", "Gelände"), ("Oberflaeche", "Oberfläche"), ("Kaelte", "Kälte"), ("Traegheit", "Trägheit"),
                 ("traegheit", "trägheit"), ("Kraterraender", "Kraterränder"), ("Canyonwaende", "Canyonwände"),
                 ("Geraete", "Geräte"), ("ganzjaehrig", "ganzjährig"), ("Ganzjaehrig", "Ganzjährig"), ("Kaeltefallen", "Kältefallen"),
                 ("aeolische", "äolische"), ("Lavaroehren", "Lavaröhren"), ("Duenne", "Dünne"), ("duenne", "dünne"),
                 ("Atmosphaere", "Atmosphäre"), ("Temperaturwechsel", "Temperaturwechsel"), ("Sueden", "Süden"),
                 ("Suedpol", "Südpol"), ("Staerke", "Stärke"), ("Stuerme", "Stürme"), ("Flaeche", "Fläche"),
                 ("flaechen", "flächen"), ("Kaeltester", "Kältester"), ("naeher", "näher"), ("fuer", "für"),
                 ("Mittelbreiten", "Mittelbreiten"), ("Tau-Wechsel", "Tau-Wechsel"), ("Luftdruck", "Luftdruck"),
                 ("ueberwiegend", "überwiegend"), ("Vegetationsfreiheit", "Vegetationsfreiheit"), ("Hoehe", "Höhe")]:
        s = s.replace(a, b)
    return s


def _link(text, lang, base):
    """{g:id} or {g:id|label} -> link to that entry."""
    import re
    titles = {e[0]: (e[2] if lang == "de" else e[4]) for e in HAND}

    def rep(m):
        gid, label = m.group(1), m.group(2)
        return f'<a class="gl" href="{base}#{gid}" data-g="{gid}">{esc(label or titles.get(gid, gid))}</a>'
    return re.sub(r"\{g:([a-z0-9_]+)(?:\|([^}]+))?\}", rep, text)


RULE_DE = {
    "permanent snow in >= 80 % of months": "Dauerschnee in mindestens 80 % der Monate",
    "or MODIS snow/ice >= 60 %": "oder MODIS Schnee/Eis mindestens 60 %",
    "and warmest month < 280 K": "und wärmster Monat unter 280 K",
    "snow-free albedo > 0.35": "schneefreie Albedo über 0,35",
    "flat: >= 95 % of area below 5 deg": "flach: mindestens 95 % der Fläche unter 5° Neigung",
    "relief < 100 m": "Relief unter 100 m",
    "elevation spread < 5 m": "Höhenstreuung unter 5 m",
    "warmest month > 280 K (not snow)": "wärmster Monat über 280 K (also kein Schnee)",
    "vegetation-free: NDVI yearly peak < 0.15": "vegetationsfrei: NDVI-Jahresmaximum unter 0,15",
    "or MODIS land cover 'barren' >= 50 %": "oder MODIS-Landbedeckung „barren“ mindestens 50 %",
    "MODIS 'barren' >= 80 %": "MODIS „barren“ mindestens 80 %",
    "albedo 0.25 to 0.45": "Albedo 0,25 bis 0,45",
    "loose ground: apparent thermal inertia < 0.026": "lockerer Boden: scheinbare thermische Trägheit unter 0,026",
    "precipitation < 150 mm/yr": "Niederschlag unter 150 mm/Jahr",
    "snow-free albedo < 0.15": "schneefreie Albedo unter 0,15",
    "water < 30 %": "Wasser unter 30 %",
    "mean surface temperature < 263 K": "mittlere Oberflächentemperatur unter 263 K (−10 °C)",
    "not permanent snow (< 80 % of months)": "kein Dauerschnee (unter 80 % der Monate)",
    "precipitation < 400 mm/yr": "Niederschlag unter 400 mm/Jahr",
    "elevation > 3000 m": "Höhe über 3000 m",
    "precipitation < 50 mm/yr": "Niederschlag unter 50 mm/Jahr",
    "mean slope > 15 deg": "mittlere Neigung über 15°",
    "precipitation < 250 mm/yr": "Niederschlag unter 250 mm/Jahr",
    "none of the rules above applies (vegetated, wet or icy)": "keine der Klassen oben trifft zu",
}


def entries(lang="de", base=""):
    """All glossary entries in order of GROUPS[lang]. base = URL of the glossary page for cross links ('' = same page)."""
    out = []
    for gid, grp, tde, xde, ten, xen in HAND:
        out.append(dict(id=gid, group=G[lang][grp], title=tde if lang == "de" else ten,
                        html=_link(xde if lang == "de" else xen, lang, base)))
    # profile weights table (generated)
    dims = ["gelaende", "oberflaeche", "thermik", "trockenheit", "atmosphaere", "staub_wind", "eis_wasser", "leben", "beleuchtung"]
    pname = {"mond_suedpol": ("Mond-Südpol", "Moon south pole"), "mars_aequatorial": ("Mars, äquatoriale Landestellen", "Mars, equatorial landing sites"),
             "mars_eis_mittelbreiten": ("Mars, eisreiche Mittelbreiten", "Mars, ice-rich mid-latitudes")}
    head = "".join(f"<th>{esc(DIM_NAME[lang][d])}</th>" for d in dims)
    rows = "".join(f"<tr><td>{esc(pname.get(k, (k, k))[0 if lang == 'de' else 1])}</td>"
                   + "".join(f"<td class='n'>{p['weights'].get(d, 0):g}</td>" for d in dims) + "</tr>"
                   for k, p in PROFILES.items())
    for e in out:
        if e["id"] == "profil":
            e["html"] += f"<div class='gtw'><table class='gtab'><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
    # classes in test order, with their rules
    for c in ENV_CLASSES:
        cid = c["id"]
        if lang == "de":
            title, desc, analog = de_text(c["name"]), de_text(c["desc"]), de_text(c["analog"])
            if cid == "kein_analog":
                title = "Kahl, aber keine Klasse passt"
                desc = "Unter den bewerteten (vegetationsfreien) Orten: kahler Boden, der zu keiner Klasse oben passt, meist weil er feuchter (z. B. über 400 mm Niederschlag) oder milder ist. Außerhalb des Rankings: bewachsen, feucht oder überwiegend Wasser."
        else:
            title, desc, analog = CLASS_EN[cid]
        rules = "".join(f"<li>{esc(RULE_DE.get(r[0], r[0]) if lang == 'de' else r[0])}</li>" for r in CLASS_RULES.get(cid, []))
        lab = ("Mars/Mond-Bezug", "Regeln (alle müssen zutreffen; „oder“ = Alternative zur Zeile davor)") if lang == "de" else ("Link to Mars/Moon", "Rules (all must hold; ‘or’ = alternative to the line above)")
        body = f"{esc(desc)}"
        if analog and analog != "-" and analog != "–":
            body += f"<br><b>{lab[0]}:</b> {esc(analog)}"
        body += f"<br><b>{lab[1]}:</b><ul class='grules'>{rules}</ul>"
        out.append(dict(id=f"cls_{cid}", group=G[lang]["Umgebungsklassen"], title=title, html=body))
    # flags
    for k, (txt, _) in FLAGS.items():
        title, desc = ((k.replace("_", "-").capitalize(), de_text(txt)) if lang == "de" else FLAG_EN[k])
        if lang == "de":
            title = {"staubquelle": "Staubquelle", "staubsturmreich": "Staubsturmreich", "windsturmreich": "Sturmreich",
                     "windstill": "Windstill", "frost_tau": "Frost-Tau", "extrem_kalt": "Extrem kalt", "niedriger_druck": "Niedriger Druck",
                     "dunkle_oberflaeche": "Dunkle Oberfläche", "landefreundlich": "Landefreundlich", "polar": "Polar"}[k]
        out.append(dict(id=f"flag_{k}", group=G[lang]["Zusatzeigenschaften"], title=title, html=esc(desc)))
    # features
    for key, (method, dim, _) in FEATURES.items():
        tde, xde, ten, xen = FEAT_TXT[key]
        title, text = (tde, xde) if lang == "de" else (ten, xen)
        meta = (f"<br><span class='gmeta'>{'Dimension' if lang == 'de' else 'Dimension'}: {esc(DIM_NAME[lang][dim])} · "
                f"{'Methode' if lang == 'de' else 'Method'}: {{g:{METHOD_ID[method]}|{METHOD_NAME[lang][method]}}} · "
                f"{'Erd-Verlässlichkeit' if lang == 'de' else 'Earth reliability'}: {EARTH_RELIABILITY.get(key, 'B')}</span>")
        out.append(dict(id=f"feat_{key}", group=G[lang]["Merkmale"], title=title, html=_link(text + meta, lang, base)))
    # known analogs
    rows = "".join(f"<tr><td>{esc(de_text(n) if lang == 'de' else n)}</td><td class='n'>{la:.1f}°, {lo:.1f}°</td><td class='n'>{r} km</td>"
                   + (f"<td>{esc(de_text(w))}</td>" if lang == "de" else "") + "</tr>"
                   for n, la, lo, r, w in KNOWN_ANALOGS)
    hd = ("<th>Standort</th><th>Lage</th><th>Radius</th><th>Analog für</th>" if lang == "de"
          else "<th>Site</th><th>Location</th><th>Radius</th>")
    intro = ("Etablierte Analog-Standorte aus der Literatur. Ein Ort innerhalb des Radius gilt als „bekannt“." if lang == "de"
             else "Established analog sites from the literature. A site within the radius counts as ‘known’.")
    out.append(dict(id="analoga", group=G[lang]["Grundbegriffe"], title="Bekannte Analoga" if lang == "de" else "Known analogs",
                    html=f"{intro}<div class='gtw'><table class='gtab'><thead><tr>{hd}</tr></thead><tbody>{rows}</tbody></table></div>"))
    order = {g: i for i, g in enumerate(GROUPS[lang])}
    out.sort(key=lambda e: order[e["group"]])  # stable: keeps the order inside a group
    return out


if __name__ == "__main__":
    for lang in ("de", "en"):
        es = entries(lang)
        print(lang, len(es), "Eintraege;", ", ".join(sorted({e['group'] for e in es})))
