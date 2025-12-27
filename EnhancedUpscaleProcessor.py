"""
Enhanced Upscale Processor for Metashape Projects
==================================================

A robust batch processor that validates all paths before processing and provides
clear feedback on project status and potential issues.

Features:
- Comprehensive path validation before processing starts
- Test mode (dry-run) to validate without processing
- Detailed logging per project
- Timeout protection
- Clear progress reporting
- Handles missing/partial data gracefully

Usage:
    python EnhancedUpscaleProcessor.py input.csv
    python EnhancedUpscaleProcessor.py input.csv --test  # Dry-run mode
    python EnhancedUpscaleProcessor.py input.csv --timeout 7200  # 2 hour timeout

CSV Format Required:
    Columns: date, site, project_path, rgb_data_path, multispec_data_path, sunsens (optional)
    
Author: GitHub Copilot
Date: 2025-12-27
"""

import csv
import subprocess
import sys
import os
from pathlib import Path
import logging
import datetime
import threading
import time
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# Configuration
# ============================================================================

METASHAPE_PYTHON_PATH = r"C:\Program Files\Agisoft\Metashape Pro\python\python.exe"
TARGET_SCRIPT_PATH = r"C:\Users\admin\Documents\Python Scripts\drone_metashape\DEMtests.py"
DEFAULT_CRS = "2056"  # Swiss coordinate system
DEFAULT_TIMEOUT = 3600  # 60 minutes in seconds
DEFAULT_SMOOTH = "medium"  # low/medium/high

# Required output files for a fully processed project
REQUIRED_OUTPUTS = {
    'rgb_ortho': ['*rgb*ortho*.tif', '*RGB*ortho*.tif', '*P1*ortho*.tif'],
    'multispec_ortho': ['*multispec*ortho*.tif', '*MS*ortho*.tif', '*micasense*ortho*.tif'],
    'model': ['*.obj'],
    'reports': ['*.pdf']
}

# Possible export directory names
EXPORT_DIR_NAMES = [
    "export",
    "Export",
    "exports",
    "Exports",
    "output",
    "Output"
]

# ============================================================================
# Data Classes
# ============================================================================

class ValidationStatus(Enum):
    """Status of path validation"""
    VALID = "[OK] Valid"
    MISSING = "[X] Missing"
    EMPTY = "[!] Empty"
    PARTIAL = "[!] Partial"

@dataclass
class ProjectData:
    """Container for project information"""
    date: str
    site: str
    project_path: Path
    rgb_data_path: Optional[Path]
    multispec_data_path: Optional[Path]
    sunsens: bool
    row_number: int
    
    # Validation results
    project_exists: bool = False
    rgb_exists: bool = False
    multispec_exists: bool = False
    already_processed: bool = False
    missing_outputs: List[str] = None  # Track what outputs are missing
    validation_status: ValidationStatus = ValidationStatus.VALID
    validation_messages: List[str] = None
    
    def __post_init__(self):
        if self.validation_messages is None:
            self.validation_messages = []
        if self.missing_outputs is None:
            self.missing_outputs = []
    
    def is_processable(self) -> bool:
        """Check if project has minimum requirements for processing"""
        return (
            self.project_exists and 
            (self.rgb_exists or self.multispec_exists) and
            not self.already_processed
        )
    
    def get_status_summary(self) -> str:
        """Get a one-line status summary"""
        parts = []
        if self.project_exists:
            parts.append("[OK] Project")
        else:
            parts.append("[X] Project")
        
        if self.rgb_exists:
            parts.append("[OK] RGB")
        elif self.rgb_data_path:
            parts.append("[X] RGB")
            
        if self.multispec_exists:
            parts.append("[OK] MS")
        elif self.multispec_data_path:
            parts.append("[X] MS")
        
        if self.already_processed:
            parts.append("[DONE] Processed")
        
        return " | ".join(parts)

# ============================================================================
# Path Validation Functions
# ============================================================================

