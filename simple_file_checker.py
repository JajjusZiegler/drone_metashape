#!/usr/bin/env python3
"""
Simple Drone Processing File Checker

This script provides a quick overview of exported files for drone processing:
- Orthophotos (.tif format) - RGB and Multispectral
- Processing reports (.pdf format) - RGB and Multispectral  
- 3D models (.obj format)

Shows which sites/dates need additional work.

Author: File Checker Tool
Date: 2025-01-01
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, namedtuple
import re

# Simple data structure for results
FileStatus = namedtuple('FileStatus', [
    'site', 'date', 'project_path', 'exports_path',
    'rgb_ortho', 'multispec_ortho', 'rgb_report', 
    'multispec_report', 'obj_model', 'total_files',
    'completion_percent', 'status', 'needs_work'
])

class SimpleDroneChecker:
    """Simple checker for essential drone processing files"""
    
    def __init__(self, base_directory):
        self.base_dir = Path(base_directory)
        if not self.base_dir.exists():
            raise ValueError(f"Directory does not exist: {base_directory}")
        
        print(f"Checking directory: {self.base_dir}")
        
    def find_exports_directory(self, project_path):
        """Find the exports directory in a project"""
        possible_exports = [
            project_path / "exports",
            project_path / "Exports", 
            project_path / "export",
            project_path / "Export",
            project_path / "level1_proc"
        ]
        
        for exports_dir in possible_exports:
            if exports_dir.exists() and exports_dir.is_dir():
                return exports_dir
        
        # Search for exports directories recursively
        for item in project_path.rglob("*"):
            if item.is_dir() and "export" in item.name.lower():
                return item
                
        return None
    
    def check_for_files(self, exports_dir, patterns):
        """Check if any files matching the patterns exist"""
        if not exports_dir or not exports_dir.exists():
            return False
            
        for pattern in patterns:
            matches = list(exports_dir.glob(pattern))
            if matches:
                return True
            # Also check subdirectories
            matches = list(exports_dir.glob(f"**/{pattern}"))
            if matches:
                return True
        return False
    
    def scan_all_sites(self):
        """Scan all sites and dates"""
        print("\nScanning for sites and dates...")
        
        all_results = []
        
        # Find all site directories
        for site_dir in self.base_dir.iterdir():
            if not site_dir.is_dir() or site_dir.name.startswith('.'):
                continue
                
            site_name = site_dir.name
            print(f"\n📁 Site: {site_name}")
            
            # Find all date directories in the site
            date_dirs = []
            for item in site_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # Check if it looks like a date (YYYYMMDD format)
                    if re.match(r'\d{4}[-_]?\d{2}[-_]?\d{2}', item.name):
                        date_dirs.append(item)
            
            if not date_dirs:
                print(f"  ⚠️  No date directories found")
                continue
                
            # Sort date directories
            date_dirs.sort(key=lambda x: x.name)
            
            for date_dir in date_dirs:
                date_name = date_dir.name
                # Normalize date format
                date_match = re.match(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', date_name)
                if date_match:
                    normalized_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}"
                else:
                    normalized_date = date_name
                
                result = self.check_site_date(site_name, normalized_date, date_dir)
                all_results.append(result)
                
                # Print quick status
                status_icon = "✅" if result.completion_percent >= 80 else "⚠️" if result.completion_percent >= 50 else "❌"
                print(f"  {status_icon} {date_name}: {result.completion_percent:.0f}% complete - {result.status}")
        
        return all_results
    
    def check_site_date(self, site, date, project_path):
        """Check files for a specific site and date"""
        # Find exports directory
        exports_dir = self.find_exports_directory(project_path)
        
        if not exports_dir:
            return FileStatus(
                site=site, date=date, project_path=str(project_path), 
                exports_path="NOT FOUND", rgb_ortho=False, multispec_ortho=False,
                rgb_report=False, multispec_report=False, obj_model=False, 
                total_files=0, completion_percent=0, status="NO EXPORTS FOLDER",
                needs_work=True
            )
        
        # Check for specific file types
        # RGB Orthophoto (.tif)
        rgb_ortho_patterns = ["*rgb*ortho*.tif", "*ortho*rgb*.tif", "*_rgb_*.tif"]
        rgb_ortho = self.check_for_files(exports_dir, rgb_ortho_patterns)
        
        # Multispectral Orthophoto (.tif)  
        multispec_ortho_patterns = ["*multispec*ortho*.tif", "*ortho*multispec*.tif", "*_multispec_*.tif"]
        multispec_ortho = self.check_for_files(exports_dir, multispec_ortho_patterns)
        
        # RGB Report (.pdf)
        rgb_report_patterns = ["*rgb*report*.pdf", "*_rgb_*.pdf"]
        rgb_report = self.check_for_files(exports_dir, rgb_report_patterns)
        
        # Multispectral Report (.pdf)
        multispec_report_patterns = ["*multispec*report*.pdf", "*_multispec_*.pdf"]
        multispec_report = self.check_for_files(exports_dir, multispec_report_patterns)
        
        # 3D Model (.obj)
        obj_patterns = ["*.obj"]
        obj_model = self.check_for_files(exports_dir, obj_patterns)
        
        # Count total files in exports
        total_files = 0
        try:
            total_files = len([f for f in exports_dir.rglob("*") if f.is_file()])
        except:
            total_files = 0
        
        # Calculate completion percentage
        required_files = [rgb_ortho, multispec_ortho, rgb_report, multispec_report, obj_model]
        completion_percent = (sum(required_files) / len(required_files)) * 100
        
        # Determine status
        if completion_percent >= 90:
            status = "COMPLETE ✅"
            needs_work = False
        elif completion_percent >= 70:
            status = "MOSTLY DONE"
            needs_work = False
        elif completion_percent >= 40:
            status = "PARTIAL"
            needs_work = True
        else:
            status = "INCOMPLETE"
            needs_work = True
        
        return FileStatus(
            site=site, date=date, project_path=str(project_path),
            exports_path=str(exports_dir), rgb_ortho=rgb_ortho, 
            multispec_ortho=multispec_ortho, rgb_report=rgb_report,
            multispec_report=multispec_report, obj_model=obj_model,
            total_files=total_files, completion_percent=completion_percent,
            status=status, needs_work=needs_work
        )
    
    def print_summary_report(self, results):
        """Print a summary report to console"""
        if not results:
            print("\n❌ No results found!")
            return
        
        print("\n" + "="*80)
        print("📊 DRONE PROCESSING FILE CHECK SUMMARY")
        print("="*80)
        print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Base Directory: {self.base_dir}")
        print(f"🔍 Total Sites/Dates Checked: {len(results)}")
        
        # Overall statistics
        complete = [r for r in results if r.completion_percent >= 90]
        mostly_done = [r for r in results if 70 <= r.completion_percent < 90]
        partial = [r for r in results if 40 <= r.completion_percent < 70]
        incomplete = [r for r in results if r.completion_percent < 40]
        
        print(f"\n📈 COMPLETION STATUS:")
        print(f"   ✅ Complete (≥90%):     {len(complete):3d} ({len(complete)/len(results)*100:.1f}%)")
        print(f"   🟡 Mostly Done (70-89%): {len(mostly_done):3d} ({len(mostly_done)/len(results)*100:.1f}%)")
        print(f"   🟠 Partial (40-69%):     {len(partial):3d} ({len(partial)/len(results)*100:.1f}%)")
        print(f"   ❌ Incomplete (<40%):    {len(incomplete):3d} ({len(incomplete)/len(results)*100:.1f}%)")
        
        # File type statistics
        rgb_ortho_count = sum(1 for r in results if r.rgb_ortho)
        multispec_ortho_count = sum(1 for r in results if r.multispec_ortho)
        rgb_report_count = sum(1 for r in results if r.rgb_report)
        multispec_report_count = sum(1 for r in results if r.multispec_report)
        obj_model_count = sum(1 for r in results if r.obj_model)
        
        print(f"\n📄 FILE AVAILABILITY:")
        print(f"   RGB Orthophotos:      {rgb_ortho_count:3d}/{len(results)} ({rgb_ortho_count/len(results)*100:.1f}%)")
        print(f"   Multispec Orthophotos: {multispec_ortho_count:3d}/{len(results)} ({multispec_ortho_count/len(results)*100:.1f}%)")
        print(f"   RGB Reports:          {rgb_report_count:3d}/{len(results)} ({rgb_report_count/len(results)*100:.1f}%)")
        print(f"   Multispec Reports:    {multispec_report_count:3d}/{len(results)} ({multispec_report_count/len(results)*100:.1f}%)")
        print(f"   3D Models (OBJ):      {obj_model_count:3d}/{len(results)} ({obj_model_count/len(results)*100:.1f}%)")
        
        # Sites needing work
        needs_work = [r for r in results if r.needs_work]
        if needs_work:
            print(f"\n⚠️  SITES NEEDING ATTENTION ({len(needs_work)} total):")
            print("-" * 80)
            
            # Group by site
            by_site = defaultdict(list)
            for result in needs_work:
                by_site[result.site].append(result)
            
            for site, site_results in sorted(by_site.items()):
                site_results.sort(key=lambda x: x.date)
                print(f"\n🏗️  Site: {site}")
                
                for result in site_results:
                    missing = []
                    if not result.rgb_ortho:
                        missing.append("RGB Ortho")
                    if not result.multispec_ortho:
                        missing.append("MS Ortho")
                    if not result.rgb_report:
                        missing.append("RGB Report")
                    if not result.multispec_report:
                        missing.append("MS Report")
                    if not result.obj_model:
                        missing.append("3D Model")
                    
                    missing_str = ", ".join(missing) if missing else "All files present"
                    print(f"   📅 {result.date}: {result.completion_percent:.0f}% - Missing: {missing_str}")
        else:
            print(f"\n✅ All sites are complete or mostly complete!")
        
        print("\n" + "="*80)
    
    def save_csv_report(self, results, filename):
        """Save results to CSV file"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            # Write header
            f.write("Site,Date,Status,Completion%,RGB_Ortho,Multispec_Ortho,RGB_Report,Multispec_Report,OBJ_Model,Total_Files,Project_Path,Exports_Path,Needs_Work\n")
            
            # Write data
            for r in results:
                f.write(f"{r.site},{r.date},{r.status},{r.completion_percent:.1f},"
                       f"{'Yes' if r.rgb_ortho else 'No'},"
                       f"{'Yes' if r.multispec_ortho else 'No'},"
                       f"{'Yes' if r.rgb_report else 'No'},"
                       f"{'Yes' if r.multispec_report else 'No'},"
                       f"{'Yes' if r.obj_model else 'No'},"
                       f"{r.total_files},{r.project_path},{r.exports_path},"
                       f"{'Yes' if r.needs_work else 'No'}\n")
        
        print(f"\n💾 Results saved to: {filename}")


