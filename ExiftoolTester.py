import exiftool
import json
from datetime import datetime
import micasense.metadata_custom
import micasense.metadata

exiftool_executable = "C:/Program Files/exiftool-13.01_64/exiftool.exe"
image_path = r"U:\working_package_2\2024_dronecampaign\01_data\dronetest\MicasenseData\Subset\IMG_0056_2.tif"

# Using utc_time from micasense.metadata
image_metadata = micasense.metadata.Metadata(image_path)
utc_time = image_metadata.utc_time()
print(f"UTC Time: {utc_time}")
print(f"Data format: {type(utc_time)}")



# Using utc_time from micasense.metadata_custom
image_metadata_custom = micasense.metadata_custom.Metadata(image_path)
utc_time_custom = image_metadata_custom.utc_time()
print(f"UTC Time (custom): {utc_time_custom}")
print(f"Data format (custom): {type(utc_time_custom)}")


