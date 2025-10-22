#!/usr/bin/env python3
"""
Project Processing Status Checker for Metashape Projects
=========================================================

This script analyzes Metashape projects to determine:
1. Which output files have been created for each project
2. Quality metrics and processing status
3. Lists unprocessed but existing project files

Output files:
1. processing_status_report.csv - Detailed status of all projects with quality metrics
2. unprocessed_projects.csv - List of projects that exist but haven't been processed
"""

import csv
import os
import glob
import re
from pathlib import Path
import pandas as pd
from datetime import datetime
import logging
from difflib import SequenceMatcher

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Data directory paths
P1_DATA_DIR = Path(r"M:\working_package_2\2024_dronecampaign\01_data\P1")
MICASENSE_DATA_DIR = Path(r"M:\working_package_2\2024_dronecampaign\01_data\Micasense")

def discover_actual_site_names():
    """
    Discover the actual site folder names in the P1 and Micasense data directories
    Returns a dictionary mapping site names found in both directories
    """
    site_mapping = {}
    
    logger.info("Discovering actual site names from data directories...")
    
    # Get P1 site folders
    p1_sites = set()
    if P1_DATA_DIR.exists():
        p1_sites = {folder.name for folder in P1_DATA_DIR.iterdir() if folder.is_dir()}
        logger.info(f"Found {len(p1_sites)} P1 site folders: {sorted(p1_sites)}")
    else:
        logger.warning(f"P1 data directory not found: {P1_DATA_DIR}")
    
    # Get Micasense site folders  
    micasense_sites = set()
    if MICASENSE_DATA_DIR.exists():
        micasense_sites = {folder.name for folder in MICASENSE_DATA_DIR.iterdir() if folder.is_dir()}
        logger.info(f"Found {len(micasense_sites)} Micasense site folders: {sorted(micasense_sites)}")
    else:
        logger.warning(f"Micasense data directory not found: {MICASENSE_DATA_DIR}")
    
    # Find sites that exist in both directories
    common_sites = p1_sites.intersection(micasense_sites)
    logger.info(f"Found {len(common_sites)} sites in both P1 and Micasense directories: {sorted(common_sites)}")
    
    # Create identity mapping for confirmed sites (they map to themselves)
    for site in common_sites:
        site_mapping[site] = site
    
    # Find sites that exist in only one directory
    p1_only = p1_sites - micasense_sites
    micasense_only = micasense_sites - p1_sites
    
    if p1_only:
        logger.warning(f"Sites found only in P1: {sorted(p1_only)}")
    if micasense_only:
        logger.warning(f"Sites found only in Micasense: {sorted(micasense_only)}")
    
    return {
        'site_mapping': site_mapping,
        'p1_sites': p1_sites,
        'micasense_sites': micasense_sites,
        'common_sites': common_sites,
        'p1_only': p1_only,
        'micasense_only': micasense_only
    }

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_site_match(csv_site_name, actual_sites, threshold=0.6):
    """
    Find the best matching actual site name for a CSV site name
    Returns (best_match, similarity_score) or (None, 0) if no good match
    """
    if not actual_sites:
        return None, 0
    
    csv_lower = csv_site_name.lower()
    
    # First try exact match (case insensitive)
    for site in actual_sites:
        if csv_lower == site.lower():
            return site, 1.0
    
    # Handle specific pattern transformations
    # CSV: "Visp_LWF" -> Actual: "lwf_visp"
    # CSV: "Davos_LWF" -> Actual: "lwf_davos"
    if '_lwf' in csv_lower:
        site_part = csv_lower.replace('_lwf', '')
        lwf_pattern = f'lwf_{site_part}'
        for site in actual_sites:
            if site.lower() == lwf_pattern:
                return site, 1.0
    
    # Handle specific known mappings
    known_mappings = {
        'wangenbrüttisellen_treenet': 'wangen_zh',
        'wangenbrüttisellen': 'wangen_zh',
        'wangen_treenet': 'wangen_zh',
    }
    
    if csv_lower in known_mappings:
        target = known_mappings[csv_lower]
        for site in actual_sites:
            if site.lower() == target:
                return site, 1.0
    
    # Try substring matching - CSV site name contained in actual folder name
    # This handles cases like "visp" -> "lwf_visp" or "davos" -> "lwf_davos"
    substring_matches = []
    for site in actual_sites:
        site_lower = site.lower()
        if csv_lower in site_lower:
            # Calculate a high score for substring matches
            substring_score = len(csv_lower) / len(site_lower)  # Proportion of match
            substring_matches.append((site, substring_score + 0.5))  # Boost substring matches
    
    # Also try reverse substring matching - actual site name parts in CSV name
    for site in actual_sites:
        site_lower = site.lower()
        site_parts = site_lower.split('_')
        for part in site_parts:
            if len(part) > 3 and part in csv_lower:  # Look for meaningful parts (4+ chars)
                substring_score = len(part) / len(csv_lower)
                substring_matches.append((site, substring_score + 0.4))  # Boost reverse matches
        
        # Also check if the start of CSV name matches start of folder name
        if csv_lower.startswith(site_parts[0]) and len(site_parts[0]) > 3:
            substring_score = len(site_parts[0]) / len(csv_lower)
            substring_matches.append((site, substring_score + 0.5))  # Higher boost for prefix matches
    
    # If we found substring matches, return the best one
    if substring_matches:
        best_substring = max(substring_matches, key=lambda x: x[1])
        return best_substring[0], best_substring[1]
    
    # Try fuzzy matching as fallback
    best_match = None
    best_score = 0
    
    for site in actual_sites:
        score = similarity(csv_site_name, site)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = site
    
    return best_match, best_score

