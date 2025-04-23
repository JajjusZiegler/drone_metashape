import Metashape
import argparse
import os
from pathlib import Path
import logging
from datetime import datetime

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Simple Multispec-only Metashape processor")
parser.add_argument('-proj_path', required=True)
parser.add_argument('-date', required=True)
parser.add_argument('-site', required=True)
parser.add_argument('-crs', required=True)
parser.add_argument('-multispec', required=True)
parser.add_argument('-smooth', default='medium', choices=['low', 'medium', 'high'])
parser.add_argument('-sunsens', action='store_true')
args = parser.parse_args()

# --- Paths ---
project_path = Path(args.proj_path)
project_dir = project_path.parent
export_dir = project_dir / "exports"
export_dir.mkdir(exist_ok=True)
log_file = export_dir / f"log_multispec_{args.date}_{args.site}.txt"

# --- Logging ---
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())
logging.info("Starting multispec-only processing")

# --- Open Project ---
doc = Metashape.Document()
doc.open(str(project_path), read_only=False)
chunk = next((ch for ch in doc.chunks if "multispec" in ch.label.lower()), None)

if not chunk:
    logging.error("No 'multispec' chunk found in project")
    raise SystemExit("No 'multispec' chunk found.")

chunk.crs = Metashape.CoordinateSystem(f"EPSG::{args.crs}")
chunk.loadReferenceExif(load_rotation=True, load_accuracy=True)

# --- Align Photos ---
print("Aligning cameras")
logging.info("Aligning cameras")
chunk.matchPhotos(
    downscale=1,
    generic_preselection=True,
    reference_preselection=False,
    tiepoint_limit=10000,
            # Resetting matches ensures that any previously aligned cameras are realigned 
            # to account for changes in reference data or other preprocessing steps.
    reset_matches=True
    )
chunk.alignCameras(reset_alignment=True)
doc.save()

# --- Dense Cloud ---
chunk.buildDepthMaps(downscale=2)
chunk.buildPointCloud()
doc.save()

# --- Model (optional) ---
chunk.buildModel(surface_type=Metashape.Arbitrary, source_data=Metashape.PointCloudData, face_count=Metashape.MediumFaceCount)
if chunk.model:
    smooth_strength = {'low': 50, 'medium': 100, 'high': 200}[args.smooth]
    chunk.decimateModel(face_count=len(chunk.model.faces) // 2)
    chunk.smoothModel(smooth_strength)
    model_path = export_dir / f"{args.date}_{args.site}_multispec_model.obj"
    chunk.exportModel(str(model_path))
    logging.info(f"Model exported to {model_path}")

# --- Reflectance Calibration ---
chunk.calibrateReflectance(use_reflectance_panels=True, use_sun_sensor=args.sunsens)
doc.save()

# --- Orthophoto ---
chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ModelData, refine_seamlines=True, blending_mode=Metashape.MosaicBlending)
ortho_path = export_dir / f"{args.date}_{args.site}_multispec_ortho.tif"
chunk.exportRaster(str(ortho_path), image_format=Metashape.ImageFormatTIFF, save_alpha=False, source_data=Metashape.OrthomosaicData)
logging.info(f"Orthophoto exported to {ortho_path}")
print(f"OUTPUT_ORTHO_MS: {ortho_path}")

# --- Report ---
report_path = export_dir / f"{args.date}_{args.site}_multispec_report.pdf"
chunk.exportReport(str(report_path))
logging.info(f"Report exported to {report_path}")
print(f"OUTPUT_REPORT_MS: {report_path}")

# --- Save and close ---
doc.save()
del doc
logging.info("Processing complete.")
