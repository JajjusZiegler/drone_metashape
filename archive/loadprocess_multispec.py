from collections import defaultdict
from upd_micasense_pos_original import ret_micasense_pos
from pathlib import Path
import argparse
import math
import collections
import numpy as np
import Metashape
import os
import sys
import exifread
from collections import defaultdict
from upd_micasense_pos_original import ret_micasense_pos
import importlib
import upd_micasense_pos_original

importlib.reload(upd_micasense_pos_original)
from pathlib import Path

# -*- coding: utf-8 -*-
"""
Created October 2023

Script to process MicaSense RedEdge-MX/Dual (gimbal 2) images captured using the Matrice 300 RTK drone system.

Assumption that folder structure is as per the TERN protocols:
Data |	Path | Example
Raw data |	<plot>/YYYYMMDD/imagery/<sensor>/level0_raw/ |	SASMDD0001/20220519/imagery/multispec/level0_raw
Data products |	<plot>/YYYYMMDD/imagery/<sensor>/level1_proc/	| SASMDD0001/20220519/imagery/multispec/level1_proc
Metashape project |	plot/YYYYMMDD/imagery/metashape| SASRIV0001/20220516/imagery/metashape/
DRTK logs | plot/YYYYMMDD/drtk/

Raw data paths can be overridden using 'Optional Inputs'.

Required Input:
    -crs "<EPSG code for target projected coordinate reference system. Also used in MicaSense position interpolation>"
    Example: -crs "7855"
    See https://epsg.org/home.html

Optional Inputs:
    1. -multispec "path to multispectral level0_raw folder containing raw data"
        Default is relative to project location: ../multispec/level0_raw/
    2. -smooth "<low/medium/high>"
        Strength value to smooth RGB model. Default is low.
        Low: for low-lying vegetation (grasslands, shrublands), Medium and high: as appropriate for forested sites.

Summary:
    * Add multispectral images.
    * Stop script for user input on calibration images.
    * When 'Resume Processing' is clicked complete the processing workflow.

"""

importlib.reload(upd_micasense_pos_original)

# Metashape Python API updates in v2.0
METASHAPE_V2_PLUS = False
found_version = Metashape.app.version.split('.')  # e.g. 2.0.1
if int(found_version[0]) >= 2:
    METASHAPE_V2_PLUS = True

###############################################################################
# Constants
###############################################################################
GEOG_COORD = collections.namedtuple('Geog_CS', ['lat_decdeg', 'lon_decdeg', 'elliph'])

SOURCE_CRS = Metashape.CoordinateSystem("EPSG::4326")  # WGS84

DICT_SMOOTH_STRENGTH = {'low': 50, 'medium': 100, 'high': 200}

CHUNK_RGB = "rgb"
CHUNK_MULTISPEC = "multispec"

IMG_QUAL_THRESHOLD = 0.7

###############################################################################
# Function definitions
###############################################################################
def find_files(folder, types):
    photo_list = list()
    for dir, subdir, file in os.walk(folder):
        for filename in file:
            if filename.lower().endswith(types):
                photo_list.append(os.path.join(dir, filename))
    return photo_list

def copyBoundingBox(from_chunk_label, to_chunk_labels):
    print("Script started...")

    doc = Metashape.app.document

    from_chunk = None
    for chunk in doc.chunks:
        if chunk.label == from_chunk_label:
            from_chunk = chunk
            break

    if not from_chunk:
        raise Exception("Chunk '" + from_chunk_label + "' not found!")

    to_chunks = []
    for chunk in doc.chunks:
        if chunk.label in to_chunk_labels:
            to_chunks.append(chunk)

    if not to_chunks:
        raise Exception("No chunks found to copy bounding box to!")

    print("Copying bounding box from chunk '" + from_chunk.label + "' to " + str(len(to_chunks)) + " chunks...")

    T0 = from_chunk.transform.matrix

    region = from_chunk.region
    R0 = region.rot
    C0 = region.center
    s0 = region.size

    for chunk in to_chunks:
        chunk.region.rot = R0
        chunk.region.center = C0
        chunk.region.size = s0

