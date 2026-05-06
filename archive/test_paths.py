"""
Quick test of path checking functionality
"""
import csv
from pathlib import Path

csv_path = "corrected_paths.csv"

print(f"Checking CSV file: {csv_path}")
print(f"File exists: {Path(csv_path).exists()}")

try:
    with open(csv_path, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        for i, row in enumerate(reader):
            if i >= 3:  # Only check first 3 rows
                break
                
            print(f"\nRow {i+1}:")
            print(f"  Site: {row['site']}")
            print(f"  Date: {row['date']}")
            
            # Check key paths
            project_path = Path(row['project_path'])
            rgb_path = Path(row['rgb'])
            multispec_path = Path(row['multispec'])
            
            print(f"  Project exists: {project_path.exists()}")
            print(f"  RGB exists: {rgb_path.exists()}")
            print(f"  Multispec exists: {multispec_path.exists()}")
            
            # Check if corrected
            original_rgb = row.get('original_rgb', row['rgb'])
            original_multispec = row.get('original_multispec', row['multispec'])
            
            rgb_corrected = str(rgb_path) != original_rgb
            multispec_corrected = str(multispec_path) != original_multispec
            
            print(f"  RGB corrected: {rgb_corrected}")
            print(f"  Multispec corrected: {multispec_corrected}")
            
            if rgb_corrected:
                print(f"    Original RGB: {original_rgb}")
                print(f"    Corrected RGB: {rgb_path}")
                
            if multispec_corrected:
                print(f"    Original Multispec: {original_multispec}")
                print(f"    Corrected Multispec: {multispec_path}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
