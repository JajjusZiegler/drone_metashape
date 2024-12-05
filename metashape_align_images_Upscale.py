import argparse
import sys
from pathlib import Path
import exifread
import Metashape
from metashape_proc_Upscale import find_files, CHUNK_RGB, CHUNK_MULTISPEC, DICT_SMOOTH_STRENGTH, P1_GIMBAL1_OFFSET, offset_dict

def load_images():
    print("Script start")

    # Parse arguments and initialise variables
    parser = argparse.ArgumentParser(
        description='Update camera positions in P1 and/or MicaSense chunks in Metashape project')
    parser.add_argument('-crs',
                        help='EPSG code for target projected CRS for micasense cameras. E.g: 7855 for GDA2020/MGA zone 55',
                        required=True)
    parser.add_argument('-multispec', help='path to multispectral level0_raw folder with raw images')
    parser.add_argument('-rgb', help='path to RGB level0_raw folder that also has the MRK files')
    parser.add_argument('-smooth', help='Smoothing strength used to smooth RGB mesh low/med/high', default="low")
    parser.add_argument('-drtk', help='If RGB coordinates to be blockshifted, file containing \
                                                      DRTK base station coordinates from field and AUSPOS')

    global args
    args = parser.parse_args()
    global MRK_PATH, MICASENSE_PATH

    # Metashape project
    global doc
    doc = Metashape.app.document
    proj_file = doc.path


    # Directory to save Metashape projects. Set this according to your project structure.
    proj_directory = Path("M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects")

    # This saves the prject. It expects the multispec folder to be in the following structure: 
    #  ...\Micasense\Pynwald\20240613\...
    if args.multispec:
               micasense_path = Path(args.multispec)
               site_name = micasense_path.parts[-2]
               date = micasense_path.parts[-1]
               proj_file = Path(f"M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/{site_name}/{date}/metashape_project.psx")
               proj_file.parent.mkdir(parents=True, exist_ok=True)
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

    # Export blockshifted P1 positions. Not used in script. Useful for debug or to restart parts of script following any issues.
    P1_CAM_CSV = Path(proj_file).parent / "dbg_shifted_p1_pos.csv"
    # By default save the CSV with updated MicaSense positions in the MicaSense folder. CSV used within script.
    MICASENSE_CAM_CSV = Path(proj_file).parent / "interpolated_micasense_pos.csv"

    ##################
    # Add images
    ##################
    #
    # rgb
    p1_images = find_files(MRK_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))
    chunk = doc.addChunk()
    chunk.label = CHUNK_RGB
    chunk.addPhotos(p1_images)

    # Check that chunk is not empty and images are in default WGS84 CRS
    if len(chunk.cameras) == 0:
        sys.exit("Chunk rgb empty")
    # check chunk coordinate systems are default EPSG::4326
    if "EPSG::4326" not in str(chunk.crs):
        sys.exit("Chunk rgb: script expects images loaded to be in CRS WGS84 EPSG::4326")

    #
    # multispec
    #
    micasense_images = find_files(MICASENSE_PATH, (".jpg", ".jpeg", ".tif", ".tiff"))

    chunk = doc.addChunk()
    chunk.label = CHUNK_MULTISPEC
    chunk.addPhotos(micasense_images)
    doc.save()

    # Check that chunk is not empty and images are in default WGS84 CRS
    if len(chunk.cameras) == 0:
        sys.exit("Multispec chunk empty")
    if "EPSG::4326" not in str(chunk.crs):
        sys.exit("Multispec chunk: script expects images loaded to be in CRS WGS84 EPSG::4326")

    # Check that lever-arm offsets are non-zero:
    # As this script is for RGB and MS images captured simultaneously on dual gimbal, lever-arm offsets cannot be 0.
    #  Zenmuse P1
    if P1_GIMBAL1_OFFSET == 0:
        err_msg = "Lever-arm offset for P1 in dual gimbal mode cannot be 0. Update offset_dict and rerun_script."
        Metashape.app.messageBox(err_msg)

    # MicaSense: get Camera Model from one of the images to check the lever-arm offsets for the relevant model
    sample_img = open(micasense_images[0], 'rb')
    exif_tags = exifread.process_file(sample_img)
    cam_model = str(exif_tags.get('Image Model'))

    # HARDCODED number of bands.
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

    # Used to find chunks in proc_*
    check_chunk_list = [CHUNK_RGB, CHUNK_MULTISPEC]
    dict_chunks = {}
    for get_chunk in doc.chunks:
        dict_chunks.update({get_chunk.label: get_chunk.key})

    # Delete 'Chunk 1' that is created by default.
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
    print(
        "Step 1. In the Workspace pane, select multispec chunk. Select Tools-Calibrate Reflectance and 'Locate panels'. Press Cancel once the panels have been located.")
    print(
        "Note: The csv of the calibration panel will have to be loaded if this is the first run on the machine. See the protocol for more information.")
    print(
        "Step 2. In the Workspace pane under multispec chunk open Calibration images folder. Select and remove images not to be used for calibration.")
    print("Step 3. Press the 'Show Masks' icon in the toolbar and inspect the masks on calibration images.")
    print(
        "Complete Steps 1 to 3 and press 'Resume Processing' to continue. Reflectance calibration will be completed in the script.")
    print("###########################")
    print("###########################")
    print("###########################")
    print("###########################")

if __name__ == "__main__":
    load_images()