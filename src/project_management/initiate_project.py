# -*- coding: utf-8 -*-
"""
Created August 2021

@author: Poornima Sivanandam

Script to initiate Metashape project by loading DJI Zenmuse P1 and MicaSense RedEdge-MX/Dual images.
"""

import argparse
import collections
import numpy as np
import Metashape
import os
import sys
import exifread
from collections import defaultdict
from pathlib import Path
import csv

# Constants
GEOG_COORD = collections.namedtuple('Geog_CS', ['lat_decdeg', 'lon_decdeg', 'elliph'])
SOURCE_CRS = Metashape.CoordinateSystem("EPSG::4326")  # WGS84
CONST_a = 6378137  # Semi major axis
CONST_inv_f = 298.257223563  # Inverse flattening 1/f WGS84 ellipsoid
CHUNK_RGB = "rgb"
CHUNK_MULTISPEC = "multispec"
IMG_QUAL_THRESHOLD = 0.7
DICT_SMOOTH_STRENGTH = {'low': 50, 'medium': 100, 'high': 200}
P1_GIMBAL1_OFFSET = (0.087, 0.0, 0.0)
offset_dict = defaultdict(dict)
offset_dict['RedEdge-M']['Red'] = (-0.097, -0.03, -0.06)
offset_dict['RedEdge-M']['Dual'] = (-0.097, 0.02, -0.08)
offset_dict['RedEdge-P']['Red'] = (0, 0, 0)
offset_dict['RedEdge-P']['Dual'] = (0, 0, 0)

def find_files(folder, types):
    photo_list = list()
    for dir, subdir, file in os.walk(folder):
        for filename in file:
            if filename.lower().endswith(types):
                photo_list.append(os.path.join(dir, filename))
    return photo_list

def read_csv(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            yield row

def parse_csv_arguments(csv_file):
    csv_data = list(read_csv(csv_file))
    if not csv_data:
        sys.exit("CSV file is empty or invalid.")
    return csv_data[0]

def update_args_from_csv(args, csv_data):
    args.crs = csv_data['crs']
    args.multispec = csv_data['multispec']
    args.rgb = csv_data['rgb']
    args.smooth = csv_data['smooth']
    args.drtk = None  # Assuming DRTK is not provided in the CSV

csv_file = 'path_to_csv_file.csv'  # Replace with the actual path to your CSV file
csv_data = parse_csv_arguments(csv_file)
update_args_from_csv(args, csv_data)

def main():
    print("Script start")

    # Parse arguments and initialise variables
    parser = argparse.ArgumentParser(description='Initiate Metashape project by loading images')
    parser.add_argument('-crs', help='EPSG code for target projected CRS for micasense cameras. E.g: 7855 for GDA2020/MGA zone 55', required=True)
    parser.add_argument('-multispec', help='path to multispectral level0_raw folder with raw images')
    parser.add_argument('-rgb', help='path to RGB level0_raw folder that also has the MRK files')
    parser.add_argument('-smooth', help='Smoothing strength used to smooth RGB mesh low/med/high', default="low")
    parser.add_argument('-drtk', help='If RGB coordinates to be blockshifted, file containing DRTK base station coordinates from field and AUSPOS')

    global args
    args = parser.parse_args()
    global MRK_PATH, MICASENSE_PATH

    # Metashape project
    global doc
    doc = Metashape.app.document

    if doc is None:
        print("Error: No active Metashape project found.")
        sys.exit(1)

    proj_file = doc.path

    # if Metashape project has not been saved
    if proj_file == '':
        if args.rgb:
            proj_file = str(Path(args.rgb).parents[0] / "metashape_project.psx")
            print("Metashape project saved as %s" % proj_file)
            doc.save(proj_file)

    if args.rgb:
        MRK_PATH = args.rgb
    else:
        # Default is relative to project location: ../rgb/level0_raw/
        MRK_PATH = Path(proj_file).parents[1] / "rgb/level0_raw"
        if not MRK_PATH.is_dir():
            sys.exit("%s directory does not exist. Check and input paths using -rgb " % str(MRK_PATH))
        else:
            MRK_PATH = str(MRK_PATH)

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

    # Add images
    # rgb
    p1_images = find_files(MRK_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))
    chunk = doc.addChunk()
    chunk.label = "rgb"
    chunk.addPhotos(p1_images, load_xmp_accuracy=True)

    # Check that chunk is not empty and images are in default WGS84 CRS
    if len(chunk.cameras) == 0:
        sys.exit("Chunk rgb empty")
    if "EPSG::4326" not in str(chunk.crs):
        sys.exit("Chunk rgb: script expects images loaded to be in CRS WGS84 EPSG::4326")

    # multispec
    micasense_images = find_files(MICASENSE_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))
    chunk = doc.addChunk()
    chunk.label = "multispec"
    chunk.addPhotos(micasense_images)
    doc.save()

    # Check that chunk is not empty and images are in default WGS84 CRS
    if len(chunk.cameras) == 0:
        sys.exit("Multispec chunk empty")
    if "EPSG::4326" not in str(chunk.crs):
        sys.exit("Multispec chunk: script expects images loaded to be in CRS WGS84 EPSG::4326")

    # Check that lever-arm offsets are non-zero:
    if P1_GIMBAL1_OFFSET == 0:
        err_msg = "Lever-arm offset for P1 in dual gimbal mode cannot be 0. Update offset_dict and rerun_script."
        Metashape.app.messageBox(err_msg)

    sample_img = open(micasense_images[0], 'rb')
    exif_tags = exifread.process_file(sample_img)
    cam_model = str(exif_tags.get('Image Model'))

    if len(chunk.sensors) >= 10:
        if offset_dict[cam_model]['Dual'] == (0, 0, 0):
            err_msg = "Lever-arm offsets for " + cam_model + " Dual on gimbal 2 cannot be 0. Update offset_dict and rerun script."
            Metashape.app.messageBox(err_msg)
        else:
            MS_GIMBAL2_OFFSET = offset_dict[cam_model]['Dual']
    else:
        if offset_dict[cam_model]['Red'] == (0, 0, 0):
            err_msg = "Lever-arm offsets for " + cam_model + " Red on gimbal 2 cannot be 0. Update offset_dict and rerun script."
            Metashape.app.messageBox(err_msg)
        else:
            MS_GIMBAL2_OFFSET = offset_dict[cam_model]['Red']

    check_chunk_list = ["rgb", "multispec"]
    dict_chunks = {}
    for get_chunk in doc.chunks:
        dict_chunks.update({get_chunk.label: get_chunk.key})

    if 'Chunk 1' in dict_chunks:
        chunk = doc.findChunk(dict_chunks['Chunk 1'])
        doc.remove(chunk)
        doc.save()

    doc.save()
    print("Add images completed.")
    print("###########################")
    print("###########################")
    print("###########################")
    print("###########################")
    print("Step 1. In the Workspace pane, select multispec chunk. Select Tools-Calibrate Reflectance and 'Locate panels'. Press Cancel once the panels have been located.")
    print("Note: The csv of the calibration panel will have to be loaded if this is the first run on the machine. See the protocol for more information.")
    print("Step 2. In the Workspace pane under multispec chunk open Calibration images folder. Select and remove images not to be used for calibration.")
    print("Step 3. Press the 'Show Masks' icon in the toolbar and inspect the masks on calibration images.")
    print("Complete Steps 1 to 3 and press 'Resume Processing' to continue. Reflectance calibration will be completed in the script.")
    print("###########################")
    print("###########################")
    print("###########################")
    print("###########################")

if __name__ == "__main__":
    main()