def main():
    """Main function"""
    print("🚁 Simple Drone Processing File Checker")
    print("=" * 50)
    
    # Get base directory
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        # Try default locations
        default_dirs = [
            r"E:\Share",
            r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\Upscale_Metashapeprojects",
            r"D:\Share",
            r"F:\Share"
        ]
        
        base_dir = None
        for test_dir in default_dirs:
            if Path(test_dir).exists():
                base_dir = test_dir
                print(f"📁 Found directory: {base_dir}")
                break
        
        if not base_dir:
            base_dir = input("📂 Enter base directory containing site folders: ").strip().strip('"')
    
    try:
        # Initialize checker and run
        checker = SimpleDroneChecker(base_dir)
        results = checker.scan_all_sites()
        
        # Print summary
        checker.print_summary_report(results)
        
        # Save CSV report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"drone_file_check_{timestamp}.csv"
        checker.save_csv_report(results, csv_filename)
        
        # Final message
        needs_attention = sum(1 for r in results if r.needs_work)
        if needs_attention == 0:
            print(f"\n🎉 SUCCESS: All {len(results)} site/date combinations are complete!")
        else:
            print(f"\n⚠️  ATTENTION NEEDED: {needs_attention}/{len(results)} site/date combinations need work")
            print("   See detailed list above for what files are missing.")
        
        print(f"\n📊 Open {csv_filename} in Excel for detailed analysis")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
