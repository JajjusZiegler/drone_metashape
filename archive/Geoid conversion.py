import rasterio
import numpy as np

def bilinear_interpolation(x, y, q11, q12, q21, q22):
    """
    Perform bilinear interpolation for a given point (x, y)
    using four neighboring values.pip 
    """
    return (q11 * (1 - x) * (1 - y) +
            q21 * x * (1 - y) +
            q12 * (1 - x) * y +
            q22 * x * y)

def get_geoid_offset(geoid_tif, lv95_x, lv95_y):
    """
    Reads the Swiss geoid model from a GeoTIFF file and returns
    the geoid height offset for given LV95 coordinates.
    
    Args:
        geoid_tif (str): Path to the Swiss geoid model GeoTIFF file.
        lv95_x (float): X-coordinate in CH1903+ (LV95).
        lv95_y (float): Y-coordinate in CH1903+ (LV95).
        
    Returns:
        float: Interpolated geoid height offset.
    """
    with rasterio.open(geoid_tif) as dataset:
        # Convert LV95 (Swiss grid) coordinates to raster pixel coordinates
        col, row = dataset.index(lv95_x, lv95_y)
        
        # Get surrounding pixel coordinates
        x1, x2 = int(col), int(col) + 1
        y1, y2 = int(row), int(row) + 1

        # Read geoid height values at four neighboring grid points
        q11 = dataset.read(1)[y1, x1]  # Top-left
        q12 = dataset.read(1)[y2, x1]  # Bottom-left
        q21 = dataset.read(1)[y1, x2]  # Top-right
        q22 = dataset.read(1)[y2, x2]  # Bottom-right

        # Compute normalized distances in raster space
        x_frac = col - x1
        y_frac = row - y1

        # Perform bilinear interpolation
        return bilinear_interpolation(x_frac, y_frac, q11, q12, q21, q22)

# Example Usage
geoid_file = "swiss_geoid.tif"  # Replace with your actual file path
lv95_x, lv95_y = 2600000, 1200000  # Example LV95 coordinate
offset = get_geoid_offset(geoid_file, lv95_x, lv95_y)
print(f"Geoid height offset: {offset:.2f} meters")
