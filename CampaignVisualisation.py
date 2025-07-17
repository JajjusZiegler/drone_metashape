import pandas as pd
import plotly.express as px
from pyproj import Transformer
from datetime import timedelta

# Load the data
file_path = r"M:\working_package_2\2024_dronecampaign\03_results\Campaigns\drone_campaigns.csv.csv"  # Adjusted to match uploaded filename
df = pd.read_csv(file_path)

# Standardize column names if needed
df.columns = df.columns.str.strip()

# Print original column names for debugging
print("Original columns:", df.columns.tolist())

# Select only relevant columns (adjust names if needed)
selected_columns = ['date', 'month', 'site', 'X_LV95', 'Y_LV95', 'flight_duration (hh:mm)']
# If your CSV uses different names, update selected_columns accordingly
try:
    df = df[selected_columns]
    df = df.rename(columns={"X_LV95": "x", "Y_LV95": "y"})
except KeyError as e:
    print(f"Column selection error: {e}. Please check the column names in your CSV.")
    exit(1)

# Rename columns for clarity (optional, since already named)
# df.columns = ['date', 'month', 'site', 'x', 'y']

# Show non-numeric values in 'x' and 'y' for debugging
non_numeric_x = df[~df['x'].astype(str).str.replace(',', '.').str.match(r'^-?\d+(\.\d+)?$')]
if not non_numeric_x.empty:
    print("Non-numeric x values:", non_numeric_x[['x', 'site']].head())

# Filter out rows where 'x' or 'y' are not numeric
is_numeric = df['x'].astype(str).str.replace(',', '.').str.match(r'^-?\d+(\.\d+)?$') & \
            df['y'].astype(str).str.replace(',', '.').str.match(r'^-?\d+(\.\d+)?$')
df = df[is_numeric]

# Replace commas with dots in coordinates and convert to float
df['x'] = df['x'].astype(str).str.replace(',', '.').astype(float)
df['y'] = df['y'].astype(str).str.replace(',', '.').astype(float)

# Convert date column to datetime
df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')

# Drop rows with invalid dates or missing coordinates
df = df.dropna(subset=['date', 'x', 'y'])

# Optional: remove duplicate events
df = df.drop_duplicates(subset=['date', 'site', 'x', 'y'])

# Create a continuous timeline for animation
min_date = df['date'].min()
df['days_since_start'] = (df['date'] - min_date).dt.days

# Create a string version of date for hover
df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')

# For animation, use actual date string as frame
unique_dates = df['date'].sort_values().dt.strftime('%Y-%m-%d').unique()

# Define all sites and their coordinates
site_table = [
    [2785456.796, 1182940.384, "Stillberg"],
    [2784434.414, 1187740.779, "Davos_LWF"],
    [2578000, 1209000, "Brüttelen"],
    [2594000, 1209000, "Schüpfen"],
    [2658300.593, 1219819.92, "Sempach_treenet"],
    [2691184.587, 1252746.366, "Wangen Brüttisellen_treenet"],
    [2682373.782, 1282008.801, "Neunkirch_LWF"],
    [2723457.843, 1225073.988, "Schänis_LWF"],
    [2614670.057, 1126918.5, "Illgraben"],
    [2611171.877, 1129703.535, "Salgesch_treenet"],
    [2632338.197, 1127358.111, "VISP_LWF"],
    [2599805.952, 1124120.904, "Lens-Forest"],
    [2724277.335, 1080017.012, "Sagno_treenet"],
    [2721303.327, 1109345.237, "Isone_LWF"],
    [2613655.83, 1128378.67, "Pfynwald"],
    [2786224.55, 1182843.6, "Martelloskop"]
]
site_df = pd.DataFrame(site_table, columns=["x", "y", "site"])

# Convert LV95 to WGS84 (lat/lon)
transformer = Transformer.from_crs(2056, 4326, always_xy=True)
site_df['lon'], site_df['lat'] = transformer.transform(site_df['x'].values, site_df['y'].values)

