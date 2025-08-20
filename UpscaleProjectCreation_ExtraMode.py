"""
Enhanced Script to process drone imagery in Metashape with flexible site handling.

Author: GitHub Copilot
Date: 2025-07-29

This script extends the original UpscaleProjectCreation2025.py with an "extra mode" that allows:
- Processing new sites not in the predefined mappings
- Custom project directory specification
- Flexible path handling while maintaining all original functionality

Example usage:
    # Standard mode (original functionality)
    python UpscaleProjectCreation_ExtraMode.py input.csv
    
    # Extra mode with new sites
    python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode
    
    # Extra mode with custom project directory
    python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode --project-path "D:/MyProjects"
    
    # Extra mode with all custom paths
    python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode \
        --rgb-path "E:/RGB_Data" --multispec-path "E:/Multispec_Data" --project-path "E:/Projects"

CSV Format for extra mode (optional custom_project_dir column):
    date,site,rgb,multispec,sunsens,custom_project_dir
    2024-07-15,New Forest Site,C:/data/rgb/new_forest,C:/data/multispec/new_forest,true,CustomForest_Analysis
    2024-07-16,Coastal Area,C:/data/rgb/coastal,C:/data/multispec/coastal,false,
"""

import argparse
import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False
    logger.warning("exifread module not available. EXIF validation will be skipped.")

try:
    import Metashape
    METASHAPE_AVAILABLE = True
except ImportError:
    METASHAPE_AVAILABLE = False
    logger.warning("Metashape module not available. Running in validation-only mode.")

# ---------- Added from metashape_proc_Upscale ----------
def find_files(folder: Path, extensions: Tuple[str]) -> List[str]:
    """Recursively find files with specified extensions."""
    return [
        str(p) for p in folder.rglob("*")
        if p.suffix.lower() in extensions and p.is_file()
    ]

# Chunk labels
CHUNK_RGB = "rgb"
CHUNK_MULTISPEC = "multispec"

# Sensor offset configuration
P1_GIMBAL1_OFFSET = (0.087, 0.0, 0.0)

offset_dict = defaultdict(dict)
offset_dict['RedEdge-M']['Red'] = (-0.097, -0.03, -0.06)
offset_dict['RedEdge-M']['Dual'] = (-0.097, 0.02, -0.08)
offset_dict['RedEdge-P']['Red'] = (0,0,0)
offset_dict['RedEdge-P']['Dual'] = (0,0,0)

# Define the comprehensive site name mapping dictionary
SITE_MAPPING = {
    "Stillberg": {
        "image_site_name": "stillberg",
        "folder_name": "Stillberg"
    },
    "Pfynwald": {
        "image_site_name": "Pfynwald",
        "folder_name": "Pfynwald"
    },
    "Illgraben": {
        "image_site_name": "Illgraben",
        "folder_name": "Illgraben"
    },
    "lwf_davos": {
        "image_site_name": "lwf_davos",
        "folder_name": "Davos_LWF"
    },
    "lwf_isone": {
        "image_site_name": "lwf_isone",
        "folder_name": "Isone_LWF"
    },
    "lwf_lens": {
        "image_site_name": "lwf_lens",
        "folder_name": "Lens_LWF"
    },
    "lwf_neunkirch": {
        "image_site_name": "lwf_neunkirch",
        "folder_name": "Neunkirch_LWF"
    },
    "lwf_schänis": {
        "image_site_name": "lwf_schänis",
        "folder_name": "Schänis_LWF"
    },
    "lwf_visp": {
        "image_site_name": "lwf_visp",
        "folder_name": "Visp_LWF"
    },
    "marteloskop": {
        "image_site_name": "marteloskop",
        "folder_name": "Marteloskop"
    },
    "sagno": {
        "image_site_name": "sagno",
        "folder_name": "Sagno_treenet"
    },
    "sanasilva_50845": {
        "image_site_name": "sanasilva_50845",
        "folder_name": "Brüttelen_sanasilva50845"
    },
    "sanasilva_50877": {
        "image_site_name": "sanasilva_50877",
        "folder_name": "Schüpfen_sanasilva50877"
    },
    "treenet_salgesch": {
        "image_site_name": "treenet_salgesch",
        "folder_name": "Salgesch_treenet"
    },
    "treenet_sempach": {
        "image_site_name": "treenet_sempach",
        "folder_name": "Sempach_treenet"
    },
    "wangen_zh": {
        "image_site_name": "wangen_zh",
        "folder_name": "WangenBrüttisellen_treenet"
    },
    "Wangen Brüttisellen": {
        "image_site_name": "Wangen Brüttisellen",
        "folder_name": "WangenBrüttisellen_treenet"
    },
    "Sanasilva-50845": {
        "image_site_name": "Sanasilva-50845",
        "folder_name": "Brüttelen_sanasilva50845"
    },
    "Sanasilva-50877": {
        "image_site_name": "Sanasilva-50877",
        "folder_name": "Schüpfen_sanasilva50877"
    },
    "LWF-Davos": {
        "image_site_name": "LWF-Davos",
        "folder_name": "Davos_LWF"
    },
    "Martelloskop": {
        "image_site_name": "Martelloskop",
        "folder_name": "Marteloskop"
    }
}

