"""
Improved Script to process drone imagery in Metashape with robust path handling.

This script includes a robust path resolver that can handle various naming inconsistencies
between CSV site names and actual folder names in the file system.

Author: GitHub Copilot
Date: 2025-01-22

Example usage:
    python robust_project_creator.py input.csv [--dry-run]
"""

import argparse
import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Optional, Dict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import Metashape
    METASHAPE_AVAILABLE = True
except ImportError:
    METASHAPE_AVAILABLE = False
    logger.warning("Metashape module not available. Running in validation-only mode.")

try:
    import exifread
    EXIFREAD_AVAILABLE = True  
except ImportError:
    EXIFREAD_AVAILABLE = False
    logger.warning("exifread module not available. EXIF validation will be skipped.")


# ---------- Added from metashape_proc_Upscale ----------
def find_files(folder: Path, extensions: Tuple[str]) -> List[str]:
    """Recursively find files with specified extensions."""
    return [
        str(p) for p in folder.rglob("*")
        if p.suffix.lower() in extensions and p.is_file()
    ]


class RobustProjectCreator:
    """
    A robust project creator that can handle various naming mismatches
    between CSV site names and actual folder structures.
    """
    
    def __init__(self, base_rgb_path: Path, base_multispec_path: Path, project_base_path: Path, extra_mode: bool = False):
        self.base_rgb_path = base_rgb_path
        self.base_multispec_path = base_multispec_path
        self.project_base_path = project_base_path
        self.extra_mode = extra_mode
        
        # Discover available folders from the actual file system
        self.available_rgb_folders = self._get_available_folders(base_rgb_path)
        self.available_multispec_folders = self._get_available_folders(base_multispec_path)
        self.available_project_folders = self._get_available_folders(project_base_path)
        
        # Define comprehensive site name mappings
        self.site_mappings = self._create_comprehensive_site_mappings()
        
        # Project settings
        self.chunk_rgb = "rgb"
        self.chunk_multispec = "multispec"
        self.p1_gimbal1_offset = (0.087, 0.0, 0.0)
        
        # Sensor offset configuration
        self.offset_dict = defaultdict(dict)
        self.offset_dict['RedEdge-M']['Red'] = (-0.097, -0.03, -0.06)
        self.offset_dict['RedEdge-M']['Dual'] = (-0.097, 0.02, -0.08)
        self.offset_dict['RedEdge-P']['Red'] = (0,0,0)
        self.offset_dict['RedEdge-P']['Dual'] = (0,0,0)
        
        logger.info(f"Running in {'EXTRA' if extra_mode else 'STANDARD'} mode")
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
    
    def _create_comprehensive_site_mappings(self) -> Dict[str, Dict[str, str]]:
        """
        Create comprehensive site mappings that cover all known naming variations.
        Returns a dictionary with mappings for RGB, multispec, and project folders.
        """
        mappings = {
            # Site name variations to standardized names
            "Wangen Brüttisellen": {
                "rgb": "wangen_zh",
                "multispec": "wangen_zh", 
                "project": "WangenBrüttisellen_treenet"
            },
            "wangen_zh": {
                "rgb": "wangen_zh",
                "multispec": "wangen_zh",
                "project": "WangenBrüttisellen_treenet"
            },
            "Sanasilva-50845": {
                "rgb": "sanasilva_50845",
                "multispec": "sanasilva_50845",
                "project": "Brüttelen_sanasilva50845"
            },
            "sanasilva_50845": {
                "rgb": "sanasilva_50845", 
                "multispec": "sanasilva_50845",
                "project": "Brüttelen_sanasilva50845"
            },
            "Sanasilva-50877": {
                "rgb": "sanasilva_50877",
                "multispec": "sanasilva_50877",
                "project": "Schüpfen_sanasilva50877"
            },
            "sanasilva_50877": {
                "rgb": "sanasilva_50877",
                "multispec": "sanasilva_50877", 
                "project": "Schüpfen_sanasilva50877"
            },
            "Martelloskop": {
                "rgb": "marteloskop",
                "multispec": "marteloskop",
                "project": "Marteloskop"
            },
            "marteloskop": {
                "rgb": "marteloskop",
                "multispec": "marteloskop",
                "project": "Marteloskop"
            },
            "LWF-Davos": {
                "rgb": "lwf_davos",
                "multispec": "lwf_davos",
                "project": "Davos_LWF"
            },
            "lwf_davos": {
                "rgb": "lwf_davos",
                "multispec": "lwf_davos",
                "project": "Davos_LWF"
            },
            "Stillberg": {
                "rgb": "Stillberg",
                "multispec": "stillberg",  # Note: lowercase in Micasense
                "project": "Stillberg"
            },
            "stillberg": {
                "rgb": "Stillberg", 
                "multispec": "stillberg",
                "project": "Stillberg"
            },
            # Add more mappings as needed
            "Pfynwald": {
                "rgb": "Pfynwald",
                "multispec": "Pfynwald",
                "project": "Pfynwald"
            },
            "Illgraben": {
                "rgb": "Illgraben", 
                "multispec": "Illgraben",
                "project": "Illgraben"
            },
            "lwf_isone": {
                "rgb": "lwf_isone",
                "multispec": "lwf_isone", 
                "project": "Isone_LWF"
            },
            "lwf_lens": {
                "rgb": "lwf_lens",
                "multispec": "lwf_lens",
                "project": "Lens_LWF"
            },
            "lwf_neunkirch": {
                "rgb": "lwf_neunkirch",
                "multispec": "lwf_neunkirch",
                "project": "Neunkirch_LWF"
            },
            "lwf_schänis": {
                "rgb": "lwf_schänis",
                "multispec": "lwf_schänis",
                "project": "Schänis_LWF"
            },
            "lwf_visp": {
                "rgb": "lwf_visp",
                "multispec": "lwf_visp",
                "project": "Visp_LWF"
            },
            "sagno": {
                "rgb": "sagno",
                "multispec": "sagno",
                "project": "Sagno_treenet"
            },
            "treenet_salgesch": {
                "rgb": "treenet_salgesch",
                "multispec": "treenet_salgesch",
                "project": "Salgesch_treenet"
            },
            "treenet_sempach": {
                "rgb": "treenet_sempach",
                "multispec": "treenet_sempach",
                "project": "Sempach_treenet"
            }
        }
        return mappings
    
    def _normalize_site_name(self, site_name: str) -> str:
        """Normalize site name for comparison (lowercase, no spaces, etc.)"""
        return site_name.lower().replace(' ', '_').replace('-', '_')
    
    def _find_fuzzy_match(self, target: str, available_folders: List[str]) -> Optional[str]:
        """
        Find a fuzzy match for the target in the available folders.
        Uses various matching strategies.
        """
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
    
    def resolve_path(self, site_name: str, date_str: str, path_type: str, custom_project_dir: str = None) -> Optional[Path]:
        """
        Resolve the correct path for a given site, date, and path type.
        
        Args:
            site_name: The site name from the CSV
            date_str: The date string
            path_type: 'rgb', 'multispec', or 'project'
            custom_project_dir: Optional custom project directory name for extra mode
        
        Returns:
            The resolved Path object or None if not found
        """
        # In extra mode, handle custom project directories and fallback to fuzzy matching
        if self.extra_mode and path_type == "project" and custom_project_dir:
            # Use custom project directory directly
            return self.project_base_path / custom_project_dir / date_str
        
        # Standard mode or RGB/multispec paths - use existing logic
        # First try direct mapping
        if site_name in self.site_mappings:
            target_folder = self.site_mappings[site_name][path_type]
            
            if path_type == "rgb":
                base_path = self.base_rgb_path
                available_folders = self.available_rgb_folders
            elif path_type == "multispec":
                base_path = self.base_multispec_path
                available_folders = self.available_multispec_folders
            elif path_type == "project":
                base_path = self.project_base_path
                available_folders = self.available_project_folders
            else:
                return None
            
            # Check if the mapped folder exists
            if target_folder in available_folders:
                if path_type == "project":
                    return base_path / target_folder / date_str
                else:
                    candidate_path = base_path / target_folder / date_str
                    if candidate_path.exists():
                        return candidate_path
        
        # If direct mapping fails or in extra mode, try fuzzy matching
        if path_type == "rgb":
            base_path = self.base_rgb_path
            available_folders = self.available_rgb_folders
        elif path_type == "multispec":
            base_path = self.base_multispec_path
            available_folders = self.available_multispec_folders
        elif path_type == "project":
            base_path = self.project_base_path
            available_folders = self.available_project_folders
        else:
            return None
        
        fuzzy_match = self._find_fuzzy_match(site_name, available_folders)
        if fuzzy_match:
            logger.info(f"Found fuzzy match for {site_name} ({path_type}): {fuzzy_match}")
            if path_type == "project":
                return base_path / fuzzy_match / date_str
            else:
                candidate_path = base_path / fuzzy_match / date_str
                if candidate_path.exists():
                    return candidate_path
        
        # In extra mode, for project paths, create a default project directory based on site name
        if self.extra_mode and path_type == "project":
            # Sanitize site name for use as directory name
            sanitized_site = site_name.replace(' ', '_').replace('-', '_').lower()
            default_project_dir = f"{sanitized_site}_project"
            logger.info(f"Extra mode: Creating default project directory '{default_project_dir}' for site '{site_name}'")
            return base_path / default_project_dir / date_str
        
        logger.warning(f"Could not resolve {path_type} path for site '{site_name}', date '{date_str}'")
        return None
    
    def add_images_to_project(self, doc, rgb_path: Path, multispec_path: Path, proj_file: Path):
        """
        Adds images to the Metashape project with validation.
        """
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
        rgb_chunk.label = self.chunk_rgb
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
        multispec_chunk.label = self.chunk_multispec
        multispec_chunk.addPhotos(micasense_images)
        
        if METASHAPE_AVAILABLE:
            multispec_chunk.locateReflectancePanels()

        # Validate multispec chunk
        if len(multispec_chunk.cameras) == 0:
            raise ValueError("Multispec chunk is empty")
        if METASHAPE_AVAILABLE and "EPSG::4326" not in str(multispec_chunk.crs):
            raise ValueError("Multispec chunk has invalid CRS")

        # Validate sensor offsets
        if self.p1_gimbal1_offset == (0, 0, 0):
            raise ValueError("Invalid P1 gimbal offset")

        # Check MicaSense configuration (only if exifread is available)
        if EXIFREAD_AVAILABLE:
            with open(micasense_images[0], 'rb') as f:
                exif_tags = exifread.process_file(f)
                cam_model = str(exif_tags.get('Image Model', 'UNKNOWN'))

            sensor_config = 'Dual' if len(multispec_chunk.sensors) >= 10 else 'Red'
            if self.offset_dict.get(cam_model, {}).get(sensor_config) == (0, 0, 0):
                raise ValueError(f"Invalid offsets for {cam_model} ({sensor_config})")

        # Clean up default chunk
        for chunk in doc.chunks:
            if chunk.label == "Chunk 1":
                doc.remove(chunk)
                break

        logger.info(f"Successfully added images to project")

    def process_projects(self, input_csv: str, output_csv: str, dry_run: bool = False):
        """
        Processes projects from the input CSV and writes results to the output CSV.
        
        Args:
            input_csv: Path to input CSV file
            output_csv: Path to output CSV file
            dry_run: If True, only validate paths without creating projects
        """
        results = []
        
        if not METASHAPE_AVAILABLE and not dry_run:
            logger.error("Metashape not available. Use --dry-run for validation only.")
            return
        
        with open(input_csv, 'r', newline='', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            
            # Debug: Print available columns
            fieldnames = reader.fieldnames
            logger.info(f"CSV columns found: {fieldnames}")
            
            # Check if we're in extra mode and have custom project directory column
            has_custom_project_dir = 'custom_project_dir' in fieldnames if fieldnames else False
            if self.extra_mode and has_custom_project_dir:
                logger.info("Extra mode: Found 'custom_project_dir' column in CSV")
            elif self.extra_mode:
                logger.info("Extra mode: No 'custom_project_dir' column found, will use auto-generated names")
            
            for row_num, row in enumerate(reader, 1):
                # Debug: Print the first row to see what we're working with
                if row_num == 1:
                    logger.info(f"First row data: {dict(row)}")
                
                # More robust column access with error handling
                try:
                    date_str = row['date']
                    site_name = row['site']
                    original_rgb = row['rgb']
                    original_multispec = row['multispec']
                    sunsens = row['sunsens']
                    
                    # Check for custom project directory in extra mode
                    custom_project_dir = None
                    if self.extra_mode and has_custom_project_dir:
                        custom_project_dir = row.get('custom_project_dir', '').strip()
                        if not custom_project_dir:
                            custom_project_dir = None
                            
                except KeyError as e:
                    logger.error(f"Missing required column: {e}")
                    logger.error(f"Available columns: {list(row.keys())}")
                    continue
                
                logger.info(f"Processing row {row_num}: {site_name} / {date_str}")
                if self.extra_mode and custom_project_dir:
                    logger.info(f"  Using custom project directory: {custom_project_dir}")
                
                # Resolve corrected paths
                rgb_path = self.resolve_path(site_name, date_str, 'rgb')
                multispec_path = self.resolve_path(site_name, date_str, 'multispec')
                project_dir = self.resolve_path(site_name, date_str, 'project', custom_project_dir)
                
                # Determine project file path
                if project_dir:
                    # In extra mode, use site name for project file naming if no custom dir specified
                    if self.extra_mode and not custom_project_dir:
                        sanitized_site = site_name.replace(' ', '_').replace('-', '_').lower()
                        project_file = project_dir / f"metashape_project_{sanitized_site}_{date_str}.psx"
                    elif self.extra_mode and custom_project_dir:
                        project_file = project_dir / f"metashape_project_{custom_project_dir}_{date_str}.psx"
                    else:
                        project_file = project_dir / f"metashape_project_{project_dir.parent.name}_{date_str}.psx"
                else:
                    project_file = None
                    logger.error(f"Could not determine project path for {site_name} / {date_str}")
                
                # Prepare result entry
                result = {
                    'date': date_str,
                    'site': site_name,
                    'rgb': str(rgb_path) if rgb_path else original_rgb,
                    'multispec': str(multispec_path) if multispec_path else original_multispec,
                    'sunsens': sunsens,
                    'project_path': str(project_file) if project_file else 'N/A',
                    'image_load_status': 'pending'
                }
                
                # Add custom project directory to result if in extra mode
                if self.extra_mode:
                    result['custom_project_dir'] = custom_project_dir or ''
                
                # Determine processing status and execute
                try:
                    if not rgb_path or not multispec_path or not project_file:
                        if not rgb_path:
                            result['image_load_status'] = "error: RGB path not found"
                        elif not multispec_path:
                            result['image_load_status'] = "error: Multispec path not found"
                        elif not project_file:
                            result['image_load_status'] = "error: Project path not resolved"
                    elif project_file.exists():
                        result['image_load_status'] = "skipped (exists)"
                        logger.info(f"Project already exists: {project_file}")
                    elif dry_run:
                        result['image_load_status'] = "ready for creation (dry run)"
                        logger.info(f"Would create project: {project_file}")
                    else:
                        # Actually create the project
                        if METASHAPE_AVAILABLE:
                            doc = Metashape.Document()
                            project_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            self.add_images_to_project(doc, rgb_path, multispec_path, project_file)
                            
                            doc.save(path=str(project_file))
                            logger.info(f"Created project: {project_file}")
                            result['image_load_status'] = "success"
                        else:
                            result['image_load_status'] = "error: Metashape not available"
                            
                except Exception as e:
                    logger.error(f"Error processing {site_name}/{date_str}: {str(e)}")
                    result['image_load_status'] = f"error: {str(e)}"
                
                results.append(result)
                
                # Log path corrections
                if rgb_path and str(rgb_path) != original_rgb:
                    logger.info(f"  RGB path corrected: {original_rgb} -> {rgb_path}")
                if multispec_path and str(multispec_path) != original_multispec:
                    logger.info(f"  Multispec path corrected: {original_multispec} -> {multispec_path}")
        
        # Write results to output CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
            fieldnames = ['date', 'site', 'rgb', 'multispec', 'sunsens', 'project_path', 'image_load_status']
            # Add custom_project_dir column for extra mode
            if self.extra_mode:
                fieldnames.insert(-1, 'custom_project_dir')  # Insert before image_load_status
            
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Add custom_project_dir to results if in extra mode
            if self.extra_mode:
                for result in results:
                    if 'custom_project_dir' not in result:
                        result['custom_project_dir'] = ''  # Default empty value
            
            writer.writerows(results)
        
        logger.info(f"Results written to: {output_csv}")
        
        # Print summary
        status_counts = {}
        for result in results:
            status = result['image_load_status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\nSummary:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")


def main():
    parser = argparse.ArgumentParser(description='Create Metashape projects with robust name mapping')
    parser.add_argument('input_csv', help='Input CSV file with project parameters')
    parser.add_argument('--output', help='Output CSV file (optional)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Only validate paths without creating projects')
    parser.add_argument('--extra-mode', action='store_true',
                       help='Enable extra mode for new site names and custom project directories')
    parser.add_argument('--rgb-path', type=str,
                       help='Custom RGB base path (overrides default)')
    parser.add_argument('--multispec-path', type=str,
                       help='Custom Multispec base path (overrides default)')
    parser.add_argument('--project-path', type=str,
                       help='Custom project base path (overrides default)')
    args = parser.parse_args()
    
    # Define base paths (use custom paths if provided)
    base_rgb_path = Path(args.rgb_path) if args.rgb_path else Path(r"M:/working_package_2/2024_dronecampaign/01_data/P1")
    base_multispec_path = Path(args.multispec_path) if args.multispec_path else Path(r"M:/working_package_2/2024_dronecampaign/01_data/Micasense")
    project_base_path = Path(args.project_path) if args.project_path else Path(r"M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/Upscale_Metashapeprojects")
    
    # Log the paths being used
    logger.info(f"Using RGB path: {base_rgb_path}")
    logger.info(f"Using Multispec path: {base_multispec_path}")
    logger.info(f"Using Project path: {project_base_path}")
    
    # Generate output filename if not provided
    if args.output:
        output_csv = args.output
    else:
        input_path = Path(args.input_csv)
        mode_suffix = "_extra" if args.extra_mode else ""
        status_suffix = "_validated" if args.dry_run else "_processed"
        output_csv = str(input_path.parent / (input_path.stem + mode_suffix + status_suffix + ".csv"))
    
    # Create project creator and process
    creator = RobustProjectCreator(base_rgb_path, base_multispec_path, project_base_path, extra_mode=args.extra_mode)
    creator.process_projects(args.input_csv, output_csv, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
