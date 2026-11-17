from pathlib import Path
import pandas as pd

# Fetching OSM volcanoes -> VolcanoReadiness -> data
DATA = Path(__file__).resolve().parent.parent / "data"

gvp = pd.read_csv(DATA / "raw" / "GVP_Volcano_List_Holocene.csv", encoding_errors="ignore")

equator = gvp[gvp["Latitude"].between(-10, 10)]

equator = equator.rename(columns={
    "Volcano Number": "volcano_number",
    "Volcano Name": "volcano_name",
    "Latitude": "lat",
    "Longitude": "lon",
})

equator.to_csv(DATA / "processed" / "volcanoes_10deg_equator.csv", index=False)
print(len(equator), "volcanoes within 10 degrees of the equator")