def check_project_already_processed(project_path: Path) -> Tuple[bool, List[str]]:
    """
    Check if project has ALL required output files.
    Returns: (is_fully_processed, list_of_missing_outputs)
    
    Required outputs:
    1. RGB orthomosaic (.tif with rgb/RGB/P1 and ortho in name)
    2. Multispectral orthomosaic (.tif with multispec/MS/micasense and ortho in name)
    3. 3D Model (.obj file)
    4. Two PDF reports (at least 2 .pdf files)
    """
    if not project_path.exists():
        return False, ["Project file not found"]
    
    project_dir = project_path.parent
    
    # List of directories to check
    dirs_to_check = [project_dir]
    
    # Check for export subdirectories
    for export_name in EXPORT_DIR_NAMES:
        export_dir = project_dir / export_name
        if export_dir.exists() and export_dir.is_dir():
            dirs_to_check.append(export_dir)
    
    # Track what we find
    has_rgb_ortho = False
    has_multispec_ortho = False
    has_model = False
    pdf_count = 0
    missing = []
    
    # Check each directory
    for check_dir in dirs_to_check:
        # Check for RGB orthomosaic
        if not has_rgb_ortho:
            for pattern in REQUIRED_OUTPUTS['rgb_ortho']:
                matches = list(check_dir.glob(pattern))
                if matches:
                    has_rgb_ortho = True
                    break
        
        # Check for multispectral orthomosaic
        if not has_multispec_ortho:
            for pattern in REQUIRED_OUTPUTS['multispec_ortho']:
                matches = list(check_dir.glob(pattern))
                if matches:
                    has_multispec_ortho = True
                    break
        
        # Check for 3D model
        if not has_model:
            for pattern in REQUIRED_OUTPUTS['model']:
                matches = list(check_dir.glob(pattern))
                if matches:
                    has_model = True
                    break
        
        # Count PDF reports
        for pattern in REQUIRED_OUTPUTS['reports']:
            matches = list(check_dir.glob(pattern))
            pdf_count += len(matches)
    
    # Determine what's missing
    if not has_rgb_ortho:
        missing.append("RGB orthomosaic")
    if not has_multispec_ortho:
        missing.append("Multispectral orthomosaic")
    if not has_model:
        missing.append("3D model (.obj)")
    if pdf_count < 2:
        missing.append(f"PDF reports (found {pdf_count}, need 2)")
    
    # Project is fully processed only if ALL required outputs exist
    is_fully_processed = (has_rgb_ortho and has_multispec_ortho and 
                          has_model and pdf_count >= 2)
    
    return is_fully_processed, missing

def validate_project(project: ProjectData) -> ProjectData:
    """Validate all paths and data availability for a project"""
    
    # Check project file
    if project.project_path.exists() and project.project_path.is_file():
        project.project_exists = True
    else:
        project.validation_messages.append(f"Project file not found: {project.project_path}")
        project.validation_status = ValidationStatus.MISSING
    
    # Check RGB data
    if project.rgb_data_path:
        if project.rgb_data_path.exists() and project.rgb_data_path.is_dir():
            project.rgb_exists = True
        else:
            project.validation_messages.append(f"RGB data path not found: {project.rgb_data_path}")
    
    # Check multispectral data
    if project.multispec_data_path:
        if project.multispec_data_path.exists() and project.multispec_data_path.is_dir():
            project.multispec_exists = True
        else:
            project.validation_messages.append(f"Multispec data path not found: {project.multispec_data_path}")
    
    # Check if already processed
    if project.project_exists:
        project.already_processed, project.missing_outputs = check_project_already_processed(project.project_path)
        if project.already_processed:
            project.validation_messages.append("Project fully processed - all outputs found")
        elif project.missing_outputs:
            project.validation_messages.append(f"Incomplete processing - missing: {', '.join(project.missing_outputs)}")
    
    # Determine overall validation status
    if not project.project_exists:
        project.validation_status = ValidationStatus.MISSING
    elif project.already_processed:
        project.validation_status = ValidationStatus.VALID  # Valid but will be skipped
    elif not project.rgb_exists and not project.multispec_exists:
        project.validation_status = ValidationStatus.MISSING
        project.validation_messages.append("No valid data sources found (neither RGB nor multispectral)")
    elif project.rgb_exists != project.multispec_exists:
        project.validation_status = ValidationStatus.PARTIAL
        project.validation_messages.append("Only one data source available (RGB or multispectral)")
    else:
        project.validation_status = ValidationStatus.VALID
    
    return project

# ============================================================================
# CSV Reading and Validation
# ============================================================================

