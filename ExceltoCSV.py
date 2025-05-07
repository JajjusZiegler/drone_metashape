import pandas as pd
from pathlib import Path

# Constants
BASE_RGB = Path(r"M:/working_package_2/2024_dronecampaign/01_data/P1")
BASE_MULTISPEC = Path(r"M:/working_package_2/2024_dronecampaign/01_data/Micasense")
CRS_VALUE = 2056

SITE_MAPPING = {
    "Stillberg": {
        "image_site_name": "stillberg",
        "project_name_variants": ["Stillberg", "stillberg"]
    },
    "Pfynwald": {
        "image_site_name": "Pfynwald",
        "project_name_variants": ["Pfynwald", "Pfynwald_Project", "Pfynwald_Area"]
    },
    "Illgraben": {
        "image_site_name": "Illgraben",
        "project_name_variants": ["Illgraben", "Illgraben_Project"]
    },
    "lwf_davos": {
        "image_site_name": "lwf_davos",
        "project_name_variants": ["Davos_LWF", "DavosLWF", "lwf_davos"]
    },
    "lwf_isone": {
        "image_site_name": "lwf_isone",
        "project_name_variants": ["Isone_LWF", "IsoneLWF", "lwf_isone"]
    },
    "lwf_lens": {
        "image_site_name": "lwf_lens",
        "project_name_variants": ["Lens_LWF", "LensForest", "lwf_lens"]
    },
    "lwf_neunkirch": {
        "image_site_name": "lwf_neunkirch",
        "project_name_variants": ["Neunkirch_LWF", "NeunkirchLWF", "lwf_neunkirch"]
    },
    "lwf_schänis": {
        "image_site_name": "lwf_schänis",
        "project_name_variants": ["Schänis_LWF", "SchänisLWF", "lwf_schänis"]
    },
    "lwf_visp": {
        "image_site_name": "lwf_visp",
        "project_name_variants": ["Visp_LWF", "VISP_LWF", "lwf_visp"]
    },
    "marteloskop": {
        "image_site_name": "marteloskop",
        "project_name_variants": ["Marteloskop", "Martelloskop", "marteloskop"]
    },
    "sagno": {
        "image_site_name": "sagno",
        "project_name_variants": ["Sagno_treenet", "SagnoTreenet", "sagno"]
    },
    "sanasilva_50845": {
        "image_site_name": "sanasilva_50845",
        "project_name_variants": ["Brüttelen_sanasilva50845", "BrüttelenSanasilva50845", "sanasilva_50845", "Sanasilva-50845"]
    },
    "sanasilva_50877": {
        "image_site_name": "sanasilva_50877",
        "project_name_variants": ["Schüpfen_sanasilva50877", "SchüpfenSanasilva50877", "sanasilva_50877", "Sanasilva-50877"]
    },
    "treenet_salgesch": {
        "image_site_name": "treenet_salgesch",
        "project_name_variants": ["Salgesch_treenet", "SalgeschTreenet", "treenet_salgesch"]
    },
    "treenet_sempach": {
        "image_site_name": "treenet_sempach",
        "project_name_variants": ["Sempach_treenet", "SempachTreenet", "treenet_sempach"]
    },
    "wangen_zh": {
        "image_site_name": "wangen_zh",
        "project_name_variants": ["WangenBrüttisellen_treenet", "WangenBrüttisellenTreenet", "wangen_zh", "Wangen_Brüttisellen_treenet"]
    }
}

# Invert to make variant → folder mapping
variant_to_folder = {}
for site_info in SITE_MAPPING.values():
    for variant in site_info["project_name_variants"]:
        variant_to_folder[variant.strip().lower()] = site_info["image_site_name"]

# --- Example usage in your DataFrame processing ---
import pandas as pd

# Example dataframe (replace this with your actual Excel loading)
df = pd.DataFrame({
    "date": ["20250409", "20250409"],
    "site": ["Sanasilva-50845", "Sanasilva-50877"]
})

# Normalize site column and map to correct folder
df["site_clean"] = df["site"].str.strip().str.lower()
df["image_folder"] = df["site_clean"].map(variant_to_folder)

# Check for any unmapped values
unmapped = df[df["image_folder"].isnull()]
if not unmapped.empty:
    print("⚠️ Unmapped sites:\n", unmapped["site"].unique())

print(df)

# Load Excel
df = pd.read_excel(r"c:\Users\admin\Downloads\UPSCALE_drone_logbook(2).xlsx", sheet_name="2025_drone_logbook")

# Format date
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["date_str"] = df["date"].dt.strftime("%Y%m%d")

# Compute sunsens
df["sunsens"] = df["weather"].str.lower().ne("sunny no clouds")

# Assign CRS
df["crs"] = CRS_VALUE

# Normalize site names
df["site"] = df["site"].str.strip().str.lower().str.replace("-", "_", regex=False)

# Map image folder names
df["image_folder_name"] = df["site"].map(variant_to_folder)

# Log unmapped sites
unmapped_sites = df[df["image_folder_name"].isnull()]
if not unmapped_sites.empty:
    print("⚠️ Unmapped sites detected:")
    print(unmapped_sites["site"].unique())

# Build paths
df["rgb"] = df.apply(
    lambda row: str(BASE_RGB / row["image_folder_name"] / row["date_str"]) if pd.notna(row["image_folder_name"]) else "Folder not found",
    axis=1
)
df["multispec"] = df.apply(
    lambda row: str(BASE_MULTISPEC / row["image_folder_name"] / row["date_str"]) if pd.notna(row["image_folder_name"]) else "Folder not found",
    axis=1
)

# Final dataframe
output_df = df[["date_str", "crs", "sunsens", "rgb", "site", "multispec"]]
output_df.columns = ["date", "crs", "sunsens", "rgb", "site", "multispec"]

# Filter rows where both 'site' and 'date' are not empty
filtered_df = output_df.dropna(subset=["site", "date"])

# Save to CSV
filtered_df.to_csv("metashape_input.csv", index=False)
print("CSV file 'metashape_input.csv' has been created with valid rows only.")