# Normalize site names for robust matching
site_df['site_norm'] = site_df['site'].str.lower().str.strip()
df['site_norm'] = df['site'].str.lower().str.strip()
campaigns = df[['date', 'site_norm']].copy()
campaigns['date_str'] = campaigns['date'].dt.strftime('%Y-%m-%d')

# Prepare campaign data
# campaigns = df[['date', 'site']].copy()
# campaigns['date_str'] = campaigns['date'].dt.strftime('%Y-%m-%d')

# Create a complete list of all dates in the period
all_dates = pd.date_range(df['date'].min(), df['date'].max(), freq='D')
all_date_str = all_dates.strftime('%Y-%m-%d').tolist()

point_delay = 30  # Fade period in days
frames = []
# Add rounded coordinates for robust matching
site_df['x_round'] = site_df['x'].round(1)
site_df['y_round'] = site_df['y'].round(1)
df['x_round'] = df['x'].round(1)
df['y_round'] = df['y'].round(1)
campaigns = df[['date', 'x_round', 'y_round']].copy()
campaigns['date_str'] = campaigns['date'].dt.strftime('%Y-%m-%d')

for i, date in enumerate(all_date_str):
    frame_sites = site_df.copy()
    frame_sites['frame_date'] = date
    # For each site, count campaigns up to current date
    frame_sites['campaign_count'] = frame_sites.apply(
        lambda row: campaigns[(campaigns['x_round'] == row['x_round']) & (campaigns['y_round'] == row['y_round']) & (campaigns['date_str'] <= date)].shape[0],
        axis=1
    )
    frame_sites['campaign_count'] = frame_sites['campaign_count'].clip(0, 10).astype(int)
    frame_sites['text'] = frame_sites['site']  # Always show site name
    frames.append(frame_sites)

anim_df = pd.concat(frames, keys=all_date_str, names=['date_str']).reset_index(level=0, drop=True)

# Prepare cumulative campaign counts for each frame (date)
campaign_counts_by_date = pd.DataFrame(index=all_date_str)
campaign_counts_by_date['2024'] = df[df['date'].dt.year == 2024].groupby(df['date'].dt.strftime('%Y-%m-%d')).size().reindex(all_date_str, fill_value=0).cumsum()
campaign_counts_by_date['2025'] = df[df['date'].dt.year == 2025].groupby(df['date'].dt.strftime('%Y-%m-%d')).size().reindex(all_date_str, fill_value=0).cumsum()
anim_df['campaign_counter_text'] = anim_df['frame_date'].map(
    lambda d: f"2024: {campaign_counts_by_date.loc[d, '2024']} | 2025: {campaign_counts_by_date.loc[d, '2025']}"
)

# Load cumulative travel distances
km_df = pd.read_csv("traveled_km.csv")
km_df['date'] = pd.to_datetime(km_df['date'])
km_df = km_df.sort_values('date')
km_map = {}
last_km = 0
for d in all_date_str:
    match = km_df[km_df['date'].dt.strftime('%Y-%m-%d') <= d]
    if not match.empty:
        last_km = match.iloc[-1]['cumulative_km']
    km_map[d] = last_km

# Load cumulative flight durations
try:
    flight_df = pd.read_csv("cumulative_flight.csv")
    flight_df['date'] = pd.to_datetime(flight_df['date'])
    flight_df = flight_df.sort_values('date')
    flight_map = {}
    last_flight = 0
    for d in all_date_str:
        match = flight_df[flight_df['date'].dt.strftime('%Y-%m-%d') <= d]
        if not match.empty:
            last_flight = match.iloc[-1]['cumulative_flight']
        flight_map[d] = last_flight
except FileNotFoundError:
    flight_map = {d: 0 for d in all_date_str}

