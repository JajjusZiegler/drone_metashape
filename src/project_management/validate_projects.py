"""
Metashape Project Validation Script

This script validates existing Metashape projects against expected image paths
and identifies projects that were created with incorrect paths.

Author: GitHub Copilot
Date: 2025-01-22

Usage:
    python validate_projects.py corrected_paths.csv [--fix] [--output report.csv]
"""

import argparse
import csv
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import Metashape
    METASHAPE_AVAILABLE = True
    logger.info("Metashape module loaded successfully")
except ImportError:
    METASHAPE_AVAILABLE = False
    logger.warning("Metashape module not available. Running in analysis-only mode.")


class ProjectValidator:
    """Validates Metashape projects against expected image paths."""
    
    def __init__(self):
        self.chunk_rgb = "rgb"
        self.chunk_multispec = "multispec"
        self.validation_results = []
        
    def get_project_image_paths(self, project_path: Path) -> Dict[str, List[str]]:
        """
        Extract image paths from a Metashape project.
        
        Returns:
            Dictionary with chunk names as keys and lists of image paths as values
        """
        if not METASHAPE_AVAILABLE:
            logger.error("Metashape not available - cannot open project files")
            return {}
        
        try:
            # Create a new document and open the project
            doc = Metashape.Document()
            doc.open(str(project_path))
            
            image_paths = {}
            
            for chunk in doc.chunks:
                chunk_images = []
                for camera in chunk.cameras:
                    if camera.photo and camera.photo.path:
                        chunk_images.append(camera.photo.path)
                
                image_paths[chunk.label] = chunk_images
            
            # Close the document to free memory
            doc.clear()
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error opening project {project_path}: {e}")
            return {}
    
    def get_expected_images(self, rgb_path: Path, multispec_path: Path) -> Dict[str, List[str]]:
        """
        Get expected images from the corrected paths.
        
        Returns:
            Dictionary with chunk names and expected image paths
        """
        expected_images = {
            self.chunk_rgb: [],
            self.chunk_multispec: []
        }
        
        # RGB images
        if rgb_path.exists():
            rgb_extensions = (".jpg", ".jpeg", ".tif", ".tiff")
            for ext in rgb_extensions:
                expected_images[self.chunk_rgb].extend(
                    [str(p) for p in rgb_path.rglob(f"*{ext}") if p.is_file()]
                )
                expected_images[self.chunk_rgb].extend(
                    [str(p) for p in rgb_path.rglob(f"*{ext.upper()}") if p.is_file()]
                )
        
        # Multispec images
        if multispec_path.exists():
            multispec_extensions = (".jpg", ".jpeg", ".tif", ".tiff")
            for ext in multispec_extensions:
                expected_images[self.chunk_multispec].extend(
                    [str(p) for p in multispec_path.rglob(f"*{ext}") if p.is_file()]
                )
                expected_images[self.chunk_multispec].extend(
                    [str(p) for p in multispec_path.rglob(f"*{ext.upper()}") if p.is_file()]
                )
        
        # Sort for consistent comparison
        expected_images[self.chunk_rgb].sort()
        expected_images[self.chunk_multispec].sort()
        
        return expected_images
    
    def validate_project_paths(self, project_path: Path, expected_rgb_path: Path, 
                             expected_multispec_path: Path) -> Dict:
        """
        Validate a single project against expected paths.
        
        Returns:
            Validation result dictionary
        """
        result = {
            'project_path': str(project_path),
            'expected_rgb_path': str(expected_rgb_path),
            'expected_multispec_path': str(expected_multispec_path),
            'project_exists': project_path.exists(),
            'rgb_path_exists': expected_rgb_path.exists(),
            'multispec_path_exists': expected_multispec_path.exists(),
            'validation_status': 'unknown',
            'rgb_images_match': False,
            'multispec_images_match': False,
            'rgb_missing_count': 0,
            'multispec_missing_count': 0,
            'rgb_extra_count': 0,
            'multispec_extra_count': 0,
            'needs_rebuild': False,
            'error_message': None
        }
        
        try:
            if not result['project_exists']:
                result['validation_status'] = 'project_not_found'
                result['needs_rebuild'] = True
                return result
            
            if not result['rgb_path_exists'] or not result['multispec_path_exists']:
                result['validation_status'] = 'expected_paths_missing'
                result['error_message'] = f"RGB exists: {result['rgb_path_exists']}, Multispec exists: {result['multispec_path_exists']}"
                result['needs_rebuild'] = False  # Cannot rebuild if paths don't exist
                return result
            
            # Get actual images from project
            actual_images = self.get_project_image_paths(project_path)
            if not actual_images and METASHAPE_AVAILABLE:
                result['validation_status'] = 'project_read_error'
                result['error_message'] = 'Could not read project or project has no images'
                result['needs_rebuild'] = True
                return result
            
            # Get expected images
            expected_images = self.get_expected_images(expected_rgb_path, expected_multispec_path)
            
            if not METASHAPE_AVAILABLE:
                result['validation_status'] = 'metashape_unavailable'
                result['error_message'] = 'Cannot validate - Metashape not available'
                return result
            
            # Compare RGB images
            actual_rgb = set(actual_images.get(self.chunk_rgb, []))
            expected_rgb = set(expected_images[self.chunk_rgb])
            
            missing_rgb = expected_rgb - actual_rgb
            extra_rgb = actual_rgb - expected_rgb
            
            result['rgb_missing_count'] = len(missing_rgb)
            result['rgb_extra_count'] = len(extra_rgb)
            result['rgb_images_match'] = len(missing_rgb) == 0 and len(extra_rgb) == 0
            
            # Compare Multispec images
            actual_multispec = set(actual_images.get(self.chunk_multispec, []))
            expected_multispec = set(expected_images[self.chunk_multispec])
            
            missing_multispec = expected_multispec - actual_multispec
            extra_multispec = actual_multispec - expected_multispec
            
            result['multispec_missing_count'] = len(missing_multispec)
            result['multispec_extra_count'] = len(extra_multispec)
            result['multispec_images_match'] = len(missing_multispec) == 0 and len(extra_multispec) == 0
            
            # Determine overall status
            if result['rgb_images_match'] and result['multispec_images_match']:
                result['validation_status'] = 'valid'
                result['needs_rebuild'] = False
            else:
                result['validation_status'] = 'path_mismatch'
                result['needs_rebuild'] = True
                
                # Create detailed error message
                issues = []
                if not result['rgb_images_match']:
                    issues.append(f"RGB: {result['rgb_missing_count']} missing, {result['rgb_extra_count']} extra")
                if not result['multispec_images_match']:
                    issues.append(f"Multispec: {result['multispec_missing_count']} missing, {result['multispec_extra_count']} extra")
                result['error_message'] = "; ".join(issues)
            
            logger.info(f"Validated {project_path.name}: {result['validation_status']}")
            
        except Exception as e:
            result['validation_status'] = 'validation_error'
            result['error_message'] = str(e)
            result['needs_rebuild'] = True
            logger.error(f"Error validating {project_path}: {e}")
        
        return result
    
    def validate_all_projects(self, corrected_csv_path: str) -> List[Dict]:
        """
        Validate all projects listed in the corrected CSV file.
        
        Returns:
            List of validation results
        """
        results = []
        
        with open(corrected_csv_path, 'r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            for row_num, row in enumerate(reader, 1):
                logger.info(f"Processing row {row_num}: {row['site']} / {row['date']}")
                
                project_path = Path(row['project_path'])
                rgb_path = Path(row['rgb'])
                multispec_path = Path(row['multispec'])
                
                result = self.validate_project_paths(project_path, rgb_path, multispec_path)
                result['row_number'] = row_num
                result['site'] = row['site']
                result['date'] = row['date']
                result['original_rgb'] = row.get('original_rgb', row['rgb'])
                result['original_multispec'] = row.get('original_multispec', row['multispec'])
                
                results.append(result)
                self.validation_results = results
        
        return results
    
    def generate_report(self, results: List[Dict], output_path: str):
        """Generate a detailed validation report."""
        
        # Count status types
        status_counts = {}
        needs_rebuild_count = 0
        
        for result in results:
            status = result['validation_status']
            status_counts[status] = status_counts.get(status, 0) + 1
            if result['needs_rebuild']:
                needs_rebuild_count += 1
        
        # Write detailed CSV report
        fieldnames = [
            'row_number', 'site', 'date', 'validation_status', 'needs_rebuild',
            'project_exists', 'rgb_path_exists', 'multispec_path_exists',
            'rgb_images_match', 'multispec_images_match', 
            'rgb_missing_count', 'multispec_missing_count',
            'rgb_extra_count', 'multispec_extra_count',
            'project_path', 'expected_rgb_path', 'expected_multispec_path',
            'original_rgb', 'original_multispec', 'error_message'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        # Print summary
        print("\n" + "="*60)
        print("VALIDATION REPORT SUMMARY")
        print("="*60)
        print(f"Total projects validated: {len(results)}")
        print(f"Projects needing rebuild: {needs_rebuild_count}")
        print("\nStatus breakdown:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        
        print(f"\nDetailed report saved to: {output_path}")
        
        # Show projects that need rebuilding
        rebuild_projects = [r for r in results if r['needs_rebuild']]
        if rebuild_projects:
            print(f"\nProjects requiring rebuild ({len(rebuild_projects)}):")
            for result in rebuild_projects:
                print(f"  - {result['site']} / {result['date']}: {result['validation_status']}")
                if result['error_message']:
                    print(f"    Issue: {result['error_message']}")
        
        return status_counts, needs_rebuild_count
    
    def create_rebuild_list(self, results: List[Dict], output_path: str):
        """Create a CSV file with projects that need to be rebuilt."""
        
        rebuild_projects = [r for r in results if r['needs_rebuild'] and 
                          r['rgb_path_exists'] and r['multispec_path_exists']]
        
        if not rebuild_projects:
            logger.info("No projects need rebuilding")
            return
        
        # Create a CSV in the same format as the corrected CSV for easy rebuilding
        fieldnames = ['date', 'site', 'rgb', 'multispec', 'sunsens', 'project_path', 'image_load_status']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in rebuild_projects:
                writer.writerow({
                    'date': result['date'],
                    'site': result['site'],
                    'rgb': result['expected_rgb_path'],
                    'multispec': result['expected_multispec_path'],
                    'sunsens': 'False',  # Default, you can update this if needed
                    'project_path': result['project_path'],
                    'image_load_status': 'needs_rebuild'
                })
        
        logger.info(f"Rebuild list with {len(rebuild_projects)} projects saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Validate Metashape projects against expected image paths')
    parser.add_argument('corrected_csv', help='Path to the corrected CSV file with expected paths')
    parser.add_argument('--output', default='validation_report.csv', help='Output validation report file')
    parser.add_argument('--rebuild-list', default='projects_to_rebuild.csv', help='Output file for projects needing rebuild')
    args = parser.parse_args()
    
    if not METASHAPE_AVAILABLE:
        print("WARNING: Metashape module not available.")
        print("This script can only check file existence, not actual project contents.")
        print("Install Metashape or run on a machine with Metashape for full validation.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    # Create validator and run validation
    validator = ProjectValidator()
    
    logger.info(f"Starting validation of projects from: {args.corrected_csv}")
    results = validator.validate_all_projects(args.corrected_csv)
    
    # Generate reports
    status_counts, rebuild_count = validator.generate_report(results, args.output)
    validator.create_rebuild_list(results, args.rebuild_list)
    
    # Summary
    print(f"\nValidation complete!")
    print(f"- Validation report: {args.output}")
    print(f"- Rebuild list: {args.rebuild_list}")
    
    if rebuild_count > 0:
        print(f"\nNext steps:")
        print(f"1. Review the validation report to understand issues")
        print(f"2. Use the rebuild list with robust_project_creator.py to recreate faulty projects")
        print(f"   Command: python robust_project_creator.py {args.rebuild_list}")


if __name__ == "__main__":
    main()
