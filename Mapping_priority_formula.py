import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from Risk_Assessment import (
    hazard_evaluation,
    mapping_evaluation,
    population_evalution,
    preparedness_evaluation,
)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

DATA = Path(__file__).resolve().parent / "data"

# The 4 input files (file a, b, c, d)
HAZARD_FILE = DATA / "hazard.csv"
POPULATION_FILE = DATA / "population.csv"
PREPAREDNESS_FILE = DATA / "preparedness.csv"
MAPPING_FILE = DATA / "volcano_readiness.csv"

# Two rows are the same volcano when they have the same name AND their
# coordinates are closer than this (allows small differences between files).
MAX_LINK_DISTANCE_M = 100


def distance_m(lat1, lon1, lat2, lon2):
    """Distance in metres between one point and arrays of points (haversine)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))


def clean_name(name) -> str:
    """Make names comparable: 'Volcán  Galeras ' and 'volcan galeras' count as the same."""
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(name.lower().split())


def link_by_gvp(volcanoes: pd.DataFrame, scores: pd.DataFrame, label: str) -> pd.DataFrame:
    """Attach one score to each volcano by GVP volcano number.

    Used for files built from the GVP list (e.g. preparedness), whose names and
    coordinates are GVP's, not OSM's. Several OSM points in one GVP volcano
    (e.g. cones of a cluster) all get that volcano's score.
    """
    col = f"{label}_score"
    lookup = scores.dropna(subset=["gvp_volcano_number"]).drop_duplicates("gvp_volcano_number")
    lookup = lookup.set_index(lookup["gvp_volcano_number"].astype(int))[col]

    volcanoes = volcanoes.copy()
    volcanoes[col] = volcanoes["gvp_volcano_number"].map(lookup)

    no_number = volcanoes["gvp_volcano_number"].isna().sum()
    not_in_file = (volcanoes["gvp_volcano_number"].notna() & volcanoes[col].isna()).sum()
    if no_number:
        print(f"Warning: {no_number} volcanoes have no {label} score (no GVP volcano number)")
    if not_in_file:
        print(f"Warning: {not_in_file} volcanoes have no {label} score "
              f"(their GVP number is not in the {label} file)")
    return volcanoes


def link(volcanoes: pd.DataFrame, scores: pd.DataFrame, label: str) -> pd.DataFrame:
    """Attach one score to each volcano.

    If the score table has a gvp_volcano_number column, link by that number.
    Otherwise use a 3-way match: name, lat and lon must all agree.

    A point counts as the same volcano when it is within MAX_LINK_DISTANCE_M
    AND has the same name. If the coordinates match but the name doesn't,
    the volcano is NOT linked and is listed so you can fix the name.
    """
    if "gvp_volcano_number" in scores.columns:
        return link_by_gvp(volcanoes, scores, label)

    col = f"{label}_score"
    score_lats = scores["lat"].to_numpy()
    score_lons = scores["lon"].to_numpy()
    score_names = scores["name"].map(clean_name).to_numpy()

    values, no_point, name_differs = [], [], []
    for name, lat, lon in zip(volcanoes["name"], volcanoes["lat"], volcanoes["lon"]):
        d = distance_m(lat, lon, score_lats, score_lons)
        close = d <= MAX_LINK_DISTANCE_M
        same = close & (score_names == clean_name(name))

        if same.any():
            best = np.where(same)[0][d[same].argmin()]     # nearest point with the same name
            values.append(scores[col].iloc[best])
        else:
            values.append(np.nan)
            if close.any():
                other = scores["name"].iloc[np.where(close)[0][d[close].argmin()]]
                name_differs.append(f"{name!r} vs {other!r}")
            else:
                no_point.append(name)

    volcanoes = volcanoes.copy()
    volcanoes[col] = values

    if no_point:
        print(f"Warning: {len(no_point)} volcanoes not found in the {label} file "
              f"(no point within {MAX_LINK_DISTANCE_M} m): {', '.join(map(str, no_point[:5]))}"
              + (" ..." if len(no_point) > 5 else ""))
    if name_differs:
        print(f"Warning: {len(name_differs)} volcanoes have matching coordinates but a different "
              f"name in the {label} file: {'; '.join(name_differs[:5])}"
              + (" ..." if len(name_differs) > 5 else ""))
    return volcanoes


def compute_ranking() -> pd.DataFrame:
    # 1. read the 4 files
    hazard_data = pd.read_csv(HAZARD_FILE)
    population_data = pd.read_csv(POPULATION_FILE)
    preparedness_data = pd.read_csv(PREPAREDNESS_FILE)
    mapping_data = pd.read_csv(MAPPING_FILE)

    # 2. each Risk_Assessment file gives its own score
    x = hazard_evaluation.score(hazard_data)
    y = population_evalution.score(hazard_data)
    z = preparedness_evaluation.score(preparedness_data)
    t = mapping_evaluation.score(mapping_data)

    # 3. link them (the hazard file is the master volcano list)
    #    by name + coordinates, or by GVP number for GVP-based files
    volcanoes = hazard_data[["name", "gvp_volcano_number", "lat", "lon"]].copy()
    volcanoes["gvp_volcano_number"] = volcanoes["gvp_volcano_number"].astype("Int64")
    volcanoes = link(volcanoes, x, "hazard")
    volcanoes = link(volcanoes, y, "population")
    volcanoes = link(volcanoes, z, "preparedness")
    volcanoes = link(volcanoes, t, "mapping")

    # 4. total score (preparedness is flipped: well prepared = lower priority)
    volcanoes["total_score"] = (
        volcanoes["hazard_score"]
        * volcanoes["population_score"]
        * (1 - volcanoes["preparedness_score"])
        * volcanoes["mapping_score"]
    )

    # 5. ranking
    ranking = volcanoes.sort_values("total_score", ascending=False).reset_index(drop=True)
    ranking.index += 1          # rank 1 = highest priority
    ranking.index.name = "rank"
    return ranking


if __name__ == "__main__":
    ranking = compute_ranking()
    print(ranking.head(20).round(3))