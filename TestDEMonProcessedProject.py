# -*- coding: utf-8 -*-
"""""
This script is modified from a previous version to specifically:
1. Load a Metashape project.
2. Process the "rgb" chunk:
    - Export DEMs at different resolutions.
    - Build and export RGB orthomosaics from these DEMs.
3. Process the "multispec" chunk:
    - Load the DEMs (exported from the "rgb" chunk).
    - Build and export multispec orthomosaics from these DEMs.

This script is designed to test the effect of DEM resolution on orthomosaic generation
for both RGB and Multispectral data, reusing RGB DEMs for multispectral orthorectification.

Usage:
    - Open your Metashape project that already has RGB and Multispectral chunks with images added and aligned.
    - Run this script in the Metashape Python console.
    - Modify BASE_DIR and chunk names if necessary to match your project.
"""""

import Metashape
import os
from pathlib import Path
import logging
from datetime import datetime
import importlib


###############################################################################
# BASE DIRECTORY - UPDATE THIS PATH TO YOUR PROJECT'S BASE FOLDER
# This script assumes the project file is in this directory or a subdirectory.
###############################################################################

BASE_DIR = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\TestFolder\Test2\20240708"  # <------- UPDATE THIS

use_model = False  # Using DEM for orthorectification as requested
use_dem = True

###############################################################################
# Constants - Modify Chunk names if your project uses different names
###############################################################################
CHUNK_RGB = "rgb"  # Name of your RGB chunk in Metashape project
CHUNK_MULTISPEC = "multispec"  # Name of your Multispectral chunk

METASHAPE_V2_PLUS = False
found_version = Metashape.app.version.split('.')
if int(found_version[0]) >= 2:
    METASHAPE_V2_PLUS = True


###############################################################################
# Function definitions
###############################################################################
def setup_logging(project_path):
    """Configure logging to file and console"""
    log_dir = Path(project_path).parent / "logs_dem_ortho_test_res_test"  # Specific log folder
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    log_file = log_dir / f"{Path(project_path).stem}_DEM_Ortho_ResTest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return log_file


def export_rgb_dem_ortho(chunk, proj_file, dem_resolutions):
    """
    Exports DEMs at different resolutions, imports them back, and builds corresponding RGB orthomosaics.
    """
    compression = Metashape.ImageCompression()
    compression.tiff_compression = Metashape.ImageCompression.TiffCompressionLZW
    compression.tiff_big = True
    compression.tiff_tiled = True
    compression.tiff_overviews = True

    print(f"--- Processing RGB Chunk: {chunk.label} for DEM and Orthomosaic at different resolutions ---")

    dem_files_rgb = {}

    for dem_res_meters in dem_resolutions:
        dem_res_cm = round(dem_res_meters * 100)

        print(f"  Setting elevation key for DEM resolution {dem_res_meters}m")
        chunk.elevation = chunk.elevations[0]  # Ensuring correct resolution assignment

        dem_file = Path(proj_file).parent / (Path(proj_file).stem + f"_{chunk.label}_dem_{dem_res_cm}cm.tif")

        res = float(dem_res_meters)

        print(f"  Exporting RGB DEM at resolution {dem_res_meters}m ({dem_res_cm}cm)...")
        chunk.exportRaster(
            path=str(dem_file),
            source_data=Metashape.ElevationData,
            image_format=Metashape.ImageFormatTIFF,
            image_compression=compression,
            resolution=res
        )
        dem_files_rgb[dem_res_meters] = dem_file
        print(f"  Exported RGB DEM: {dem_file}")

        # Import DEM back into the RGB chunk
        print(f"  Importing DEM {dem_file} back into RGB chunk...")
        chunk.elevation = None  # Clear existing elevation data
        chunk.importRaster(path=str(dem_file), crs=chunk.crs, format=Metashape.ImageFormatTIFF)
        print(f"  Imported DEM {dem_file}")

        # Generate RGB orthomosaic using the imported DEM
        print(f"  Building RGB Orthomosaic using imported DEM ({dem_res_cm}cm)...")
        chunk.buildOrthomosaic(
            surface_data=Metashape.DataSource.ElevationData,
            refine_seamlines=True,
            fill_holes=False,
            blending_mode=Metashape.BlendingMode.DisabledBlending,
            resolution= float(0.1) # 10cm resolution
        )

        ortho_file = Path(proj_file).parent / (Path(proj_file).stem + f"_{chunk.label}_ortho_dem{dem_res_cm}cm.tif")

        print(f"  Exporting RGB Orthomosaic...")
        chunk.exportRaster(
            path=str(ortho_file),
            image_format=Metashape.ImageFormatTIFF,
            save_alpha=False,
            source_data=Metashape.OrthomosaicData,
            image_compression=compression
        )
        print(f"  Exported RGB Orthomosaic: {ortho_file}")

    return dem_files_rgb