def read_and_validate_csv(csv_path: str, count_images_flag: bool = True) -> Tuple[List[ProjectData], List[str]]:
    """
    Read CSV and validate all projects.
    Returns: (list of ProjectData, list of error messages)
    """
    projects = []
    errors = []
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        errors.append(f"CSV file not found: {csv_path}")
        return projects, errors
    
    required_columns = {'date', 'site', 'project_path'}
    
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Validate columns
            if not required_columns.issubset(set(reader.fieldnames)):
                missing = required_columns - set(reader.fieldnames)
                errors.append(f"CSV missing required columns: {missing}")
                return projects, errors
            
            # Check for data path columns (either naming convention)
            has_data_paths = ('rgb_data_path' in reader.fieldnames or 'rgb' in reader.fieldnames) and \
                           ('multispec_data_path' in reader.fieldnames or 'multispec' in reader.fieldnames)
            if not has_data_paths:
                errors.append("CSV missing data path columns (need 'rgb' and 'multispec' OR 'rgb_data_path' and 'multispec_data_path')")
                return projects, errors
            
            # Read and validate each row
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                try:
                    # Extract required fields
                    date = row.get('date', '').strip()
                    site = row.get('site', '').strip()
                    project_path_str = row.get('project_path', '').strip()
                    
                    if not all([date, site, project_path_str]):
                        errors.append(f"Row {row_num}: Missing required fields (date, site, or project_path)")
                        continue
                    
                    # Extract optional fields - handle both naming conventions
                    rgb_path_str = row.get('rgb_data_path', '') or row.get('rgb', '')
                    rgb_path_str = rgb_path_str.strip()
                    multispec_path_str = row.get('multispec_data_path', '') or row.get('multispec', '')
                    multispec_path_str = multispec_path_str.strip()
                    sunsens_str = row.get('sunsens', '').strip().lower()
                    
                    # Create ProjectData
                    project = ProjectData(
                        date=date,
                        site=site,
                        project_path=Path(project_path_str),
                        rgb_data_path=Path(rgb_path_str) if rgb_path_str else None,
                        multispec_data_path=Path(multispec_path_str) if multispec_path_str else None,
                        sunsens=(sunsens_str in ['true', 'yes', '1']),
                        row_number=row_num
                    )
                    
                    # Validate the project
                    project = validate_project(project)
                    projects.append(project)
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: Error processing row - {str(e)}")
        
    except Exception as e:
        errors.append(f"Error reading CSV file: {str(e)}")
    
    return projects, errors

# ============================================================================
# Logging Setup
# ============================================================================

def setup_main_logger() -> logging.Logger:
    """Set up the main script logger"""
    logger = logging.getLogger('EnhancedProcessor')
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

