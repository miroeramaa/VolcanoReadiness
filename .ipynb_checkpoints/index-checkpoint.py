import requests
import pandas as pd

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def get_active_volcanoes(lat_band=30):
    query = f"""
    [out:json][timeout:180];
    nwr["natural"="volcano"]["volcano:status"="active"]
       ({-lat_band},-180,{lat_band},180);
    out center tags;
    """
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=200)
    resp.raise_for_status()
    elements = resp.json()["elements"]

    rows = []
    for el in elements:
        # Nodes have lat/lon directly; ways/relations get a computed "center"
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        tags = el.get("tags", {})
        rows.append({
            "osm_type": el["type"],
            "osm_id": el["id"],
            "name": tags.get("name"),
            "name_en": tags.get("name:en"),
            "lat": lat,
            "lon": lon,
            "elevation": tags.get("ele"),
            "volcano_type": tags.get("volcano:type"),
            "wikidata": tags.get("wikidata"),
        })
    return pd.DataFrame(rows)

df = get_active_volcanoes(30)
print(len(df))
print(df.head())