from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
GVP_FILE = DATA / "GVP_Volcano_List_Holocene.csv"


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Turn the readiness value (already 0-1) into the mapping score.

    Input:  name, lat, lon, readiness   (data/volcano_readiness.csv)
    Output: name, lat, lon, gvp_volcano_number, mapping_score

    The names and coordinates in this file come from the GVP list, not OSM,
    so each volcano is given its GVP volcano number. Mapping_priority_formula
    then links by that number instead of by name + coordinates.
    """
    df = df.copy()
    df["mapping_score"] = pd.to_numeric(df["readiness"], errors="coerce")

    gvp = pd.read_csv(GVP_FILE, encoding_errors="ignore")
    gvp = gvp[["Volcano Number", "Latitude", "Longitude"]].rename(
        columns={"Volcano Number": "gvp_volcano_number",
                 "Latitude": "lat", "Longitude": "lon"}
    )
    df = df.merge(gvp, on=["lat", "lon"], how="left")

    missing = df["gvp_volcano_number"].isna().sum()
    if missing:
        print(f"Warning: {missing} volcanoes in the mapping file "
              f"have no matching GVP volcano")

    return df[["name", "lat", "lon", "gvp_volcano_number", "mapping_score"]]