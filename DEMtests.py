# -*- coding: utf-8 -*-
"""""
This script processes images captured by DJI Zenmuse P1 (gimbal 1) and MicaSense RedEdge-MX/Dual (gimbal 2) sensors 
using the Matrice 300 RTK drone system. It assumes a specific folder structure as per TERN protocols and provides 
options to override raw data paths.
The script performs the following tasks:
1. Adds RGB and multispectral images to the Metashape project.
2. Stops for user input on calibration images.
3. Resumes processing to complete the workflow, including:
    - Blockshifting P1 (RGB camera) coordinates if required.
    - Converting coordinates to the target CRS.
    - Checking image quality and removing low-quality images.
    - Applying GPS/INS offsets.
    - Aligning images.
    - Building dense clouds and models.
    - Smoothing and exporting models.
    - Building and exporting orthomosaics.
    - Calibrating reflectance for multispectral images.
Functions:
    - cartesian_to_geog(X, Y, Z): Converts Cartesian coordinates to geographic coordinates using WGS84 ellipsoid.
    - find_files(folder, types): Finds files of specified types in a folder.
    - copyBoundingBox(from_chunk_label, to_chunk_labels): Copies bounding box from one chunk to others.
    - proc_rgb(): Processes RGB images to create orthomosaic and 3D model.
    - proc_multispec(): Processes multispectral images to create orthomosaic with relative reflectance.
    - resume_proc(): Resumes processing after user input on calibration images.
Usage:
    Run the script with the required and optional inputs as arguments. Follow the instructions in the console to 
    complete the calibration steps and resume processing.
"""""
"""
Created August 2021

@author: Poornima Sivanandam

Script to process DJI Zenmuse P1 (gimbal 1) and MicaSense RedEdge-MX/Dual (gimbal 2) images captured simultaneously
using the Matrice 300 RTK drone system.

Assumption that folder structure is as per the TERN protocols:
Data |	Path | Example
Raw data |	<plot>/YYYYMMDD/imagery/<sensor>/level0_raw/ |	SASMDD0001/20220519/imagery/rgb/level0_raw
Data products |	<plot>/YYYYMMDD/imagery/<sensor>/level1_proc/	| SASMDD0001/20220519/imagery/multispec/level1_proc
Metashape project |	plot/YYYYMMDD/imagery/metashape| SASRIV0001/20220516/imagery/metashape/
DRTK logs | plot/YYYYMMDD/drtk/

Raw data paths can be overriden using 'Optional Inputs'.

Required Input:
    -crs "<EPSG code for target projected coordinate reference system. Also used in MicaSense position interpolation>"
    Example: -crs "7855"
    See https://epsg.org/home.html

Optional Inputs:
    1. -multispec "path to multispectral level0_raw folder containing raw data"
        Default is relative to project location: ../multispec/level0_raw/
    2. -rgb "path to RGB level0_raw folder which also has the MRK file(s)"
        Default is relative to project location: ../rgb/level0_raw/
    3. -smooth "<low/medium/high>"
        Strength value to smooth RGB model. Default is low.
        Low: for low-lying vegetation (grasslands, shrublands), Medium and high: as appropriate for forested sites.
    4. When P1 (RGB camera) coordinates have to be blockshifted:
        - Path to file containing DRTK init and AUSPOS cartesian coords passed using "-drtk <path to file>".

Summary:
    * Add RGB and multispectral images.
    * Stop script for user input on calibration images.
    * When 'Resume Processing' is clicked complete the processing workflow.

"""

import argparse
import math
import collections
import numpy as np
import Metashape
import os
import sys
import exifread
from collections import defaultdict
from upd_micasense_pos_filename import ret_micasense_pos
import importlib
import upd_micasense_pos_filename
import csv
import logging
from datetime import datetime
import TransformHeight
import requests


importlib.reload(upd_micasense_pos_filename)
from pathlib import Path


# Note: External modules imported were installed through:
# "C:\Program Files\Agisoft\Metashape Pro\python\python.exe" -m pip install <modulename>
# See M300 data processing protocol for more information.

# Metashape Python API updates in v2.0
METASHAPE_V2_PLUS = False
found_version = Metashape.app.version.split('.')  # e.g. 2.0.1
if int(found_version[0]) >= 2:
    METASHAPE_V2_PLUS = True

###############################################################################
# User-defined variables
# BASE DIRECTORY If you run multiple projects, update this path
# Decoide if you want to use model or DEM or for Orthomoasaic
###############################################################################
BASE_DIR = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects"



dem_res = [0.05]  # DEM resolutions in meters. For testing set to [0.2, 0.5] . For final processing set to desired value(s). 
ortho_res = 0.01  # Orthomosaic resolution in meters. For testing set to 0.5 or higher. For final processing set to 0.01
ortho_res_multi = 0.05 # Orthomosaic resolution for multispec chunk in meters. For testing set to 0.1 or higher. For final processing set to 0.05
####
#   IMPORTANT set quality settings !

use_model = True
use_dem = True

###############################################################################
# Constants
###############################################################################
GEOG_COORD = collections.namedtuple('Geog_CS', ['lat_decdeg', 'lon_decdeg', 'elliph'])

SOURCE_CRS = Metashape.CoordinateSystem("EPSG::4326")  # WGS84

CONST_a = 6378137  # Semi major axis
CONST_inv_f = 298.257223563  # Inverse flattening 1/f WGS84 ellipsoid
# Chunks in Metashape
CHUNK_RGB = "rgb"
CHUNK_MULTISPEC = "multispec"

