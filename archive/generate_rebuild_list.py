#!/usr/bin/env python3
"""
Generate rebuild list for projects with path corrections
"""
import pandas as pd
import os
from pathlib import Path

def generate_rebuild_list():
    """Generate CSV with only projects that need rebuilding"""
    
    # Read the corrected CSV
    corrected_csv = "metashape_input_corrected.csv"
    
    if not os.path.exists(corrected_csv):
        print(f"❌ Error: {corrected_csv} not found!")
        print("Please run fix_project_paths.py first to generate the corrected CSV")
        return
    
    df = pd.read_csv(corrected_csv)
    
    # Define problematic sites that had path corrections
    problematic_sites = {
        "Wangen Brüttisellen": "wangen_zh folder mismatch",
        "Sanasilva-50845": "folder name dash/underscore mismatch", 
        "Sanasilva-50877": "folder name dash/underscore mismatch",
        "LWF-Davos": "folder name dash/underscore mismatch",
        "Martelloskop": "folder name spelling difference",
        "Stillberg": "case sensitivity mismatch"
    }
    
    # Filter for problematic projects
    problematic_df = df[df['site'].isin(problematic_sites.keys())].copy()
    
    # Add status column
    problematic_df['rebuild_reason'] = problematic_df['site'].map(problematic_sites)
    problematic_df['status'] = 'needs_rebuild'
    
    # Save rebuild list
    rebuild_csv = "projects_to_rebuild.csv"
    problematic_df.to_csv(rebuild_csv, index=False)
    
    print(f"✅ Generated rebuild list: {rebuild_csv}")
    print(f"📊 Found {len(problematic_df)} projects that need rebuilding:")
    print()
    
    # Summary by site
    summary = problematic_df.groupby('site').size().sort_values(ascending=False)
    for site, count in summary.items():
        print(f"  • {site}: {count} projects ({problematic_sites[site]})")
    
    print(f"\n📈 Total: {len(problematic_df)} out of {len(df)} projects ({len(problematic_df)/len(df)*100:.1f}%)")
    
    # Show some examples
    print("\n🔍 Sample problematic projects:")
    for i, row in problematic_df.head(3).iterrows():
        print(f"  • {row['date']} - {row['site']}")
        print(f"    RGB: {row['rgb']}")
        print(f"    Multispec: {row['multispec']}")
        print(f"    Project: {row['project_path']}")
        print(f"    Issue: {row['rebuild_reason']}")
        print()
    
    return rebuild_csv

if __name__ == "__main__":
    generate_rebuild_list()
