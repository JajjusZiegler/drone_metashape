import pandas as pd
import csv
import os

from pathlib import Path


def process_logbook(excel_file: str, sheet_name: str = "2025_drone_logbook") -> pd.DataFrame:
    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"Excel file not found: {excel_file}")
    
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["date_str"] = df["date"].dt.strftime("%Y%m%d")

    df["weather"] = df["weather"].astype(str).str.strip().str.lower()
    df["sunsens"] = df["weather"].ne("sunny no clouds")
    df["crs"] = 2056

    # Clean up site and Site_list strings
    df["site"] = df["site"].astype(str).str.strip()
    df["site_path"] = df["Site_list"].astype(str).str.strip()

    # Base paths
    base_rgb = Path(r"M:/working_package_2/2024_dronecampaign/01_data/P1")
    base_multi = Path(r"M:/working_package_2/2024_dronecampaign/01_data/Micasense")

    # Construct file paths
    df["rgb"] = df.apply(lambda row: str(base_rgb / row["site_path"] / row["date_str"]), axis=1)
    df["multispec"] = df.apply(lambda row: str(base_multi / row["site_path"] / row["date_str"]), axis=1)

    return df

def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_columns = {'date', 'site', 'rgb', 'multispec', 'crs', 'sunsens'}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise ValueError(f"Missing columns in DataFrame: {missing}")

    df_selected = df[['date', 'site', 'rgb', 'multispec', 'crs', 'sunsens']].copy()

    # Quote paths
    for col in ['rgb', 'multispec']:
        df_selected[col] = df_selected[col].apply(lambda x: f'"{x}"' if isinstance(x, str) and not x.startswith('"') else x)

    df_selected['date'] = pd.to_datetime(df_selected['date'], errors='coerce').dt.strftime('%Y%m%d')
    df_selected.dropna(subset=['multispec'], inplace=True)
    df_selected = df_selected[df_selected['multispec'].str.strip() != '']

    df_rgb_multi = df_selected.dropna(subset=['rgb'])
    df_multispec_only = df_selected[df_selected['rgb'].isna()].drop(columns=['rgb'])

    return df_rgb_multi, df_multispec_only

def save_to_csv(df: pd.DataFrame, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, quoting=csv.QUOTE_NONE, escapechar='\\')

if __name__ == "__main__":
    excel_filepath = input("Enter Excel file path: ").strip()
    base_name = input("Enter base name for CSVs: ").strip()
    output_dir = input("Enter output directory (blank = same as Excel): ").strip()

    if not output_dir:
        output_dir = os.path.dirname(excel_filepath)
    else:
        os.makedirs(output_dir, exist_ok=True)

    output_rgb_multi_csv = os.path.join(output_dir, f"{base_name}_RGBandMulti_data.csv")
    output_multispec_csv = os.path.join(output_dir, f"{base_name}_multispectral_data.csv")

    try:
        # Process the Excel file
        df = process_logbook(excel_filepath)

        # Clean the DataFrame
        df_rgb_multi, df_multispec_only = clean_dataframe(df)

        # Save the cleaned data to CSV files
        save_to_csv(df_rgb_multi, output_rgb_multi_csv)
        save_to_csv(df_multispec_only, output_multispec_csv)

        print(f"Data successfully saved to:\n{output_rgb_multi_csv}\n{output_multispec_csv}")
    except Exception as e:
        print(f"An error occurred: {e}")