class FlexibleProjectCreator:
    """
    A flexible project creator that can handle both predefined site mappings
    and new sites with custom project directories.
    """
    
    def __init__(self, base_rgb_path: Path, base_multispec_path: Path, project_base_path: Path, extra_mode: bool = False):
        self.base_rgb_path = base_rgb_path
        self.base_multispec_path = base_multispec_path
        self.project_base_path = project_base_path
        self.extra_mode = extra_mode
        
        # Available folders from the actual file system
        self.available_rgb_folders = self._get_available_folders(base_rgb_path)
        self.available_multispec_folders = self._get_available_folders(base_multispec_path)
        self.available_project_folders = self._get_available_folders(project_base_path)
        
        logger.info(f"Running in {'EXTRA' if extra_mode else 'STANDARD'} mode")
        logger.info(f"RGB base path: {base_rgb_path}")
        logger.info(f"Multispec base path: {base_multispec_path}")
        logger.info(f"Project base path: {project_base_path}")
        logger.info(f"Found {len(self.available_rgb_folders)} RGB folders")
        logger.info(f"Found {len(self.available_multispec_folders)} Multispec folders")
        logger.info(f"Found {len(self.available_project_folders)} Project folders")
    
    def _get_available_folders(self, base_path: Path) -> List[str]:
        """Get list of available folders in the base path."""
        try:
            return [f.name for f in base_path.iterdir() if f.is_dir()]
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"Could not read {base_path}: {e}")
            return []
    
    def _normalize_site_name(self, site_name: str) -> str:
        """Normalize site name for comparison (lowercase, no spaces, etc.)"""
        return site_name.lower().replace(' ', '_').replace('-', '_')
    
    def _find_fuzzy_match(self, target: str, available_folders: List[str]) -> Optional[str]:
        """Find a fuzzy match for the target in the available folders."""
        target_norm = self._normalize_site_name(target)
        
        # First try exact match
        for folder in available_folders:
            if self._normalize_site_name(folder) == target_norm:
                return folder
        
        # Try partial matches
        for folder in available_folders:
            folder_norm = self._normalize_site_name(folder)
            if target_norm in folder_norm or folder_norm in target_norm:
                return folder
        
        # Try word-based matching
        target_words = target_norm.split('_')
        for folder in available_folders:
            folder_words = self._normalize_site_name(folder).split('_')
            if any(word in folder_words for word in target_words if len(word) > 2):
                return folder
        
        return None
    
    def find_site_folder(self, csv_site_name: str, custom_project_dir: str = None) -> Optional[Path]:
        """
        Find the existing site folder within the project directory.
        In extra mode, can create new project directories.
        """
        # In extra mode with custom project directory
        if self.extra_mode and custom_project_dir:
            # Check if custom_project_dir is a full path or just a folder name
            if custom_project_dir.startswith(('/', '\\')) or ':' in custom_project_dir:
                # It's a full path, use it directly
                return Path(custom_project_dir)
            else:
                # It's just a folder name, combine with base path
                return self.project_base_path / custom_project_dir
        
        # Try original mapping first
        for mapping in SITE_MAPPING.values():
            if csv_site_name.lower() == mapping["image_site_name"].lower():
                folder_path = self.project_base_path / mapping["folder_name"]
                if folder_path.is_dir():
                    return folder_path
                break
        
        # In extra mode, try fuzzy matching with existing folders
        if self.extra_mode:
            fuzzy_match = self._find_fuzzy_match(csv_site_name, self.available_project_folders)
            if fuzzy_match:
                logger.info(f"Found fuzzy match for project folder '{csv_site_name}': {fuzzy_match}")
                return self.project_base_path / fuzzy_match
            
            # Create new project directory based on site name
            sanitized_site = self._normalize_site_name(csv_site_name)
            new_project_dir = f"{sanitized_site}_project"
            logger.info(f"Extra mode: Creating new project directory '{new_project_dir}' for site '{csv_site_name}'")
            return self.project_base_path / new_project_dir
        
        return None
    
    def find_correct_rgb_path(self, original_site: str, date_str: str) -> Optional[Path]:
        """Try to find the correct RGB path if the original doesn't exist."""
        # First try the original path
        original_path = self.base_rgb_path / original_site / date_str
        if original_path.exists():
            return original_path
        
        # Special mappings for known mismatches
        site_corrections = {
            "Wangen Brüttisellen": "wangen_zh",
            "Sanasilva-50845": "sanasilva_50845",
            "Sanasilva-50877": "sanasilva_50877",
            "Martelloskop": "marteloskop",
            "LWF-Davos": "lwf_davos",
        }
        
        # Try the corrected site name first
        if original_site in site_corrections:
            corrected_site = site_corrections[original_site]
            corrected_path = self.base_rgb_path / corrected_site / date_str
            if corrected_path.exists():
                logger.info(f"Found corrected RGB path: {corrected_site} (instead of {original_site})")
                return corrected_path
        
        # In extra mode or if standard corrections fail, try fuzzy matching
        fuzzy_match = self._find_fuzzy_match(original_site, self.available_rgb_folders)
        if fuzzy_match:
            candidate_path = self.base_rgb_path / fuzzy_match / date_str
            if candidate_path.exists():
                logger.info(f"Found alternative RGB path: {fuzzy_match} (instead of {original_site})")
                return candidate_path
        
        return None
    
    def find_correct_multispec_path(self, original_site: str, date_str: str) -> Optional[Path]:
        """Try to find the correct Multispec path if the original doesn't exist."""
        # First try the original path
        original_path = self.base_multispec_path / original_site / date_str
        if original_path.exists():
            return original_path
        
        # Special mappings for known mismatches
        site_corrections = {
            "Wangen Brüttisellen": "wangen_zh",
            "Sanasilva-50845": "sanasilva_50845",
            "Sanasilva-50877": "sanasilva_50877",
            "Martelloskop": "marteloskop",
            "LWF-Davos": "lwf_davos",
            "Stillberg": "stillberg",  # Note: lowercase in Micasense folders
        }
        
        # Try the corrected site name first
        if original_site in site_corrections:
            corrected_site = site_corrections[original_site]
            corrected_path = self.base_multispec_path / corrected_site / date_str
            if corrected_path.exists():
                logger.info(f"Found corrected Multispec path: {corrected_site} (instead of {original_site})")
                return corrected_path
        
        # In extra mode or if standard corrections fail, try fuzzy matching
        fuzzy_match = self._find_fuzzy_match(original_site, self.available_multispec_folders)
        if fuzzy_match:
            candidate_path = self.base_multispec_path / fuzzy_match / date_str
            if candidate_path.exists():
                logger.info(f"Found alternative Multispec path: {fuzzy_match} (instead of {original_site})")
                return candidate_path
        
        return None
    
    def add_images_to_project(self, doc, rgb_path: Path, multispec_path: Path, proj_file: Path):
        """Adds images to the Metashape project with validation."""
        logger.info(f"Adding images to project: {proj_file}")
        logger.info(f"RGB path: {rgb_path}")
        logger.info(f"Multispec path: {multispec_path}")

        # Validate input paths
        if not rgb_path.exists():
            raise ValueError(f"RGB path not found: {rgb_path}")
        if not multispec_path.exists():
            raise ValueError(f"Multispec path not found: {multispec_path}")

        # Add RGB images
        p1_images = find_files(rgb_path, (".jpg", ".jpeg", ".tif", ".tiff"))
        if not p1_images:
            raise ValueError("No RGB images found")

        rgb_chunk = doc.addChunk()
        rgb_chunk.label = CHUNK_RGB
        rgb_chunk.addPhotos(p1_images)
        
        if METASHAPE_AVAILABLE:
            rgb_chunk.loadReferenceExif(load_rotation=True, load_accuracy=True)

        # Validate RGB chunk
        if len(rgb_chunk.cameras) == 0:
            raise ValueError("RGB chunk is empty")
        if METASHAPE_AVAILABLE and "EPSG::4326" not in str(rgb_chunk.crs):
            raise ValueError("RGB chunk has invalid CRS")

        # Add multispec images
        micasense_images = find_files(multispec_path, (".jpg", ".jpeg", ".tif", ".tiff"))
        if not micasense_images:
            raise ValueError("No multispec images found")

        multispec_chunk = doc.addChunk()
        multispec_chunk.label = CHUNK_MULTISPEC
        multispec_chunk.addPhotos(micasense_images)
        
        if METASHAPE_AVAILABLE:
            multispec_chunk.locateReflectancePanels()

        # Validate multispec chunk
        if len(multispec_chunk.cameras) == 0:
            raise ValueError("Multispec chunk is empty")
        if METASHAPE_AVAILABLE and "EPSG::4326" not in str(multispec_chunk.crs):
            raise ValueError("Multispec chunk has invalid CRS")

        # Validate sensor offsets
        if P1_GIMBAL1_OFFSET == (0, 0, 0):
            raise ValueError("Invalid P1 gimbal offset")

        # Check MicaSense configuration (only if exifread is available)
        if EXIFREAD_AVAILABLE:
            with open(micasense_images[0], 'rb') as f:
                exif_tags = exifread.process_file(f)
                cam_model = str(exif_tags.get('Image Model', 'UNKNOWN'))

            sensor_config = 'Dual' if len(multispec_chunk.sensors) >= 10 else 'Red'
            if offset_dict.get(cam_model, {}).get(sensor_config) == (0, 0, 0):
                raise ValueError(f"Invalid offsets for {cam_model} ({sensor_config})")

        # Clean up default chunk
        for chunk in doc.chunks:
            if chunk.label == "Chunk 1":
                doc.remove(chunk)
                break

        logger.info(f"Successfully added images to project")
    
    def process_projects(self, input_csv: str, output_csv: str, dry_run: bool = False):
        """Process projects from the input CSV and write results to the output CSV."""
        all_results = []
        
        if not METASHAPE_AVAILABLE and not dry_run:
            logger.error("Metashape not available. Use --dry-run for validation only.")
            return

        with open(input_csv, 'r', newline='', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            
            # Check if we're in extra mode and have custom project directory column
            fieldnames = reader.fieldnames
            has_custom_project_dir = 'custom_project_dir' in fieldnames if fieldnames else False
            if self.extra_mode and has_custom_project_dir:
                logger.info("Extra mode: Found 'custom_project_dir' column in CSV")
            elif self.extra_mode:
                logger.info("Extra mode: No 'custom_project_dir' column found, will use auto-generated names")
            
            for row_num, reader_row in enumerate(reader, 1):
                # Extract required columns
                date_str = reader_row['date']
                site_name_from_csv = reader_row['site']
                rgb_path_str = reader_row['rgb'].strip('"')  # Remove quotes if present
                multispec_path_str = reader_row['multispec'].strip('"')  # Remove quotes if present
                sunsens = reader_row['sunsens'].lower() == 'true'  # Convert string to boolean
                
                # Check for custom project directory in extra mode
                custom_project_dir = None
                if self.extra_mode and has_custom_project_dir:
                    custom_project_dir = reader_row.get('custom_project_dir', '').strip()
                    if not custom_project_dir:
                        custom_project_dir = None

                logger.info(f"\nProcessing row {row_num}: {site_name_from_csv} / {date_str}")
                if self.extra_mode and custom_project_dir:
                    logger.info(f"  Using custom project directory: {custom_project_dir}")
                logger.info(f"CSV RGB path: {rgb_path_str}")
                logger.info(f"CSV Multispec path: {multispec_path_str}")

                # Find the correct site folder
                site_folder = self.find_site_folder(site_name_from_csv, custom_project_dir)
                
                if not site_folder:
                    logger.warning(f"Could not find or create site folder for '{site_name_from_csv}'")
                    result = [
                        date_str, site_name_from_csv, rgb_path_str, multispec_path_str, sunsens,
                        'N/A', 'error: site folder not found'
                    ]
                    if self.extra_mode:
                        result.insert(-1, custom_project_dir or '')  # Add custom_project_dir column
                    all_results.append(result)
                    continue

                # Define project path within the found site folder
                if self.extra_mode and custom_project_dir:
                    # Extract just the folder name from custom_project_dir if it's a full path
                    if custom_project_dir.startswith(('/', '\\')) or ':' in custom_project_dir:
                        # It's a full path, extract just the last part
                        custom_dir_name = Path(custom_project_dir).name
                    else:
                        # It's just a folder name
                        custom_dir_name = custom_project_dir
                    
                    # Sanitize the custom directory name for use in filename
                    sanitized_custom_dir = self._normalize_site_name(custom_dir_name)
                    proj_file = site_folder / date_str / f"metashape_project_{sanitized_custom_dir}_{date_str}.psx"
                elif self.extra_mode:
                    sanitized_site = self._normalize_site_name(site_name_from_csv)
                    proj_file = site_folder / date_str / f"metashape_project_{sanitized_site}_{date_str}.psx"
                else:
                    proj_file = site_folder / date_str / f"metashape_project_{site_folder.name}_{date_str}.psx"

                # Prepare initial result entry
                result = [
                    date_str, site_name_from_csv, rgb_path_str, multispec_path_str, sunsens,
                    str(proj_file), 'pending'  # Default status
                ]
                if self.extra_mode:
                    result.insert(-1, custom_project_dir or '')  # Add custom_project_dir column

                try:
                    # Skip if project already exists
                    if proj_file.exists():
                        logger.info(f"Project already exists: {proj_file}")
                        result[-1] = 'skipped (exists)'
                    elif dry_run:
                        logger.info(f"Would create project: {proj_file}")
                        result[-1] = 'ready for creation (dry run)'
                    else:
                        # Validate and correct paths before processing
                        rgb_path = Path(rgb_path_str)
                        multispec_path = Path(multispec_path_str)
                        
                        if not rgb_path.exists():
                            logger.warning(f"RGB path does not exist: {rgb_path}")
                            corrected_rgb_path = self.find_correct_rgb_path(site_name_from_csv, date_str)
                            if corrected_rgb_path:
                                logger.info(f"Using corrected RGB path: {corrected_rgb_path}")
                                rgb_path = corrected_rgb_path
                                result[2] = str(rgb_path)  # Update result with corrected path
                            else:
                                result[-1] = 'error: RGB path not found'
                                all_results.append(result)
                                continue
                                
                        if not multispec_path.exists():
                            logger.warning(f"Multispec path does not exist: {multispec_path}")
                            corrected_multispec_path = self.find_correct_multispec_path(site_name_from_csv, date_str)
                            if corrected_multispec_path:
                                logger.info(f"Using corrected Multispec path: {corrected_multispec_path}")
                                multispec_path = corrected_multispec_path
                                result[3] = str(multispec_path)  # Update result with corrected path
                            else:
                                result[-1] = 'error: Multispec path not found'
                                all_results.append(result)
                                continue

                        # Create new Metashape document and project
                        if METASHAPE_AVAILABLE:
                            doc = Metashape.Document()
                            proj_file.parent.mkdir(parents=True, exist_ok=True)

                            # Add images to project
                            self.add_images_to_project(doc, rgb_path, multispec_path, proj_file)

                            # Save project
                            doc.save(path=str(proj_file))
                            logger.info(f"Created project: {proj_file}")
                            result[-1] = 'success'
                        else:
                            result[-1] = 'error: Metashape not available'

                except Exception as e:
                    logger.error(f"Error processing {site_name_from_csv}/{date_str}: {str(e)}")
                    result[-1] = f'error: {str(e)}'

                finally:
                    all_results.append(result)

        # Write all results to the output CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
            fieldnames = ['date', 'site', 'rgb', 'multispec', 'sunsens', 'project_path', 'image_load_status']
            if self.extra_mode:
                fieldnames.insert(-1, 'custom_project_dir')  # Insert before image_load_status
            
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Convert list results to dict format
            dict_results = []
            for result in all_results:
                if self.extra_mode:
                    dict_result = {
                        'date': result[0],
                        'site': result[1], 
                        'rgb': result[2],
                        'multispec': result[3],
                        'sunsens': result[4],
                        'project_path': result[5],
                        'custom_project_dir': result[6],
                        'image_load_status': result[7]
                    }
                else:
                    dict_result = {
                        'date': result[0],
                        'site': result[1],
                        'rgb': result[2], 
                        'multispec': result[3],
                        'sunsens': result[4],
                        'project_path': result[5],
                        'image_load_status': result[6]
                    }
                dict_results.append(dict_result)
            
            writer.writerows(dict_results)

        logger.info(f"Results written to: {output_csv}")
        
        # Print summary
        status_counts = {}
        for result in dict_results:
            status = result['image_load_status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\nSummary:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

def main():
    parser = argparse.ArgumentParser(description='Process drone imagery in Metashape with flexible site handling')
    parser.add_argument('input_csv', help='Input CSV file with project parameters')
    parser.add_argument('--output', help='Output CSV file (optional)')
    parser.add_argument('--extra-mode', action='store_true',
                       help='Enable extra mode for new site names and custom project directories')
    parser.add_argument('--dry-run', action='store_true',
                       help='Only validate paths without creating projects')
    parser.add_argument('--rgb-path', type=str,
                       help='Custom RGB base path (overrides default)')
    parser.add_argument('--multispec-path', type=str,
                       help='Custom Multispec base path (overrides default)')
    parser.add_argument('--project-path', type=str,
                       help='Custom project base path (overrides default)')
    args = parser.parse_args()

    # Check Metashape license if not in dry-run mode
    if not args.dry_run and METASHAPE_AVAILABLE:
        try:
            if not Metashape.app.activated:
                logger.error("Metashape license not activated")
                return
        except AttributeError:
            logger.error("Metashape module not properly installed")
            return

    # Define base paths (use custom paths if provided)
    base_rgb_path = Path(args.rgb_path) if args.rgb_path else Path(r"M:/working_package_2/2024_dronecampaign/01_data/P1")
    base_multispec_path = Path(args.multispec_path) if args.multispec_path else Path(r"M:/working_package_2/2024_dronecampaign/01_data/Micasense")
    
    if args.project_path:
        project_base_path = Path(args.project_path)
    else:
        project_base_path = Path(r"M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/Upscale_Metashapeprojects")

    # Generate output filename if not provided
    if args.output:
        output_csv = args.output
    else:
        input_path = Path(args.input_csv)
        mode_suffix = "_extra" if args.extra_mode else ""
        status_suffix = "_validated" if args.dry_run else "_project_created"
        if args.project_path:
            output_csv = str(Path(args.project_path) / (input_path.stem + mode_suffix + status_suffix + ".csv"))
        else:
            output_csv = str(project_base_path / (input_path.stem + mode_suffix + status_suffix + ".csv"))

    logger.info(f"Input CSV: {args.input_csv}")
    logger.info(f"Output CSV: {output_csv}")

    # Create project creator and process
    creator = FlexibleProjectCreator(base_rgb_path, base_multispec_path, project_base_path, extra_mode=args.extra_mode)
    creator.process_projects(args.input_csv, output_csv, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
