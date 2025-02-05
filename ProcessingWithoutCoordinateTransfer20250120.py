import Metashape
import os
import argparse

# Default processing parameters
DEFAULT_RGB_PARAMS = {
    "match_photos_downscale": 1,
    "match_photos_keypoint_limit": 40000,
    "match_photos_tiepoint_limit": 10000,
    "depth_maps_downscale": 1,
    "dem_interpolation": Metashape.EnabledInterpolation,
    "orthomosaic_blending": Metashape.DisabledBlending,
    "analyze_images_quality_threshold": 0.7,
    "dem_resolution": 0.01,  # None means use default resolution
    "orthomosaic_resolution": 0.01
}

DEFAULT_MULTISPEC_PARAMS = {
    "match_photos_downscale": 1,
    "match_photos_keypoint_limit": 40000,
    "match_photos_tiepoint_limit": 10000,
    "depth_maps_downscale": 1,
    "dem_interpolation": Metashape.EnabledInterpolation,
    "orthomosaic_blending": Metashape.DisabledBlending,
    "analyze_images_quality_threshold": 0.7,
    "dem_resolution": 0.05,
    "orthomosaic_resolution": 0.05
}

def match_and_align(chunk, params, chunk_type):
    """Matches photos and aligns cameras for a given chunk."""
    print(f"Aligning {chunk_type} cameras...")
    if chunk_type == "RGB":
        chunk.matchPhotos(
            downscale=params["match_photos_downscale"],
            keypoint_limit=params["match_photos_keypoint_limit"],
            tiepoint_limit=params["match_photos_tiepoint_limit"],
            reference_preselection=True
        )
    else:
        chunk.matchPhotos(
            downscale=params["match_photos_downscale"],
            keypoint_limit=params["match_photos_keypoint_limit"],
            tiepoint_limit=params["match_photos_tiepoint_limit"],
            generic_preselection=True
        )
    chunk.alignCameras()

def process_chunk(chunk, params, chunk_type, rgb_dem=None):
    """Processes a single chunk with given parameters, including image quality analysis."""
    print(f"Starting {chunk_type} processing...")
    try:
        print(f"Analyzing {chunk_type} images for quality...")
        chunk.analyzeImages(quality_threshold=params["analyze_images_quality_threshold"])
        print(f"{chunk_type} Images analyzed.")

        if not chunk.cameras[0].transform:
            match_and_align(chunk, params, chunk_type)
        else:
            print(f"{chunk_type} cameras are already aligned. Skipping alignment.")

        print(f"Gradual selection for reprojection error for {chunk_type}...")
        f = Metashape.TiePoints.Filter()
        threshold = 0.5
        f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
        f.removePoints(threshold)

        print(f"Optimizing {chunk_type} camera alignment...")
        chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True, adaptive_fitting=False)

        if not chunk.depth_maps:
            print(f"Building {chunk_type} Depth Maps...")
            chunk.buildDepthMaps(downscale=params["depth_maps_downscale"], filter_mode=Metashape.MildFiltering)
        else:
            print(f"{chunk_type} Depth Maps already exist. Skipping.")

        if not chunk.point_cloud:
            print(f"Building {chunk_type} Point Cloud...")
            chunk.buildPointCloud(source_data=Metashape.DataSource.DepthMapsData, point_colors=True)
        else:
            print(f"{chunk_type} Point Cloud already exists. Skipping.")

        if not chunk.elevations:
            print(f"Building {chunk_type} DEM...")
            chunk.buildDem(source_data=Metashape.PointCloudData, interpolation=params["dem_interpolation"], projection=chunk.crs)
        else:
            print(f"{chunk_type} DEM already exists. Skipping.")

        if not chunk.orthomosaic:
            print(f"Building {chunk_type} Orthomosaic...")
            if chunk_type == "Multispectral" and rgb_dem is not None:  # Check if it is multispectral and if an RGB DEM exists
                print("Using RGB DEM as base for Multispectral Orthomosaic")
                chunk.buildOrthomosaic(surface_data=rgb_dem, blending_mode=params["orthomosaic_blending"], projection=chunk.crs)
            else:
                chunk.buildOrthomosaic(surface_data=Metashape.ElevationData, blending_mode=params["orthomosaic_blending"], projection=chunk.crs)
        else:
            print(f"{chunk_type} Orthomosaic already exists. Skipping.")

        export_dir = os.path.join(os.path.dirname(chunk.project.path), "exports")

        if chunk.elevation:
            dem_path = os.path.join(export_dir, chunk.label + "_DEM.tif")
            print(f"Exporting {chunk_type} DEM to {dem_path}...")
            chunk.exportRaster(path=dem_path, source_data=Metashape.ElevationData, image_format=Metashape.ImageFormatTIFF, projection=chunk.crs, resolution=params["dem_resolution"])

        if chunk.orthomosaic:
            ortho_path = os.path.join(export_dir, chunk.label + "_Ortho.tif")
            print(f"Exporting {chunk_type} Orthomosaic to {ortho_path}...")
            chunk.exportRaster(path=ortho_path, source_data=Metashape.OrthomosaicData, image_format=Metashape.ImageFormatTIFF, projection=chunk.crs, resolution=params["orthomosaic_resolution"])

        # Export Report
        report_path = os.path.join(export_dir, chunk.label + "_report.pdf")
        print(f"Exporting processing report for {chunk_type} to {report_path}...")
        chunk.exportReport(report_path)
    except Exception as e:
        print(f"Error during {chunk_type} processing: {e}")
        return