IMG_QUAL_THRESHOLD = 0.7

DICT_SMOOTH_STRENGTH = {'low': 50, 'medium': 100, 'high': 200}

# Lever-arm offsets for different sensors on *Matrice 300*
# TODO: update this for other sensors and drone platforms
P1_GIMBAL1_OFFSET = (0.087, 0.0, 0.0)

# Measure lever-arm offsets (X, Y, Z) from the single gimbal position to the ‘master’ camera (by default, the lowest wavelength)
# In Metashape, the offsets are positive with respect to the actual camera positions. 
# See Metashape manual or TERN RGB Multispectral processing protocol for details.
offset_dict = defaultdict(dict)
offset_dict['RedEdge-M']['Red'] = (-0.097, -0.03, -0.06)
offset_dict['RedEdge-M']['Dual'] = (-0.097, 0.02, -0.08)
offset_dict['RedEdge-P']['Red'] = (0,0,0)
offset_dict['RedEdge-P']['Dual'] = (0,0,0)

###############################################################################
# Function definitions
###############################################################################
def setup_logging(project_path):
    """Configure logging to file and console"""
    log_dir = Path(project_path).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # File handler
    log_file = log_dir / f"{Path(project_path).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return log_file

def cartesian_to_geog(X, Y, Z):
    """
    Author: Poornima Sivanandam
    Convert Cartesian coordinates to geographic coordinates using WGS84 ellipsoid.
    Return Lat, Lon, ellipsoidal height as a named tuple.
    Calculations from Transformation_Conversion.xlsx at https://github.com/icsm-au/DatumSpreadsheets
    """
    f = 1 / CONST_inv_f
    e_sq = 2 * f - f ** 2
    p = math.sqrt(X ** 2 + Y ** 2)
    r = math.sqrt(p ** 2 + Z ** 2)
    mu = math.atan((Z / p) * (1 - f) + (e_sq * CONST_a) / r)

    lat_top_line = Z * (1 - f) + e_sq * CONST_a * math.sin(mu) ** 3
    lat_bottom_line = (1 - f) * (p - e_sq * CONST_a * math.cos(mu) ** 3)

    lon = math.atan(Y / X)
    lat = math.atan(lat_top_line / lat_bottom_line)

    if (lon < 0):
        tmp_lon = lon + math.pi
    else:
        tmp_lon = lon

    lon_dec_deg = (tmp_lon / math.pi) * 180
    lat_dec_deg = (lat / math.pi) * 180

    ellip_h = p * math.cos(lat) + Z * math.sin(lat) - CONST_a * math.sqrt(1 - e_sq * math.sin(lat) ** 2)

    conv_coord = GEOG_COORD(lat_dec_deg, lon_dec_deg, ellip_h)

    return conv_coord


def find_files(folder, types):
    photo_list = list()
    for dir, subdir, file in os.walk(folder):
        for filename in file:
            if (filename.lower().endswith(types)):
                photo_list.append(os.path.join(dir, filename))
    return (photo_list)

def copyBoundingBox(from_chunk_label, to_chunk_label):
    print("Script started...")

    from_chunk = doc.findChunk(dict_chunks[from_chunk_label])

    to_chunk = doc.findChunk(dict_chunks[to_chunk_label])


    print("Copying bounding box from chunk '" + from_chunk.label + "' to " + to_chunk_label + " chunks...")

    T0 = from_chunk.transform.matrix

    region = from_chunk.region
    R0 = region.rot
    C0 = region.center
    s0 = region.size

    
    T = from_chunk.transform.matrix.inv() * T0

    R = Metashape.Matrix([[T[0, 0], T[0, 1], T[0, 2]],
                              [T[1, 0], T[1, 1], T[1, 2]],
                              [T[2, 0], T[2, 1], T[2, 2]]])

    scale = R.row(0).norm()
    R = R * (1 / scale)

    new_region = Metashape.Region()
    new_region.rot = R * R0
    c = T.mulp(C0)
    new_region.center = c
    new_region.size = s0 * scale * 1.2 # 20% larger bounding box

    to_chunk.region = new_region

def export_rgb_dem_ortho(chunk, proj_file, dem_resolutions, ortho_resolution):
    """
    Exports DEMs at different resolutions, imports them back, and builds corresponding RGB orthomosaics.
    """
    compression = Metashape.ImageCompression()
    compression.tiff_compression = Metashape.ImageCompression.TiffCompressionLZW  # default on Metashape
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

        res_m = float(dem_res_meters)

        print(f"  Exporting RGB DEM at resolution {dem_res_meters}m ({dem_res_cm}cm)...")
        chunk.exportRaster(
            path=str(dem_file),
            source_data=Metashape.ElevationData,
            image_format=Metashape.ImageFormatTIFF,
            image_compression=compression,
            resolution=res_m
        )
        dem_files_rgb[dem_res_meters] = dem_file
        print(f"  Exported RGB DEM: {dem_file}")
        logging.info(f"Exported RGB DEM at resolution {dem_res_meters}m: {dem_file}")

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
            fill_holes=True,
            blending_mode=Metashape.BlendingMode.MosaicBlending,
            resolution= float(ortho_resolution) # User-defined ortho resolution in function arguments
        )

        logging.info(f"Built RGB Orthomosaic using imported DEM ({dem_res_cm}cm) for orthorectification in chunk {chunk.label} with parameters: surface_data=Metashape.DataSource.ElevationData, refine_seamlines=True, fill_holes=True, blending_mode=Metashape.BlendingMode.MosaicBlending")
        
        ortho_file = Path(proj_file).parent / (Path(proj_file).stem + f"_{chunk.label}_ortho_{int(ortho_resolution * 100)}cm_dem{int(res_m * 100)}cm.tif") # Added dem resolution to ortho filename

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

