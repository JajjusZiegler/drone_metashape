# -*- coding: utf-8 -*-
import Metashape
import os
import glob
import datetime
import numpy as np
import argparse
from pathlib import Path

# Constants for MRK parsing
GPSUTC_deltat = 0
LEAPSECS = 37 

def get_timestamp_from_mrk_line(mrk_line):
    parts = mrk_line.split()
    if len(parts) < 3:
        return None, None
        
    secs = float(parts[1])
    week = int(parts[2].strip("[]"))
    
    # Position (Lat/Lon/Ellh) usually in columns 6, 7, 8
    # Format: 177 429395.042 [2386] N 7622997.777, 638666.273, 563.856 ...
    # The columns depend on the specific MRK format. 
    # Based on previous scripts: col 6 is Lat, 7 is Lon, 8 is EllH (comma separated sometimes)
    
    try:
        lat = float(parts[6].split(",")[0])
        lon = float(parts[7].split(",")[0])
        ellh = float(parts[8].split(",")[0])
        pos = (lat, lon, ellh)
    except:
        pos = (0,0,0)

    epoch_secs = secs + (week * 7 * 24 * 60 * 60)
    temp_timestamp = datetime.datetime(1980, 1, 6) + datetime.timedelta(seconds=epoch_secs)
    p1_timestamp = temp_timestamp - datetime.timedelta(seconds=GPSUTC_deltat)
    
    return p1_timestamp.timestamp(), pos

def read_mrk_data(rgb_folder):
    print(f"Reading MRK files from: {rgb_folder}")
    mrk_files = sorted(glob.glob(os.path.join(rgb_folder, "**", "*.MRK"), recursive=True))
    
    data = []
    if not mrk_files:
        print("No MRK files found.")
        return data

    for m_file in mrk_files:
        print(f"  Parsing {os.path.basename(m_file)}")
        with open(m_file, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                ts, pos = get_timestamp_from_mrk_line(line)
                if ts:
                    data.append({
                        'file': os.path.basename(m_file),
                        'line': i + 1,
                        'timestamp': ts,
                        'mrk_pos_raw': pos # usually Lat/Lon/Alt
                    })
    return data

def compare_alignment(project_path, rgb_root):
    print(f"Opening project: {project_path}")
    doc = Metashape.Document()
    doc.open(str(project_path), read_only=True)
    
    # Find RGB Chunk
    rgb_chunk = None
    for chunk in doc.chunks:
        if chunk.cameras:
            cam = chunk.cameras[0]
            if cam.photo and cam.photo.meta:
                if "Exif/Model" in cam.photo.meta:
                    model = cam.photo.meta["Exif/Model"]
                else:
                    model = ""
                
                if "P1" in model or "Zenmuse" in model or "M300" in model:
                    rgb_chunk = chunk
                    break
    
    if not rgb_chunk:
        print("Could not identify RGB chunk definitively (looking for P1/Zenmuse).")
        # Fallback
        for chunk in doc.chunks:
            if "multispec" not in chunk.label.lower():
                rgb_chunk = chunk
                print(f"Fallback to chunk: {chunk.label}")
                break
    
    if not rgb_chunk:
        print("No suitable chunk found.")
        return

    print(f"Using Chunk: {rgb_chunk.label}")
    
    # Get Metashape Cameras
    ms_cameras = []
    for cam in rgb_chunk.cameras:
        ms_cameras.append(cam)
    
    # Sort Metashape cameras by filename
    ms_cameras.sort(key=lambda c: c.label)

    # Get MRK Data
    mrk_data = read_mrk_data(rgb_root)

    print("\n--- Comparison Summary ---")
    print(f"Metashape Cameras: {len(ms_cameras)}")
    print(f"MRK Entries:       {len(mrk_data)}")
    
    min_len = min(len(ms_cameras), len(mrk_data))
    
    print("\n--- Detailed Check (First 5 and Last 5) ---")
    if chunk.crs:
        print(f"Chunk CRS: {chunk.crs.name}")
    
    headers = f"{'Index':<5} | {'Camera Label (Metashape)':<30} | {'Aligned?':<8} | {'MRK Time':<20} | {'Dist (Aligned vs MRK*)':<20}"
    print("-" * len(headers))
    print(headers)

    # Helper to check position distance (rough check if coords match)
    # Note: MRK is usually WGS84 Lat/Lon, Metashape Aligned is in CRS (e.g. Swiss)
    # To compare, we'd need to project MRK. For now, we just print status.
    
    indices_to_show = list(range(0, min(5, min_len))) + list(range(max(5, min_len-5), min_len))
    indices_to_show = sorted(list(set(indices_to_show))) # matches unique
    
    for i in indices_to_show:
        cam = ms_cameras[i]
        mrk = mrk_data[i]
        
        aligned_str = "YES" if cam.transform else "NO"
        ts_str = f"{mrk['timestamp']:.3f}"
        
        print(f"{i:<5} | {cam.label:<30} | {aligned_str:<8} | {ts_str:<20} | {'N/A':<20}")

        # If we really want to compare positions, we need projection. 
        # But mostly we want to verify 1:1 match of index.
        
    print("\n--- Analysis ---")
    if len(ms_cameras) != len(mrk_data):
         print("WARNING: Count mismatch indicates potential issues with direct index-based matching.")
         diff = len(mrk_data) - len(ms_cameras)
         if diff > 0:
             print(f"There are {diff} more MRK entries than cameras. Possibly images were not imported or deleted.")
         else:
             print(f"There are {abs(diff)} more Cameras than MRK entries. Possibly extra images.")
    else:
        print("Counts match. Direct index-based matching is likely valid assuming sorted order.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-psx", required=True)
    parser.add_argument("--rgb-root", required=True)
    args = parser.parse_args()
    
    compare_alignment(args.project_psx, args.rgb_root)