def process_project(project_path, rgb_params=None, multispec_params=None):
    """Processes a single Metashape project."""
    try:
        doc = Metashape.Document()
        doc.open(project_path, ignore_lock=True)
        print(f"Project opened successfully: {project_path}")
    except Exception as e:
        print(f"Error opening project {project_path}: {e}")
        return

    try:
        rgb_chunk = doc.chunk("rgb")
        multispec_chunk = doc.chunk("multispec")
        print("RGB and Multispec chunks found.")
    except:
        print(f"Error: Could not find 'rgb' or 'multispec' chunks in {project_path}. Skipping.")
        return

    if rgb_params is None:
        rgb_params = DEFAULT_RGB_PARAMS
    if multispec_params is None:
        multispec_params = DEFAULT_MULTISPEC_PARAMS

    # Match and align RGB chunk
    match_and_align(rgb_chunk, rgb_params, "RGB")

    # Match and align Multispectral chunk
    match_and_align(multispec_chunk, multispec_params, "Multispectral")

    # Process RGB chunk
    process_chunk(rgb_chunk, rgb_params, "RGB")

    # Process Multispectral chunk
    process_chunk(multispec_chunk, multispec_params, "Multispectral", rgb_chunk.elevation if rgb_chunk.elevation else None)  # Pass the RGB DEM to multispectral if it exists

    # Tie Point Matching between chunks
    print("Matching Tie Points between chunks...")
    try:
        tie_points = Metashape.TiePoints()
        tie_points.addPhotos(rgb_chunk.cameras + multispec_chunk.cameras)
        tie_points.generateTiePoints(accuracy=Metashape.HighAccuracy, preselection=Metashape.GenericPreselection, keypoint_limit=40000, tiepoint_limit=4000)
        tie_points.filterTiePoints(projection_accuracy=0.3, reprojection_error=0.3)
        rgb_chunk.tie_points = tie_points
        multispec_chunk.tie_points = tie_points

        rgb_chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True, adaptive_fitting=False)
        multispec_chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True, adaptive_fitting=False)
        print("Tie Points matched and chunks optimized.")
    except Exception as e:
        print(f"Error matching Tie Points: {e}")
        return

    doc.save()
    print(f"Project {project_path} processing complete.")

def process_multiple_projects_from_file(filepath, rgb_params=None, multispec_params=None):
    """Reads project paths from a file and processes each."""
    try:
        with open(filepath, 'r') as file:
            project_paths = [line.strip() for line in file.readlines()]
        for project_path in project_paths:
            process_project(project_path, rgb_params, multispec_params)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def main():
    parser = argparse.ArgumentParser(description="Process Metashape projects from a text file.")
    parser.add_argument('project_paths', type=str, help='Path to the text file containing Metashape project paths.')
    parser.add_argument('--rgb_downscale', type=int, help='Downscale factor for RGB matching', default=DEFAULT_RGB_PARAMS["match_photos_downscale"])
    parser.add_argument('--multispec_downscale', type=int, help='Downscale factor for Multispectral matching', default=DEFAULT_MULTISPEC_PARAMS["match_photos_downscale"])
    parser.add_argument('--rgb_dem_res', type=float, help='DEM Resolution for RGB', default=DEFAULT_RGB_PARAMS["dem_resolution"])
    parser.add_argument('--multispec_dem_res', type=float, help='DEM Resolution for Multispectral', default=DEFAULT_MULTISPEC_PARAMS["dem_resolution"])

    args = parser.parse_args()

    rgb_params = DEFAULT_RGB_PARAMS.copy()
    multispec_params = DEFAULT_MULTISPEC_PARAMS.copy()

    rgb_params["match_photos_downscale"] = args.rgb_downscale
    multispec_params["match_photos_downscale"] = args.multispec_downscale
    rgb_params["dem_resolution"] = args.rgb_dem_res
    multispec_params["dem_resolution"] = args.multispec_dem_res

    #process_multiple_projects_from_file(args.project_paths, rgb_params, multispec_params)
    process_project(args.project_paths, rgb_params, multispec_params)

if __name__ == "__main__":
    main()