def process_multispec_ortho_from_dems(chunk, proj_file, rgb_dem_files, ortho_resolution):
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
        dem_res_cm = round(dem_res * 100)
        ortho_resolution_cm = int(ortho_resolution * 100)
        print(f"  Loading RGB DEM at resolution {dem_res}m into Multispec Chunk: {chunk.label}")
        chunk.elevation = None # Clear existing elevation data
        chunk.importRaster(path=str(dem_file), crs=chunk.crs, format=Metashape.ImageFormatTIFF)
        print(f"  Loaded DEM: {dem_file}")

        print(f"  Building Multispec Orthomosaic using DEM at resolution {dem_res}m for chunk: {chunk.label}")
        chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ElevationData, refine_seamlines=True, fill_holes=True, blending_mode=Metashape.BlendingMode.MosaicBlending,
            resolution= float(ortho_resolution)) # User-defined ortho resolution in fuction arguments

        ortho_file = Path(proj_file).parent / (Path(proj_file).stem + f"_{chunk.label}_ortho_{ortho_resolution_cm}cm_dem{dem_res_cm}cm.tif") # Added dem resolution to ortho filename
        chunk.exportRaster(path=str(ortho_file),
                             image_format=Metashape.ImageFormatTIFF, save_alpha=False,
                             source_data=Metashape.OrthomosaicData, image_compression=compression)
        logging.info(f"  Exported Multispec Orthomosaic at resolution {ortho_resolution} using DEM at resolution {dem_res}m for orthorectification in chunk {chunk.label}: {ortho_file}")

    print(f"--- Completed Multispec Chunk: {chunk.label} processing using RGB DEMs ---")

def get_master_band_paths_by_suffix(chunk, suffix="_6.tif"):
    """
    Retrieves a list of file paths for all cameras in the given Metashape chunk,
    filtering for paths that end with the specified suffix.

    Args:
        chunk: The Metashape.Chunk object.
        suffix (str, optional): The file name suffix to filter for.
                                 Defaults to "_6.tif".

    Returns:
        A list of strings, where each string is the file path of a camera
        whose path ends with the specified suffix.
        Returns an empty list if the chunk is None or no matching paths are found.
    """
    if not chunk:
        print("Error: Input chunk is None.")
        return []

    master_band_paths = []
    for camera in chunk.cameras:
        if camera.photo and camera.photo.path.endswith(suffix):
            master_band_paths.append(camera.photo.path)
        elif camera.photo:
            pass  # Ignore paths that don't match the suffix
        else:
            print(f"Warning: Camera '{camera.label}' has no associated photo path.")
    return master_band_paths

