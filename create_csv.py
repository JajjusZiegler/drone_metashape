import pandas as pd
import csv

def read_second_sheet(filepath):
    return pd.read_excel(filepath, sheet_name=1)

# Example usage
filepath = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\logbook_proc_parameters.xlsx"
df = read_second_sheet(filepath)

# Remove triple quotes from the entire DataFrame
df = df.applymap(lambda x: x.replace('"""', '') if isinstance(x, str) else x)

print(df.columns)

# Select specific columns
selected_columns = ['date', 'site', 'rgb', 'multispec', 'crs', 'sunsens']
df_selected = df[selected_columns].copy()

# Add quotation marks if missing
df_selected['rgb'] = df_selected['rgb'].apply(lambda x: f'"{x}"' if isinstance(x, str) and not x.startswith('"') and not x.endswith('"') else x)
df_selected['multispec'] = df_selected['multispec'].apply(lambda x: f'"{x}"' if isinstance(x, str) and not x.startswith('"') and not x.endswith('"') else x)

# Filter out rows with NaN in 'multispec'
df_filtered = df_selected.dropna(subset=['multispec'])

# Handle rows where 'rgb' is NaN
df_multispectral = df_filtered[df_filtered['rgb'].isna()].copy()
df_multispectral.drop(columns=['rgb'], inplace=True)

# Filter out rows with NaN in 'multispec'
df_filtered = df_filtered.dropna(subset=['rgb'])

# Convert 'date' column to YYYYMMDD format
df_filtered['date'] = pd.to_datetime(df_filtered['date']).dt.strftime('%Y%m%d')
df_multispectral['date'] = pd.to_datetime(df_multispectral['date']).dt.strftime('%Y%m%d')

# Ensure triple quotes are removed in the final output
df_filtered = df_filtered.applymap(lambda x: x.replace('"""', '') if isinstance(x, str) else x)
df_multispectral = df_multispectral.applymap(lambda x: x.replace('"""', '') if isinstance(x, str) else x)

print(df_filtered['rgb'])
print(df_filtered['multispec'])

# Define the output CSV file paths
output_csv_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\RGBandMulti_data.csv"
multispectral_csv_path = r"M:\working_package_2\2024_dronecampaign\02_processing\metashape_projects\multispectral_data.csv"

# Save the filtered rows to CSV files
df_filtered.to_csv(output_csv_path, index=False, quoting=csv.QUOTE_NONE, escapechar='\\')
df_multispectral.to_csv(multispectral_csv_path, index=False, quoting=csv.QUOTE_NONE, escapechar='\\')

print(f"CSV file created at: {output_csv_path}")
print(f"Multispectral CSV file created at: {multispectral_csv_path}")