def create_site_name_mapping(csv_sites, discovered_sites):
    """
    Create mapping between CSV site names and actual folder names
    """
    logger.info("Creating site name mapping...")
    
    actual_sites = discovered_sites['common_sites']
    mapping = {}
    unmapped_sites = []
    
    for csv_site in csv_sites:
        if not csv_site:  # Skip empty site names
            continue
            
        best_match, score = find_best_site_match(csv_site, actual_sites)
        
        if best_match:
            mapping[csv_site] = best_match
            logger.info(f"Mapped '{csv_site}' -> '{best_match}' (similarity: {score:.2f})")
        else:
            unmapped_sites.append(csv_site)
            logger.warning(f"No good match found for CSV site: '{csv_site}'")
    
    if unmapped_sites:
        logger.warning(f"Unmapped sites: {unmapped_sites}")
        logger.info("Available actual sites: " + ", ".join(sorted(actual_sites)))
    
    return mapping, unmapped_sites

def get_corrected_data_paths(csv_site, date, site_mapping, discovered_sites):
    """
    Get the correct RGB and Micasense data paths based on actual folder structure
    """
    corrected_paths = {
        'rgb_data_path': '',
        'multispec_data_path': '',
        'rgb_path_exists': False,
        'multispec_path_exists': False,
        'actual_site_name': '',
        'mapping_used': False
    }
    
    # Determine the actual site name to use
    actual_site = site_mapping.get(csv_site)
    if actual_site:
        corrected_paths['actual_site_name'] = actual_site
        corrected_paths['mapping_used'] = True
    else:
        # Try using the CSV site name directly
        actual_site = csv_site
        corrected_paths['actual_site_name'] = csv_site
    
    # Construct expected data paths
    if actual_site and date:
        # RGB path
        rgb_path = P1_DATA_DIR / actual_site / date
        if rgb_path.exists():
            corrected_paths['rgb_data_path'] = str(rgb_path)
            corrected_paths['rgb_path_exists'] = True
        
        # Micasense path  
        micasense_path = MICASENSE_DATA_DIR / actual_site / date
        if micasense_path.exists():
            corrected_paths['multispec_data_path'] = str(micasense_path)
            corrected_paths['multispec_path_exists'] = True
    
    return corrected_paths

