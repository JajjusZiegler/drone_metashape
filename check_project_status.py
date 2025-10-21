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
from pathlib import Path
import pandas as pd
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_file_exists(file_path):
    """Check if a file exists and return file size if it does"""
    if os.path.exists(file_path):
        try:
            size = os.path.getsize(file_path)
            return True, size
        except OSError:
            return True, 0
    return False, 0

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

def check_project_outputs(project_path, site, date):
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
    
    # File patterns to look for
    file_prefix = f"{date}_{site}"
    
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
    
    # Search patterns
    search_patterns = {
        'rgb_ortho': [
            f"*rgb*ortho*.tif",
            f"{file_prefix}*rgb*ortho*.tif",
            f"*{site}*rgb*ortho*.tif"
        ],
        'multispec_ortho': [
            f"*multispec*ortho*.tif",
            f"{file_prefix}*multispec*ortho*.tif", 
            f"*{site}*multispec*ortho*.tif"
        ],
        'rgb_report': [
            f"*rgb*report*.pdf",
            f"{file_prefix}*rgb*report*.pdf",
            f"*{site}*rgb*report*.pdf"
        ],
        'multispec_report': [
            f"*multispec*report*.pdf",
            f"{file_prefix}*multispec*report*.pdf",
            f"*{site}*multispec*report*.pdf"
        ],
        'dem_files': [
            f"*dem*.tif",
            f"{file_prefix}*dem*.tif",
            f"*{site}*dem*.tif"
        ],
        'model_files': [
            f"*model*.obj",
            f"*smooth*.obj",
            f"{file_prefix}*model*.obj"
        ]
    }
    
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

def generate_processing_report(csv_file_path, output_file="processing_status_report.csv"):
    """Generate detailed processing status report"""
    
    logger.info(f"Reading project data from: {csv_file_path}")
    
    # Read the CSV file
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        projects = list(reader)
    
    logger.info(f"Found {len(projects)} projects to check")
    
    report_data = []
    
    for i, project in enumerate(projects, 1):
        logger.info(f"Checking project {i}/{len(projects)}: {project.get('site', 'Unknown')} - {project.get('date', 'Unknown')}")
        
        project_path = project.get('project_path', '')
        site = project.get('site', '')
        date = project.get('date', '')
        
        # Check project outputs
        outputs = check_project_outputs(project_path, site, date)
        
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
        
        processing_status = "Complete" if completeness_score == max_score else \
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
            'rgb_data_path': project.get('rgb', ''),
            'multispec_data_path': project.get('multispec', ''),
            'sunsens': project.get('sunsens', ''),
            'image_load_status': project.get('image_load_status', '')
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
        
        return df
    
    return None

def generate_unprocessed_report(df, output_file="unprocessed_projects.csv"):
    """Generate report of unprocessed but existing projects"""
    
    # Filter for projects that exist but are not complete
    unprocessed = df[
        (df['project_exists'] == True) & 
        (df['processing_status'].isin(['Not Processed', 'Partial']))
    ].copy()
    
    if len(unprocessed) > 0:
        # Select relevant columns for unprocessed report
        unprocessed_report = unprocessed[[
            'date', 'site', 'project_path', 'processing_status', 
            'completeness_score', 'total_outputs', 'rgb_data_path', 
            'multispec_data_path', 'sunsens'
        ]]
        
        unprocessed_report.to_csv(output_file, index=False)
        logger.info(f"Unprocessed projects report saved to: {output_file}")
        
        print(f"\n📋 UNPROCESSED PROJECTS")
        print(f"{'='*50}")
        print(f"Found {len(unprocessed)} unprocessed projects:")
        
        for _, row in unprocessed_report.iterrows():
            print(f"  • {row['site']} ({row['date']}) - {row['processing_status']}")
        
        return unprocessed_report
    else:
        logger.info("No unprocessed projects found!")
        print(f"\n✅ All projects are complete!")
        return None

def main():
    """Main function"""
    print("🔍 Metashape Project Processing Status Checker")
    print("=" * 50)
    
    # Default CSV file path from your message
    default_csv = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects\UPSCALE_logbook_RGBandMulti_data_project_created.csv"
    
    csv_file_path = input(f"Enter CSV file path (or press Enter for default):\n{default_csv}\n> ").strip()
    
    if not csv_file_path:
        csv_file_path = default_csv
    
    if not os.path.exists(csv_file_path):
        print(f"❌ Error: CSV file not found: {csv_file_path}")
        return
    
    # Set output directory to same location as CSV file
    output_dir = Path(csv_file_path).parent
    report_file = output_dir / "processing_status_report.csv"
    unprocessed_file = output_dir / "unprocessed_projects.csv"
    
    print(f"📁 Output files will be saved to: {output_dir}")
    print(f"📊 Processing status report: {report_file}")
    print(f"📋 Unprocessed projects: {unprocessed_file}")
    print()
    
    # Generate reports
    try:
        df = generate_processing_report(csv_file_path, str(report_file))
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
