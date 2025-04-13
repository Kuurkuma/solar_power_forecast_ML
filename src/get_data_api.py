import os
import glob
import requests
import pandas as pd
import time 

# --- Configuration ---

INPUT_CSV_DIR = '/Users/macbook/Development/sun_eu/data/01_raw'  
OUTPUT_CSV_DIR = '/Users/macbook/Development/sun_eu/data/02_interim' 


# --- PVGIS API Base URL and Fixed Parameters ---
PVGIS_API_BASE_URL = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc" # PV Calculation endpoint
# Note: These parameters are for PV system simulation, NOT raw irradiance time series
PVGIS_BASE_PARAMS = dict(
    peakpower=1,       # Nominal power of the PV system in kWp
    loss=14,           # System losses in percent (%)
    # mountingplace='building', # Consider adding if needed (API dependent)
    # slope=35,          # Consider adding if fixed slope needed
    vertical_axis=1,   # From original code - assuming vertical tracking axis
    angle=90,          # From original code - assuming related to tracking/tilt
    azimuth=0,         # From original code - base azimuth (might be overridden by aspect)
    outputformat='json'
)
API_TIMEOUT = 45 # Seconds to wait for API response
API_DELAY = 0.5 # Seconds to wait between API calls to avoid overloading server


# --- Helper Functions ---

def load_and_prepare_csv(csv_path):
    """Loads a CSV, performs coordinate handling placeholder, ensures required columns."""
    print(f"\n--- Loading: {os.path.basename(csv_path)} ---")
    try:
        df = pd.read_csv(csv_path, skiprows=8)

        # --- CRITICAL: Coordinate Handling ---
        # The original xy2latlon function was removed as it was non-functional.
        # You MUST adapt this section based on your CSV data.

        # Option A: If your CSV ALREADY has correct WGS84 'lat' and 'lon' columns:
        if 'lat' in df.columns and 'lon' in df.columns:
            print("Found 'lat' and 'lon' columns. Assuming WGS84 format.")
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')

        # Option B: If your CSV has projected coordinates (e.g., 'POINT_X', 'POINT_Y' in LAEA):
        # elif 'POINT_X' in df.columns and 'POINT_Y' in df.columns:
        #     print("Found 'POINT_X', 'POINT_Y'. Implementing coordinate conversion...")
        #     try:
        #         from pyproj import Proj, transform, exceptions # Requires: pip install pyproj
        #         inProj = Proj('epsg:3035') # Example: LAEA Europe EPSG code - CHANGE IF NEEDED
        #         outProj = Proj('epsg:4326') # WGS84 EPSG code
        #         # Note: transform expects lists/arrays
        #         lon_list, lat_list = transform(inProj, outProj,
        #                                        df['POINT_X'].values,
        #                                        df['POINT_Y'].values,
        #                                        always_xy=True) # Ensure lon, lat order
        #         df['lon'] = lon_list
        #         df['lat'] = lat_list
        #         print("Coordinate conversion successful.")
        #     except ImportError:
        #         print("ERROR: 'pyproj' library not found. Please install it (`pip install pyproj`) for coordinate conversion.")
        #         return None
        #     except exceptions.CRSError as e:
        #          print(f"ERROR: Coordinate system error during transformation: {e}")
        #          return None
        #     except Exception as e:
        #         print(f"ERROR: Unexpected error during coordinate transformation: {e}")
        #         return None

        # Option C: Handle other column names for lat/lon if needed
        # elif 'Latitude' in df.columns and 'Longitude' in df.columns:
            # df.rename(columns={'Latitude': 'lat', 'Longitude': 'lon'}, inplace=True)
            # print("Renamed 'Latitude'/'Longitude' to 'lat'/'lon'.")
            # df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            # df['lon'] = pd.to_numeric(df['lon'], errors='coerce')

        else:
            print("ERROR: Required coordinate columns ('lat'/'lon' or specific projected names) not found.")
            return None # Cannot proceed without coordinates

        # --- Ensure other necessary columns exist ---
        required_cols = ['ORIG_FID', 'azimuth_cw', 'azimuth_aw']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"ERROR: Missing required columns: {', '.join(missing_cols)}")
            return None

        # Ensure numeric types where expected, handle potential errors
        for col in ['azimuth_cw', 'azimuth_aw']:
             df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with missing essential data after conversions/checks
        initial_rows = len(df)
        df.dropna(subset=['lat', 'lon', 'ORIG_FID', 'azimuth_cw', 'azimuth_aw'], inplace=True)
        if len(df) < initial_rows:
            print(f"Dropped {initial_rows - len(df)} rows with missing essential data.")

        if df.empty:
            print("DataFrame is empty after cleaning.")
            return None

        print(f"Successfully loaded and prepared {len(df)} rows.")
        return df

    except FileNotFoundError:
        print(f"ERROR: File not found: {csv_path}")
        return None
    except Exception as e:
        print(f"ERROR: Failed to load or prepare {os.path.basename(csv_path)}: {e}")
        return None

