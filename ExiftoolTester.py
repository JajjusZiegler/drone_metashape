import exiftool
import json
import micasense.metadata_custom

exiftool_executable = "C:/Program Files/exiftool-13.03_64/exiftool.exe"
image_path = r"M:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\Subset\IMG_0056_2.tif"

with exiftool.ExifTool(exiftool_executable) as et:
    metadata = et.execute("-j", image_path)
    metadata = json.loads(metadata)[0]
    for tag, value in metadata.items():
        print(f"{tag}: {value}")

image_metadata = micasense.metadata_custom.Metadata(image_path)
utc_time = image_metadata.utc_time()
print(f"UTC Time: {utc_time}")
