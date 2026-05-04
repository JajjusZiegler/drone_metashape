import argparse
import math
import collections
import numpy as np
import Metashape
import os
import sys
import exifread
from collections import defaultdict
from upd_micasense_pos import ret_micasense_pos
import importlib
import upd_micasense_pos
import csv



importlib.reload(upd_micasense_pos)
from pathlib import Path

# Define the base directory where the Metashape projects will be saved
csv_file_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\test.csv"

BASE_DIR = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\test_metashape_proj_creation"

CHUNK_MULTISPEC = "multispec"
CHUNK_RGB = "rgb"

def open_document(file_path):
    #doc = Metashape.app.document
    doc = Metashape.Document()
    doc.open(file_path,read_only=False, ignore_lock=False)
    return doc


def create_project_structure(site, date):
    doc = Metashape.Document()
    proj_file = os.path.join(BASE_DIR, site, date, f"{site}_{date}_metashape.psx")
    if not os.path.exists(proj_file):
        doc.save(proj_file)
    return proj_file

def find_files(folder, types):
    photo_list = list()
    for dir, subdir, file in os.walk(folder):
        for filename in file:
            if (filename.lower().endswith(types)):
                photo_list.append(os.path.join(dir, filename))
    return (photo_list)

def load_images(doc, rgb, multispec, CHUNK_RGB, CHUNK_MULTISPEC):

        p1_images = find_files(rgb, (".jpg", ".jpeg", ".tif", ".tiff"))
        chunk = doc.addChunk()
        chunk.label = CHUNK_RGB
        chunk.addPhotos(p1_images)  # , load_xmp_accuracy=True if you want to add accuracy from XMP

        # Check that chunk is not empty and images are in default WGS84 CRS
        if len(chunk.cameras) == 0:
            sys.exit("Chunk rgb empty")
        # check chunk coordinate systems are default EPSG::4326
        if "EPSG::4326" not in str(chunk.crs):
            sys.exit("Chunk rgb: script expects images loaded to be in CRS WGS84 EPSG::4326")

        # multispec
        micasense_images = find_files(multispec, (".jpg", ".jpeg", ".tif", ".tiff"))
        chunk = doc.addChunk()
        chunk.label = CHUNK_MULTISPEC
        chunk.addPhotos(micasense_images)
        doc.save()

def check_chunks(doc, CHUNK_RGB, CHUNK_MULTISPEC):
            # Used to find chunks in proc_*
        check_chunk_list = [CHUNK_RGB, CHUNK_MULTISPEC]
        dict_chunks = {}
        for get_chunk in doc.chunks:
            dict_chunks.update({get_chunk.label: get_chunk.key})

        chunk = doc.findChunk(dict_chunks[CHUNK_RGB])
        if not chunk:
            sys.exit("Chunk rgb not found in the project")

        chunk = doc.findChunk(dict_chunks[CHUNK_MULTISPEC])
        if not chunk:
            sys.exit("Chunk multispec not found in the project")
            # Delete 'Chunk 1' that is created by default.
        if 'Chunk 1' in dict_chunks:
            chunk = doc.findChunk(dict_chunks['Chunk 1'])
            doc.remove(chunk)
            doc.save()

def print_proj_message():
    print(f"Project message printed for file")
    

def pick_calibration_images():
    label = "Next Project Setup"
    Metashape.app.removeMenuItem(label)
    Metashape.app.addMenuItem(label, print_proj_message)
    Metashape.app.messageBox("Project setup complete")
    print("To execute this script press {}".format(label))


def process_row(row, csv_path):
    site = row['site']
    date = row['date']
    crs = row['crs']
    multispec = row['multispec']
    rgb = row['rgb']
    sunsens = row['sunsens'].lower() == "true"

    # Create project structure
    proj_file = create_project_structure(site, date)
    doc = open_document(proj_file)
    load_images(doc, rgb, multispec, CHUNK_RGB, CHUNK_MULTISPEC)
    check_chunks(doc, CHUNK_RGB, CHUNK_MULTISPEC)
    #pick_calibration_images()

    doc.save()

    # Close the current project
    doc.clear()
    with open(csv_path, mode='a', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([date,site,crs,multispec,rgb,sunsens,proj_file])



# Open the CSV and read rows
with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    csv_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\test_proj_creation.csv"
    with open(csv_path, mode='w', newline='', encoding='utf-8') as csv_file:    
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["date","site","crs","multispec","rgb","smooth","drtk","sunsens","test","multionly","proj_path"])
    for row in csv_reader:
        process_row(row, csv_path)