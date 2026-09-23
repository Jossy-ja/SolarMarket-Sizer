"""
pvgis.py
--------
Thin wrapper around the European Commission's PVGIS API (free, no API key
required). Docs: https://joint-research-centre.ec.europa.eu/pvgis-online-tool/getting-started-pvgis/api-non-interactive-service_en

We use the `seriescalc` endpoint, which returns hourly PV power output for a
given location, system size, and orientation, built from satellite-derived
solar radiation data (typically averaged from ~10-20 years of historical data).

NOTE: This module makes a live HTTPS call to re.jrc.ec.europa.eu. If you're
running this in a sandboxed environment without internet access, use
`load_pvgis_csv()` after manually downloading the data from the PVGIS web
tool (https://re.jrc.ec.europa.eu/pvg_tools/en/) as a CSV instead.
"""

import io
import requests
import pandas as pd

PVGIS_BASE_URL = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"


def fetch_pvgis_hourly(
    lat: float,
    lon: float,
    peakpower_kw: float = 1.0,
    loss_pct: float = 14.0,
    tilt_deg: float = 15,
    azimuth_deg: float = 0,
    year_start: int = 2019,
    year_end: int = 2019,
    pv_technology: str = "crystSi",
    mounting: str = "free",
) -> pd.DataFrame:
    
    """
    Fetch hourly PV generation data from PVGIS for a 1 kWp reference system
    (scale the result yourself for other system sizes — PV output is linear
    with peak power).

    Parameters
    ----------
    lat, lon : site coordinates (decimal degrees)
    peakpower_kw : nominal PV system size in kWp
    loss_pct : total system losses (%) — inverter, wiring, soiling, etc.
               PVGIS default is ~14%
    tilt_deg : panel tilt angle from horizontal
    azimuth_deg : panel azimuth, 0 = south, negative = east, positive = west
                  (PVGIS convention)
    year_start, year_end : year range for the hourly time series
                            (PVGIS typically supports 2005-2020 for most
                            locations; check coverage for your site)
    pv_technology : 'crystSi', 'CIS', 'CdTe', or 'Unknown'
    mounting : 'free' (free-standing) or 'building' (roof/facade integrated)

    Returns
    -------
    pd.DataFrame indexed by hourly timestamp with columns:
        - 'poa_global_wm2' : plane-of-array irradiance (W/m2)
        - 'pv_power_w'     : AC power output (W)
        - 'temp_air_c'     : ambient temperature (deg C)
    """
    params = {
        "lat": lat,
        "lon": lon,
        "startyear": year_start,
        "endyear": year_end,
        "pvcalculation": 1,
        "peakpower": peakpower_kw,
        "loss": loss_pct,
        "angle": tilt_deg,
        "aspect": azimuth_deg,
        "pvtechchoice": pv_technology,
        "mountingplace": mounting,
        "outputformat": "csv",
        "browser": 0,
    }

    resp = requests.get(PVGIS_BASE_URL, params=params, timeout=60)
    resp.raise_for_status()

    return _parse_pvgis_csv(resp.text)


def load_pvgis_csv(filepath: str) -> pd.DataFrame:
    """
    Parse a PVGIS hourly CSV that was manually downloaded from the PVGIS
    web tool (useful if you don't have direct API/network access).
    """
    with open(filepath, "r") as f:
        text = f.read()
    return _parse_pvgis_csv(text)


def _parse_pvgis_csv(text: str) -> pd.DataFrame:
    """Shared CSV parsing logic for both the API response and manual downloads."""
    lines = text.splitlines()

    # PVGIS CSV has metadata header lines before the actual data table,
    # and footer lines after it. The data table starts with a line
    # beginning with "time" and ends before a blank line / "Ptot" summary line.
    data_start = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("time"):
            data_start = i
            break
    if data_start is None:
        raise ValueError("Could not find data header row in PVGIS CSV output.")

    data_end = len(lines)
    for i in range(data_start + 1, len(lines)):
        line = lines[i].strip()
        # PVGIS data rows start with a date like "20190101:0010".
        # A blank line or any non-digit-leading line marks the footer.
        if line == "" or not line[:1].isdigit():
            data_end = i
            break

    csv_block = "\n".join(lines[data_start:data_end])
    df = pd.read_csv(io.StringIO(csv_block))

    # PVGIS time format: YYYYMMDD:HHMM
    df["time"] = pd.to_datetime(df["time"], format="%Y%m%d:%H%M")
    df = df.set_index("time")

    rename_map = {"G(i)": "poa_global_wm2", "P": "pv_power_w", "T2m": "temp_air_c"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    keep_cols = [c for c in ["poa_global_wm2", "pv_power_w", "temp_air_c"] if c in df.columns]
    return df[keep_cols]


def scale_pv_output(pv_1kwp_series_w: pd.Series, target_kwp: float) -> pd.Series:
    """
    Scale a 1 kWp (or any known-size) PVGIS output series to a different
    system size, since PV output is ~linear with installed capacity.
    Returns power in kW.
    """
    reference_kwp = 1.0
    return pv_1kwp_series_w / 1000.0 * (target_kwp / reference_kwp)


if __name__ == "__main__":
    # Example usage (requires internet access to re.jrc.ec.europa.eu):
    # df = fetch_pvgis_hourly(lat=6.5244, lon=3.3792, peakpower_kw=1.0)  # Lagos, NG
    # print(df.head())
    # print("Annual yield per kWp (kWh):", df["pv_power_w"].sum() / 1000)
    print("Run fetch_pvgis_hourly(lat, lon) with internet access to test live.")