def proc_rgb():
    """
    Author: Poornima Sivanandam
    Arguments: None
    Return: None
    Create: RGB orthomosaic in rgb/level1_proc or in Metashape project folder
        smoothed 3D model file in Metashape project folder
    Summary:
        * blockshift (optional through args)
        * convert to target CRS
        * Image Quality check
        * Apply GPS/INS offset for gimbal 1
        * Update Camera Accuracy settings for M300 RTK GNSS accuracy
        * Align images
        * Build dense cloud
        * Build model, decimate and smooth (use args)
        * Export model (for multispec chunk)
        * Build and export orthomosaic
    """
    # If P1 positions are to be blockshifted, do the following:
    # - Read the .txt file and convert Cartesian coordinates to WGS84 Lat/Lon
    # - Calculate the difference and apply the shift directly to the cameras (Lon/Lat/Ellipsoidal height) in 'rgb' chunk
    # Convert coordinate system for Lat/Lon to target projected coordinate system

    chunk = doc.findChunk(dict_chunks[CHUNK_RGB])
    proj_file = doc.path
    blockshift_p1 = False




    if args.drtk is not None:
        blockshift_p1 = True
        DRTK_TXT_FILE = args.drtk
        print("P1 blockshift set")

        # read from txt/csv cartesian for RTK initial (line 1) and AUSPOS coords (line 2)
        with open(DRTK_TXT_FILE, 'r') as file:
            line = file.readline()
            split_line = line.split(',')
            drtk_field = cartesian_to_geog(float(split_line[0]), float(split_line[1]), float(split_line[2]))
            line = file.readline()
            split_line = line.split(',')
            drtk_auspos = cartesian_to_geog(float(split_line[0]), float(split_line[1]), float(split_line[2]))

        # calc difference
        diff_lat = round((drtk_auspos.lat_decdeg - drtk_field.lat_decdeg), 6)
        diff_lon = round((drtk_auspos.lon_decdeg - drtk_field.lon_decdeg), 6)
        diff_elliph = round((drtk_auspos.elliph - drtk_field.elliph), 6)
        P1_shift = Metashape.Vector((diff_lon, diff_lat, diff_elliph))

        print("Shifting P1 cameras by: " + str(P1_shift))

        # shift coordinates in the chunk
        for camera in chunk.cameras:
            if not camera.label == camera.master.label:
                continue
            if not camera.reference.location:
                continue
            else:
                camera.reference.location = camera.reference.location + P1_shift


    # Log the reference CRS before reloading
    logging.info(f"Reference CRS before reloading: {chunk.crs}")
        # Export updated positions as csv for debug purposes. Not used in script.
    #chunk.exportReference(path=str(P1_CAM_CSV_WGS84), format=Metashape.ReferenceFormatCSV, columns="nxyz",
    #                          delimiter=",", items=Metashape.ReferenceItemsCameras)

    # Reload EXIF information in WGS84 to prevent any issues with blockshifting
    chunk.loadReferenceExif(load_rotation=True, load_accuracy=True)

    # Log the reference CRS after reloading
    logging.info(f"Reference CRS after reloading: {chunk.crs}")

    # Convert to projected coordinate system if necessary
    target_crs = Metashape.CoordinateSystem("EPSG::" + args.crs)
    current_chunk_crs = chunk.crs

    if current_chunk_crs != target_crs: # Check if CRS is different (direct object comparison)
        logging.info("Performing coordinate system transformation...")

        for camera in chunk.cameras:
            if not camera.reference.location:
                continue
            camera.reference.location = Metashape.CoordinateSystem.transform(camera.reference.location, SOURCE_CRS,
                                                                               target_crs)
        chunk.crs = target_crs
        logging.info("Chunk CRS transformed.")
    elif current_chunk_crs == target_crs:
        logging.info("Chunk is already in the target CRS. Skipping transformation.")
    else:
        logging.warning("Current chunk CRS is not defined. Transformation check skipped, setting target CRS directly.")
        chunk.crs = target_crs # Still set the target CRS even if current is undefined, as per original script.
        logging.info("Chunk CRS set directly.")
    
            
    # Export updated positions as csv for debug purposes. Not used in script.
    chunk.exportReference(path=str(P1_CAM_CSV_CH1903), format=Metashape.ReferenceFormatCSV, columns="nxyz",
                              delimiter=",", items=Metashape.ReferenceItemsCameras)

    # # Convert to projected coordinate system
    # target_crs = Metashape.CoordinateSystem("EPSG::" + args.crs)
    # for camera in chunk.cameras:
    #    if not camera.reference.location:
    #        continue
    #    camera.reference.location = Metashape.CoordinateSystem.transform(camera.reference.location, SOURCE_CRS,
    #                                                                     target_crs)

    # chunk.crs = target_crs

    global P1_shift_vec
    if blockshift_p1:
        # Export updated positions as csv for debug purposes. Not used in script.
        chunk.exportReference(path=str(P1_CAM_CSV_blockshift), format=Metashape.ReferenceFormatCSV, columns="nxyz",
                              delimiter=",", items=Metashape.ReferenceItemsCameras)

        # If P1  blockshifted, pass vector for x, y, z shift of micasense image position
        P1_shift_vec = np.array([diff_lat, diff_lon, diff_elliph])
    else:
        P1_shift_vec = np.array([0.0, 0.0, 0.0])

    doc.save()

    #
    # Estimate image quality and remove cameras with quality < threshold
    #
    if METASHAPE_V2_PLUS:
        chunk.analyzeImages()
    else:
        chunk.analyzePhotos()
    low_img_qual = []
    low_img_qual = [camera for camera in chunk.cameras if (float(camera.meta["Image/Quality"]) < IMG_QUAL_THRESHOLD)]
    if low_img_qual:
        print("Removing cameras with Image Quality < %.1f" % IMG_QUAL_THRESHOLD)
        logging.info("Removing cameras with Image Quality < %.1f" % IMG_QUAL_THRESHOLD)
        chunk.remove(low_img_qual)
    doc.save()

    #
    # GPS/INS offset
    #
    print(chunk.sensors[0].antenna.location_ref)
    print("Update GPS/INS offset for P1")
    chunk.sensors[0].antenna.location_ref = Metashape.Vector(P1_GIMBAL1_OFFSET)
    print(chunk.sensors[0].antenna.location_ref)

    #
    # Align Photos
    #
    

    # change camera position accuracy to 0.1 m
    chunk.camera_location_accuracy = Metashape.Vector((0.10, 0.10, 0.10))

    # # Downscale values per https://www.agisoft.com/forum/index.php?topic=11697.0
    # # Downscale: highest, high, medium, low, lowest: 0, 1, 2, 4, 8
    # # Quality:  High, Reference Preselection: Source

    for camera in chunk.cameras:
        if camera.transform:
            print(f"Camera {camera.label} is aligned")
        else:
            print(f"Camera {camera.label} is not aligned")
            chunk.matchPhotos(downscale=quality1, generic_preselection=False, reference_preselection=True,
                              reference_preselection_mode=Metashape.ReferencePreselectionSource)
            chunk.alignCameras()
            print("Aligning Cameras")
            logging.info("Aligning Cameras")
            doc.save()

    # Gradual selection based on reprojection error
    print("Gradual selection for reprojection error...")
    f = Metashape.TiePoints.Filter()
    threshold = 0.5
    f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
    f.removePoints(threshold)
    doc.save()
    #
    # Optimise Cameras
    #
    # Optimize camera alignment by adjusting intrinsic parameters
    logging.info("Optimizing camera alignment...")
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True, adaptive_fitting=False)
    doc.save()

    #
    # Build Dense Cloud
    #
    # check if exists and reuse depthmap? # reuse_depth=True below
    # downscale: ultra, high, medium, low, lowest: 1, 2, 4, 8, 16
    if chunk.point_cloud:
        logging.info("Skipping point cloud generation as it already exists.")
    else:  
        logging.info("Building dense cloud in RGB chunk...")
        print("Build dense cloud")
        if METASHAPE_V2_PLUS:
            chunk.buildDepthMaps(downscale=quality2,reuse_depth=True)
            chunk.buildPointCloud(keep_depth=True)
        else:
            chunk.buildDenseCloud()
        doc.save()

    compression = Metashape.ImageCompression()
    compression.tiff_compression = Metashape.ImageCompression.TiffCompressionLZW  # default on Metashape
    compression.tiff_big = True
    compression.tiff_tiled = True
    compression.tiff_overviews = True
    #
    # Build Mesh
    #
    if use_model:

        if chunk.model:
            logging.info(f"Skipping model generation as it already exists.")
        else:
            logging.info(f"Build mesh")
            if METASHAPE_V2_PLUS:
                chunk.buildModel(surface_type=Metashape.HeightField, source_data=Metashape.PointCloudData,
                                 face_count=Metashape.MediumFaceCount)
            else:
                chunk.buildModel(surface_type=Metashape.HeightField, source_data=Metashape.DenseCloudData,
                                 face_count=Metashape.MediumFaceCount)
            doc.save()

            # Decimate and smooth mesh to use as orthorectification surface
            # Halve face count?
            chunk.decimateModel(face_count=len(chunk.model.faces) / 2)
            # Smooth model
            smooth_val = DICT_SMOOTH_STRENGTH[args.smooth]
            chunk.smoothModel(smooth_val)
            # Export model for use in micasense chunk
            model_file = Path(proj_file).parent / f"{Path(proj_file).stem}_rgb_smooth_{DICT_SMOOTH_STRENGTH[args.smooth]}.obj"

            logging.info(f"Exporting smoothed model to build Orthomosaic in Multispectral chunk: {model_file}")

            chunk.exportModel(path=str(model_file), crs=target_crs, format=Metashape.ModelFormatOBJ)
            # build Orthomoasaic from Model data
            chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ModelData, refine_seamlines=True)
            
            ortho_file = Path(proj_file).parent / (Path(proj_file).stem + "_rgb_model_ortho_01.tif")

            chunk.exportRaster(path=str(ortho_file), resolution_x=ortho_res, resolution_y=ortho_res,
                                   image_format=Metashape.ImageFormatTIFF,
                                   save_alpha=False, source_data=Metashape.OrthomosaicData, image_compression=compression)
            print("Exported orthomosaic " + str(ortho_file))

            logging.info(f"Exported RGB orthomosaic: {ortho_file}")
            print(f"OUTPUT_ORTHO_RGB: {ortho_file}")
        

    #
    # Build DEM
    #

    
    if use_dem:

            if chunk.elevation:
                logging.info("Skipping DEM generation and full resolution Orthomosaic as it already exists.")
            else:
                print("Build DEM at full resolution. ")
                if METASHAPE_V2_PLUS:
                    chunk.buildDem(source_data=Metashape.PointCloudData, interpolation=Metashape.EnabledInterpolation) # DisabledInterpolation for full resolution
                else:
                    chunk.buildDem(source_data=Metashape.DenseCloudData, interpolation=Metashape.EnabledInterpolation) # DisabledInterpolation for full resolution
                    chunk.elevation = chunk.elevations[0]  # Ensuring correct resolution assignment

                    dem_file = Path(proj_file).parent / (Path(proj_file).stem + "_dem_full_res.tif")

                    chunk.exportRaster(path=str(dem_file), source_data=Metashape.ElevationData, image_format=Metashape.ImageFormatTIFF, image_compression=compression)
                    #include test variable for debugging:

                    chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ElevationData, refine_seamlines=True)
                    chunk.exportRaster(path=str(Path(proj_file).parent / (Path(proj_file).stem + "_rgb_ortho_fullresdem_1cm.tif")), resolution_x=ortho_res, resolution_y=ortho_res,)
                    doc.save()
            chunk.elevation = chunk.elevations[0]  # Ensuring correct resolution assignment

            rgb_dem_files =export_rgb_dem_ortho(chunk, proj_file, dem_res, ortho_res)

            report_path = Path(proj_file).parent / (Path(proj_file).stem + "_rgb_report.pdf")

            print(f"Exporting processing report to {report_path}...")
            chunk.exportReport(path = str(report_path))
            doc.save()

            logging.info(f"Exported RGB report: {report_path}")
            print(f"OUTPUT_REPORT_RGB: {report_path}")

            print("RGB chunk processing complete!")

            return rgb_dem_files #to be passed to process_multispec_ortho_from_dems
        


    # test = args.test #default is False 

    # if not test:
    #     #
    #     # Build and export orthomosaic
    #     #
    #     print("Build orthomosaic")
    #     if use_model:
    #         chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ModelData, refine_seamlines=True)
    #     elif use_dem:
    #         chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ElevationData, refine_seamlines=True)
    #     else:
    #         print("No valid surface data source specified for orthomosaic building.")
    #     doc.save()

    #     if chunk.orthomosaic:
    #         # set resolution to 1 cm
    #         res_xy = 0.01

    #         # if rgb/ folder does not exist in MRK_PATH save orthomosaic in the project directory
    #         # else save ortho in rgb/level1_proc/
    #         p1_idx = MRK_PATH.find("rgb")
    #         if p1_idx == -1:
    #             dir_path = Path(proj_file).parent
    #             print("Cannot find rgb/ folder. Saving ortho in " + str(dir_path))
    #         else:
    #             # create p1/level1_proc folder if it does not exist
    #             dir_path = Path(MRK_PATH[:p1_idx + len("rgb")]) / "level1_proc"
    #             dir_path.mkdir(parents=True, exist_ok=True)

    #         # file naming format: <projname>_rgb_ortho_<res_in_m>.tif
    #         ortho_file = dir_path / (
    #                 Path(proj_file).stem + "_rgb_ortho_01.tif")


    #         chunk.exportRaster(path=str(ortho_file), resolution_x=res_xy, resolution_y=res_xy,
    #                            image_format=Metashape.ImageFormatTIFF,
    #                            save_alpha=False, source_data=Metashape.OrthomosaicData, image_compression=compression)
    #         print("Exported orthomosaic " + str(ortho_file))

    #         logging.info(f"Exported RGB orthomosaic: {ortho_file}")
    #         print(f"OUTPUT_ORTHO_RGB: {ortho_file}")


    #     else:
    #         print("Skipping orthomosaic building and exporting due to test mode.")

        # Export the processing report

   


