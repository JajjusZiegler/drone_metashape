# -*- coding: utf-8 -*-
import Metashape
import sys
import argparse

def inspect_chunk(project_path):
    print(f"Opening project: {project_path}")
    doc = Metashape.Document()
    doc.open(project_path, read_only=True)
    
    print(f"Project has {len(doc.chunks)} chunks.")
    
    rgb_chunk = None
    for chunk in doc.chunks:
        print(f"Checking chunk: '{chunk.label}'")
        if not chunk.cameras:
            print("  No cameras in this chunk.")
            continue
            
        print(f"  Camera count: {len(chunk.cameras)}")
        cam = chunk.cameras[0]
        print(f"  First camera label: {cam.label}")
        
        # Check Metadata structure
        if not cam.photo or not cam.photo.meta:
            print("  No photo meta data available.")
        else:
            print("  Meta keys sample:")
            try:
                # Metashape metadata is not a standard dict, iterate if possible or try specific keys
                keys_to_check = ["Exif/Model", "Exif/DateTimeOriginal", "Exif/SubSecTime"]
                for k in keys_to_check:
                    if k in cam.photo.meta:
                        print(f"    {k}: {cam.photo.meta[k]}")
                    else:
                        print(f"    {k}: <NOT FOUND>")
            except Exception as e:
                print(f"    Error accessing meta: {e}")

        # Check for P1/RGB indications
        is_rgb = False
        if cam.photo and cam.photo.meta:
             if "Exif/Model" in cam.photo.meta:
                 model = cam.photo.meta["Exif/Model"]
                 print(f"  Camera Model: {model}")
                 if "P1" in model or "Zenmuse" in model or "M300" in model:
                     is_rgb = True
        
        if is_rgb:
            rgb_chunk = chunk
            print("  -> Identified as potential RGB chunk.")
        
        # Check coordinates
        if cam.transform:
            print("  Camera has transform (Aligned).")
            if chunk.crs:
                print(f"  Chunk CRS: {chunk.crs.name}")
                center_internal = cam.center
                center_geo = chunk.crs.project(chunk.transform.matrix.mulp(center_internal))
                print(f"  Projected Position (First Cam): {center_geo}")
            else:
                print("  Chunk has NO CRS.")
        else:
            print("  Camera has NO transform (Not Aligned).")

    if rgb_chunk:
        print(f"\nSelected RGB Chunk: {rgb_chunk.label}")
    else:
        print("\nNo RGB chunk definitely identified.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project_psx", help="Path to Metashape project")
    args = parser.parse_args()
    
    inspect_chunk(args.project_psx)