def discover_all_projects(base_directory):
    """
    Scan the entire directory structure to find all Metashape projects
    Returns a list of discovered projects with inferred metadata
    """
    logger.info(f"Scanning for all Metashape projects in: {base_directory}")
    
    base_path = Path(base_directory)
    if not base_path.exists():
        logger.error(f"Base directory does not exist: {base_directory}")
        return []
    
    discovered_projects = []
    
    # Find all .psx files recursively
    psx_files = list(base_path.glob("**/*.psx"))
    logger.info(f"Found {len(psx_files)} .psx files")
    
    for psx_file in psx_files:
        try:
            # Extract information from file path and name
            project_info = extract_project_info(psx_file)
            if project_info:
                discovered_projects.append(project_info)
                logger.debug(f"Discovered project: {project_info['site']} - {project_info['date']}")
        except Exception as e:
            logger.warning(f"Error processing {psx_file}: {e}")
    
    logger.info(f"Successfully processed {len(discovered_projects)} projects")
    return discovered_projects

def extract_project_info(psx_file):
    """
    Extract site name, date, and other info from project file path and name
    Handles various naming conventions
    """
    project_path = Path(psx_file)
    
    # Try to extract info from filename first
    filename = project_path.stem
    
    # Common patterns in project names
    patterns = [
        # Pattern: metashape_project_SiteName_Date.psx
        r'metashape_project_(.+?)_(\d{8})',
        # Pattern: SiteName_Date.psx  
        r'(.+?)_(\d{8})',
        # Pattern: Date_SiteName.psx
        r'(\d{8})_(.+)',
    ]
    
    site = None
    date = None
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                # Determine which group is date vs site
                for group in groups:
                    if re.match(r'\d{8}', group):  # 8 digits = date
                        date = group
                    else:
                        site = group
                break
    
    # If filename parsing failed, try to extract from directory structure
    if not site or not date:
        path_parts = project_path.parts
        
        # Look for date patterns in path parts (YYYYMMDD)
        for part in reversed(path_parts):
            if re.match(r'\d{8}', part):
                date = part
                break
        
        # Look for site name in parent directories
        if not site:
            # Try the project directory name
            project_dir = project_path.parent.name
            # Remove common prefixes/suffixes
            site_candidate = re.sub(r'(metashape_project_|_\d{8})', '', project_dir)
            if site_candidate and site_candidate != project_dir:
                site = site_candidate
            else:
                # Use the project directory name as-is
                site = project_dir
    
    # Final fallback - use directory name as site
    if not site:
        site = project_path.parent.name
    
    # Validate and clean up
    if date and not re.match(r'\d{8}', date):
        logger.warning(f"Invalid date format extracted: {date} from {psx_file}")
        date = None
    
    if not site:
        logger.warning(f"Could not extract site name from {psx_file}")
        site = "Unknown"
    
    return {
        'project_path': str(psx_file),
        'site': site,
        'date': date or "Unknown",
        'source': 'directory_scan'
    }

def check_file_exists(file_path):
    """Check if a file exists and return file size if it does"""
    if os.path.exists(file_path):
        try:
            size = os.path.getsize(file_path)
            return True, size
        except OSError:
            return True, 0
    return False, 0

def validate_data_paths(rgb_data_path, multispec_data_path, site, date):
    """
    Validate that the provided data paths exist and contain expected data
    Returns status information about data availability
    """
    validation_info = {
        'rgb_path_exists': False,
        'multispec_path_exists': False,
        'rgb_images_found': 0,
        'multispec_images_found': 0,
        'rgb_actual_path': '',
        'multispec_actual_path': '',
        'path_issues': []
    }
    
    # Check RGB path
    if rgb_data_path:
        rgb_path = Path(rgb_data_path)
        if rgb_path.exists():
            validation_info['rgb_path_exists'] = True
            validation_info['rgb_actual_path'] = str(rgb_path)
            # Count RGB images (common extensions)
            rgb_patterns = ['*.jpg', '*.jpeg', '*.tif', '*.tiff', '*.dng']
            for pattern in rgb_patterns:
                validation_info['rgb_images_found'] += len(list(rgb_path.glob(pattern)))
        else:
            validation_info['path_issues'].append(f"RGB path does not exist: {rgb_data_path}")
    
    # Check multispectral path
    if multispec_data_path:
        multispec_path = Path(multispec_data_path)
        if multispec_path.exists():
            validation_info['multispec_path_exists'] = True
            validation_info['multispec_actual_path'] = str(multispec_path)
            # Count multispectral images
            ms_patterns = ['*.jpg', '*.jpeg', '*.tif', '*.tiff']
            for pattern in ms_patterns:
                validation_info['multispec_images_found'] += len(list(multispec_path.glob(pattern)))
        else:
            validation_info['path_issues'].append(f"Multispec path does not exist: {multispec_data_path}")
    
    return validation_info

