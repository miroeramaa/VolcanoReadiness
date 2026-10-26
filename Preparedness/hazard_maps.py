"""Volcano number -> number of hazard maps in the IAVCEI Volcanic Hazard Maps
Database (volcanichazardmaps.org), scraped from its browse-by-volcano pages.

    from hazard_maps import hazard_map_counts
    maps = hazard_map_counts()
    volcanoes = volcanoes.merge(maps, on="Volcano Number", how="left").fillna({"n_hazard_maps": 0})
    volcanoes["has_hazard_map"] = volcanoes["n_hazard_maps"] > 0
"""
import re
import string
import time

import pandas as pd
import requests

URL = "https://volcanichazardmaps.org/volcano/?volcano={}"
# the site's firewall (Mod_Security) rejects python-requests' default headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def hazard_map_counts():
    counts = {}
    for letter in string.ascii_uppercase:
        r = requests.get(URL.format(letter), headers=HEADERS, timeout=60)
        r.raise_for_status()
        html = r.text
        time.sleep(1)  # be polite: 26 requests, one per second
        # each volcano heading carries "[VNUM = 264020]"; its map links follow it
        parts = re.split(r"VNUM\s*=\s*(\d+)", html)
        for vnum, chunk in zip(parts[1::2], parts[2::2]):
            chunk = re.split(r"<footer|</main|sidebar", chunk)[0]  # not past the list
            counts[int(vnum)] = len(set(re.findall(r"map\?id=(\d+)", chunk)))
    return pd.DataFrame(list(counts.items()), columns=["Volcano Number", "n_hazard_maps"])


if __name__ == "__main__":
    df = hazard_map_counts()
    df.to_csv("hazard_maps.csv", index=False)
    print(f"{len(df)} volcanoes, {df['n_hazard_maps'].sum()} maps -> hazard_maps.csv")