def proc_multispec(rgb_dem_files):
    """
    Author: Poornima Sivanandam
    Description: 
        Processes multispectral imagery by interpolating positions, filtering images, setting primary channels,
        applying GPS offsets, calibrating reflectance, aligning images, and exporting an orthomosaic.
    """
    chunk = doc.findChunk(dict_chunks[CHUNK_MULTISPEC])
    target_crs = Metashape.CoordinateSystem("EPSG::" + args.crs)
    
    # Determine master camera suffix
    camera = chunk.cameras[0]
    img_suffix_master = camera.master.label.split('_')[2]
    
    # Set shift vector for P1 to zero if only multispectral processing is performed
    global P1_shift_vec
    P1_shift_vec = np.array([0.0, 0.0, 0.0])
    print(f"Interpolating Micasense position based on P1 with blockshift {P1_shift_vec}")
    logging.info(f"Interpolating Micasense position based on P1 with blockshift {P1_shift_vec}")
    
    # Get master camera paths for Micasense images
    micasense_master_paths = get_master_band_paths_by_suffix(chunk, f"_{img_suffix_master}.tif")


    # Interpolate Micasense positions and apply transformations
    ret_micasense_pos(micasense_master_paths, MRK_PATH, MICASENSE_PATH, img_suffix_master, args.crs, str(MICASENSE_CAM_CSV), P1_shift_vec)
    #TransformHeight.process_csv(input_file=str(MICASENSE_CAM_CSV), output_file=str(MICASENSE_CAM_CSV_UPDATED), geoid_path=str(GEOID_PATH))
    
    # Load updated positions into Metashape
    chunk.importReference(str(MICASENSE_CAM_CSV), format=Metashape.ReferenceFormatCSV, columns="nxyz",
                          delimiter=",", crs=target_crs, skip_rows=1, items=Metashape.ReferenceItemsCameras)
    chunk.crs = target_crs
    doc.save()
    
    del_camera_names = list()

    # Only look at altitude of master band images
    for camera in chunk.cameras:
        if not camera.label == camera.master.label:
            continue
        if not camera.reference.location:
            continue
        if camera.reference.location.z == 0:
            del_camera_names.append(camera.label)

    # Delete images outside of P1 capture times
    logging.info("Deleting MicaSense images that triggered outside P1 capture times")
    for camera in chunk.cameras:
        # Only calibration images are in a group. The following line is necessary to avoid NoneType error on other images
        if camera.group is not None:
            if camera.group.label == 'Calibration images':
                continue
        if camera.label in del_camera_names:
            chunk.remove(camera)
    
    # Set the primary channel
    set_primary = "NIR" if cam_model == 'RedEdge-M' else 'Panchro'
    for s in chunk.sensors:
        if set_primary in s.label:
            print(f"Setting primary channel to {s.label}")
            logging.info(f"Setting primary channel to {s.label}")
            chunk.primary_channel = s.layer_index
            break
    
    # Apply GPS offset correction
    print("Updating Micasense GPS offset")
    chunk.sensors[0].antenna.location_ref = Metashape.Vector(MS_GIMBAL2_OFFSET)
    
    # Configure raster transformation for reflectance calculation
    print("Updating Raster Transform for relative reflectance")
    logging.info("Updating Raster Transform for relative reflectance")
    num_bands = len(chunk.sensors)
    raster_transform_formula = [f"B{band}/32768" for band in range(1, num_bands + 1) if cam_model != 'RedEdge-P' or band != (5 if num_bands >= 10 else 3)]
    chunk.raster_transform.formula = raster_transform_formula
    chunk.raster_transform.calibrateRange()
    chunk.raster_transform.enabled = True
    doc.save()
    

    if METASHAPE_V2_PLUS:
        chunk.analyzeImages()
    else:
        chunk.analyzePhotos()
    low_img_qual = []
    low_img_qual = [camera.master for camera in chunk.cameras if (float(camera.meta["Image/Quality"]) < 0.5)]
    if low_img_qual:
        print("Removing cameras with Image Quality < %.1f" % 0.5)
        logging.info("Removing cameras with Image Quality < %.1f" % 0.5)
        chunk.remove(list(set(low_img_qual)))
    doc.save()
    
    # Calibrate Reflectance
    chunk.calibrateReflectance(use_reflectance_panels=True, use_sun_sensor=args.sunsens)
    print(f"Calibrated reflectance using reflectance panels: {True} and sun sensor: {args.sunsens}")
    logging.info(f"Calibrated reflectance using reflectance panels: {True} and sun sensor: {args.sunsens}")

    
    # Align Photos and optimize camera alignment
    chunk.camera_location_accuracy = Metashape.Vector((0.50, 0.50, 0.50))
        # Downscale values per https://www.agisoft.com/forum/index.php?topic=11697.0
    # Downscale: highest, high, medium, low, lowest: 0, 1, 2, 4, 8 # to be set below
    # Quality:  Set below, Reference Preselection: Source

    for camera in chunk.cameras:
        if camera.transform:
            print(f"Camera {camera.label} is aligned")
           
        else:
            chunk.matchPhotos(downscale=quality3, generic_preselection=True, reference_preselection=True, reference_preselection_mode=Metashape.ReferencePreselectionSource, tiepoint_limit=10000)
            print("Aligning cameras")
            logging.info("Aligning cameras")
            chunk.alignCameras()
            doc.save()
    
    # Gradual selection and optimization
    print("Optimizing camera alignment...")
    f = Metashape.TiePoints.Filter()
    f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
    f.removePoints(0.5)
    # Optimize camera alignment by adjusting intrinsic parameters
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True, adaptive_fitting=False)
    doc.save()
    
    # Reset bounding box region
    chunk.resetRegion()
    
    # Build and export orthomosaic
    if use_model:
        model_file = Path(proj_file).parent / f"{Path(proj_file).stem}_rgb_smooth_{DICT_SMOOTH_STRENGTH[args.smooth]}.obj"
        chunk.importModel(path=str(model_file), crs=target_crs, format=Metashape.ModelFormatOBJ)
        chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ModelData, refine_seamlines=True)
    
    if use_dem:
       
       process_multispec_ortho_from_dems(chunk, proj_file, rgb_dem_files, ortho_res_multi)
    
    # Export Processing Report
    report_path = Path(proj_file).parent/ f"{Path(proj_file).stem}_multispec_report.pdf"
    print(f"Exporting processing report to {report_path}...")
    chunk.exportReport(path=str(report_path))
    doc.save()
    
    print("Multispec chunk processing complete!")

