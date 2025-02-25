import os
import glob
import csv

def populate_site_identification_rules(micasense_base_dir, p1_base_dir, existing_rules=None):
    """
    Populates site identification rules by scanning Micasense and P1 base directories.
    """

    if existing_rules is None:
        site_identification_rules = {}
    else:
        site_identification_rules = existing_rules

    def process_base_dir(base_dir, source_type):
        if os.path.isdir(base_dir):
            for folder_name in os.listdir(base_dir):
                folder_path = os.path.join(base_dir, folder_name)
                if os.path.isdir(folder_path):
                    image_site_name = folder_name
                    if image_site_name not in site_identification_rules:
                        site_identification_rules[image_site_name] = {
                            "image_site_name": image_site_name,
                            "project_name_variants": [image_site_name]
                        }
                    # No more 'else' block here, we want dynamic names to be primary

    process_base_dir(micasense_base_dir, "Micasense")
    process_base_dir(p1_base_dir, "P1")

    return site_identification_rules


def scrape_metashape_files(base_dir, output_csv):
    """
    Scrapes file paths, dynamically populating site rules and refining project_name_variants manually.
    --- DEBUG PRINTS ADDED for date_path ---
    """

    data = []

    # Base directories for images
    micasense_base_dir = r"M:\working_package_2\2024_dronecampaign\01_data\Micasense"
    p1_base_dir = r"M:\working_package_2\2024_dronecampaign\01_data\P1"

    # --- Dynamically Populate Site Identification Rules ---
    site_identification_rules = populate_site_identification_rules(micasense_base_dir, p1_base_dir)
    print("Dynamically populated site identification rules (Image Names from folders):")
    for site, rules in site_identification_rules.items():
        print(f"  Site: {site}, Image Name: {rules['image_site_name']}, Project Variants: {rules['project_name_variants']}")
    print("-" * 40)

    manual_site_rules_override = {
        "Stillberg": {

            "image_site_name": "Stillberg", # Consistent image folder name

            "project_name_variants": ["Stillberg", "stillberg"] # List project name variations

        },

        "Pfynwald": {

            "image_site_name": "Pfynwald",

            "project_name_variants": ["Pfynwald", "Pfynwald_Project", "Pfynwald_Area"]

        },

        "Illgraben": {

            "image_site_name": "Illgraben",

            "project_name_variants": ["Illgraben", "Illgraben_Project"]

        },

        "lwf_davos": {  # Using image folder name as canonical site name for LWF sites

            "image_site_name": "Davos_LWF",

            "project_name_variants": ["Davos_LWF", "DavosLWF", "lwf_davos"] # Examples of project variations

        },

        "lwf_isone": {

            "image_site_name": "Isone_LWF",

            "project_name_variants": ["Isone_LWF", "IsoneLWF", "lwf_isone"]

        },

        "lwf_lens": {

            "image_site_name": "Lens_LWF",

            "project_name_variants": ["Lens_LWF", "LensForest", "lwf_lens"]

        },

        "lwf_neunkirch": {

            "image_site_name": "Neunkirch_LWF",

            "project_name_variants": ["Neunkirch_LWF", "NeunkirchLWF", "lwf_neunkirch"]

        },

        "lwf_schänis": {

            "image_site_name": "Schänis_LWF",

            "project_name_variants": ["Schänis_LWF", "SchänisLWF", "lwf_schänis"]

        },

        "lwf_visp": {

            "image_site_name": "Visp_LWF",

            "project_name_variants": ["Visp_LWF", "VISP_LWF", "lwf_visp"]

        },

        "marteloskop": {

            "image_site_name": "Marteloskop",

            "project_name_variants": ["Marteloskop","Martelloskop" "marteloskop"]

        },

        "sagno": {

            "image_site_name": "Sagno_treenet",

            "project_name_variants": ["Sagno_treenet", "SagnoTreenet", "sagno"]

        },

        "sanasilva_50845": {

            "image_site_name": "Sanasilva_50845",

            "project_name_variants": ["Brüttelen_sanasilva50845", "BrüttelenSanasilva50845", "sanasilva_50845"]

        },

        "sanasilva_50877": {

            "image_site_name": "Schüpfen_sanasilva50877",

            "project_name_variants": ["Schüpfen_sanasilva50877", "SchüpfenSanasilva50877", "sanasilva_50877"]

        },

        "treenet_salgesch": {

            "image_site_name": "Salgesch_treenet",

            "project_name_variants": ["Salgesch_treenet", "SalgeschTreenet", "treenet_salgesch"]

        },

        "treenet_sempach": {

            "image_site_name": "Sempach_treenet",

            "project_name_variants": ["Sempach_treenet", "SempachTreenet", "treenet_sempach"]

        },

        "wangen_zh": {

            "image_site_name": "WangenBrüttisellen_treenet",

            "project_name_variants": ["WangenBrüttisellen_treenet", "WangenBrüttisellenTreenet", "wangen_zh", "Wangen_Brüttisellen_treenet"] # Added more variants        }
        # Add more manual project name variations here, *without* overriding image_site_name unless absolutely necessary.
    }
    }

    # --- Merge dynamic rules with manual overrides ---
    for site, manual_rules in manual_site_rules_override.items():
        if site in site_identification_rules:
            existing_variants = set(site_identification_rules[site]["project_name_variants"])
            variants_to_add = set(manual_rules["project_name_variants"])
            updated_variants = list(existing_variants.union(variants_to_add))
            site_identification_rules[site]["project_name_variants"] = updated_variants
        else:
            site_identification_rules[site] = manual_rules


    for site_folder in os.listdir(base_dir):
        site_path = os.path.join(base_dir, site_folder)
        if not os.path.isdir(site_path):
            continue

        for date_folder in os.listdir(site_path):
            date_path = os.path.join(site_path, date_folder)
            if not os.path.isdir(date_path):
                continue

            site_project_name = site_folder
            date = date_folder

            # Initialize file paths
            psx_file = "File not found"
            multispectral_ortho = "File not found"
            multispectral_report = "File not found"
            rgb_ortho = "File not found"
            rgb_report = "File not found"
            rgb_location = "Folder not found"
            multispec_location = "Folder not found"
            identified_site_name = "Site name not identified"


            # --- Site Identification Logic ---
            for canonical_site_name, rules in site_identification_rules.items():
                for variant in rules["project_name_variants"]:
                    if site_project_name == variant:
                        image_site_name = rules["image_site_name"]
                        identified_site_name = canonical_site_name
                        print(f"  Project site '{site_project_name}' identified as site: '{canonical_site_name}' (Image folder name: '{image_site_name}')")
                        break
                if identified_site_name != "Site name not identified":
                    break
            else:
                print(f"  WARNING: Project site '{site_project_name}' NOT IDENTIFIED in rules.")


            # Construct image folder paths
            if identified_site_name != "Site name not identified":
                image_site_name_micasense = image_site_name
                image_site_name_p1 = image_site_name

                if image_site_name_micasense != "Site name not identified":
                    multispec_location = os.path.join(micasense_base_dir, image_site_name_micasense, date)
                    if not os.path.isdir(multispec_location):
                        multispec_location = "Folder not found"

                if image_site_name_p1 != "Site name not identified":
                    image_site_name_p1_path = image_site_name_p1
                    rgb_location = os.path.join(p1_base_dir, image_site_name_p1_path, date)
                    if not os.path.isdir(rgb_location):
                        rgb_location = "Folder not found"
            else:
                pass


            # Debug prints (same as before)
            print(f"Site Project Folder: {site_project_name}, Date: {date}")
            print(f"  Identified Site (Canonical): {identified_site_name}")
            print(f"  Multispec Location: {multispec_location}, Exists: {os.path.isdir(multispec_location) if multispec_location != 'Folder not found' else False}")
            print(f"  RGB Location: {rgb_location}, Exists: {os.path.isdir(rgb_location) if rgb_location != 'Folder not found' else False}")

            # --- DEBUG PRINTS - DATE PATH BEFORE glob.glob ---
            print(f"  DEBUG: Searching for PSX files in: {date_path}") # ADDED
            psx_files = glob.glob(os.path.join(date_path, "*.psx"))
            if psx_files:
                psx_file = psx_files[0]

            print(f"  DEBUG: Searching for multispec ortho in: {date_path}") # ADDED
            multispec_ortho_files = glob.glob(os.path.join(date_path, "*_multispec_ortho_*.tif"))
            if multispec_ortho_files:
                multispectral_ortho = multispec_ortho_files[0]

            print(f"  DEBUG: Searching for multispec report in: {date_path}") # ADDED
            multispec_report_files = glob.glob(os.path.join(date_path, "*_multispec_report.pdf"))
            if multispec_report_files:
                multispectral_report = multispec_report_files[0]

            print(f"  DEBUG: Searching for rgb ortho in: {date_path}") # ADDED
            rgb_ortho_files = glob.glob(os.path.join(date_path, "*_rgb_ortho_*.tif"))
            if rgb_ortho_files:
                rgb_ortho = rgb_ortho_files[0]

            print(f"  DEBUG: Searching for rgb report in: {date_path}") # ADDED
            rgb_report_files = glob.glob(os.path.join(date_path, "*_rgb_report.pdf"))
            if rgb_report_files:
                rgb_report = rgb_report_files[0]

            print("-" * 40)


            data.append({
                'date': date,
                'site': identified_site_name,
                'rgb': rgb_location,
                'multispec': multispec_location,
                'psx_file': psx_file,
                'multispectral_ortho': multispectral_ortho,
                'multispectral_report': multispectral_report,
                'rgb_ortho': rgb_ortho,
                'rgb_report': rgb_report
            })


    with open(output_csv, 'w', newline='') as csvfile:
        fieldnames = ['date', 'site', 'rgb', 'multispec', 'psx_file', 'multispectral_ortho', 'multispectral_report', 'rgb_ortho', 'rgb_report']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"Data written to {output_csv}")

if __name__ == "__main__":
    base_directory = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\metashape_proj"
    output_csv_file = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\metashape_proj\metashape_file_paths.csv"
    scrape_metashape_files(base_directory, output_csv_file)