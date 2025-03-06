import numpy as np
import rasterio
from rasterio.enums import Resampling
from scipy.ndimage import gaussian_filter
import argparse

# --- Function to read a DEM ---
def read_dem(file_path):
    with rasterio.open(file_path) as src:
        dem = src.read(1)  # Read first band
        profile = src.profile  # Save metadata
    return dem, profile

# --- Function to resample the low-resolution DEM to match the high-resolution DEM ---
def resample_dem(src_path, target_profile):
    with rasterio.open(src_path) as src:
        data = src.read(
            out_shape=(1, target_profile['height'], target_profile['width']),
            resampling=Resampling.bilinear
        )
        return data[0]  # Return resampled DEM

# --- Adaptive DEM Smoothing ---
def smooth_high_res_dem(high_res_dem, low_res_dem, sigma=5, blend_factor=0.6):
    # Compute the difference (highlighting tree canopy variations)
    diff = high_res_dem - low_res_dem

    # Identify problematic areas (large negative differences)
    tree_mask = diff < -0.5  # Threshold (adjust based on DEM characteristics)

    # Apply Gaussian smoothing only to tree areas
    smoothed_high_res = high_res_dem.copy()
    smoothed_high_res[tree_mask] = gaussian_filter(high_res_dem, sigma=sigma)[tree_mask]

    # Blend the smoothed and original DEM for a natural transition
    final_dem = blend_factor * smoothed_high_res + (1 - blend_factor) * high_res_dem
    return final_dem

# --- Main Processing Function ---
def process_dems(high_res_path, low_res_path, output_path):
    # Load high-resolution DEM
    high_res_dem, high_res_profile = read_dem(high_res_path)

    # Resample low-resolution DEM to match high-resolution DEM
    low_res_dem = resample_dem(low_res_path, high_res_profile)

    # Smooth high-resolution DEM adaptively
    smoothed_dem = smooth_high_res_dem(high_res_dem, low_res_dem)

    # Save the final smoothed DEM
    high_res_profile.update(dtype=rasterio.float32)
    with rasterio.open(output_path, 'w', **high_res_profile) as dst:
        dst.write(smoothed_dem.astype(np.float32), 1)

# --- Run the script ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and smooth DEMs.")
    parser.add_argument("high_res_dem_path", type=str, help="Path to the high-resolution DEM file")
    parser.add_argument("low_res_dem_path", type=str, help="Path to the low-resolution DEM file")
    parser.add_argument("output_dem_path", type=str, help="Path to save the smoothed DEM file")
    
    args = parser.parse_args()
    
    process_dems(args.high_res_dem_path, args.low_res_dem_path, args.output_dem_path)
    print("Smoothing complete! Output saved to:", args.output_dem_path)