# Ensure legend always shows 0-10
campaign_categories = [str(i) for i in range(0, 11)]
discrete_colors = [
    "#1f77b4",  # 0 - blue
    "#ff7f0e",  # 1 - orange
    "#2ca02c",  # 2 - green
    "#d62728",  # 3 - red
    "#9467bd",  # 4 - purple
    "#8c564b",  # 5 - brown
    "#e377c2",  # 6 - pink
    "#7f7f7f",  # 7 - gray
    "#bcbd22",  # 8 - yellow-green
    "#17becf",  # 9 - cyan
    "#FFD700"   # 10 - gold
]
anim_df['campaign_count'] = anim_df['campaign_count'].astype(str)
dummy_rows = pd.DataFrame({
    'lat': [0]*11*len(all_date_str),
    'lon': [0]*11*len(all_date_str),
    'site': ['dummy']*11*len(all_date_str),
    'frame_date': [d for d in all_date_str for _ in range(11)],
    'campaign_count': campaign_categories*len(all_date_str),
    'text': ['']*11*len(all_date_str),
    'campaign_counter_text': ['']*11*len(all_date_str)
})
anim_df = pd.concat([anim_df, dummy_rows], ignore_index=True)

fig = px.scatter_mapbox(
    anim_df,
    lat="lat",
    lon="lon",
    hover_name="site",
    hover_data={"campaign_count": True},
    animation_frame="frame_date",
    category_orders={"frame_date": all_date_str, "campaign_count": campaign_categories},
    zoom=7,
    center={"lat": 46.8, "lon": 8.2},
    height=800,
    color="campaign_count",
    color_discrete_sequence=discrete_colors,
    text="text",
    custom_data=[anim_df['campaign_counter_text']]
)

fig.update_traces(
    marker=dict(size=16, opacity=0.8),
    textposition="top right"
)

frame_duration = 50  # 0.1 second per day for smoother animation

# Add campaign_counter_text column to anim_df for each frame
anim_df['campaign_counter_text'] = anim_df['frame_date'].map(
    lambda d: f"2024: {campaign_counts_by_date.loc[d, '2024']} | 2025: {campaign_counts_by_date.loc[d, '2025']}"
)

fig.update_layout(
    mapbox_style="open-street-map",
    title="Field Campaigns in Switzerland Over Time",
    margin={"r":0,"t":40,"l":0,"b":0},
    updatemenus=[{
        "buttons": [
            {
                "args": [None, {"frame": {"duration": frame_duration, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0.01}}],
                "label": "Play",
                "method": "animate"
            },
            {
                "args": [[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                "label": "Pause",
                "method": "animate"
            }
        ],
        "direction": "left",
        "pad": {"r": 10, "t": 87},
        "showactive": False,
        "type": "buttons",
        "x": 0.1,
        "xanchor": "right",
        "y": 0,
        "yanchor": "top"
    }]
)

# Add correct annotations for each frame
def parse_minutes(hhmm):
    try:
        h, m = map(int, str(hhmm).split(':'))
        return h * 60 + m
    except:
        return 0

df['flight_minutes'] = df['flight_duration (hh:mm)'].apply(parse_minutes)
daily_flight = df.groupby(df['date'])['flight_minutes'].sum().reindex(pd.to_datetime(all_date_str), fill_value=0)
cumulative_flight = daily_flight.cumsum()
cumulative_flight_map = dict(zip([d.strftime('%Y-%m-%d') for d in cumulative_flight.index], cumulative_flight.values))

for frame in fig.frames:
    frame_date = frame.name
    frame_counter = anim_df[anim_df['frame_date'] == frame_date]['campaign_counter_text'].iloc[0]
    traveled_km = km_map.get(frame_date, 0)
    flight_minutes = cumulative_flight_map.get(frame_date, 0)
    flight_hours = flight_minutes / 60
    frame.layout.annotations = [
        dict(
            text=f"<b>{frame_date}</b>",
            x=0.5, y=0.97, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=40, color="darkblue"),
            align="center"
        ),
        dict(
            text=f"<b>{frame_counter}</b>",
            x=0.01, y=0.97, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=28, color="darkred"),
            align="left"
        ),
        dict(
            text=f"<b>Traveled: {traveled_km:.1f} km</b>",
            x=0.01, y=0.92, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=22, color="darkgreen"),
            align="left"
        ),
        dict(
            text=f"<b>Flight: {flight_hours:.1f} h</b>",
            x=0.01, y=0.87, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=22, color="darkblue"),
            align="left"
        )
    ]

fig.show()
fig.write_html("CampaignMap.html")
print("Map saved as CampaignMap.html. Open this file in your browser.")
