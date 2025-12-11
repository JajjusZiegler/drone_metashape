"""
Script to fix project creation with robust path handling for site naming mismatches.

This script creates a more resilient mapping system that can handle various naming inconsistencies
between CSV site names and actual folder names in the file system.

Author: GitHub Copilot
Date: 2025-01-22
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

class RobustPathResolver:
    """
    A robust path resolver that can handle various naming mismatches
    between CSV site names and actual folder structures.
    """
    
    def __init__(self, base_rgb_path: Path, base_multispec_path: Path, project_base_path: Path):
        self.base_rgb_path = base_rgb_path
        self.base_multispec_path = base_multispec_path
        self.project_base_path = project_base_path
        
        # Discover available folders from the actual file system
        self.available_rgb_folders = self._get_available_folders(base_rgb_path)
        self.available_multispec_folders = self._get_available_folders(base_multispec_path)
        self.available_project_folders = self._get_available_folders(project_base_path)
        
        # Define comprehensive site name mappings
        self.site_mappings = self._create_comprehensive_site_mappings()
        
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
            # Format: CSV site name -> {rgb: folder_name, multispec: folder_name, project: folder_name}
            
            # Wangen Brüttisellen / wangen_zh
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
            
            # Sanasilva sites
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
            
            # Marteloskop (note: project folder has capital M)
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
            "Marteloskop": {
                "rgb": "marteloskop",
                "multispec": "marteloskop",
                "project": "Marteloskop"
            },
            
            # LWF sites
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
            
            # Stillberg (IMPORTANT: RGB=Stillberg, Multispec=stillberg)
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
            
            # Other sites
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
            "sagno": {
                "rgb": "sagno",
                "multispec": "sagno",
                "project": "Sagno_treenet"
            },
            
            # TreeNet sites
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
    
    def resolve_path(self, site_name: str, date_str: str, path_type: str) -> Optional[Path]:
        """
        Resolve the correct path for a given site, date, and path type.
        
        Args:
            site_name: The site name from the CSV
            date_str: The date string
            path_type: 'rgb', 'multispec', or 'project'
        
        Returns:
            The resolved Path object or None if not found
        """
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
        
        # If direct mapping fails, try fuzzy matching
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
        
        logger.warning(f"Could not resolve {path_type} path for site '{site_name}', date '{date_str}'")
        return None
    
    def resolve_project_info(self, site_name: str, date_str: str) -> Dict[str, Optional[Path]]:
        """
        Resolve all paths for a given site and date.
        
        Returns:
            Dictionary with 'rgb', 'multispec', and 'project' paths
        """
        return {
            'rgb': self.resolve_path(site_name, date_str, 'rgb'),
            'multispec': self.resolve_path(site_name, date_str, 'multispec'), 
            'project': self.resolve_path(site_name, date_str, 'project')
        }
    
    def validate_and_create_csv(self, input_csv: str, output_csv: str):
        """
        Validate paths in the input CSV and create a corrected output CSV.
        """
        results = []
        
        with open(input_csv, 'r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            for row_num, row in enumerate(reader, 1):
                date_str = row['date']
                site_name = row['site']
                original_rgb = row['rgb']
                original_multispec = row['multispec']
                sunsens = row['sunsens']
                
                logger.info(f"Processing row {row_num}: {site_name} / {date_str}")
                
                # Resolve corrected paths
                paths = self.resolve_project_info(site_name, date_str)
                
                # Determine project file path
                if paths['project']:
                    project_file = paths['project'] / f"metashape_project_{paths['project'].parent.name}_{date_str}.psx"
                else:
                    project_file = None
                    logger.error(f"Could not determine project path for {site_name} / {date_str}")
                
                # Determine status
                status = "error"
                if paths['rgb'] and paths['multispec'] and project_file:
                    if project_file.exists():
                        status = "skipped (exists)"
                    else:
                        status = "ready for creation"
                elif not paths['rgb']:
                    status = "error: RGB path not found"
                elif not paths['multispec']:
                    status = "error: Multispec path not found"
                elif not project_file:
                    status = "error: Project path not resolved"
                
                # Create result row
                result = {
                    'date': date_str,
                    'site': site_name,
                    'rgb': str(paths['rgb']) if paths['rgb'] else original_rgb,
                    'multispec': str(paths['multispec']) if paths['multispec'] else original_multispec,
                    'sunsens': sunsens,
                    'project_path': str(project_file) if project_file else 'N/A',
                    'image_load_status': status,
                    'original_rgb': original_rgb,
                    'original_multispec': original_multispec
                }
                results.append(result)
                
                # Log the resolution
                if paths['rgb'] and str(paths['rgb']) != original_rgb:
                    logger.info(f"  RGB path corrected: {original_rgb} -> {paths['rgb']}")
                if paths['multispec'] and str(paths['multispec']) != original_multispec:
                    logger.info(f"  Multispec path corrected: {original_multispec} -> {paths['multispec']}")
        
        # Write results to output CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
            fieldnames = ['date', 'site', 'rgb', 'multispec', 'sunsens', 'project_path', 'image_load_status', 'original_rgb', 'original_multispec']
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
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
    parser = argparse.ArgumentParser(description='Fix project paths with robust name mapping')
    parser.add_argument('input_csv', help='Input CSV file with project parameters')
    parser.add_argument('--output', help='Output CSV file (optional)')
    args = parser.parse_args()
    
    # Define base paths
    base_rgb_path = Path(r"M:/working_package_2/2024_dronecampaign/01_data/P1")
    base_multispec_path = Path(r"M:/working_package_2/2024_dronecampaign/01_data/Micasense") 
    project_base_path = Path(r"M:/working_package_2/2024_dronecampaign/02_processing/metashape_projects/Upscale_Metashapeprojects")
    
    # Generate output filename if not provided
    if args.output:
        output_csv = args.output
    else:
        input_path = Path(args.input_csv)
        output_csv = str(input_path.parent / (input_path.stem + "_corrected.csv"))
    
    # Create resolver and process
    resolver = RobustPathResolver(base_rgb_path, base_multispec_path, project_base_path)
    resolver.validate_and_create_csv(args.input_csv, output_csv)


if __name__ == "__main__":
    main()