# Write arguments to CSV file
def write_arguments_to_csv():
    global BASE_DIR
    csv_file = os.path.join(BASE_DIR, "arguments_logstep2.csv")
    headers = ["proj_path"] + [arg for arg in vars(args).keys()]

    # Collect argument values
    row = [proj_file] + [str(getattr(args, arg)) for arg in vars(args).keys()]

    # Check if the row already exists in the CSV file
    if os.path.exists(csv_file):
        with open(csv_file, mode='r', newline='') as file:
            reader = csv.reader(file)
            for existing_row in reader:
                if existing_row == row:
                    print("Row already exists in the CSV file. Skipping writing.")
                    return

    # Write the row to the CSV file
    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(headers)  # Write headers if file is empty
        writer.writerow(row)
        print("Arguments written to CSV file.")

# Resume processing
def resume_proc():
    # Process RGB chunk if multionly is not set
    #if not args.multionly:
    rgb_output = proc_rgb()
    # Process multispec chunk
    if rgb_output:
        proc_multispec(rgb_output)
    else:
        logging.info("Error: RGB processing failed. Set Multispec input seperately.")
        rgb_dem_list = {0.05: Path(proj_file).parent / (Path(proj_file).stem + "_rgb_dem_5cm.tif")}
        logging.info("Using default DEM  for multispec processing.")

        proc_multispec(rgb_dem_list) 
    
    print("End of script")
    #del doc

