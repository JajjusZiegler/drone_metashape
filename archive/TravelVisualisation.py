import pandas as pd
import requests
import time
import json
from pyproj import Transformer
from math import radians, sin, cos, sqrt, atan2

# --- USER CONFIG ---
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjRmNGQ5NDY3NjY4ZDQ4NmY5NGE0NDA3YTYyZGI0Y2E0IiwiaCI6Im11cm11cjY0In0="  # <-- Set your key here
ZURICH_COORDS = (8.5417, 47.3769)  # (lon, lat) for Zurich
CSV_PATH = r"M:\working_package_2\2024_dronecampaign\03_results\Campaigns\drone_campaigns.csv.csv"
CACHE_PATH = "route_cache.json"
REQUEST_DELAY = 2  # seconds

# --- Load and prepare data ---
df = pd.read_csv(CSV_PATH)
df.columns = df.columns.str.strip()
df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
df = df.dropna(subset=['date', 'X_LV95', 'Y_LV95'])
df['x'] = df['X_LV95'].astype(str).str.replace(',', '.').astype(float)
df['y'] = df['Y_LV95'].astype(str).str.replace(',', '.').astype(float)

# Convert LV95 to WGS84 (lat/lon)
transformer = Transformer.from_crs(2056, 4326, always_xy=True)
df['lon'], df['lat'] = transformer.transform(df['x'].values, df['y'].values)

# --- Load route cache ---
try:
    with open(CACHE_PATH, "r") as f:
        route_cache = json.load(f)
except:
    route_cache = {}

# --- Helper: Get road distance from ORS with caching and delay ---
def get_road_distance(p1, p2, api_key):
    key = f"{p1[0]:.6f},{p1[1]:.6f}|{p2[0]:.6f},{p2[1]:.6f}"
    if key in route_cache:
        return route_cache[key]
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key}
    body = {
        "coordinates": [p1, p2],
        "format": "geojson"
    }
    time.sleep(REQUEST_DELAY)
    response = requests.post(url, json=body, headers=headers)
    if response.status_code == 200 and 'routes' in response.json():
        data = response.json()
        summary = data['routes'][0].get('summary', {})
        if 'distance' in summary:
            distance = summary['distance'] / 1000  # km
            route_cache[key] = distance
            with open(CACHE_PATH, "w") as f:
                json.dump(route_cache, f)
            return distance
        else:
            print(f"ORS response missing 'distance': {data}")
            return None
    else:
        print(f"ORS error: {response.status_code}", response.text)
        return None

# --- Group campaigns by day ---
day_groups = df.groupby(df['date'])

# --- Calculate travel distances ---
daily_distances = []
cumulative_distance = 0

routable_coords = {
    "Stillberg": (9.874984, 46.779794),
    "Davos_LWF": (9.854050, 46.812945),
    "Brüttelen": (7.159473, 47.031268),
    "Schüpfen": (7.354347, 47.032700),
    "Sempach_treenet": (9.854050, 46.812945),
    "Wangen Brüttisellen_treenet": (8.652573, 47.412123),
    "Neunkirch_LWF": (8.537747, 47.687959),
    "Schänis_LWF": (9.064164, 47.169910),
    "Illgraben": (7.623654, 46.309922),
    "Salgesch_treenet": (7.573422, 46.315104),
    "VISP_LWF": (7.862053, 46.296674),
    "Lens-Forest": (7.444938, 46.275686),
    "Sagno_treenet": (9.037009, 45.859016),
    "Isone_LWF": (8.990242, 46.131794),
    "Pfynwald": (7.623654, 46.309922),
    "Martelloskop": (9.874984, 46.779794)
}

for day, group in day_groups:
    # Build ordered list: Zurich → sites → Zurich
    route = [ZURICH_COORDS]
    for _, row in group.iterrows():
        site_name = row['site'] if 'site' in row else None
        if site_name in routable_coords:
            route.append(routable_coords[site_name])
        else:
            route.append((row['lon'], row['lat']))  # fallback
    route.append(ZURICH_COORDS)
    # Calculate total road distance for the day
    day_distance = 0
    for i in range(len(route)-1):
        p1 = list(route[i])
        p2 = list(route[i+1])
        dist = get_road_distance(p1, p2, ORS_API_KEY)
        if dist is not None:
            day_distance += dist
    cumulative_distance += day_distance
    daily_distances.append((day.date(), day_distance, cumulative_distance))

# --- Print and save results ---
print("Date       | Day Road Distance (km) | Cumulative (km)")
print("-----------------------------------------------")
results = []
for day, dist, cumu in daily_distances:
    print(f"{day} | {dist:.1f}           | {cumu:.1f}")
    results.append({"date": str(day), "day_km": dist, "cumulative_km": cumu})
pd.DataFrame(results).to_csv("traveled_km.csv", index=False)
