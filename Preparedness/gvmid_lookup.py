"""Count GVMID monitoring stations near each volcano in a GVP list.

    from load_gvp import load_gvp
    from gvmid_lookup import load_stations, count_stations

    volcanoes = load_gvp("GVP_Volcano_List_Holocene_202610190409.xls")
    stations = load_stations("gvmid/")   # folder of unzipped .xlsx files
    result = count_stations(volcanoes, stations, radius_km=20)
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd


def _col(df, pattern):
    """First column whose lower-cased name matches the regex, else None."""
    return next((c for c in df.columns if re.search(pattern, str(c).lower())), None)


def load_stations(folder):
    """All stations in the unzipped GVMID folder: method, lat, lon, active.
    The method is taken from each file's name (e.g. Seismic.xlsx -> seismic)."""
    frames = []
    print("YO")
    for path in Path(folder).glob("*.xlsx"):
        for df in pd.read_excel(path, sheet_name=None).values():
            print(df.head(5))
            lat, lon, end = _col(df, "lat"), _col(df, "lon"), _col(df, r"etime|end")
            if lat is None or lon is None:
                continue
            frames.append(pd.DataFrame({
                "method": path.stem.lower(),
                "lat": pd.to_numeric(df[lat], errors="coerce"),
                "lon": pd.to_numeric(df[lon], errors="coerce"),
                "active": df[end].isna() if end else True,
            }))
    return pd.concat(frames, ignore_index=True).dropna(subset=["lat", "lon"])


def count_stations(volcanoes, stations, radius_km=20):
    """Per volcano: active stations within radius_km, total and by method."""
    st = stations[stations["active"]]
    slat, slon = np.radians(st["lat"].to_numpy()), np.radians(st["lon"].to_numpy())

    rows = []
    for _, v in volcanoes.iterrows():
        vlat, vlon = np.radians(v["Latitude"]), np.radians(v["Longitude"])
        a = (np.sin((slat - vlat) / 2) ** 2
             + np.cos(vlat) * np.cos(slat) * np.sin((slon - vlon) / 2) ** 2)
        near = st[2 * 6371 * np.arcsin(np.sqrt(a)) <= radius_km]
        rows.append({"Volcano Number": v["Volcano Number"],
                     "n_stations": len(near),
                     "n_methods": near["method"].nunique(),
                     **near["method"].value_counts().add_prefix("n_").to_dict()})

    out = pd.DataFrame(rows).fillna(0)
    return volcanoes[["Volcano Number", "Volcano Name"]].merge(out, on="Volcano Number")