# Proceed to next project



############################################
##  Main code
############################################
print("Script start")



# Parse arguments and initialise variables
parser = argparse.ArgumentParser(
    description='Update camera positions in P1 and/or MicaSense chunks in Metashape project')
parser.add_argument('-proj_path', help='path to Metashape project file', required=True)
parser.add_argument('-date', help='Date of flight in YYYYMMDD format', required=True)
parser.add_argument('-site', help='Site name', required=True)
parser.add_argument('-crs',
                    help='EPSG code for target projected CRS for micasense cameras. E.g: 7855 for GDA2020/MGA zone 55',
                    required=True)
parser.add_argument('-multispec', help='path to multispectral level0_raw folder with raw images')
parser.add_argument('-rgb', help='path to RGB level0_raw folder that also has the MRK files')
parser.add_argument('-smooth', help='Smoothing strength used to smooth RGB mesh low/med/high', default="medium")
parser.add_argument('-drtk', help='If RGB coordinates to be blockshifted, file containing \
                                                  DRTK base station coordinates from field and AUSPOS', default=None)
parser.add_argument('-sunsens', help='use sun sensor data for reflectance calibration', action='store_true')
parser.add_argument('-test', help='make processing faster for debugging', action='store_true')
parser.add_argument('-multionly', help='process multispec chunk only', action='store_true')

global args
args = parser.parse_args()

# Initialize logging first
setup_logging(args.proj_path)
logging.info(f"Starting processing for project: {args.proj_path}")

global MRK_PATH, MICASENSE_PATH

global doc
# Metashape project
mask = 1 # 2 ** len(Metashape.app.enumGPUDevices()) - 1 #Ser GPU devices
Metashape.app.gpu_mask = mask

devices = Metashape.app.enumGPUDevices()
print("Detected GPUs in Metashape:")
for i, device in enumerate(devices):
    logging.info(f"  GPU {i+1}: {device['name']}") # Accessing 'name' as a dictionary key