def construct_api_urls(df, base_url, base_params):
    """Constructs the full PVGIS API URLs for 'cw' and 'aw' aspects."""
    print("Constructing API URLs...")
    # Create the base query string from fixed parameters
    # Using requests.PreparedRequest to handle encoding properly is safer
    base_req = requests.PreparedRequest()
    base_req.prepare_url(base_url, base_params)
    base_url_with_params = base_req.url

    # Add row-specific parameters (aspect, lat, lon)
    df['url_cw'] = base_url_with_params + '&aspect=' + df['azimuth_cw'].astype(str) + \
                   '&lat=' + df['lat'].astype(str) + '&lon=' + df['lon'].astype(str)
    df['url_aw'] = base_url_with_params + '&aspect=' + df['azimuth_aw'].astype(str) + \
                   '&lat=' + df['lat'].astype(str) + '&lon=' + df['lon'].astype(str)
    print("URLs constructed.")
    return df

def fetch_and_parse_pvgis(api_url, row_id, aspect_key):
    """Fetches data for one URL, parses E_y, handles errors."""
    try:
        print(f"Querying ID {row_id} ({aspect_key})... ", end="")
        response = requests.get(api_url, timeout=API_TIMEOUT)
        response.raise_for_status() # Check for HTTP errors (4xx, 5xx)
        data = response.json() # Parse JSON directly

        # Navigate the JSON structure to get E_y (Annual Energy Yield)
        # Use .get() chain to avoid KeyError if structure is missing
        e_y = data.get('outputs', {}).get('totals', {}).get('fixed', {}).get('E_y')

        if e_y is not None:
            print(f"Success, E_y = {e_y:.2f}")
            return float(e_y)
        else:
            print("Failed - E_y not found in JSON response.")
            # Optionally log the full response structure if E_y is missing
            # print(f"DEBUG: Full JSON response for missing E_y:\n{data}")
            return pd.NA # Use pandas NA for missing numeric data

    except requests.exceptions.Timeout:
        print(f"Failed - Timeout accessing API.")
        return pd.NA
    except requests.exceptions.HTTPError as e:
        print(f"Failed - HTTP Error: {e.response.status_code}")
        return pd.NA
    except requests.exceptions.RequestException as e:
        print(f"Failed - Network/Request Error: {e}")
        return pd.NA
    except ValueError as e: # Catches JSON decoding errors
         print(f"Failed - Invalid JSON response: {e}")
         return pd.NA
    except Exception as e:
        print(f"Failed - Unexpected Error during fetch/parse: {e}")
        return pd.NA

# --- Main Execution Logic ---
def main():
    """Main function to process CSV files and query PVGIS."""
    csv_files = glob.glob(os.path.join(INPUT_CSV_DIR, "*.csv"))

    if not csv_files:
        print(f"No CSV files found in directory: {INPUT_CSV_DIR}")
        return

    print(f"Found {len(csv_files)} CSV files to process.")

    for csv_file_path in csv_files:
        # 1. Load and Prepare Data
        df_processed = load_and_prepare_csv(csv_file_path)
        if df_processed is None:
            continue # Skip to next file if loading/preparation failed

        # 2. Construct URLs
        df_with_urls = construct_api_urls(df_processed, PVGIS_API_BASE_URL, PVGIS_BASE_PARAMS)

        # 3. Fetch Data from API
        results_cw = {} # Store E_y results for clockwise aspect
        results_aw = {} # Store E_y results for anti-clockwise aspect
        total_rows = len(df_with_urls)
        print(f"\nFetching PVGIS data for {total_rows} locations in {os.path.basename(csv_file_path)}...")

        for index, row in df_with_urls.iterrows():
            orig_id = row['ORIG_FID']
            print(f" Processing row {index + 1}/{total_rows} (ID: {orig_id})")

            # Fetch Clockwise Data
            e_y_cw = fetch_and_parse_pvgis(row['url_cw'], orig_id, 'cw')
            results_cw[orig_id] = e_y_cw
            time.sleep(API_DELAY) # Be nice to the API server

            # Fetch Anti-Clockwise Data
            e_y_aw = fetch_and_parse_pvgis(row['url_aw'], orig_id, 'aw')
            results_aw[orig_id] = e_y_aw
            time.sleep(API_DELAY) # Be nice to the API server

        print(f"\nFinished fetching data for {os.path.basename(csv_file_path)}.")

        # 4. Add Results to DataFrame
        df_with_urls['E_Y_cw'] = df_with_urls['ORIG_FID'].map(results_cw)
        df_with_urls['E_Y_aw'] = df_with_urls['ORIG_FID'].map(results_aw)

        # 5. Save Updated DataFrame
        base_filename = os.path.splitext(os.path.basename(csv_file_path))[0]
        output_filename = f"{base_filename}_results.csv"
        output_path = os.path.join(OUTPUT_CSV_DIR, output_filename)

        try:
            # Drop the potentially very long URL columns before saving
            df_to_save = df_with_urls.drop(columns=['url_cw', 'url_aw'], errors='ignore')
            df_to_save.to_csv(output_path, index=False, float_format='%.4f')
            print(f"Successfully saved results to: {output_path}")
        except Exception as e:
            print(f"ERROR: Failed to save results CSV to {output_path}: {e}")

    print("\n--- All CSV files processed. ---")

# --- Run the main function ---
if __name__ == "__main__":
    main()
    print("\nScript finished.")