def proc_multispec():
    """
    Author: Poornima Sivanandam
    Arguments: None
    Return: None
    Create: Multispec orthomosaic in multispec/level1_proc or in Metashape project folder
    Summary:
        * Interpolate micasense image position using p1 pos and timestamp.
        * Remove images that triggered outside p1 capture times
        * Image Quality check
        * Apply GPS/INS offset for gimbal 2
        * Set primary channel to NIR
        * Update Camera Accuracy settings for M300 RTK GNSS accuracy
        * Set raster transform to export relative reflectance in orthomosaic
        * Calibrate reflectance using both sun sensors and panels
        * Align images
        * Build dense cloud
        * Import RGB smoothed model (see proc_rgb)
        * Build and export orthomosaic with raster transformed values (relative reflectance)
    """

    chunk = doc.findChunk(dict_chunks[CHUNK_MULTISPEC])

    target_crs = Metashape.CoordinateSystem("EPSG::" + args.crs)

    # Get image suffix of master camera
    camera = chunk.cameras[0]
    cam_master = camera.master.label.split('_')

    # file naming assumption: IMG_xxxx_suffixNum
    img_suffix_master = cam_master[2]

    P1_shift_vec = np.array([0.0, 0.0, 0.0])

    print("Interpolate Micasense position based on P1 with blockshift" + str(P1_shift_vec))

    # inputs: paths to MRK file for P1 position, Micasense image path, image suffix for master band images, target CRS
    # returns output csv file with interpolated micasense positions
    ret_micasense_pos(MRK_PATH, MICASENSE_PATH, img_suffix_master, args.crs,
                      str(MICASENSE_CAM_CSV), P1_shift_vec)

    # Load updated positions in the chunk
    chunk.importReference(str(MICASENSE_CAM_CSV), format=Metashape.ReferenceFormatCSV, columns="nxyz",
                          delimiter=",", crs=target_crs, skip_rows=1,
                          items=Metashape.ReferenceItemsCameras)
    doc.save()

    # ret_micasense_pos wrote Altitude = 0 (last column) for MicaSense images that triggered when P1 did not.
    # Create a list of cameras with Altitude = 0
    del_camera_names = list()

    # Only look at altitude of master band images
    for camera in chunk.cameras:
        if camera.master.reference.location.z == 0:
            del_camera_names.append(camera.master.label)

    # Disable images outside of P1 capture times
    print("Disabling MicaSense images that triggered outside P1 capture times")
    for camera in chunk.cameras:
        if camera.label in del_camera_names:
            camera.enabled = False

    # save project
    doc.save()

    # Set primary channel
    #
    # Get index of NIR band. Micasense Dual: NIR is sensors[9], and in RedEdge-M sensors[4]
    if cam_model == 'RedEdge-M':
        primary_channel = 4
    elif cam_model == 'RedEdge-P':
        primary_channel = 9
    for s in chunk.sensors:
        s.index = primary_channel

    # GPS/INS offset for master sensor
    #
    print("Updating Micasense GPS offset")
    chunk.sensors[0].antenna.location_ref = Metashape.Vector(MS_GIMBAL2_OFFSET)

    #
    # Set Raster Transform to calculate reflectance
    #
    print("Updating Raster Transform for relative reflectance")
    raster_transform_formula = []
    num_bands = len(chunk.sensors)
    if cam_model == 'RedEdge-M':
        raster_transform_formula = ["B1/32768", "B2/32768", "B3/32768", "B4/32768", "B5/32768"]
    elif cam_model == 'RedEdge-P':
        raster_transform_formula = ["B1/32768", "B2/32768", "B3/32768", "B4/32768", "B5/32768", "B6/32768", "B7/32768", "B8/32768", "B9/32768", "B10/32768"]

    chunk.raster_transform.formula = raster_transform_formula
    chunk.raster_transform.calibrateRange()
    chunk.raster_transform.enabled = True
    doc.save()

    #
    # Estimate image quality and remove cameras with quality < threshold
    #
    if METASHAPE_V2_PLUS:
        chunk.estimateImageQuality()
    else:
        chunk.estimateImageQuality()
    low_img_qual = []
    low_img_qual = [camera.master for camera in chunk.cameras if (float(camera.meta["Image/Quality"]) < 0.5)]
    if low_img_qual:
        for camera in low_img_qual:
            camera.enabled = False
    doc.save()
    #
    #
    # Calibrate Reflectance
    #
    chunk.calibrateReflectance(use_reflectance_panels=True, use_sun_sensor= args.sunsens)

    #
    # Align Photos
    #
    # change camera position accuracy to 0.1 m
    chunk.camera_location_accuracy = Metashape.Vector((0.10, 0.10, 0.10))

    # Downscale values per https://www.agisoft.com/forum/index.php?topic=11697.0
    # Downscale: highest, high, medium, low, lowest: 0, 1, 2, 4, 8 # to be set below
    # Quality:  High, Reference Preselection: Source
    chunk.matchPhotos(downscale= quality3 , generic_preselection=False, reference_preselection=True,
                      reference_preselection_mode=Metashape.ReferencePreselectionSource)
    doc.save()
    print("Aligning cameras")
    chunk.alignCameras()
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
    print("Optimise alignment")
    chunk.optimizeCameras()
    doc.save()

    # copy bounding box from rgb chunk

    copyBoundingBox(CHUNK_RGB, CHUNK_MULTISPEC)

    #
    # Build and export orthomosaic
    #
    # Import P1 model for use in orthorectification
    smooth_val = DICT_SMOOTH_STRENGTH[args.smooth]
    model_file = Path(proj_file).parent / (Path(proj_file).stem + "_rgb_smooth_" + str(smooth_val) + ".obj")
    chunk.importModel(path=str(model_file), crs=target_crs, format=Metashape.ModelFormatOBJ)

    print("Build orthomosaic")
    chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ModelData, refine_seamlines=True)
    doc.save()

    if chunk.orthomosaic:
        orthomosaic_path = Path(proj_file).parent / (Path(proj_file).stem + "_multispec_orthomosaic.tif")
        chunk.exportOrthomosaic(path=str(orthomosaic_path), format=Metashape.ImageFormatTIFF, raster_transform=Metashape.RasterTransformValue)
        print(f"Orthomosaic exported to {orthomosaic_path}")

    # Export the processing report
    report_path = dir_path / (
                Path(proj_file).stem + "_multispec_report.pdf")
    print(f"Exporting processing report to {report_path}...")
    chunk.exportReport(path = str(report_path))
    doc.save()
        
    print("Multispec chunk processing complete!")


