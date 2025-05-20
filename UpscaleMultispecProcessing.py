import Metashape
import argparse
import os
from pathlib import Path
import logging
from datetime import datetime
import exifread

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
reference_dir = project_dir / "references"


# --- Logging ---
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())
logging.info("Starting multispec-only processing")


#--- functions ---
def find_files(folder, types):
    photo_list = list()
    for dir, subdir, file in os.walk(folder):
        for filename in file:
            if (filename.lower().endswith(types)):
                photo_list.append(os.path.join(dir, filename))
    return (photo_list)

# --- variables ---
MICASENSE_PATH = args.multispec
micasense_images = find_files(MICASENSE_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))
sample_img = open(micasense_images[0], 'rb')
exif_tags = exifread.process_file(sample_img)
cam_model = str(exif_tags.get('Image Model'))


# --- Open Project ---
doc = Metashape.Document()
doc.open(str(project_path), read_only=False)

doc.read_only = False    #make sure the project is not read-only

chunk = next((ch for ch in doc.chunks if "multispec" in ch.label.lower()), None)

if not chunk:
    logging.error("No 'multispec' chunk found in project")
    raise SystemExit("No 'multispec' chunk found.")



    # Set the primary channel
set_primary = "NIR" if cam_model == 'RedEdge-M' else 'Panchro'
for s in chunk.sensors:
    if set_primary in s.label:
        print(f"Setting primary channel to {s.label}")
        logging.info(f"Setting primary channel to {s.label}")
        chunk.primary_channel = s.layer_index
        break

chunk.loadReferenceExif(load_rotation=True, load_accuracy=True)
# Define source and target coordinate systems
SOURCE_CRS = Metashape.CoordinateSystem("EPSG::4326")  # Example CRS, replace with the correct one
target_crs = Metashape.CoordinateSystem(f"EPSG::{args.crs}")

for camera in chunk.cameras:
    if not camera.reference.location:
        continue
    camera.reference.location = Metashape.CoordinateSystem.transform(camera.reference.location, SOURCE_CRS, target_crs)

        
# Configure raster transformation for reflectance calculation
print("Updating Raster Transform for relative reflectance")
logging.info("Updating Raster Transform for relative reflectance")
num_bands = len(chunk.sensors)
raster_transform_formula = [f"B{band}/32768" for band in range(1, num_bands + 1)]
chunk.raster_transform.formula = raster_transform_formula
chunk.raster_transform.calibrateRange()
chunk.raster_transform.enabled = True
doc.save()

compression = Metashape.ImageCompression()
compression.tiff_compression = Metashape.ImageCompression.TiffCompressionLZW
compression.tiff_big = True
compression.tiff_tiled = True
compression.tiff_overviews = True

# Ensure the reference directory exists
reference_dir.mkdir(parents=True, exist_ok=True)

analyze_done_multi = reference_dir / "MultiAnalyzeImageDone.txt"

if not analyze_done_multi.exists():
        chunk.analyzeImages()
        with open(analyze_done_multi, 'w') as done_file:
            done_file.write("analyzeImages step completed.\n")

low_img_qual = []
low_img_qual = [camera.master for camera in chunk.cameras if (float(camera.meta["Image/Quality"]) < 0.5)]
if low_img_qual:
        print("Removing cameras with Image Quality < %.1f" % 0.5)
        logging.info("Removing cameras with Image Quality < %.1f" % 0.5)
        chunk.remove(list(set(low_img_qual)))
doc.save()
    
calibrated = reference_dir / "MultiCalibrated.txt"
    # Calibrate reflectance using reflectance
if not calibrated.exists():
    chunk.calibrateReflectance(use_reflectance_panels=True, use_sun_sensor=args.sunsens)
    with open(calibrated, 'w') as calibrated_file:
        calibrated_file.write("Calibrated reflectance step completed.\n")
    print(f"Calibrated reflectance using reflectance panels: {True} and sun sensor: {args.sunsens}")
    logging.info(f"Calibrated reflectance using reflectance panels: {True} and sun sensor: {args.sunsens}")

    # --- Align Photos ---
    alignment_done_file = reference_dir / "AlignmentDone.txt"

    if not alignment_done_file.exists():
        print("Aligning cameras")
        logging.info("Aligning cameras")
        chunk.matchPhotos(
            downscale=0,
            generic_preselection=True,
            reference_preselection=False,
            tiepoint_limit=10000,
            reset_matches=True  # Resetting matches ensures that any previously aligned cameras are realigned
        )
        chunk.alignCameras(reset_alignment=True)
        doc.save()

        # Write a file to indicate alignment is done
        with open(alignment_done_file, 'w') as done_file:
            done_file.write("Alignment step completed.\n")
  
    print("Alignment already completed. Skipping this step.")
    logging.info("Alignment already completed. Skipping this step.")

# --- Dense Cloud ---
depth_maps_done_file = reference_dir / "DepthMapsDone.txt"

if not depth_maps_done_file.exists():
    print("Building depth maps")
    logging.info("Building depth maps")
    chunk.buildDepthMaps(downscale=2, filter_mode=Metashape.MildFiltering)
    doc.save()
    # Write a file to indicate depth maps are done
    with open(depth_maps_done_file, 'w') as done_file:
        done_file.write("Depth maps step completed.\n")
else:
    print("Depth maps already completed. Skipping this step.")
    logging.info("Depth maps already completed. Skipping this step.")
                 

dense_cloud_done_file = reference_dir / "DenseCloudDone.txt"
if not dense_cloud_done_file.exists():
    print("Building dense point cloud")
    logging.info("Building dense point cloud")
    chunk.buildPointCloud()
    doc.save()
    # Write a file to indicate dense cloud is done
    with open(dense_cloud_done_file, 'w') as done_file:
        done_file.write("Dense point cloud step completed.\n")
else:
    print("Dense point cloud already completed. Skipping this step.")
    logging.info("Dense point cloud already completed. Skipping this step.")

# --- Model (optional) ---
if not chunk.model:
    chunk.buildModel(surface_type=Metashape.Arbitrary, source_data=Metashape.PointCloudData, face_count=Metashape.MediumFaceCount)
else:
    logging.info("Model already exists. Skipping model building step.")
if not chunk.model:
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
ortho_path = export_dir / f"{args.date}_{args.site}_multispec_ortho.tif"

if not ortho_path.exists():

    chunk.buildOrthomosaic(surface_data=Metashape.DataSource.ModelData, refine_seamlines=True, blending_mode=Metashape.MosaicBlending)
    chunk.exportRaster(str(ortho_path), image_format=Metashape.ImageFormatTIFF, save_alpha=False,image_compression=compression, source_data=Metashape.OrthomosaicData, resolution= float(0.05), raster_transform=Metashape.RasterTransformValue)
    logging.info(f"Orthophoto exported to {ortho_path}")
    print(f"OUTPUT_ORTHO_MS: {ortho_path}")
else:
    print("Orthophoto already exists. Skipping export.")

# --- Report ---
report_path = export_dir / f"{args.date}_{args.site}_multispec_report.pdf"

if not report_path.exists():
    chunk.exportReport(str(report_path))
    logging.info(f"Report exported to {report_path}")
    print(f"OUTPUT_REPORT_MS: {report_path}")
else:
    print("Report already exists. Skipping export.")

# --- Save and close ---
doc.save()
del doc

logging.info("Processing complete.")