import os
import exiftool
import micasense.metadata as metadata

def test_utc_time(image_path):
    exiftool_path = r"C:\Program Files\exiftool-13.03_64\exiftool.exe"  # Hardcoded path to exiftool.exe
    
    # Check if the file exists
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"The file {image_path} does not exist.")
    
    # Check if exiftool executable exists
    if not os.path.isfile(exiftool_path):
        raise FileNotFoundError(f"The exiftool executable {exiftool_path} does not exist.")
    
    meta = metadata.Metadata(image_path, exiftool_path=exiftool_path)
    utc_time = meta.utc_time()
    mica_time = utc_time.strftime("%Y:%m:%d %H:%M:%S")
    print(f"UTC Time for {image_path}: {mica_time}")

# Example usage
image_path = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\Subset\IMG_0056_2.tif"  # Adjust this path to your multispectral image
print(f"Testing UTC time extraction for: {image_path}")
test_utc_time(image_path)