doc = Metashape.Document()

# set logging location:

Metashape.app.settings.log_enable = True
Metashape.app.settings.log_path = str(Path(args.proj_path).parent / "metashape_log.txt")
# Open the Metashape project
proj_file = args.proj_path
doc.open(proj_file, read_only=False)  # Open the document in editable mode

doc.read_only = False    #make sure the project is not read-only

if doc is None:
    print("Error: Metashape document object is not initialized.")
    sys.exit()

if args.rgb:
    MRK_PATH = args.rgb
else:
    # Default is relative to project location: ../rgb/level0_raw/
    MRK_PATH = Path(proj_file).parents[1] / "rgb/level0_raw"
    if not MRK_PATH.is_dir():
        sys.exit("%s directory does not exist. Check and input paths using -rgb " % str(MRK_PATH))
    else:
        MRK_PATH = str(MRK_PATH)

# TODO update when other sensors are used
if args.multispec:
    MICASENSE_PATH = args.multispec
else:
    # Default is relative to project location: ../multispec/level0_raw/
    MICASENSE_PATH = Path(proj_file).parents[1] / "multispec/level0_raw"

    if not MICASENSE_PATH.is_dir():
        sys.exit("%s directory does not exist. Check and input paths using -multispec " % str(MICASENSE_PATH))
    else:
        MICASENSE_PATH = str(MICASENSE_PATH)

if args.drtk is not None:
    DRTK_TXT_FILE = args.drtk
    if not Path(DRTK_TXT_FILE).is_file():
        sys.exit("%s file does not exist. Check and input correct path using -drtk option" % str(DRTK_TXT_FILE))

if args.smooth not in DICT_SMOOTH_STRENGTH:
    sys.exit("Value for -smooth must be one of low, medium or high.")

# Set quality values for the downscale value in RGB and Multispec for testing
if args.test:
    quality1 = 4 #highest, high, medium, low, lowest: 0, 1, 2, 4, 8
    quality2 = 8 #ultra, high, medium, low, lowest: 1, 2, 4, 8, 16
    quality3 = 2 #highest, high, medium, low, lowest: 0, 1, 2, 4, 8
    print("Test mode enabled: quality1 set to 4, quality2 set to 8, quality3 set to 2")
else:
    quality1 = 1  #highest, high, medium, low, lowest: 0, 1, 2, 4, 8
    quality2 = 2  #ultra, high, medium, low, lowest: 1, 2, 4, 8, 16
    quality3 = 0 #highest, high, medium, low, lowest: 0, 1, 2, 4, 8
    print("Default mode: quality1 set to 0, quality2 set to 1, quality3 set to 0")

logging.info(f"Quality settings: quality1={quality1}, quality2={quality2}, quality3={quality3}")

# Export blockshifted P1 positions. Not used in script. Useful for debug or to restart parts of script following any issues.
P1_CAM_CSV_WGS84 = Path(proj_file).parent / "p1_pos_WGS84.csv"
P1_CAM_CSV_CH1903 = Path(proj_file).parent / "p1_pos_CH1903.csv"
P1_CAM_CSV_blockshift = Path(proj_file).parent / "p1_pos_blockshift.csv"
# By default save the CSV with updated MicaSense positions in the MicaSense folder. CSV used within script.
MICASENSE_CAM_CSV = Path(proj_file).parent / "interpolated_micasense_pos.csv"
MICASENSE_CAM_CSV_UPDATED = Path(proj_file).parent / "interpolated_micasense_pos_updated.csv"
GEOID_PATH = r"M:\working_package_2\2024_dronecampaign\02_processing\geoid\ch_swisstopo_chgeo2004_ETRS89_LN02.tif"
##################
# Add images
##################
# If the multionli argument is not set, add images to the project


# Check that lever-arm offsets are non-zero:
# As this script is for RGB and MS images captured simultaneously on dual gimbal, lever-arm offsets cannot be 0.
#  Zenmuse P1
if P1_GIMBAL1_OFFSET == 0:
    err_msg = "Lever-arm offset for P1 in dual gimbal mode cannot be 0. Update offset_dict and rerun_script."
    Metashape.app.messageBox(err_msg)

# MicaSense: get Camera Model from one of the images to check the lever-arm offsets for the relevant model
micasense_images = find_files(MICASENSE_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))
sample_img = open(micasense_images[0], 'rb')
exif_tags = exifread.process_file(sample_img)
cam_model = str(exif_tags.get('Image Model'))

# HARDCODED number of bands.
# Dual sensor (RedEdge-MX Dual: 10, RedEdge-P Dual: 11)
# Dual sensor: If offsets are 0, exit with error.
MS_GIMBAL2_OFFSET = offset_dict[cam_model]['Dual']




# Used to find chunks in proc_*
check_chunk_list = [CHUNK_RGB, CHUNK_MULTISPEC]
dict_chunks = {}
for get_chunk in doc.chunks:
    dict_chunks.update({get_chunk.label: get_chunk.key})


try:
    # VERY IMPORTANT THE ACTUAL PROCESSING HAPPENS HERE
    resume_proc()
    logging.info("Processing completed successfully")
except Exception as e:
    logging.error(f"Processing failed: {str(e)}", exc_info=True)
    raise  # Re-raise exception to trigger error in main script
finally:
    doc.save()
    logging.info("Project saved")
print("DONE WITH PROJ:", proj_file)


