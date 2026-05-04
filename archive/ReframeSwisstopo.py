import pandas as pd
import requests
import io

# Define API endpoint
API_URL = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"

# ✅ Your specified file paths
input_file = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects - Copy\Brüttelen_sanasilva50845\20240813\test.csv"
output_file = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects - Copy\Brüttelen_sanasilva50845\20240813\converted_est_ref.txt"

# Read the input file
with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

header_lines = lines[:0]  # Preserve metadata lines
data_lines = lines[0:]  # Actual data

# Load CSV with correct headers
df = pd.read_csv(io.StringIO("\n".join(data_lines)), sep=",", engine="python")

# Print original column names
print("Original column names:", df.columns.tolist())

# Strip spaces from ALL column names immediately after reading
df.columns = df.columns.str.strip()

# Print column names after stripping spaces
print("Column names after stripping spaces:", df.columns.tolist())

# Define new column names (without leading/trailing spaces)
longitude_col = "XYZ Estimated X"
latitude_col = "XYZ Estimated Y"
altitude_col = "XYZ Estimated Z"
label_col = "Label"

# Print the column names we are expecting
print(f"\nExpecting longitude column: '{longitude_col}'")
print(f"Expecting latitude column: '{latitude_col}'")

# Ensure required coordinate columns exist (after stripping spaces)
if longitude_col not in df.columns or latitude_col not in df.columns:
    print("\nERROR: Required coordinate columns not found after stripping spaces!")
    print(f"Available columns: {df.columns.tolist()}")
    raise ValueError("Missing required coordinate columns!")
else:
    print("\nSUCCESS: Required coordinate columns found after stripping spaces.")

# ✅ Convert coordinate columns to float64 explicitly
if longitude_col in df.columns:
    df[longitude_col] = pd.to_numeric(df[longitude_col], errors="coerce").astype(float)
    print(f"Successfully converted '{longitude_col}' to numeric.")
else:
    print(f"Warning: '{longitude_col}' not found for numeric conversion.")

if latitude_col in df.columns:
    df[latitude_col] = pd.to_numeric(df[latitude_col], errors="coerce").astype(float)
    print(f"Successfully converted '{latitude_col}' to numeric.")
else:
    print(f"Warning: '{latitude_col}' not found for numeric conversion.")

if altitude_col in df.columns:
    df[altitude_col] = pd.to_numeric(df[altitude_col], errors="coerce").astype(float)
    print(f"Successfully converted '{altitude_col}' to numeric.")
else:
    print(f"Warning: '{altitude_col}' not found for numeric conversion.")

# Function to convert coordinates
def transform_coordinates(lon, lat, alt=None):
    params = {"northing": lat, "easting": lon, "altitude": alt, "format": "json"}  # Correct order
    response = requests.get(API_URL, params=params)
    if response.status_code == 200:
        result = response.json()
        return result
    else:
        print(f"Error: {response.text}")
        return None

# Create an empty list to store the transformed data
transformed_data = []

# Process only rows where 'Label' ends with '_6'
for index, row in df.iterrows():
    #  THIS IS THE CRUCIAL CHANGE:
    label_check = str(row[label_col]).strip().endswith("_6.tif")  # Exact match for "_6.tif"
    longitude_check = pd.notna(row[longitude_col]) if longitude_col in df.columns else False
    latitude_check = pd.notna(row[latitude_col]) if latitude_col in df.columns else False

    print(f"Row {index}: Label='{row[label_col]}', Label Check={label_check}, Longitude Check={longitude_check}, Latitude Check={latitude_check}")

    if label_check and longitude_check and latitude_check:
        longitude = row[longitude_col]
        latitude = row[latitude_col]
        original_altitude = row.get(altitude_col)  # Store the original altitude

        print(
            f"  Processing: Label={row[label_col]}, Longitude={longitude}, Latitude={latitude}, Altitude={original_altitude}"
        )

        params = {
            "northing": latitude,
            "easting": longitude,
            "altitude": original_altitude,
            "format": "json",
        }
        response = requests.get(API_URL, params=params)

        if response.status_code == 200:
            result = response.json()
            try:
                new_x = float(result["easting"])
                new_y = float(result["northing"])
                api_altitude = float(result.get("altitude", 0.0) or 0.0)

                if isinstance(new_x, float) and isinstance(new_y, float):
                    transformed_data.append(
                        {
                            "Label": row[label_col],
                            "Easting": new_x,
                            "Northing": new_y,
                            "Original_Altitude": original_altitude,
                        }
                    )
                else:
                    print(
                        f"  Transformation failed for {row[label_col]}, Longitude: {longitude}, Latitude: {latitude}: Invalid coordinate values in API response: Easting: {new_x}, Northing: {new_y}"
                    )
            except (KeyError, ValueError, TypeError) as e:
                print(
                    f"  Transformation failed for {row[label_col]}, Longitude: {longitude}, Latitude: {latitude}: Error processing API response: {e}, Response: {result}"
                )

        else:
            print(
                f"  Transformation failed for {row[label_col]}, Longitude: {longitude}, Latitude: {latitude}: API error {response.status_code}, Response: {response.text}"
            )

# Create a new DataFrame from the transformed data
transformed_df = pd.DataFrame(transformed_data)

# Save the transformed data to a new CSV file
transformed_df.to_csv(
    output_file, index=False, header=True, sep=",", encoding="utf-8"
)

print(f"✅ Transformation complete! Output saved to {output_file}")