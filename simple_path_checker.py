"""
Simple Project Path Checker

This script checks if project files exist and if the expected RGB/Multispec paths exist.
Does not require Metashape - just checks file system paths.

Usage: python simple_path_checker.py corrected_paths.csv
"""

import csv
import sys
from pathlib import Path

def check_paths(csv_path):
    """Check paths from corrected CSV file."""
    
    results = []
    
    print(f"Checking paths from: {csv_path}")
    print("="*80)
    
    with open(csv_path, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        for row_num, row in enumerate(reader, 1):
            site = row['site']
            date = row['date']
            project_path = Path(row['project_path'])
            rgb_path = Path(row['rgb'])
            multispec_path = Path(row['multispec'])
            original_rgb = row.get('original_rgb', row['rgb'])
            original_multispec = row.get('original_multispec', row['multispec'])
            
            # Check if paths exist
            project_exists = project_path.exists()
            rgb_exists = rgb_path.exists()
            multispec_exists = multispec_path.exists()
            
            # Check if paths were corrected
            rgb_corrected = str(rgb_path) != original_rgb
            multispec_corrected = str(multispec_path) != original_multispec
            
            # Determine if this project might have issues
            potentially_problematic = False
            issues = []
            
            if not project_exists:
                issues.append("PROJECT_MISSING")
            else:
                if rgb_corrected:
                    issues.append("RGB_PATH_CORRECTED")
                    potentially_problematic = True
                if multispec_corrected:
                    issues.append("MULTISPEC_PATH_CORRECTED") 
                    potentially_problematic = True
            
            if not rgb_exists:
                issues.append("RGB_PATH_NOT_FOUND")
            if not multispec_exists:
                issues.append("MULTISPEC_PATH_NOT_FOUND")
            
            status = "NEEDS_INVESTIGATION" if potentially_problematic and project_exists else "OK"
            if not project_exists:
                status = "PROJECT_MISSING"
            elif not rgb_exists or not multispec_exists:
                status = "PATHS_MISSING"
            
            result = {
                'row': row_num,
                'site': site,
                'date': date,
                'status': status,
                'project_exists': project_exists,
                'rgb_exists': rgb_exists,
                'multispec_exists': multispec_exists,
                'rgb_corrected': rgb_corrected,
                'multispec_corrected': multispec_corrected,
                'issues': "|".join(issues),
                'project_path': str(project_path),
                'rgb_path': str(rgb_path),
                'multispec_path': str(multispec_path),
                'original_rgb': original_rgb,
                'original_multispec': original_multispec
            }
            
            results.append(result)
            
            # Print summary for each row
            status_symbol = "❌" if potentially_problematic else "✅"
            if not project_exists:
                status_symbol = "🚫"
            elif not rgb_exists or not multispec_exists:
                status_symbol = "⚠️"
                
            print(f"{status_symbol} Row {row_num:2d}: {site:<25} {date} - {status}")
            if issues:
                print(f"    Issues: {', '.join(issues)}")
            if rgb_corrected:
                print(f"    RGB:    {original_rgb}")
                print(f"         -> {rgb_path}")
            if multispec_corrected:
                print(f"    Multi:  {original_multispec}")
                print(f"         -> {multispec_path}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    project_missing = sum(1 for r in results if not r['project_exists'])
    needs_investigation = sum(1 for r in results if r['status'] == 'NEEDS_INVESTIGATION')
    paths_missing = sum(1 for r in results if r['status'] == 'PATHS_MISSING')
    ok = sum(1 for r in results if r['status'] == 'OK')
    
    print(f"Total projects: {total}")
    print(f"OK (no path corrections): {ok}")
    print(f"Needs investigation (existing projects with corrected paths): {needs_investigation}")
    print(f"Missing expected paths: {paths_missing}")
    print(f"Project files missing: {project_missing}")
    
    # Write detailed report
    output_file = "path_check_report.csv"
    fieldnames = [
        'row', 'site', 'date', 'status', 'project_exists', 'rgb_exists', 'multispec_exists',
        'rgb_corrected', 'multispec_corrected', 'issues', 'project_path', 'rgb_path', 
        'multispec_path', 'original_rgb', 'original_multispec'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\nDetailed report saved to: {output_file}")
    
    # Show projects that likely need rebuilding
    problem_projects = [r for r in results if r['status'] == 'NEEDS_INVESTIGATION']
    if problem_projects:
        print(f"\nProjects that likely need rebuilding ({len(problem_projects)}):")
        for r in problem_projects:
            print(f"  - {r['site']} / {r['date']}")
            if r['rgb_corrected']:
                print(f"    RGB path was corrected")
            if r['multispec_corrected']:
                print(f"    Multispec path was corrected")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python simple_path_checker.py corrected_paths.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    results = check_paths(csv_path)
