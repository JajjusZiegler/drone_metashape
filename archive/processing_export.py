# -*- coding: utf-8 -*-
"""
Created August 2021

Script to process and export Metashape project with DJI Zenmuse P1 and MicaSense RedEdge-MX/Dual images.
"""

import argparse
import math
import collections
import numpy as np
import Metashape
import os
import sys
from collections import defaultdict
from pathlib import Path
from upd_micasense_pos import ret_micasense_pos
import importlib
import upd_micasense_pos
from metashape_proc_tern import proc_rgb, proc_multispec

importlib.reload(upd_micasense_pos)

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


def main():
    parser = argparse.ArgumentParser(description='Process and export Metashape project with DJI Zenmuse P1 and MicaSense RedEdge-MX/Dual images.')
    parser.add_argument('-crs', help='EPSG code for target projected CRS for micasense cameras. E.g: 7855 for GDA2020/MGA zone 55', required=True)
    parser.add_argument('-multispec', help='path to multispectral level0_raw folder with raw images')
    parser.add_argument('-rgb', help='path to RGB level0_raw folder that also has the MRK files')
    parser.add_argument('-smooth', help='Smoothing strength used to smooth RGB mesh low/med/high', default="low")
    parser.add_argument('-drtk', help='If RGB coordinates to be blockshifted, file containing DRTK base station coordinates from field and AUSPOS')
    args = parser.parse_args()

    global MRK_PATH, MICASENSE_PATH, P1_shift_vec, doc, dict_chunks

    doc = Metashape.app.document
    proj_file = doc.path

    if args.rgb:
        MRK_PATH = args.rgb
    else:
        MRK_PATH = Path(proj_file).parents[1] / "rgb/level0_raw"
        if not MRK_PATH.is_dir():
            sys.exit("%s directory does not exist. Check and input paths using -rgb " % str(MRK_PATH))
        else:
            MRK_PATH = str(MRK_PATH)

    if args.multispec:
        MICASENSE_PATH = args.multispec
    else:
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

    P1_CAM_CSV = Path(proj_file).parent / "dbg_shifted_p1_pos.csv"
    MICASENSE_CAM_CSV = Path(proj_file).parent / "interpolated_micasense_pos.csv"

    check_chunk_list = [CHUNK_RGB, CHUNK_MULTISPEC]
    dict_chunks = {}
    for get_chunk in doc.chunks:
        dict_chunks.update({get_chunk.label: get_chunk.key})

    proc_rgb()
    proc_multispec()
    print("End of script")

if __name__ == "__main__":
    main()

