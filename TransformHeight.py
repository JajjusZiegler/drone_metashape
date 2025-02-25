import pandas as pd
import rasterio
import pyproj  # Import pyproj

def convert_height(easting, northing, ellip_height, geoid_path, input_crs, target_crs):
    try:
        #print(f"Trying to open geoid file: {geoid_path}")
        with rasterio.open(geoid_path) as dataset:
            #print(f"Successfully opened geoid file: {geoid_path}")
            #print(f"Sampling coordinates (CH1903+): Easting={easting}, Northing={northing}")

            # Coordinate Transformation using pyproj
            transformer = pyproj.Transformer.from_crs(input_crs, target_crs, always_xy=True)
            lon, lat = transformer.transform(easting, northing)
            #print(f"Transformed coordinates (WGS 84 - approximate): Longitude={lon}, Latitude={lat}")

            #print("Using dataset.sample() WITHOUT resampling argument")
            # Sample using TRANSFORMED coordinates (lon, lat)
            for val in dataset.sample([(lon, lat)]):
                #print(f"Raw value from dataset.sample(): {val}")
                geoid_undulation = val[0]
                #print(f"Extracted geoid_undulation: {geoid_undulation}")
                ortho_height = ellip_height - geoid_undulation
                #print(f"Calculated ortho_height: {ortho_height}")
                return ortho_height
    except Exception as e:
        print(f"Error processing coordinates ({easting}, {northing}): {e}")
        return None

def process_csv(input_file, output_file, geoid_path):
    try:
        print(f"Reading CSV: {input_file}")
        df = pd.read_csv(input_file)
        df.columns = df.columns.str.strip()
        print(f"CSV columns before processing: {df.columns.tolist()}")

        # Define input CRS (CH1903+) and target CRS (WGS 84 Geographic - EPSG:4326)
        input_crs = pyproj.CRS("EPSG:2056")  # CH1903+ / LV95
        target_crs = pyproj.CRS("EPSG:4326")  # WGS 84 Geographic (Lat/Lon)

        print("Converting heights using geoid model and coordinate transformation...")
        df["Ortho Height"] = df.apply(
            lambda row: convert_height(row["Easting"], row["Northing"], row["Ellip Height"], geoid_path, input_crs, target_crs),
            axis=1
        )

        # Set ortho heights below 0 to 0
        print("Setting Ortho Heights below 0 to 0...")
        df["Ortho Height"] = df["Ortho Height"].clip(lower=0) # Use clip function to set lower bound to 0
        print("Ortho Heights below 0 set to 0.")

        # Remove the original 'Ellip Height' column
        df = df.drop(columns=["Ellip Height"])
        print(f"CSV columns after removing 'Ellip Height': {df.columns.tolist()}")

        # Reorder columns
        column_order = ["Label", "Easting", "Northing", "Ortho Height"]
        df = df[column_order]
        print(f"CSV columns after reordering: {df.columns.tolist()}")

        print(f"Saving corrected CSV to: {output_file}")
        df.to_csv(output_file, index=False)
        print("✅ Processing complete.")
    except Exception as e:
        print(f"Error processing CSV: {e}")

# # Example usage with your geoid TIFF path
# process_csv(
#     input_file=r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\TestFolder\Test1\20240808\interpolated_micasense_pos.csv",
#     output_file=r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\TestFolder\Test1\20240808\interpolated_micasense_pos_correted_height.csv",
#     geoid_path=r"M:\working_package_2\2024_dronecampaign\02_processing\geoid\ch_swisstopo_chgeo2004_ETRS89_LN02.tif"
#     )