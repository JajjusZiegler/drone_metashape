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
    
    # Extra mode with special project path for unmapped sites
    python UpscaleProjectCreation_ExtraMode.py input.csv --extra-mode \
        --extra-mode-proj-path "D:/NewSites_Projects"

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
from datetime import datetime
import Metashape

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
        "image_site_name": "marteloskop",
        "folder_name": "Marteloskop"
    }
}

class FlexibleProjectCreator:
    """
    A flexible project creator that can handle both predefined site mappings
    and new sites with custom project directories.
    """
    
    def __init__(self, base_rgb_path: Path, base_multispec_path: Path, project_base_path: Path, extra_mode: bool = False, extra_mode_proj_path: Optional[Path] = None):
        self.base_rgb_path = base_rgb_path
        self.base_multispec_path = base_multispec_path
        self.project_base_path = project_base_path
        self.extra_mode = extra_mode
        self.extra_mode_proj_path = extra_mode_proj_path
        
        # Available folders from the actual file system
        self.available_rgb_folders = self._get_available_folders(base_rgb_path)
        self.available_multispec_folders = self._get_available_folders(base_multispec_path)
        self.available_project_folders = self._get_available_folders(project_base_path)
        
        logger.info(f"Running in {'EXTRA' if extra_mode else 'STANDARD'} mode")
        logger.info(f"RGB base path: {base_rgb_path}")
        logger.info(f"Multispec base path: {base_multispec_path}")
        logger.info(f"Project base path: {project_base_path}")
        if extra_mode and extra_mode_proj_path:
            logger.info(f"Extra mode project path: {extra_mode_proj_path}")
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
        return site_name.lower().replace(' ', '_').replace('-', '_').replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
    
    def _find_site_mapping(self, csv_site_name: str) -> Optional[dict]:
        """Find site mapping by checking both keys and image_site_name values."""
        csv_norm = csv_site_name.lower().strip()
        
        # First: Check direct key matches (case insensitive)
        for key, mapping in SITE_MAPPING.items():
            if key.lower() == csv_norm:
                logger.info(f"Found direct mapping key match: '{csv_site_name}' -> '{key}'")
                return mapping
        
        # Second: Check image_site_name matches (case insensitive)  
        for key, mapping in SITE_MAPPING.items():
            if mapping["image_site_name"].lower() == csv_norm:
                logger.info(f"Found image_site_name match: '{csv_site_name}' -> '{mapping['image_site_name']}'")
                return mapping
        
        # Third: Try normalized matches
        csv_normalized = self._normalize_site_name(csv_site_name)
        for key, mapping in SITE_MAPPING.items():
            key_normalized = self._normalize_site_name(key)
            image_name_normalized = self._normalize_site_name(mapping["image_site_name"])
            
            if csv_normalized == key_normalized or csv_normalized == image_name_normalized:
                logger.info(f"Found normalized match: '{csv_site_name}' -> '{key}' (normalized)")
                return mapping
        
        # Fourth: Try partial matches
        for key, mapping in SITE_MAPPING.items():
            key_normalized = self._normalize_site_name(key)
            image_name_normalized = self._normalize_site_name(mapping["image_site_name"])
            
            if (csv_normalized in key_normalized or key_normalized in csv_normalized or
                csv_normalized in image_name_normalized or image_name_normalized in csv_normalized):
                logger.info(f"Found partial match: '{csv_site_name}' -> '{key}' (partial)")
                return mapping
        
        return None
    
    def _find_fuzzy_match(self, target: str, available_folders: List[str]) -> Optional[str]:
        """Find a fuzzy match for the target in the available folders."""
        target_norm = self._normalize_site_name(target)
        logger.debug(f"Fuzzy matching '{target}' (normalized: '{target_norm}') against {len(available_folders)} folders")
        
        # First try exact match
        for folder in available_folders:
            if self._normalize_site_name(folder) == target_norm:
                logger.info(f"Found exact fuzzy match: '{target}' -> '{folder}'")
                return folder
        
        # Try partial matches (both directions)
        for folder in available_folders:
            folder_norm = self._normalize_site_name(folder)
            if target_norm in folder_norm or folder_norm in target_norm:
                logger.info(f"Found partial fuzzy match: '{target}' -> '{folder}'")
                return folder
        
        # Try word-based matching with improved logic
        target_words = [word for word in target_norm.split('_') if len(word) > 2]
        best_match = None
        best_score = 0
        
        for folder in available_folders:
            folder_words = [word for word in self._normalize_site_name(folder).split('_') if len(word) > 2]
            
            # Count matching words
            matches = sum(1 for target_word in target_words 
                         if any(target_word in folder_word or folder_word in target_word 
                               for folder_word in folder_words))
            
            # Calculate score as ratio of matches to total words
            if target_words:  # Avoid division by zero
                score = matches / len(target_words)
                if score > best_score and score >= 0.5:  # At least 50% match
                    best_score = score
                    best_match = folder
        
        if best_match:
            logger.info(f"Found word-based fuzzy match: '{target}' -> '{best_match}' (score: {best_score:.2f})")
        else:
            logger.debug(f"No fuzzy match found for '{target}'")
        
        return best_match
    
    def find_site_folder(self, csv_site_name: str, custom_project_dir: str = None) -> Optional[Path]:
        """
        Find the existing site folder within the project directory.
        In extra mode, can create new project directories.
        """
        logger.info(f"Finding site folder for: '{csv_site_name}'")
        
        # In extra mode with custom project directory
        if self.extra_mode and custom_project_dir:
            # Check if custom_project_dir is a full path or just a folder name
            if custom_project_dir.startswith(('/', '\\')) or ':' in custom_project_dir:
                # It's a full path, use it directly
                logger.info(f"Using custom project dir (full path): {custom_project_dir}")
                return Path(custom_project_dir)
            else:
                # It's just a folder name, combine with base path
                custom_path = self.project_base_path / custom_project_dir
                logger.info(f"Using custom project dir (relative): {custom_path}")
                return custom_path
        
        # Try improved site mapping first
        site_mapping = self._find_site_mapping(csv_site_name)
        if site_mapping:
            folder_path = self.project_base_path / site_mapping["folder_name"]
            if folder_path.is_dir():
                logger.info(f"Found existing mapped folder: {folder_path}")
                return folder_path
            else:
                logger.warning(f"Mapped folder does not exist: {folder_path}")
                # Don't break here, continue with fuzzy matching
        
        # In extra mode, try fuzzy matching with existing folders
        if self.extra_mode:
            fuzzy_match = self._find_fuzzy_match(csv_site_name, self.available_project_folders)
            if fuzzy_match:
                logger.info(f"Found fuzzy match for project folder '{csv_site_name}': {fuzzy_match}")
                return self.project_base_path / fuzzy_match
            
            # Create new project directory based on site name
            sanitized_site = self._normalize_site_name(csv_site_name)
            new_project_dir = f"{sanitized_site}_project"
            
            # Use extra mode project path if specified, otherwise use regular project base path
            if self.extra_mode_proj_path:
                logger.info(f"Extra mode: Creating new project directory '{new_project_dir}' for site '{csv_site_name}' in extra mode path: {self.extra_mode_proj_path}")
                return self.extra_mode_proj_path / new_project_dir
            else:
                logger.info(f"Extra mode: Creating new project directory '{new_project_dir}' for site '{csv_site_name}' in regular path: {self.project_base_path}")
                return self.project_base_path / new_project_dir
        
        return None
    
    def find_correct_rgb_path(self, original_site: str, date_str: str) -> Optional[Path]:
        """Try to find the correct RGB path if the original doesn't exist."""
        logger.debug(f"Finding RGB path for site: '{original_site}', date: '{date_str}'")
        
        # First try the original path
        original_path = self.base_rgb_path / original_site / date_str
        if original_path.exists():
            logger.info(f"Found original RGB path: {original_path}")
            return original_path
        
        # Try site mapping to get the correct image_site_name
        site_mapping = self._find_site_mapping(original_site)
        if site_mapping:
            mapped_site = site_mapping["image_site_name"]
            mapped_path = self.base_rgb_path / mapped_site / date_str
            if mapped_path.exists():
                logger.info(f"Found mapped RGB path: {mapped_site} (instead of {original_site})")
                return mapped_path
        
        # Special mappings for known mismatches (legacy support)
        site_corrections = {
            "Wangen Brüttisellen": "wangen_zh",
            "Sanasilva-50845": "sanasilva_50845", 
            "Sanasilva-50877": "sanasilva_50877",
            "Martelloskop": "marteloskop",
            "LWF-Davos": "lwf_davos",
        }
        
        # Try the corrected site name
        if original_site in site_corrections:
            corrected_site = site_corrections[original_site]
            corrected_path = self.base_rgb_path / corrected_site / date_str
            if corrected_path.exists():
                logger.info(f"Found corrected RGB path: {corrected_site} (instead of {original_site})")
                return corrected_path
        
        # Try fuzzy matching with available RGB folders
        fuzzy_match = self._find_fuzzy_match(original_site, self.available_rgb_folders)
        if fuzzy_match:
            candidate_path = self.base_rgb_path / fuzzy_match / date_str
            if candidate_path.exists():
                logger.info(f"Found fuzzy matched RGB path: {fuzzy_match} (instead of {original_site})")
                return candidate_path
        
        logger.warning(f"No RGB path found for site: '{original_site}', date: '{date_str}'")
        return None
    
    def find_correct_multispec_path(self, original_site: str, date_str: str) -> Optional[Path]:
        """Try to find the correct Multispec path if the original doesn't exist."""
        logger.debug(f"Finding Multispec path for site: '{original_site}', date: '{date_str}'")
        
        # First try the original path
        original_path = self.base_multispec_path / original_site / date_str
        if original_path.exists():
            logger.info(f"Found original Multispec path: {original_path}")
            return original_path
        
        # Try site mapping to get the correct image_site_name
        site_mapping = self._find_site_mapping(original_site)
        if site_mapping:
            mapped_site = site_mapping["image_site_name"]
            mapped_path = self.base_multispec_path / mapped_site / date_str
            if mapped_path.exists():
                logger.info(f"Found mapped Multispec path: {mapped_site} (instead of {original_site})")
                return mapped_path
        
        # Special mappings for known mismatches (legacy support)
        site_corrections = {
            "Wangen Brüttisellen": "wangen_zh",
            "Sanasilva-50845": "sanasilva_50845",
            "Sanasilva-50877": "sanasilva_50877",
            "Martelloskop": "marteloskop",
            "LWF-Davos": "lwf_davos",
            "Stillberg": "stillberg",  # Note: lowercase in Micasense folders
        }
        
        # Try the corrected site name
        if original_site in site_corrections:
            corrected_site = site_corrections[original_site]
            corrected_path = self.base_multispec_path / corrected_site / date_str
            if corrected_path.exists():
                logger.info(f"Found corrected Multispec path: {corrected_site} (instead of {original_site})")
                return corrected_path
        
        # Try fuzzy matching with available Multispec folders
        fuzzy_match = self._find_fuzzy_match(original_site, self.available_multispec_folders)
        if fuzzy_match:
            candidate_path = self.base_multispec_path / fuzzy_match / date_str
            if candidate_path.exists():
                logger.info(f"Found fuzzy matched Multispec path: {fuzzy_match} (instead of {original_site})")
                return candidate_path
        
        logger.warning(f"No Multispec path found for site: '{original_site}', date: '{date_str}'")
        return None
    
    def diagnose_site_matching(self, csv_site_name: str) -> dict:
        """
        Diagnostic method to understand how a site name would be matched.
        Returns a dictionary with matching information.
        """
        diagnosis = {
            "input_site": csv_site_name,
            "normalized_input": self._normalize_site_name(csv_site_name),
            "mapping_found": None,
            "rgb_fuzzy_match": None,
            "multispec_fuzzy_match": None,
            "project_fuzzy_match": None,
            "available_rgb_folders": self.available_rgb_folders[:10],  # Show first 10
            "available_multispec_folders": self.available_multispec_folders[:10],
            "available_project_folders": self.available_project_folders[:10]
        }
        
        # Check site mapping
        site_mapping = self._find_site_mapping(csv_site_name)
        if site_mapping:
            diagnosis["mapping_found"] = {
                "image_site_name": site_mapping["image_site_name"],
                "folder_name": site_mapping["folder_name"]
            }
        
        # Check fuzzy matches
        diagnosis["rgb_fuzzy_match"] = self._find_fuzzy_match(csv_site_name, self.available_rgb_folders)
        diagnosis["multispec_fuzzy_match"] = self._find_fuzzy_match(csv_site_name, self.available_multispec_folders)
        diagnosis["project_fuzzy_match"] = self._find_fuzzy_match(csv_site_name, self.available_project_folders)
        
        return diagnosis
    
    def _find_existing_project(self, site_folder: Path, date_str: str, site_name: str, custom_project_dir: str = None) -> Optional[Path]:
        """
        Look for existing project files with various naming patterns.
        Returns the path to the existing project if found, None otherwise.
        """
        if not site_folder.exists():
            return None
            
        date_folder = site_folder / date_str
        if not date_folder.exists():
            return None
        
        # List of possible project file patterns to check
        possible_patterns = []
        
        # Pattern 1: Standard mode naming (folder name based)
        possible_patterns.append(f"metashape_project_{site_folder.name}_{date_str}.psx")
        
        # Pattern 2: Extra mode naming (sanitized site name)
        sanitized_site = self._normalize_site_name(site_name)
        possible_patterns.append(f"metashape_project_{sanitized_site}_{date_str}.psx")
        
        # Pattern 3: Custom project dir naming
        if custom_project_dir:
            if custom_project_dir.startswith(('/', '\\')) or ':' in custom_project_dir:
                custom_dir_name = Path(custom_project_dir).name
            else:
                custom_dir_name = custom_project_dir
            sanitized_custom = self._normalize_site_name(custom_dir_name)
            possible_patterns.append(f"metashape_project_{sanitized_custom}_{date_str}.psx")
        
        # Pattern 4: Check for any metashape project files in the date folder
        try:
            existing_projects = list(date_folder.glob("metashape_project_*.psx"))
            if existing_projects:
                # Return the first existing project found
                logger.info(f"Found existing project with different naming: {existing_projects[0]}")
                return existing_projects[0]
        except (OSError, PermissionError):
            pass
        
        # Check each specific pattern
        for pattern in possible_patterns:
            proj_path = date_folder / pattern
            if proj_path.exists():
                logger.info(f"Found existing project matching pattern '{pattern}': {proj_path}")
                return proj_path
        
        logger.debug(f"No existing project found in {date_folder}")
        logger.debug(f"Checked patterns: {possible_patterns}")
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

                logger.info(f"Target project file: {proj_file}")

                # Prepare initial result entry
                result = [
                    date_str, site_name_from_csv, rgb_path_str, multispec_path_str, sunsens,
                    str(proj_file), 'pending'  # Default status
                ]
                if self.extra_mode:
                    result.insert(-1, custom_project_dir or '')  # Add custom_project_dir column

                try:
                    # Check for existing projects with various naming patterns
                    existing_project = self._find_existing_project(site_folder, date_str, site_name_from_csv, custom_project_dir)
                    
                    if existing_project:
                        logger.info(f"Project already exists: {existing_project}")
                        result[5] = str(existing_project)  # Update with actual existing path
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
    parser.add_argument('--diagnose', action='store_true',
                       help='Run diagnostics on site name matching for each row in CSV')
    parser.add_argument('--rgb-path', type=str,
                       help='Custom RGB base path (overrides default)')
    parser.add_argument('--multispec-path', type=str,
                       help='Custom Multispec base path (overrides default)')
    parser.add_argument('--project-path', type=str,
                       help='Custom project base path (overrides default)')
    parser.add_argument('--extra-mode-proj-path', type=str,
                       help='Custom project path specifically for unmapped sites in extra mode')
    args = parser.parse_args()

    # Validate arguments
    if args.extra_mode_proj_path and not args.extra_mode:
        logger.error("--extra-mode-proj-path can only be used with --extra-mode")
        return

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
        # Create timestamped filename in the project lists folder
        input_path = Path(args.input_csv)
        mode_suffix = "_extra" if args.extra_mode else ""
        status_suffix = "_validated" if args.dry_run else "_project_created"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define the output folder for project lists
        output_folder = project_base_path / "0001_project_lists"
        output_folder.mkdir(parents=True, exist_ok=True)
        
        filename = f"{input_path.stem}{mode_suffix}{status_suffix}_{timestamp}.csv"
        output_csv = str(output_folder / filename)

    logger.info(f"Input CSV: {args.input_csv}")
    logger.info(f"Output CSV: {output_csv}")

    # Parse extra mode project path
    extra_mode_proj_path = Path(args.extra_mode_proj_path) if args.extra_mode_proj_path else None

    # Create project creator and process
    creator = FlexibleProjectCreator(base_rgb_path, base_multispec_path, project_base_path, 
                                   extra_mode=args.extra_mode, extra_mode_proj_path=extra_mode_proj_path)
    
    # Run diagnostics if requested
    if args.diagnose:
        print("\n" + "="*80)
        print("SITE NAME MATCHING DIAGNOSTICS")  
        print("="*80)
        
        with open(args.input_csv, 'r', newline='', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            unique_sites = set()
            
            for row in reader:
                unique_sites.add(row['site'])
            
            # Categorize sites
            mapped_sites = []
            extra_mode_sites = []
            
            for site in sorted(unique_sites):
                print(f"\n--- DIAGNOSING SITE: '{site}' ---")
                diagnosis = creator.diagnose_site_matching(site)
                
                print(f"Input site: {diagnosis['input_site']}")
                print(f"Normalized: {diagnosis['normalized_input']}")
                
                if diagnosis['mapping_found']:
                    print(f"✅ Mapping found:")
                    print(f"   - Image site name: {diagnosis['mapping_found']['image_site_name']}")
                    print(f"   - Project folder: {diagnosis['mapping_found']['folder_name']}")
                    mapped_sites.append(site)
                else:
                    print("❌ No predefined mapping found")
                    extra_mode_sites.append(site)
                
                print(f"Fuzzy matches:")
                print(f"   - RGB folders: {diagnosis['rgb_fuzzy_match'] or 'None'}")
                print(f"   - Multispec folders: {diagnosis['multispec_fuzzy_match'] or 'None'}")
                print(f"   - Project folders: {diagnosis['project_fuzzy_match'] or 'None'}")
                
                if not diagnosis['mapping_found'] and not any([
                    diagnosis['rgb_fuzzy_match'], 
                    diagnosis['multispec_fuzzy_match'], 
                    diagnosis['project_fuzzy_match']
                ]):
                    print("⚠️  No matches found - new directories will be created in extra mode")
            
            # Summary
            print(f"\n" + "="*80)
            print("SUMMARY")
            print("="*80)
            print(f"Sites with predefined mappings ({len(mapped_sites)}): {mapped_sites}")
            print(f"Sites requiring extra-mode ({len(extra_mode_sites)}): {extra_mode_sites}")
            print(f"\nRecommendation:")
            if extra_mode_sites:
                print(f"  Use --extra-mode flag to handle: {', '.join(extra_mode_sites)}")
            else:
                print(f"  All sites have predefined mappings - standard mode should work fine")
        
        print(f"\nAvailable RGB folders ({len(creator.available_rgb_folders)} total):")
        for folder in creator.available_rgb_folders[:20]:  # Show first 20
            print(f"  - {folder}")
        if len(creator.available_rgb_folders) > 20:
            print(f"  ... and {len(creator.available_rgb_folders) - 20} more")
            
        print(f"\nAvailable Multispec folders ({len(creator.available_multispec_folders)} total):")
        for folder in creator.available_multispec_folders[:20]:  # Show first 20
            print(f"  - {folder}")
        if len(creator.available_multispec_folders) > 20:
            print(f"  ... and {len(creator.available_multispec_folders) - 20} more")
            
        print(f"\nAvailable Project folders ({len(creator.available_project_folders)} total):")
        for folder in creator.available_project_folders[:20]:  # Show first 20
            print(f"  - {folder}")
        if len(creator.available_project_folders) > 20:
            print(f"  ... and {len(creator.available_project_folders) - 20} more")
        
        print("\n" + "="*80)
        print("DIAGNOSIS COMPLETE")
        print("="*80)
        return
    
    creator.process_projects(args.input_csv, output_csv, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
