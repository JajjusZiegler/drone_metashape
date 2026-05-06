import rasterio

def rename_raster_bands(raster_path, new_band_names, output_path=None):
    """
    Renames bands in a raster file.

    Args:
        raster_path (str): Path to the input raster file.
        new_band_names (list): A list of new names for each band.
        output_path (str, optional): Path to save the renamed raster.

    Returns:
        str: Path to the output raster file path on success, None on error.
    """

    try:
        with rasterio.open(raster_path, 'r') as src:  # Open in read-only mode for source
            if len(new_band_names) != src.count:
                raise ValueError(f"Number of band names ({len(new_band_names)}) must match band count ({src.count}).")

            profile = src.profile.copy() # Copy the profile to modify
            profile.update(
                driver='GTiff',  # Force output to GeoTIFF format (explicitly set driver)
                descriptions=tuple(new_band_names) # Update descriptions in the profile
            )

            output_file = output_path if output_path else "renamed_raster_output.tif" # Ensure output path is set if None is provided

            with rasterio.open(output_file, 'w', **profile) as dst:
                for i in range(1, src.count + 1):
                    dst.write(src.read(i), i)

            # --- DEBUGGING: Read back and print descriptions from the newly created file ---
            with rasterio.open(output_file, 'r') as test_dst:
                print(f"DEBUG: Descriptions in the newly created file '{output_file}':")
                print(test_dst.descriptions)
            # --- DEBUGGING END ---


            print(f"Raster bands renamed and saved to: {output_file}")
            return output_file

    except rasterio.errors.RasterioIOError as e:
        print(f"Error opening raster file: {e}")
        return None
    except ValueError as ve:
        print(f"Value Error: {ve}")
        return None
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")
        return None


if __name__ == "__main__":
    raster_file_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\TestFolder\Test1\20240808\metashape_project_Test1_20240808_multispec_ortho_05.tif"  # Replace with your raster file path
    band_names_list = [
        "Blue-444", "Blue", "Green-531", "Green", "Red-650",
        "Red", "Red edge-705", "Red edge", "Red edge-740", "NIR"
    ]
    output_raster_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\TestFolder\Test1\20240808\renamed_raster1.tif" # Or a filename like "renamed_raster.tif"

    print(f"Script is using raster file path: {raster_file_path}") # Path verification print
    renamed_file = rename_raster_bands(raster_file_path, band_names_list, output_raster_path)

    if renamed_file:
        print(f"Renamed raster file is available at: {renamed_file}")