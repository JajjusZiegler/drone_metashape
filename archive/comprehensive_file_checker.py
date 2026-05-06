#!/usr/bin/env python3
"""
Comprehensive File Checker for Drone Metashape Processing

This script checks all sites and dates for expected export files from drone processing:
- Orthophotos (.tif format)
- Processing reports (RGB and multispectral .pdf)
- 3D models (.obj files)
- Reference files and status markers

Author: Automated Tool
Date: 2025-01-01
"""

import os
import sys
import re
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import argparse

# Try to import pandas for enhanced reporting
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not available. Using basic reporting.")

# Try to import humanize for file sizes
try:
    import humanize
    HAS_HUMANIZE = True
except ImportError:
    HAS_HUMANIZE = False
    print("Warning: humanize not available. Using basic file size formatting.")


@dataclass
class FileCheckResult:
    """Data class to store file check results"""
    site: str
    date: str
    project_dir: Optional[Path] = None
    exports_dir: Optional[Path] = None
    references_dir: Optional[Path] = None
    
    # Expected files
    rgb_ortho_tif: bool = False
    multispec_ortho_tif: bool = False
    rgb_dem_tif: bool = False
    obj_model: bool = False
    rgb_report_pdf: bool = False
    multispec_report_pdf: bool = False
    
    # Additional useful files
    has_reference_markers: bool = False
    has_interpolated_positions: bool = False
    
    # Summary statistics
    total_tif_files: int = 0
    total_pdf_files: int = 0
    total_obj_files: int = 0
    total_files: int = 0
    total_size_bytes: int = 0
    
    # Completion status
    completion_score: float = 0.0
    status: str = "Unknown"
    issues: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class DroneFileChecker:
    """Main class for checking drone processing files"""
    
    def __init__(self, base_directory: str):
        """
        Initialize the file checker
        
        Args:
            base_directory: Base directory containing all site folders
        """
        self.base_dir = Path(base_directory)
        if not self.base_dir.exists():
            raise ValueError(f"Base directory does not exist: {base_directory}")
        
        # Expected file patterns based on the processing scripts
        self.expected_patterns = {
            'rgb_ortho': [
                '*_rgb_ortho_*.tif',
                '*rgb*ortho*.tif',
                '*ortho*rgb*.tif'
            ],
            'multispec_ortho': [
                '*_multispec_ortho_*.tif',
                '*multispec*ortho*.tif',
                '*ortho*multispec*.tif'
            ],
            'rgb_dem': [
                '*_rgb_dem_*.tif',
                '*_dem_*.tif',
                '*dem*.tif'
            ],
            'obj_model': [
                '*.obj',
                '*_rgb_*.obj',
                '*model*.obj'
            ],
            'rgb_report': [
                '*_rgb_report.pdf',
                '*rgb*report*.pdf'
            ],
            'multispec_report': [
                '*_multispec_report.pdf',
                '*multispec*report*.pdf'
            ]
        }
        
        # Reference file patterns
        self.reference_patterns = [
            'RGBanalyzeImageDone.txt',
            'RGBAlignmentDone.txt',
            'MultiAnalyzeImageDone.txt',
            'MultiAlignmenteDone.txt',
            'MultiCalibrated.txt',
            'interpolated_micasense_pos*.csv',
            'p1_pos_*.csv'
        ]
    
    def scan_for_sites_and_dates(self) -> Dict[str, List[str]]:
        """
        Scan base directory for sites and dates
        
        Returns:
            Dictionary mapping site names to lists of dates
        """
        sites_dates = defaultdict(set)
        
        print(f"Scanning directory: {self.base_dir}")
        
        # Look for site directories
        for site_path in self.base_dir.iterdir():
            if not site_path.is_dir() or site_path.name.startswith('.'):
                continue
                
            site_name = site_path.name
            print(f"  Found site: {site_name}")
            
            # Look for date directories within site
            for date_path in site_path.iterdir():
                if not date_path.is_dir() or date_path.name.startswith('.'):
                    continue
                
                # Check if directory name looks like a date (YYYYMMDD or YYYY-MM-DD)
                date_match = re.match(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', date_path.name)
                if date_match:
                    # Normalize date format to YYYYMMDD
                    date_str = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}"
                    sites_dates[site_name].add(date_str)
                    print(f"    Found date: {date_str}")
        
        # Convert sets to sorted lists
        result = {}
        for site, dates in sites_dates.items():
            result[site] = sorted(list(dates))
        
        return result
    
    def find_project_directories(self, site: str, date: str) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """
        Find project, exports, and references directories for a site/date
        
        Args:
            site: Site name
            date: Date string (YYYYMMDD)
            
        Returns:
            Tuple of (project_dir, exports_dir, references_dir)
        """
        # Look for project directory
        possible_paths = [
            self.base_dir / site / date,
            self.base_dir / site / f"{date[:4]}-{date[4:6]}-{date[6:8]}",
            self.base_dir / site / f"{date[:4]}_{date[4:6]}_{date[6:8]}"
        ]
        
        project_dir = None
        for path in possible_paths:
            if path.exists() and path.is_dir():
                project_dir = path
                break
        
        if not project_dir:
            return None, None, None
        
        # Find exports directory
        exports_dir = None
        for pattern in ['exports', 'Exports', 'export', 'Export', 'level1_proc']:
            test_dir = project_dir / pattern
            if test_dir.exists() and test_dir.is_dir():
                exports_dir = test_dir
                break
        
        # If not found directly, search recursively
        if not exports_dir:
            for item in project_dir.rglob('*'):
                if item.is_dir() and any(pat.lower() in item.name.lower() for pat in ['export', 'level1']):
                    exports_dir = item
                    break
        
        # Find references directory
        references_dir = None
        for pattern in ['references', 'References', 'reference', 'Reference']:
            test_dir = project_dir / pattern
            if test_dir.exists() and test_dir.is_dir():
                references_dir = test_dir
                break
        
        return project_dir, exports_dir, references_dir
    
    def check_files_in_directory(self, directory: Path, patterns: List[str]) -> List[Path]:
        """
        Check for files matching patterns in a directory
        
        Args:
            directory: Directory to search
            patterns: List of glob patterns to match
            
        Returns:
            List of matching file paths
        """
        if not directory or not directory.exists():
            return []
        
        found_files = []
        for pattern in patterns:
            try:
                matches = list(directory.glob(pattern))
                found_files.extend(matches)
                # Also check subdirectories
                matches_recursive = list(directory.glob(f"**/{pattern}"))
                found_files.extend(matches_recursive)
            except Exception as e:
                print(f"    Warning: Error searching for pattern {pattern} in {directory}: {e}")
        
        # Remove duplicates while preserving order
        unique_files = []
        seen = set()
        for f in found_files:
            if str(f) not in seen:
                seen.add(str(f))
                unique_files.append(f)
        
        return unique_files
    
    def get_file_stats(self, directory: Path) -> Tuple[int, int]:
        """
        Get file count and total size for directory
        
        Args:
            directory: Directory to analyze
            
        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        if not directory or not directory.exists():
            return 0, 0
        
        file_count = 0
        total_size = 0
        
        try:
            for item in directory.rglob('*'):
                if item.is_file():
                    file_count += 1
                    try:
                        total_size += item.stat().st_size
                    except (OSError, PermissionError):
                        pass  # Skip files we can't access
        except Exception as e:
            print(f"    Warning: Error analyzing directory {directory}: {e}")
        
        return file_count, total_size
    
    def check_site_date(self, site: str, date: str) -> FileCheckResult:
        """
        Check files for a specific site and date
        
        Args:
            site: Site name
            date: Date string
            
        Returns:
            FileCheckResult object with analysis results
        """
        result = FileCheckResult(site=site, date=date)
        
        # Find directories
        project_dir, exports_dir, references_dir = self.find_project_directories(site, date)
        result.project_dir = project_dir
        result.exports_dir = exports_dir
        result.references_dir = references_dir
        
        if not project_dir:
            result.issues.append("Project directory not found")
            result.status = "PROJECT NOT FOUND"
            return result
        
        if not exports_dir:
            result.issues.append("Exports directory not found")
        
        if not references_dir:
            result.issues.append("References directory not found")
        
        # Check for expected export files
        if exports_dir:
            # RGB orthophoto
            rgb_ortho_files = self.check_files_in_directory(exports_dir, self.expected_patterns['rgb_ortho'])
            result.rgb_ortho_tif = len(rgb_ortho_files) > 0
            
            # Multispectral orthophoto
            multispec_ortho_files = self.check_files_in_directory(exports_dir, self.expected_patterns['multispec_ortho'])
            result.multispec_ortho_tif = len(multispec_ortho_files) > 0
            
            # RGB DEM
            rgb_dem_files = self.check_files_in_directory(exports_dir, self.expected_patterns['rgb_dem'])
            result.rgb_dem_tif = len(rgb_dem_files) > 0
            
            # 3D Model (OBJ)
            obj_files = self.check_files_in_directory(exports_dir, self.expected_patterns['obj_model'])
            result.obj_model = len(obj_files) > 0
            
            # RGB Report
            rgb_report_files = self.check_files_in_directory(exports_dir, self.expected_patterns['rgb_report'])
            result.rgb_report_pdf = len(rgb_report_files) > 0
            
            # Multispectral Report
            multispec_report_files = self.check_files_in_directory(exports_dir, self.expected_patterns['multispec_report'])
            result.multispec_report_pdf = len(multispec_report_files) > 0
            
            # Count file types
            all_tif_files = self.check_files_in_directory(exports_dir, ['*.tif', '*.tiff'])
            all_pdf_files = self.check_files_in_directory(exports_dir, ['*.pdf'])
            all_obj_files = self.check_files_in_directory(exports_dir, ['*.obj'])
            
            result.total_tif_files = len(all_tif_files)
            result.total_pdf_files = len(all_pdf_files)
            result.total_obj_files = len(all_obj_files)
            
            # Get directory statistics
            file_count, total_size = self.get_file_stats(exports_dir)
            result.total_files = file_count
            result.total_size_bytes = total_size
        
        # Check for reference files
        if references_dir:
            reference_files = self.check_files_in_directory(references_dir, self.reference_patterns)
            result.has_reference_markers = len(reference_files) > 0
            
            # Check for specific position files
            pos_files = self.check_files_in_directory(references_dir, ['interpolated_micasense_pos*.csv', '*_pos_*.csv'])
            result.has_interpolated_positions = len(pos_files) > 0
        
        # Calculate completion score
        expected_files = [
            result.rgb_ortho_tif,
            result.multispec_ortho_tif,
            result.rgb_report_pdf,
            result.multispec_report_pdf,
            result.obj_model
        ]
        
        completion_count = sum(expected_files)
        result.completion_score = (completion_count / len(expected_files)) * 100
        
        # Determine status
        if result.completion_score >= 95:
            result.status = "COMPLETE ✓"
        elif result.completion_score >= 75:
            result.status = "MOSTLY COMPLETE"
        elif result.completion_score >= 50:
            result.status = "PARTIALLY COMPLETE"
        elif result.completion_score >= 25:
            result.status = "INITIAL PROGRESS"
        else:
            result.status = "MINIMAL PROGRESS"
        
        # Add specific issues
        if not result.rgb_ortho_tif:
            result.issues.append("Missing RGB orthophoto")
        if not result.multispec_ortho_tif:
            result.issues.append("Missing multispectral orthophoto")
        if not result.rgb_report_pdf:
            result.issues.append("Missing RGB processing report")
        if not result.multispec_report_pdf:
            result.issues.append("Missing multispectral processing report")
        if not result.obj_model:
            result.issues.append("Missing 3D model (OBJ)")
        
        # Check for very small files (potential processing issues)
        if exports_dir and result.total_size_bytes < 100000:  # Less than 100KB
            result.issues.append(f"Very small total export size ({self.format_file_size(result.total_size_bytes)})")
        
        return result
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if HAS_HUMANIZE:
            return humanize.naturalsize(size_bytes)
        else:
            # Simple formatting
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def check_all_sites_and_dates(self) -> List[FileCheckResult]:
        """
        Check all sites and dates
        
        Returns:
            List of FileCheckResult objects
        """
        sites_dates = self.scan_for_sites_and_dates()
        
        if not sites_dates:
            print("No sites or dates found!")
            return []
        
        print(f"\nFound {len(sites_dates)} sites with dates")
        
        all_results = []
        total_combinations = sum(len(dates) for dates in sites_dates.values())
        
        print(f"Checking {total_combinations} site/date combinations...\n")
        
        current = 0
        for site, dates in sites_dates.items():
            print(f"Checking site: {site}")
            for date in dates:
                current += 1
                print(f"  [{current}/{total_combinations}] Checking {site}/{date}...")
                
                result = self.check_site_date(site, date)
                all_results.append(result)
                
                # Brief status report
                print(f"    Status: {result.status} ({result.completion_score:.1f}%)")
                if result.issues:
                    print(f"    Issues: {len(result.issues)} found")
        
        return all_results
    
    def generate_summary_report(self, results: List[FileCheckResult]) -> str:
        """
        Generate a text summary report
        
        Args:
            results: List of FileCheckResult objects
            
        Returns:
            Formatted summary report as string
        """
        if not results:
            return "No results to report."
        
        report = []
        report.append("=" * 80)
        report.append("COMPREHENSIVE DRONE FILE CHECKER REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Base Directory: {self.base_dir}")
        report.append(f"Total Site/Date Combinations Checked: {len(results)}")
        report.append("")
        
        # Overall statistics
        complete_count = sum(1 for r in results if r.completion_score >= 95)
        mostly_complete_count = sum(1 for r in results if 75 <= r.completion_score < 95)
        partial_count = sum(1 for r in results if 25 <= r.completion_score < 75)
        minimal_count = sum(1 for r in results if r.completion_score < 25)
        
        report.append("OVERALL SUMMARY:")
        report.append("-" * 40)
        report.append(f"Complete (≥95%):        {complete_count:3d} ({complete_count/len(results)*100:.1f}%)")
        report.append(f"Mostly Complete (75-94%): {mostly_complete_count:3d} ({mostly_complete_count/len(results)*100:.1f}%)")
        report.append(f"Partially Complete (25-74%): {partial_count:3d} ({partial_count/len(results)*100:.1f}%)")
        report.append(f"Minimal Progress (<25%): {minimal_count:3d} ({minimal_count/len(results)*100:.1f}%)")
        report.append("")
        
        # Average completion by site
        site_stats = defaultdict(list)
        for result in results:
            site_stats[result.site].append(result.completion_score)
        
        report.append("SITE-LEVEL SUMMARY:")
        report.append("-" * 40)
        report.append(f"{'Site':<20} {'Dates':<6} {'Avg Complete':<12} {'Status'}")
        report.append("-" * 60)
        
        for site, scores in sorted(site_stats.items()):
            avg_score = sum(scores) / len(scores)
            if avg_score >= 95:
                status = "COMPLETE ✓"
            elif avg_score >= 75:
                status = "MOSTLY COMPLETE"
            elif avg_score >= 50:
                status = "PARTIALLY COMPLETE"
            else:
                status = "NEEDS WORK"
            
            report.append(f"{site:<20} {len(scores):<6} {avg_score:>8.1f}%     {status}")
        
        report.append("")
        
        # Issues summary
        all_issues = []
        for result in results:
            all_issues.extend(result.issues)
        
        issue_counts = defaultdict(int)
        for issue in all_issues:
            issue_counts[issue] += 1
        
        if issue_counts:
            report.append("MOST COMMON ISSUES:")
            report.append("-" * 40)
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
                report.append(f"{count:3d}x  {issue}")
            report.append("")
        
        # Detailed results for problematic sites
        problematic_results = [r for r in results if r.completion_score < 75]
        if problematic_results:
            report.append("SITES NEEDING ATTENTION (< 75% complete):")
            report.append("-" * 40)
            
            for result in sorted(problematic_results, key=lambda x: x.completion_score):
                report.append(f"\n{result.site}/{result.date} - {result.status} ({result.completion_score:.1f}%)")
                report.append(f"  Project: {result.project_dir or 'NOT FOUND'}")
                report.append(f"  Exports: {result.exports_dir or 'NOT FOUND'}")
                
                # File status
                file_status = []
                if result.rgb_ortho_tif:
                    file_status.append("RGB Ortho ✓")
                else:
                    file_status.append("RGB Ortho ✗")
                
                if result.multispec_ortho_tif:
                    file_status.append("MS Ortho ✓")
                else:
                    file_status.append("MS Ortho ✗")
                
                if result.obj_model:
                    file_status.append("3D Model ✓")
                else:
                    file_status.append("3D Model ✗")
                
                if result.rgb_report_pdf:
                    file_status.append("RGB Report ✓")
                else:
                    file_status.append("RGB Report ✗")
                
                if result.multispec_report_pdf:
                    file_status.append("MS Report ✓")
                else:
                    file_status.append("MS Report ✗")
                
                report.append(f"  Files: {' | '.join(file_status)}")
                
                if result.issues:
                    report.append(f"  Issues: {'; '.join(result.issues)}")
        
        report.append("\n" + "=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def export_to_csv(self, results: List[FileCheckResult], output_file: str) -> None:
        """
        Export results to CSV file
        
        Args:
            results: List of FileCheckResult objects
            output_file: Output CSV file path
        """
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Site', 'Date', 'Status', 'Completion_Percent',
                'RGB_Ortho', 'Multispec_Ortho', 'RGB_DEM', 'OBJ_Model', 
                'RGB_Report', 'Multispec_Report', 'Reference_Markers', 
                'Position_Files', 'Total_TIF_Files', 'Total_PDF_Files', 
                'Total_OBJ_Files', 'Total_Files', 'Total_Size_MB', 
                'Project_Directory', 'Exports_Directory', 'Issues'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    'Site': result.site,
                    'Date': result.date,
                    'Status': result.status,
                    'Completion_Percent': f"{result.completion_score:.1f}",
                    'RGB_Ortho': 'Yes' if result.rgb_ortho_tif else 'No',
                    'Multispec_Ortho': 'Yes' if result.multispec_ortho_tif else 'No',
                    'RGB_DEM': 'Yes' if result.rgb_dem_tif else 'No',
                    'OBJ_Model': 'Yes' if result.obj_model else 'No',
                    'RGB_Report': 'Yes' if result.rgb_report_pdf else 'No',
                    'Multispec_Report': 'Yes' if result.multispec_report_pdf else 'No',
                    'Reference_Markers': 'Yes' if result.has_reference_markers else 'No',
                    'Position_Files': 'Yes' if result.has_interpolated_positions else 'No',
                    'Total_TIF_Files': result.total_tif_files,
                    'Total_PDF_Files': result.total_pdf_files,
                    'Total_OBJ_Files': result.total_obj_files,
                    'Total_Files': result.total_files,
                    'Total_Size_MB': f"{result.total_size_bytes / (1024*1024):.2f}",
                    'Project_Directory': str(result.project_dir) if result.project_dir else '',
                    'Exports_Directory': str(result.exports_dir) if result.exports_dir else '',
                    'Issues': '; '.join(result.issues) if result.issues else ''
                })
        
        print(f"Results exported to: {output_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Comprehensive File Checker for Drone Metashape Processing')
    parser.add_argument('base_directory', help='Base directory containing all site folders')
    parser.add_argument('--output-csv', help='Output CSV file for results')
    parser.add_argument('--output-txt', help='Output text file for summary report')
    parser.add_argument('--site', help='Check only specific site')
    parser.add_argument('--date', help='Check only specific date (YYYYMMDD)')
    
    args = parser.parse_args()
    
    try:
        # Initialize checker
        checker = DroneFileChecker(args.base_directory)
        
        # Check files
        if args.site and args.date:
            print(f"Checking specific site/date: {args.site}/{args.date}")
            result = checker.check_site_date(args.site, args.date)
            results = [result]
        else:
            print("Checking all sites and dates...")
            results = checker.check_all_sites_and_dates()
        
        if not results:
            print("No results found!")
            return
        
        # Generate summary report
        summary = checker.generate_summary_report(results)
        print("\n" + summary)
        
        # Save text report
        if args.output_txt:
            with open(args.output_txt, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"\nSummary report saved to: {args.output_txt}")
        else:
            # Default output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_txt = f"drone_file_check_report_{timestamp}.txt"
            with open(default_txt, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"\nSummary report saved to: {default_txt}")
        
        # Save CSV export
        if args.output_csv:
            checker.export_to_csv(results, args.output_csv)
        else:
            # Default output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_csv = f"drone_file_check_results_{timestamp}.csv"
            checker.export_to_csv(results, default_csv)
        
        # Final summary
        complete_count = sum(1 for r in results if r.completion_score >= 95)
        print(f"\n✓ SUMMARY: {complete_count}/{len(results)} site/date combinations are complete (≥95%)")
        
        needs_attention = [r for r in results if r.completion_score < 75]
        if needs_attention:
            print(f"⚠ WARNING: {len(needs_attention)} site/date combinations need attention (<75%)")
            print("See detailed report above for specific issues.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # If run without arguments, provide interactive mode
    if len(sys.argv) == 1:
        print("Comprehensive File Checker for Drone Metashape Processing")
        print("=" * 60)
        
        # Get base directory from user
        default_base = r"E:\Share"
        if not Path(default_base).exists():
            default_base = input("Enter base directory containing site folders: ").strip()
        else:
            user_input = input(f"Enter base directory (default: {default_base}): ").strip()
            if user_input:
                default_base = user_input
        
        # Create temporary args
        sys.argv = ['comprehensive_file_checker.py', default_base]
        
    main()