def get_file_info(file_path):
    """Get detailed file information including modification date"""
    if os.path.exists(file_path):
        try:
            stat = os.stat(file_path)
            return {
                'exists': True,
                'size_mb': round(stat.st_size / (1024*1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            }
        except OSError:
            return {'exists': True, 'size_mb': 0, 'modified': 'Unknown'}
    return {'exists': False, 'size_mb': 0, 'modified': 'N/A'}

def check_project_outputs(project_path, site, date, rgb_data_path=None, multispec_data_path=None):
    """
    Check for all expected output files for a project
    Expected outputs:
    - RGB orthomosaic (multiple resolutions possible)
    - Multispectral orthomosaic 
    - RGB report
    - Multispectral report
    - DEM files
    - 3D models
    """
    project_dir = Path(project_path).parent
    export_dir = project_dir / "exports"
    
    # Create multiple possible file prefixes to handle naming variations
    file_prefixes = [
        f"{date}_{site}",
        f"{date}_{site.replace('-', '_')}",  # Handle dash/underscore variations
        f"{date}_{site.replace('_', '-')}",
        site,
        site.replace('-', '_'),
        site.replace('_', '-')
    ]
    
    # Extract site name variations from project path if available
    if project_dir.exists():
        project_folder_name = project_dir.name
        # Try to extract site name from project folder
        if '_' in project_folder_name:
            potential_site = project_folder_name.split('_')[0]
            file_prefixes.extend([
                f"{date}_{potential_site}",
                potential_site
            ])
    
    # Remove duplicates while preserving order
    file_prefixes = list(dict.fromkeys(file_prefixes))
    
    results = {
        'project_exists': os.path.exists(project_path),
        'export_dir_exists': export_dir.exists() if project_dir.exists() else False,
        'rgb_ortho': [],
        'multispec_ortho': [],
        'rgb_report': None,
        'multispec_report': None,
        'dem_files': [],
        'model_files': [],
        'total_outputs': 0,
        'total_size_mb': 0
    }
    
    if not project_dir.exists():
        return results
    
    # Create comprehensive search patterns using all possible prefixes
    search_patterns = {
        'rgb_ortho': [f"*rgb*ortho*.tif"],
        'multispec_ortho': [f"*multispec*ortho*.tif"],
        'rgb_report': [f"*rgb*report*.pdf"],
        'multispec_report': [f"*multispec*report*.pdf"],
        'dem_files': [f"*dem*.tif"],
        'model_files': [f"*model*.obj", f"*smooth*.obj"]
    }
    
    # Add prefix-specific patterns
    for prefix in file_prefixes:
        if prefix:  # Skip empty prefixes
            search_patterns['rgb_ortho'].extend([
                f"{prefix}*rgb*ortho*.tif",
                f"*{prefix}*rgb*ortho*.tif"
            ])
            search_patterns['multispec_ortho'].extend([
                f"{prefix}*multispec*ortho*.tif",
                f"*{prefix}*multispec*ortho*.tif"
            ])
            search_patterns['rgb_report'].extend([
                f"{prefix}*rgb*report*.pdf",
                f"*{prefix}*rgb*report*.pdf"
            ])
            search_patterns['multispec_report'].extend([
                f"{prefix}*multispec*report*.pdf",
                f"*{prefix}*multispec*report*.pdf"
            ])
            search_patterns['dem_files'].extend([
                f"{prefix}*dem*.tif",
                f"*{prefix}*dem*.tif"
            ])
            search_patterns['model_files'].extend([
                f"{prefix}*model*.obj",
                f"*{prefix}*model*.obj"
            ])
    
    # Search in project directory and exports subdirectory
    search_dirs = [project_dir]
    if export_dir.exists():
        search_dirs.append(export_dir)
    
    for search_dir in search_dirs:
        for file_type, patterns in search_patterns.items():
            for pattern in patterns:
                matching_files = list(search_dir.glob(pattern))
                
                for file_path in matching_files:
                    file_info = get_file_info(file_path)
                    
                    if file_info['exists']:
                        if file_type in ['rgb_report', 'multispec_report']:
                            if results[file_type] is None:  # Take first match
                                results[file_type] = {
                                    'path': str(file_path),
                                    'size_mb': file_info['size_mb'],
                                    'modified': file_info['modified']
                                }
                        else:
                            # For lists (orthos, dems, models)
                            file_entry = {
                                'path': str(file_path),
                                'size_mb': file_info['size_mb'],
                                'modified': file_info['modified']
                            }
                            if file_entry not in results[file_type]:
                                results[file_type].append(file_entry)
                        
                        results['total_size_mb'] += file_info['size_mb']
                        results['total_outputs'] += 1
    
    return results

def generate_processing_report(csv_file_path=None, base_directory=None, output_file="processing_status_report.csv", scan_directory=False):
    """Generate detailed processing status report"""
    
    projects = []
    csv_projects = []
    scanned_projects = []
    
    # Load projects from CSV if provided
    if csv_file_path:
        logger.info(f"Reading project data from CSV: {csv_file_path}")
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            csv_projects = list(reader)
        logger.info(f"Found {len(csv_projects)} projects from CSV")
    
    # Scan directory if requested
    if scan_directory and base_directory:
        logger.info(f"Scanning directory for all projects: {base_directory}")
        scanned_projects = discover_all_projects(base_directory)
        logger.info(f"Found {len(scanned_projects)} projects from directory scan")
    
    # Combine results
    if csv_projects and scanned_projects:
        # Merge CSV and scanned projects, CSV takes priority for metadata
        logger.info("Combining CSV and directory scan results...")
        csv_paths = {proj.get('project_path', '') for proj in csv_projects}
        
        # Start with CSV projects
        projects = csv_projects.copy()
        
        # Add scanned projects that aren't in CSV
        for scanned_proj in scanned_projects:
            if scanned_proj['project_path'] not in csv_paths:
                projects.append(scanned_proj)
                logger.info(f"Added new project from scan: {scanned_proj['site']} - {scanned_proj['date']}")
        
        logger.info(f"Combined total: {len(projects)} projects ({len(csv_projects)} from CSV + {len(projects) - len(csv_projects)} new from scan)")
    
    elif csv_projects:
        projects = csv_projects
    elif scanned_projects:
        projects = scanned_projects
    else:
        logger.error("No projects found from any source")
        return None
    
    # Discover actual site names from data directories
    discovered_sites = discover_actual_site_names()
    
    # Get unique site names from CSV
    csv_sites = list(set(project.get('site', '') for project in projects if project.get('site', '')))
    logger.info(f"Found {len(csv_sites)} unique sites in CSV: {sorted(csv_sites)}")
    
    # Create site name mapping
    site_mapping, unmapped_sites = create_site_name_mapping(csv_sites, discovered_sites)
    
    report_data = []
    
    for i, project in enumerate(projects, 1):
        logger.info(f"Checking project {i}/{len(projects)}: {project.get('site', 'Unknown')} - {project.get('date', 'Unknown')}")
        
        project_path = project.get('project_path', '')
        site = project.get('site', '')
        date = project.get('date', '')
        
        # Log project details for debugging
        logger.debug(f"  Project path: {project_path}")
        logger.debug(f"  Site: {site}")  
        logger.debug(f"  Date: {date}")
        
        # Get RGB and multispec data paths from CSV
        csv_rgb_path = project.get('rgb_data_path', project.get('rgb', ''))
        csv_multispec_path = project.get('multispec_data_path', project.get('multispec', ''))
        
        # Get corrected data paths using site mapping
        corrected_paths = get_corrected_data_paths(site, date, site_mapping, discovered_sites)
        
        # Use corrected paths if they exist, otherwise fall back to CSV paths
        rgb_data_path = corrected_paths['rgb_data_path'] if corrected_paths['rgb_path_exists'] else csv_rgb_path
        multispec_data_path = corrected_paths['multispec_data_path'] if corrected_paths['multispec_path_exists'] else csv_multispec_path
        
        # Validate final data paths
        data_validation = validate_data_paths(rgb_data_path, multispec_data_path, site, date)
        
        # Check project outputs
        outputs = check_project_outputs(project_path, site, date, rgb_data_path, multispec_data_path)
        
        # Calculate processing completeness score
        completeness_score = 0
        max_score = 6  # RGB ortho, MS ortho, RGB report, MS report, DEM, Model
        
        if outputs['rgb_ortho']:
            completeness_score += 1
        if outputs['multispec_ortho']:
            completeness_score += 1
        if outputs['rgb_report']:
            completeness_score += 1
        if outputs['multispec_report']:
            completeness_score += 1
        if outputs['dem_files']:
            completeness_score += 1
        if outputs['model_files']:
            completeness_score += 1
        
        processing_status = "Complete" if completeness_score >= 5 else \
                          "Partial" if completeness_score > 0 else \
                          "Not Processed" if outputs['project_exists'] else "Project Missing"
        
        report_row = {
            'date': date,
            'site': site,
            'project_path': project_path,
            'project_exists': outputs['project_exists'],
            'processing_status': processing_status,
            'completeness_score': f"{completeness_score}/{max_score}",
            'total_outputs': outputs['total_outputs'],
            'total_size_mb': round(outputs['total_size_mb'], 2),
            
            # RGB outputs
            'rgb_ortho_count': len(outputs['rgb_ortho']),
            'rgb_ortho_paths': '; '.join([f['path'] for f in outputs['rgb_ortho']]),
            'rgb_report_exists': outputs['rgb_report'] is not None,
            'rgb_report_path': outputs['rgb_report']['path'] if outputs['rgb_report'] else '',
            
            # Multispectral outputs  
            'multispec_ortho_count': len(outputs['multispec_ortho']),
            'multispec_ortho_paths': '; '.join([f['path'] for f in outputs['multispec_ortho']]),
            'multispec_report_exists': outputs['multispec_report'] is not None,
            'multispec_report_path': outputs['multispec_report']['path'] if outputs['multispec_report'] else '',
            
            # Other outputs
            'dem_count': len(outputs['dem_files']),
            'dem_paths': '; '.join([f['path'] for f in outputs['dem_files']]),
            'model_count': len(outputs['model_files']),
            'model_paths': '; '.join([f['path'] for f in outputs['model_files']]),
            
            # Original CSV data
            'csv_rgb_data_path': csv_rgb_path,
            'csv_multispec_data_path': csv_multispec_path,
            'corrected_rgb_data_path': rgb_data_path,
            'corrected_multispec_data_path': multispec_data_path,
            'actual_site_name': corrected_paths['actual_site_name'],
            'site_mapping_used': corrected_paths['mapping_used'],
            'sunsens': project.get('sunsens', ''),
            'image_load_status': project.get('image_load_status', ''),
            
            # Data path validation
            'rgb_path_exists': data_validation['rgb_path_exists'],
            'multispec_path_exists': data_validation['multispec_path_exists'],
            'rgb_images_found': data_validation['rgb_images_found'],
            'multispec_images_found': data_validation['multispec_images_found'],
            'path_issues': '; '.join(data_validation['path_issues'])
        }
        
        report_data.append(report_row)
    
    # Write report to CSV
    if report_data:
        df = pd.DataFrame(report_data)
        df.to_csv(output_file, index=False)
        logger.info(f"Processing status report saved to: {output_file}")
        
        # Print summary statistics
        total_projects = len(report_data)
        complete_projects = len(df[df['processing_status'] == 'Complete'])
        partial_projects = len(df[df['processing_status'] == 'Partial'])
        not_processed = len(df[df['processing_status'] == 'Not Processed'])
        missing_projects = len(df[df['processing_status'] == 'Project Missing'])
        
        print(f"\n📊 PROCESSING SUMMARY")
        print(f"{'='*50}")
        print(f"Total projects: {total_projects}")
        print(f"Complete: {complete_projects} ({complete_projects/total_projects*100:.1f}%)")
        print(f"Partial: {partial_projects} ({partial_projects/total_projects*100:.1f}%)")
        print(f"Not processed: {not_processed} ({not_processed/total_projects*100:.1f}%)")
        print(f"Missing projects: {missing_projects} ({missing_projects/total_projects*100:.1f}%)")
        
        # Site mapping summary
        mapped_sites = len([row for row in report_data if row['site_mapping_used']])
        print(f"\n🗺️  SITE MAPPING SUMMARY")
        print(f"{'='*50}")
        print(f"Total unique sites in CSV: {len(csv_sites)}")
        print(f"Sites found in data directories: {len(discovered_sites['common_sites'])}")
        print(f"Projects using corrected site mapping: {mapped_sites}")
        print(f"Unmapped sites: {len(unmapped_sites)} - {unmapped_sites if unmapped_sites else 'None'}")
        
        return df
    
    return None

def generate_unprocessed_report(df, output_file="unprocessed_projects.csv"):
    """Generate report of ALL projects that are missing required output files in export directory"""
    
    # Filter for projects that:
    # 1. Project exists (the .psx file exists) OR project should exist based on CSV
    # 2. Are missing output files (not complete processing status)
    # Note: We include ALL projects missing outputs, regardless of data availability
    unprocessed = df[
        (df['processing_status'] != 'Complete')
    ].copy()
    
    # Optional: Can still prioritize projects with existing data paths, but include all
    # This ensures we catch projects that need processing but may not have data yet
    
    if len(unprocessed) > 0:
        # Add columns to identify missing outputs
        unprocessed['missing_rgb_ortho'] = unprocessed['rgb_ortho_count'] == 0
        unprocessed['missing_multispec_ortho'] = unprocessed['multispec_ortho_count'] == 0
        unprocessed['missing_rgb_report'] = ~unprocessed['rgb_report_exists']
        unprocessed['missing_multispec_report'] = ~unprocessed['multispec_report_exists']
        unprocessed['missing_dem'] = unprocessed['dem_count'] == 0
        unprocessed['missing_model'] = unprocessed['model_count'] == 0
        
        # Create summary of missing outputs
        def get_missing_outputs(row):
            missing = []
            # Check for missing RGB outputs (regardless of data availability)
            if row['missing_rgb_ortho']:
                missing.append('RGB_ortho')
            if row['missing_multispec_ortho']:
                missing.append('MS_ortho')
            if row['missing_rgb_report']:
                missing.append('RGB_report')
            if row['missing_multispec_report']:
                missing.append('MS_report')
            if row['missing_dem']:
                missing.append('DEM')
            if row['missing_model']:
                missing.append('Model')
            return '; '.join(missing)
        
        unprocessed['missing_outputs'] = unprocessed.apply(get_missing_outputs, axis=1)
        
        # Rename columns to match UpscaleRunScript.py expectations and select relevant columns
        unprocessed_report = unprocessed.copy()
        unprocessed_report['rgb_data_path'] = unprocessed_report['corrected_rgb_data_path']
        unprocessed_report['multispec_data_path'] = unprocessed_report['corrected_multispec_data_path']
        
        # Select columns compatible with UpscaleRunScript.py
        unprocessed_report = unprocessed_report[[
            'date', 'site', 'project_path', 'rgb_data_path', 'multispec_data_path', 
            'sunsens', 'processing_status', 'completeness_score', 'total_outputs', 
            'missing_outputs', 'actual_site_name', 'site_mapping_used', 
            'rgb_path_exists', 'multispec_path_exists', 'rgb_images_found', 
            'multispec_images_found', 'path_issues'
        ]]
        
        unprocessed_report.to_csv(output_file, index=False)
        logger.info(f"Unprocessed projects report saved to: {output_file}")
        
        print(f"\n📋 ALL UNPROCESSED PROJECTS (Missing Required Output Files)")
        print(f"{'='*55}")
        print(f"Found {len(unprocessed)} projects missing required outputs in export directory:")
        
        for _, row in unprocessed_report.iterrows():
            data_info = []
            if row['rgb_images_found'] > 0:
                data_info.append(f"RGB: {row['rgb_images_found']} images")
            if row['multispec_images_found'] > 0:
                data_info.append(f"MS: {row['multispec_images_found']} images")
            data_str = " | ".join(data_info) if data_info else "No data found"
            
            print(f"  • {row['site']} ({row['date']}) - {row['processing_status']} - {data_str}")
        
        return unprocessed_report
    else:
        logger.info("No unprocessed projects found!")
        print(f"\n✅ All projects have complete output files in export directory!")
        return None

def main():
    """Main function"""
    print("🔍 Metashape Project Processing Status Checker")
    print("=" * 50)
    
    # Ask user for input method
    print("Choose input method:")
    print("1. Use CSV file (existing project list)")
    print("2. Scan directory for all projects")
    print("3. Both (CSV + directory scan)")
    
    choice = input("Enter choice (1-3): ").strip()
    
    # Default paths
    default_csv = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\UPSCALE_logbook_RGBandMulti_data_project_created.csv"
    default_dir = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects"
    
    csv_file_path = None
    base_directory = None
    scan_directory = False
    
    if choice in ['1', '3']:  # CSV input
        csv_file_path = input(f"Enter CSV file path (or press Enter for default):\n{default_csv}\n> ").strip()
        if not csv_file_path:
            csv_file_path = default_csv
        
        if not os.path.exists(csv_file_path):
            print(f"❌ Error: CSV file not found: {csv_file_path}")
            if choice == '1':
                return
            csv_file_path = None
    
    if choice in ['2', '3']:  # Directory scan
        base_directory = input(f"Enter base directory to scan (or press Enter for default):\n{default_dir}\n> ").strip()
        if not base_directory:
            base_directory = default_dir
        
        if not os.path.exists(base_directory):
            print(f"❌ Error: Directory not found: {base_directory}")
            if choice == '2':
                return
            base_directory = None
        else:
            scan_directory = True
    
    # Set output directory
    if csv_file_path:
        output_dir = Path(csv_file_path).parent
    elif base_directory:
        output_dir = Path(base_directory)
    else:
        print("❌ Error: No valid input source provided")
        return
    
    # Create output file names with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = output_dir / f"processing_status_report_{timestamp}.csv"
    unprocessed_file = output_dir / f"unprocessed_projects_{timestamp}.csv"
    
    print(f"\n📁 Output files will be saved to: {output_dir}")
    print(f"📊 Processing status report: {report_file}")
    print(f"📋 Unprocessed projects: {unprocessed_file}")
    print()
    
    # Generate reports
    try:
        df = generate_processing_report(
            csv_file_path=csv_file_path,
            base_directory=base_directory,
            output_file=str(report_file),
            scan_directory=scan_directory
        )
        if df is not None:
            generate_unprocessed_report(df, str(unprocessed_file))
            print(f"\n✅ Reports generated successfully!")
            print(f"📊 Detailed report: {report_file}")
            print(f"📋 Unprocessed list: {unprocessed_file}")
        else:
            print("❌ Failed to generate reports")
            
    except Exception as e:
        logger.error(f"Error generating reports: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