def process_multispec_ortho_from_dems(chunk, proj_file, rgb_dem_files):
    """
    Loads RGB DEMs into the multispec chunk and builds multispec orthomosaics for each DEM.
    """
    compression = Metashape.ImageCompression()
    compression.tiff_compression = Metashape.ImageCompression.TiffCompressionLZW
    compression.tiff_big = True
    compression.tiff_tiled = True
    compression.tiff_overviews = True

    print(f"--- Processing Multispec Chunk: {chunk.label} using RGB DEMs for Orthomosaics ---")

    # print(f"Building Dense Cloud for Multispec Chunk: {chunk.label}") # Ensure dense cloud exists
    # if METASHAPE_V2_PLUS:
    #     chunk.buildDepthMaps(downscale=2)  # Medium downscale, adjust if needed
    #     chunk.buildPointCloud()
    # else:
    #     chunk.buildDepthMaps(downscale=4)  # Medium/Low downscale for older versions
    #     chunk.buildDenseCloud(quality=Metashape.DenseCloudQuality.Medium)

    for dem_res, dem_file in rgb_dem_files.items():
        print(f"  Loading RGB DEM at resolution {dem_res}m into Multispec Chunk: {chunk.label}")
        chunk.elevation = None # Clear existing elevation data
        chunk.importRaster(path=str(dem_file), crs=chunk.crs, format=Metashape.ImageFormatTIFF)
        print(f"  Loaded DEM: {dem_file}")

        print(f"  Building Multispec Orthomosaic using DEM at resolution {dem_res}m for chunk: {chunk.label}")
        chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ElevationData, refine_seamlines=True, fill_holes=False, blending_mode=Metashape.BlendingMode.DisabledBlending,
            resolution= float(0.2)) # 20cm resolution

        ortho_file = Path(proj_file).parent / (Path(proj_file).stem + f"_{chunk.label}_ortho_{int(dem_res * 100)}cm_dem{int(dem_res * 100)}cm.tif") # Added dem resolution to ortho filename
        chunk.exportRaster(path=str(ortho_file),
                             image_format=Metashape.ImageFormatTIFF, save_alpha=False,
                             source_data=Metashape.OrthomosaicData, image_compression=compression)
        print(f"  Exported Multispec Orthomosaic using DEM at resolution {dem_res}m in chunk {chunk.label}: {ortho_file}")

    print(f"--- Completed Multispec Chunk: {chunk.label} processing using RGB DEMs ---")


###############################################################################
# Main script execution
###############################################################################
if __name__ == '__main__':
    doc = Metashape.Document()
    proj_file = os.path.join(BASE_DIR, "metashape_project_Test2_20240708.psx")

    # Try opening the project explicitly
    if not os.path.exists(proj_file):
        raise FileNotFoundError(f"Project file not found: {proj_file}")

    doc.open(proj_file,  read_only=False)  # Opens the Metashape project

    log_file = setup_logging(proj_file)
    logging.info(f"----- Starting DEM Resolution Test Script -----")
    logging.info(f"Project file: {proj_file}")
    print(f"Logging to file: {log_file}")

    # Create a dictionary mapping chunk labels to their chunk objects
    check_chunk_list = [CHUNK_RGB, CHUNK_MULTISPEC]
    dict_chunks = {chunk.label: chunk for chunk in doc.chunks}

    if not dict_chunks:
        raise ValueError("No chunks were found in the project. Ensure the project is correctly opened and contains data.")

    # Check if required chunks exist
    for chunk_name in check_chunk_list:
        if chunk_name not in dict_chunks:
            raise ValueError(f"Chunk '{chunk_name}' not found in the Metashape project. Check chunk names.")

    # Retrieve chunks safely
    chunk_rgb = dict_chunks[CHUNK_RGB]
    chunk_multispec = dict_chunks[CHUNK_MULTISPEC]

    dem_resolutions_test = [0.1, 0.2, 0.5, 3]  # Resolutions to test

    # Process RGB Chunk - Export DEMs and RGB Orthomosaics
    rgb_dem_files = export_rgb_dem_ortho(chunk_rgb, proj_file, dem_resolutions_test)
    if not isinstance(rgb_dem_files, dict):
        raise TypeError(f"export_rgb_dem_ortho() did not return a dictionary, got {type(rgb_dem_files)} instead.")

    # Process Multispec Chunk - Load RGB DEMs and build Multispec Orthomosaics
    process_multispec_ortho_from_dems(chunk_multispec, proj_file, rgb_dem_files)

    logging.info(f"----- DEM Resolution Test Script Finished -----")
    print(f"----- DEM Resolution Test Script Finished -----")
    print(f"Outputs are saved in the project folder: {Path(proj_file).parent}")