def setup_project_logger(project: ProjectData) -> logging.Logger:
    """Set up a logger for a specific project"""
    project_dir = project.project_path.parent
    logs_dir = project_dir / 'logs' / 'consolelog'
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    log_file_name = f"consolelog_{project.site}_{project.date}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file_path = logs_dir / log_file_name
    
    logger = logging.getLogger(f"project_{project.site}_{project.date}_{project.row_number}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # Clear any existing handlers
    
    file_handler = logging.FileHandler(str(log_file_path), mode='w')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    
    return logger

# ============================================================================
# Processing Functions
# ============================================================================

def build_processing_command(project: ProjectData, crs: str, smooth: str, test_mode: bool) -> List[str]:
    """Build the command to execute for processing a project"""
    cmd = [
        METASHAPE_PYTHON_PATH,
        TARGET_SCRIPT_PATH,
        "-proj_path", str(project.project_path),
        "-date", project.date,
        "-site", project.site,
        "-crs", crs,
        "-smooth", smooth
    ]
    
    # Add RGB path if available
    if project.rgb_data_path and project.rgb_exists:
        cmd.extend(["-rgb", str(project.rgb_data_path)])
    
    # Add multispec path if available
    if project.multispec_data_path and project.multispec_exists:
        cmd.extend(["-multispec", str(project.multispec_data_path)])
    
    # Add sun sensor flag
    if project.sunsens:
        cmd.append("-sunsens")
    
    # Add test flag
    if test_mode:
        cmd.append("-test")
    
    return cmd

def monitor_subprocess(process, project_logger, timeout_seconds: int) -> Tuple[bool, Dict[str, str]]:
    """
    Monitor subprocess execution with timeout.
    Returns: (timed_out: bool, output_paths: dict)
    """
    output_paths = {}
    last_output_time = time.time()
    timed_out = False
    
    def update_last_output_time():
        nonlocal last_output_time
        last_output_time = time.time()
    
    def read_stdout():
        for line in process.stdout:
            print(line, end='')
            project_logger.info(line.strip())
            update_last_output_time()
            
            # Capture output paths
            if line.startswith('OUTPUT_ORTHO_RGB:'):
                output_paths['ortho_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_ORTHO_MS:'):
                output_paths['ortho_ms'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_RGB:'):
                output_paths['report_rgb'] = line.split(':', 1)[1].strip()
            elif line.startswith('OUTPUT_REPORT_MS:'):
                output_paths['report_ms'] = line.split(':', 1)[1].strip()
    
    def read_stderr():
        for line in process.stderr:
            print(line, end='', file=sys.stderr)
            project_logger.error(line.strip())
            update_last_output_time()
    
    # Start reader threads
    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    
    # Monitor for timeout
    while process.poll() is None:
        if time.time() - last_output_time > timeout_seconds:
            project_logger.error(f"Timeout reached ({timeout_seconds}s). Terminating process.")
            process.terminate()
            timed_out = True
            break
        time.sleep(1)
    
    # Wait for threads to finish
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    
    return timed_out, output_paths

def process_project(project: ProjectData, crs: str, smooth: str, test_mode: bool, timeout: int, logger: logging.Logger) -> Dict:
    """
    Process a single project.
    Returns: dict with processing results
    """
    result = {
        'site': project.site,
        'date': project.date,
        'success': False,
        'status': 'pending',
        'message': '',
        'output_paths': {}
    }
    
    project_logger = setup_project_logger(project)
    project_logger.info(f"Starting processing for {project.site} - {project.date}")
    project_logger.info(f"Project path: {project.project_path}")
    project_logger.info(f"RGB data: {project.rgb_exists}")
    project_logger.info(f"Multispec data: {project.multispec_exists}")
    
    # Build command
    cmd = build_processing_command(project, crs, smooth, test_mode)
    project_logger.info(f"Executing command: {' '.join(cmd)}")
    logger.info(f"  Command: {' '.join(cmd)}")
    
    try:
        # Execute processing
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        timed_out, output_paths = monitor_subprocess(process, project_logger, timeout)
        
        if timed_out:
            result['status'] = 'timeout'
            result['message'] = f'Processing timed out after {timeout} seconds'
            project_logger.error(result['message'])
            return result
        
        if process.returncode != 0:
            result['status'] = 'error'
            result['message'] = f'Processing failed with return code {process.returncode}'
            project_logger.error(result['message'])
            return result
        
        # Success
        result['success'] = True
        result['status'] = 'completed'
        result['message'] = 'Processing completed successfully'
        result['output_paths'] = output_paths
        project_logger.info(result['message'])
        
    except Exception as e:
        result['status'] = 'error'
        result['message'] = f'Exception during processing: {str(e)}'
        project_logger.error(result['message'])
        logger.error(f"  ERROR: {str(e)}")
    
    return result

# ============================================================================
# Reporting Functions
# ============================================================================

def print_validation_summary(projects: List[ProjectData], logger: logging.Logger):
    """Print a summary of validation results"""
    logger.info("\n" + "="*80)
    logger.info("VALIDATION SUMMARY")
    logger.info("="*80)
    
    total = len(projects)
    valid = sum(1 for p in projects if p.validation_status == ValidationStatus.VALID and not p.already_processed)
    already_processed = sum(1 for p in projects if p.already_processed)
    partial = sum(1 for p in projects if p.validation_status == ValidationStatus.PARTIAL)
    missing = sum(1 for p in projects if p.validation_status == ValidationStatus.MISSING)
    processable = sum(1 for p in projects if p.is_processable())
    
    logger.info(f"Total projects in CSV: {total}")
    logger.info(f"  [OK] Valid and ready: {valid}")
    logger.info(f"  [DONE] Already processed: {already_processed}")
    logger.info(f"  [!] Partial data: {partial}")
    logger.info(f"  [X] Missing/invalid: {missing}")
    logger.info(f"\n  => Processable now: {processable}")
    logger.info("="*80)
    
    # Show ready for processing projects
    ready_projects = [p for p in projects if p.validation_status == ValidationStatus.VALID and not p.already_processed and p.is_processable()]
    if ready_projects:
        logger.info(f"\n[OK] READY FOR PROCESSING ({len(ready_projects)} projects):")
        logger.info("-" * 80)
        for p in ready_projects:
            status_note = ""
            if p.missing_outputs:
                status_note = f" (incomplete: missing {', '.join(p.missing_outputs)})"
            logger.info(f"  - {p.site:30s} | {p.date}{status_note}")
    
    # Show already processed prFULLY PROCESSED - ALL OUTPUTS PRESENT
    processed_projects = [p for p in projects if p.already_processed]
    if processed_projects:
        logger.info(f"\n[DONE] ALREADY PROCESSED ({len(processed_projects)} projects):")
        logger.info("-" * 80)
        for p in processed_projects:
            logger.info(f"  - {p.site:30s} | {p.date}")
    
    # Show missing/problematic projects
    problem_projects = [p for p in projects if not p.is_processable() and not p.already_processed]
    if problem_projects:
        logger.info(f"\n[X] MISSING FILES / NOT PROCESSABLE ({len(problem_projects)} projects):")
        logger.info("-" * 80)
        for p in problem_projects:
            issues = []
            if not p.project_exists:
                issues.append("No .psx")
            if p.rgb_data_path and not p.rgb_exists:
                issues.append("No RGB data")
            if p.multispec_data_path and not p.multispec_exists:
                issues.append("No MS data")
            if not p.rgb_data_path and not p.multispec_data_path:
                issues.append("No data paths")
            if p.missing_outputs:
                issues.append(f"Incomplete: {', '.join(p.missing_outputs)}")
            
            issue_str = ", ".join(issues) if issues else "Unknown issue"
            logger.info(f"  - {p.site:30s} | {p.date:8s} | {issue_str}")

def print_project_details(projects: List[ProjectData], logger: logging.Logger, show_all: bool = False):
    """Print detailed information about each project (only if --show-all flag is used)"""
    if not show_all:
        return  # Skip detailed output unless explicitly requested
    
    logger.info("\n" + "="*80)
    logger.info("DETAILED PROJECT INFORMATION")
    logger.info("="*80)
    
    for project in projects:
        logger.info(f"\n[Row {project.row_number}] {project.site} - {project.date}")
        logger.info(f"  Status: {project.get_status_summary()}")
        logger.info(f"  Project: {project.project_path}")
        if project.rgb_data_path:
            logger.info(f"  RGB:     {project.rgb_data_path}")
        if project.multispec_data_path:
            logger.info(f"  MS:      {project.multispec_data_path}")
        
        if project.validation_messages:
            for msg in project.validation_messages:
                logger.info(f"  [!] {msg}")
        
        if not project.is_processable() and not project.already_processed:
            logger.info(f"  [!] NOT PROCESSABLE")
        elif project.already_processed:
            logger.info(f"  [DONE] Already processed")

def save_results_csv(projects: List[ProjectData], results: List[Dict], output_path: str):
    """Save processing results to CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'row_number', 'date', 'site', 'project_path',
            'rgb_data_path', 'multispec_data_path', 'sunsens',
            'validation_status', 'processing_status', 'message',
            'ortho_rgb', 'ortho_ms', 'report_rgb', 'report_ms'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Match results to projects
        result_dict = {f"{r['site']}_{r['date']}": r for r in results}
        
        for project in projects:
            key = f"{project.site}_{project.date}"
            result = result_dict.get(key, {})
            
            row = {
                'row_number': project.row_number,
                'date': project.date,
                'site': project.site,
                'project_path': str(project.project_path),
                'rgb_data_path': str(project.rgb_data_path) if project.rgb_data_path else '',
                'multispec_data_path': str(project.multispec_data_path) if project.multispec_data_path else '',
                'sunsens': project.sunsens,
                'validation_status': project.validation_status.value,
                'processing_status': result.get('status', 'not_processed'),
                'message': result.get('message', ''),
                'ortho_rgb': result.get('output_paths', {}).get('ortho_rgb', ''),
                'ortho_ms': result.get('output_paths', {}).get('ortho_ms', ''),
                'report_rgb': result.get('output_paths', {}).get('report_rgb', ''),
                'report_ms': result.get('output_paths', {}).get('report_ms', '')
            }
            
            writer.writerow(row)

# ============================================================================
# Main Processing
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced Upscale Processor with comprehensive validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python EnhancedUpscaleProcessor.py projects.csv
  python EnhancedUpscaleProcessor.py projects.csv --test
  python EnhancedUpscaleProcessor.py projects.csv --crs 7855 --timeout 7200
        """
    )
    
    parser.add_argument('csv_file', help='Path to CSV file with project information')
    parser.add_argument('--test', action='store_true', help='Test mode (dry-run, validation only)')
    parser.add_argument('--crs', default=DEFAULT_CRS, help=f'CRS EPSG code (default: {DEFAULT_CRS})')
    parser.add_argument('--smooth', choices=['low', 'medium', 'high'], default=DEFAULT_SMOOTH,
                       help=f'Smoothing strength for RGB model (default: {DEFAULT_SMOOTH})')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                       help=f'Timeout in seconds per project (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--skip-processed', action='store_true', default=True,
                       help='Skip projects that appear already processed (default: True)')
    parser.add_argument('--show-all', action='store_true',
                       help='Show all projects including already processed')
    
    args = parser.parse_args()
    
    # Setup logger
    logger = setup_main_logger()
    
    # Print header
    logger.info("="*80)
    logger.info("ENHANCED UPSCALE PROCESSOR")
    logger.info("="*80)
    logger.info(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"CSV File: {args.csv_file}")
    logger.info(f"Mode: {'TEST/DRY-RUN' if args.test else 'PRODUCTION'}")
    logger.info(f"CRS: EPSG:{args.crs}")
    logger.info(f"Smoothing: {args.smooth}")
    logger.info(f"Timeout: {args.timeout}s ({args.timeout/60:.1f} minutes)")
    logger.info("="*80)
    
    # Validate prerequisites
    logger.info("\nValidating prerequisites...")
    errors = []
    
    if not Path(METASHAPE_PYTHON_PATH).exists():
        errors.append(f"Metashape Python not found: {METASHAPE_PYTHON_PATH}")
    else:
        logger.info(f"  [OK] Metashape Python: {METASHAPE_PYTHON_PATH}")
    
    if not Path(TARGET_SCRIPT_PATH).exists():
        errors.append(f"Target script not found: {TARGET_SCRIPT_PATH}")
    else:
        logger.info(f"  [OK] Target script: {TARGET_SCRIPT_PATH}")
    
    if errors:
        logger.error("\nFATAL ERRORS:")
        for error in errors:
            logger.error(f"  [X] {error}")
        sys.exit(1)
    
    # Read and validate CSV
    logger.info("\nReading and validating CSV...")
    projects, csv_errors = read_and_validate_csv(args.csv_file)
    
    if csv_errors:
        logger.error("\nCSV ERRORS:")
        for error in csv_errors:
            logger.error(f"  [X] {error}")
        if not projects:
            sys.exit(1)
    
    logger.info(f"  [OK] Read {len(projects)} projects from CSV")
    
    # Print validation summary
    print_validation_summary(projects, logger)
    print_project_details(projects, logger, show_all=args.show_all)
    
    # Filter processable projects
    if args.skip_processed:
        to_process = [p for p in projects if p.is_processable()]
    else:
        to_process = [p for p in projects if p.project_exists and (p.rgb_exists or p.multispec_exists)]
    
    # Categorize projects by processing status
    unprocessed = [p for p in to_process if not p.missing_outputs or 
                   len(p.missing_outputs) >= 4]  # Missing most/all outputs
    incomplete = [p for p in to_process if p.missing_outputs and 
                  len(p.missing_outputs) < 4]  # Missing some outputs
    
    if not to_process:
        logger.warning("\n[!] No projects to process!")
        sys.exit(0)
    
    # Show processing options
    logger.info(f"\n{'='*80}")
    logger.info("PROCESSING OPTIONS")
    logger.info("="*80)
    logger.info(f"1. Process UNPROCESSED projects only ({len(unprocessed)} projects)")
    logger.info(f"   - Projects with no outputs or missing most outputs")
    if unprocessed:
        for p in unprocessed[:5]:  # Show first 5
            logger.info(f"     * {p.site} - {p.date}")
        if len(unprocessed) > 5:
            logger.info(f"     ... and {len(unprocessed)-5} more")
    
    logger.info(f"\n2. Process INCOMPLETE projects only ({len(incomplete)} projects)")
    logger.info(f"   - Projects missing some outputs (1-3 files)")
    if incomplete:
        for p in incomplete[:3]:  # Show first 3 incomplete
            missing_str = ', '.join(p.missing_outputs[:2])  # Show first 2 missing items
            logger.info(f"     * {p.site} - {p.date} (missing: {missing_str})")
        if len(incomplete) > 3:
            logger.info(f"     ... and {len(incomplete)-3} more")
    
    logger.info(f"\n3. Process ALL not fully processed ({len(to_process)} projects)")
    logger.info(f"   - Both unprocessed ({len(unprocessed)}) + incomplete ({len(incomplete)})")
    
    logger.info(f"\n4. Cancel")
    logger.info("="*80)
    
    # Confirm processing
    logger.info(f"\n{'='*80}")
    if args.test:
        logger.info("TEST MODE: No actual processing will occur")
        logger.info(f"Would process {len(to_process)} projects")
    else:
        # Get user choice for what to process
        while True:
            choice = input("\nSelect processing option (1-4): ").strip()
            if choice == "1":
                to_process = unprocessed
                logger.info(f"\nSelected: Process {len(to_process)} UNPROCESSED projects")
                break
            elif choice == "2":
                to_process = incomplete
                logger.info(f"\nSelected: Process {len(to_process)} INCOMPLETE projects")
                break
            elif choice == "3":
                # to_process already contains all not fully processed
                logger.info(f"\nSelected: Process ALL {len(to_process)} not fully processed projects")
                break
            elif choice == "4":
                logger.info("Processing cancelled by user")
                sys.exit(0)
            else:
                logger.warning("Invalid choice. Please enter 1, 2, 3, or 4.")
        
        if not to_process:
            logger.warning("\n[!] No projects selected for processing!")
            sys.exit(0)
        
        logger.info(f"Ready to process {len(to_process)} projects")
        logger.info(f"Estimated time: {len(to_process) * args.timeout / 3600:.1f} hours (max)")
        
        confirm = input("\n[!] Continue with processing? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            logger.info("Processing cancelled by user")
            sys.exit(0)
    
    # Process projects
    logger.info(f"\n{'='*80}")
    logger.info("STARTING PROCESSING")
    logger.info("="*80)
    
    results = []
    start_time = time.time()
    
    for idx, project in enumerate(to_process, 1):
        logger.info(f"\n[{idx}/{len(to_process)}] Processing: {project.site} - {project.date}")
        logger.info(f"  Row {project.row_number} in CSV")
        
        if args.test:
            # Test mode - just validate
            result = {
                'site': project.site,
                'date': project.date,
                'success': True,
                'status': 'test_validated',
                'message': 'Test mode - validation passed',
                'output_paths': {}
            }
            logger.info(f"  [OK] Test mode - validation passed")
        else:
            # Real processing
            result = process_project(project, args.crs, args.smooth, args.test, args.timeout, logger)
            
            if result['success']:
                logger.info(f"  [OK] Completed successfully")
            else:
                logger.error(f"  [X] Failed: {result['message']}")
        
        results.append(result)
    
    # Summary
    elapsed_time = time.time() - start_time
    logger.info(f"\n{'='*80}")
    logger.info("PROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"Total time: {elapsed_time/3600:.2f} hours")
    logger.info(f"Projects processed: {len(results)}")
    
    if not args.test:
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        logger.info(f"  [OK] Successful: {successful}")
        logger.info(f"  [X] Failed: {failed}")
        
        # Save results
        output_csv = Path(args.csv_file).parent / f"processing_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_results_csv(projects, results, str(output_csv))
        logger.info(f"\n📊 Results saved to: {output_csv}")
    
    logger.info("="*80)

if __name__ == "__main__":
    main()
