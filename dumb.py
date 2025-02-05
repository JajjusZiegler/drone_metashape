from pathlib import Path
import Metashape

compression = Metashape.ImageCompression()
compression.tiff_compression = Metashape.ImageCompression.TiffCompressionLZW  # default on Metashape
compression.tiff_big = True
compression.tiff_tiled = True
compression.tiff_overviews = True

proj_file = r"M:/working_package_2/2024_dronecampaign/01_data/dronetest/processing_test/Site_test5/20240723/Site_test5_20240723_metashape.psx"

dem_file = Path(proj_file).parent / (Path(proj_file).stem + "_dem_01.tif")

doc = Metashape.Document()
doc.open(proj_file, read_only=False)

CHUNK_RGB = "rgb"
CHUNK_MULTISPEC = "multispec"
check_chunk_list = [CHUNK_RGB, CHUNK_MULTISPEC]
dict_chunks = {}
for get_chunk in doc.chunks:
    dict_chunks.update({get_chunk.label: get_chunk.key})
chunk = doc.findChunk(dict_chunks[CHUNK_RGB])
print(compression)
chunk.exportRaster(path=str(dem_file), source_data=Metashape.ElevationData, image_format=Metashape.ImageFormatTIFF, image_compression=compression)