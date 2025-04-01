import pandas as pd
import csv
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(filename='csv_creation.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def read_excel_sheet(filepath: str, sheet_index: int = 1) -> pd.DataFrame:
    """Reads the specified sheet from an Excel file."""
    if not os.path.exists(filepath):
        logging.error(f"File not found: {filepath}")
        raise FileNotFoundError(f"Excel file not found: {filepath}")

    try:
        df = pd.read_excel(filepath, sheet_name=sheet_index)
        logging.info(f"Successfully read sheet {sheet_index} from {filepath}")
        return df
    except Exception as e:
        logging.error(f"Error reading Excel file: {e}")
        raise

def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cleans the DataFrame and splits it into RGB+Multispec and Multispec-only."""
    required_columns = {'date', 'site', 'rgb', 'multispec', 'crs', 'sunsens'}
    
    if not required_columns.issubset(df.columns):
        missing_cols = required_columns - set(df.columns)
        logging.error(f"Missing required columns: {missing_cols}")
        raise ValueError(f"Missing required columns in Excel sheet: {missing_cols}")

    # Remove triple quotes globally
    df = df.map(lambda x: x.replace('"""', '') if isinstance(x, str) else x)

    # Select relevant columns
    df_selected = df[['date', 'site', 'rgb', 'multispec', 'crs', 'sunsens']].copy()

    # Ensure paths are quoted
    for col in ['rgb', 'multispec']:
        df_selected[col] = df_selected[col].apply(lambda x: f'"{x}"' if isinstance(x, str) and not x.startswith('"') else x)

    # Convert date column to YYYYMMDD format
    df_selected['date'] = pd.to_datetime(df_selected['date'], errors='coerce').dt.strftime('%Y%m%d')

    # Remove rows where `multispec` is empty
    df_selected = df_selected.dropna(subset=['multispec'])
    df_selected = df_selected[df_selected['multispec'].str.strip() != '']

    # Split data into two DataFrames
    df_rgb_multi = df_selected.dropna(subset=['rgb'])  # Rows with both RGB and multispec
    df_multispec_only = df_selected[df_selected['rgb'].isna()].drop(columns=['rgb'])  # Rows with only multispec

    return df_rgb_multi, df_multispec_only

def save_to_csv(df: pd.DataFrame, output_path: str):
    """Saves a DataFrame to a CSV file."""
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    df.to_csv(output_path, index=False, quoting=csv.QUOTE_NONE, escapechar='\\')
    logging.info(f"CSV file saved at: {output_path}")

if __name__ == "__main__":
    # Define file paths
    excel_filepath = r"M:\working_package_2\2024_dronecampaign\02_processing\logbook_proc_parameters.xlsx"
    
    # Generate output file paths based on the input file name
    base_name = os.path.splitext(os.path.basename(excel_filepath))[0]
    output_dir = os.path.dirname(excel_filepath)
    output_rgb_multi_csv = os.path.join(output_dir, f"{base_name}_RGBandMulti_data.csv")
    output_multispec_csv = os.path.join(output_dir, f"{base_name}_multispectral_data.csv")

    try:
        df = read_excel_sheet(excel_filepath)
        df_rgb_multi, df_multispec_only = clean_dataframe(df)

        save_to_csv(df_rgb_multi, output_rgb_multi_csv)
        save_to_csv(df_multispec_only, output_multispec_csv)

    except Exception as e:
        logging.error(f"Script failed: {e}")
        print(f"Error: {e}")
