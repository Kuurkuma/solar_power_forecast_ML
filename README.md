# Data collection
**Data Source:** PVGIS API (Non-interactive service) providing hourly time series data.

### Hourly radiation
PVGIS provides a full data set of solar radiation and other data needed to calculate PV power hour by hour for long time periods. PVGIS can also perform the hourly PV power calculation. The PV output values from the PVGIS interface "Hourly data" tool are calculated for a free-standing PV system. The hourly values of PV output from a building integrated system can be obtained using the Non-interactive service of the said "Hourly data" tool.

**output options** = CSV or JSON format.

**csv**
The headers:

- Latitude (in decimal degrees)
- Longitude (in decimal degrees)
- Elevation (m)
- Name of the solar radiation database used
- Slope (inclination) angle for the fixed plane (in  degrees)
- Azimuth/orientation angle for the fixed plane (in degrees)

If the PV output calculation has been requested:
- Nominal power of PV system and the type of PV technology used
- System loss used for the calculation

These are then followed by one line of column headers, and then the hourly values of the following quantities, with each field in a separate column:

- time [UTC]
- P [W] - PV power output (if requested)
- G(i) [W/m2] - Global in-plane irradiance (if radiation components are not requested)
- Gb(i) [W/m2] - Direct in-plane irradiance (if radiation components are requested)
- Gd(i) [W/m2] - Diffuse in-plane irradiance (if radiation components are requested)
- Gr(i) [W/m2] - Reflected in-plane irradiance (if radiation components are requested)
- H_sun [°] - Sun height (elevation)
- T2m [°C] - Air temperature
- WS10m [m/s] - Wind speed at 10m

The last part of the output contains a list of descriptions of each column of data.

json
{ "inputs": { "location": { "latitude": 45.809, "longitude": 8.632, "elevation": 223 }, "meteo_data": { "radiation_db": "PVGIS-SARAH", "meteo_db": "ERA-Interim", "year_min": 2005, "year_max": 2016, "use_horizon": true, "horizon_db": "DEM-calcualted", }, "mounting_system": { "fixed": { "slope": { "value": 30, "optimal": False }, "azimuth": { "value": 0, "optimal": False }, "type": "free-standing", }, }, "pv_module": { "technology": "c-Si", "peak_power": 1, "system_loss": 14, }, }, "outputs": { "hourly": { { "time": "20050101:0000", "P": 0, "Gb(i)": 0, "Gd(i)": 0, "Gr(i)": 0, "H_sun": 0, "T2m": 4.49, "WS10m": 2.92, "Int": 0, }, {...} } }, "meta": { "inputs": { "location": { "description": "Selected location" "variables": { "latitude": { "description": "Latitude", "units": "decimal degrees" }, {...} } }, {...} }, "outputs": { "months_selected": { "type": "time series" "timestamp": "hourly averages" "variables": { "P": { "description": "PV system power", "units": "W" }, {...} }, {...} } } }}