############################################
##  Main code
############################################
print("Script start")

# Parse arguments and initialise variables
parser = argparse.ArgumentParser(
    description='Update camera positions in MicaSense chunks in Metashape project')
parser.add_argument('-crs',
                    help='EPSG code for target projected CRS for micasense cameras. E.g: 7855 for GDA2020/MGA zone 55',
                    required=True)
parser.add_argument('-multispec', help='path to multispectral level0_raw folder with raw images')
parser.add_argument('-smooth', help='Smoothing strength used to smooth RGB mesh low/med/high', default="low")
parser.add_argument('-sunsens', help='boolean to use sun sensor data for reflectance calibration', default=False)
parser.add_argument('-test', help='boolean to make processing faster for debugging', default=False)

global args
args = parser.parse_args()
global MRK_PATH, MICASENSE_PATH



# Metashape project
global doc
doc = Metashape.app.document
proj_file = doc.path

MRK_PATH = "M:\working_package_2\2024_dronecampaign\01_data\dronetest\P1Data\DJI_202408080937_002_p1micasense60mtest"

# if Metashape project has not been saved
if proj_file == '':
    raise Exception("Metashape project has not been saved. Please save the project and try again.")

if args.multispec:
    MICASENSE_PATH = args.multispec
else:
    # Default is relative to project location: ../multispec/level0_raw/
    MICASENSE_PATH = str(Path(proj_file).parent / "../multispec/level0_raw/")

if args.smooth not in DICT_SMOOTH_STRENGTH:
    raise Exception("Invalid smoothing strength. Choose from 'low', 'medium', or 'high'.")

# Set quality values for the downscale value in Multispec for testing
if args.test:
    quality3 = 4  # low quality for testing
else:
    quality3 = 1  # high quality for production

# By default save the CSV with updated MicaSense positions in the MicaSense folder. CSV used within script.
MICASENSE_CAM_CSV = Path(proj_file).parent / "interpolated_micasense_pos.csv"

##################
# Add images
##################
#
# multispec
micasense_images = find_files(MICASENSE_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))

chunk = doc.addChunk()
chunk.label = CHUNK_MULTISPEC
chunk.addPhotos(micasense_images)
doc.save()

# Check that chunk is not empty and images are in default WGS84 CRS
if len(chunk.cameras) == 0:
    raise Exception("No images found in the multispec folder.")
if "EPSG::4326" not in str(chunk.crs):
    raise Exception("Chunk coordinate system is not EPSG::4326.")

# MicaSense: get Camera Model from one of the images to check the lever-arm offsets for the relevant model
sample_img = open(micasense_images[0], 'rb')
exif_tags = exifread.process_file(sample_img)
cam_model = str(exif_tags.get('Image Model'))

# HARDCODED number of bands.
if len(chunk.sensors) >= 10:
    MS_GIMBAL2_OFFSET = (0.0, 0.0, 0.0)  # Update with actual offset values
else:
    raise Exception("Unexpected number of sensors in the multispec chunk.")

# Used to find chunks in proc_*
check_chunk_list = [CHUNK_MULTISPEC]
dict_chunks = {}
for get_chunk in doc.chunks:
    if get_chunk.label in check_chunk_list:
        dict_chunks[get_chunk.label] = get_chunk

# Delete 'Chunk 1' that is created by default.
if 'Chunk 1' in dict_chunks:
    doc.remove(dict_chunks['Chunk 1'])

# Process multispec chunk
proc_multispec()
print("End of script")