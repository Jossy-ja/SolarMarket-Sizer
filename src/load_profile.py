"""
load_profile.py
----------------
Generates a synthetic hourly electricity demand profile for an urban market.

IMPORTANT: This is an ESTIMATED profile built from stated assumptions, not
metered data. No public dataset of real market electricity demand exists at
this granularity, so the profile is intentionally transparent and adjustable.
State your assumptions clearly in the README / notebook when you use this.
"""

import numpy as np
import pandas as pd


def generate_end_use_profile(
    num_stalls: int = 80,
    stall_load_kw: float = 0.35,
    lighting_kw: float = 5.0,
    refrigeration_kw: float = 3.0,
    water_pump_kw: float = 2.0,
    security_kw: float = 1.0,
    other_fixed_kw: float = 2.0,
    open_hour: int = 6,
    close_hour: int = 19,
) -> pd.DataFrame:
    """
    Generate an hourly market demand profile from explicit end-use assumptions.

    The profile is synthetic and represents assumed electricity demand from:
    - market stalls
    - lighting
    - refrigeration
    - water pumping
    - security
    - other fixed/common loads

    Parameters
    ----------
    num_stalls : int
        Number of market stalls.
    stall_load_kw : float
        Average connected demand per stall during operating hours.
    lighting_kw : float
        Market lighting demand during operating hours.
    refrigeration_kw : float
        Refrigeration demand, assumed to operate continuously.
    water_pump_kw : float
        Water pumping demand during selected operating hours.
    security_kw : float
        Security/essential load operating continuously.
    other_fixed_kw : float
        Other common-area electrical loads.
    open_hour, close_hour : int
        Main market operating hours.

    Returns
    -------
    pd.DataFrame
        Hourly profile with individual end-use columns and total load.
    """

    hours = np.arange(24)

    stall_load = np.zeros(24)
    lighting_load = np.zeros(24)
    refrigeration_load = np.full(24, refrigeration_kw)
    water_pump_load = np.zeros(24)
    security_load = np.full(24, security_kw)
    other_load = np.zeros(24)

    # Main stall demand during market operating hours
    operating_hours = (hours >= open_hour) & (hours < close_hour)

    stall_load[operating_hours] = (
        num_stalls * stall_load_kw
    )

    # Lighting operates mainly while the market is open
    lighting_load[operating_hours] = lighting_kw

    # Water pumping during operating hours
    water_pump_load[operating_hours] = water_pump_kw

    # Other common loads during operating hours
    other_load[operating_hours] = other_fixed_kw

    profile = pd.DataFrame({
        "stall_load_kw": stall_load,
        "lighting_kw": lighting_load,
        "refrigeration_kw": refrigeration_load,
        "water_pump_kw": water_pump_load,
        "security_kw": security_load,
        "other_fixed_kw": other_load,
    })

    profile["total_load_kw"] = profile.sum(axis=1)

    return profile

def generate_year_profile(
    num_stalls: int = 80,
    stall_load_kw: float = 0.35,
    lighting_kw: float = 5.0,
    refrigeration_kw: float = 3.0,
    water_pump_kw: float = 2.0,
    security_kw: float = 1.0,
    other_fixed_kw: float = 2.0,
    open_hour: int = 6,
    close_hour: int = 19,
    weekend_factor: float = 0.6,
    market_days: list | None = None,
    start_date: str = "2025-01-01",
    periods_days: int = 365,
) -> pd.DataFrame:
    """
    Generate a synthetic hourly electricity demand profile for a market.

    Demand is constructed from explicit end-use assumptions rather than
    a single assumed peak-load value.

    IMPORTANT
    ---------
    This is a synthetic demand model, not measured electricity data.
    """

    if market_days is None:
        market_days = list(range(7))

    daily_profile = generate_end_use_profile(
        num_stalls=num_stalls,
        stall_load_kw=stall_load_kw,
        lighting_kw=lighting_kw,
        refrigeration_kw=refrigeration_kw,
        water_pump_kw=water_pump_kw,
        security_kw=security_kw,
        other_fixed_kw=other_fixed_kw,
        open_hour=open_hour,
        close_hour=close_hour,
    )

    idx = pd.date_range(
        start=start_date,
        periods=periods_days * 24,
        freq="h",
    )

    df = pd.DataFrame(index=idx)

    df["hour"] = df.index.hour
    df["weekday"] = df.index.weekday

    is_market_day = df["weekday"].isin(market_days)

    day_multiplier = np.where(
        is_market_day,
        1.0,
        weekend_factor,
    )

    for column in daily_profile.columns:
        df[column] = (
            df["hour"]
            .map(daily_profile[column])
            .astype(float)
            * day_multiplier
        )

    return df[
        [
            "stall_load_kw",
            "lighting_kw",
            "refrigeration_kw",
            "water_pump_kw",
            "security_kw",
            "other_fixed_kw",
            "total_load_kw",
        ]
    ]
def apply_demand_scenario(
    profile: pd.DataFrame,
    scenario: str = "base",
    low_factor: float = 0.80,
    high_factor: float = 1.20,
) -> pd.DataFrame:
    """
    Apply a demand scenario multiplier to an existing load profile.

    Parameters
    ----------
    profile : pd.DataFrame
        Hourly demand profile containing 'total_load_kw'.
    scenario : str
        Demand scenario: 'low', 'base', or 'high'.
    low_factor : float
        Multiplier applied to the base profile under the low scenario.
    high_factor : float
        Multiplier applied to the base profile under the high scenario.

    Returns
    -------
    pd.DataFrame
        Copy of the profile with demand scaled according to the scenario.
    """

    scenario = scenario.lower()

    factors = {
        "low": low_factor,
        "base": 1.0,
        "high": high_factor,
    }

    if scenario not in factors:
        raise ValueError(
            "scenario must be one of: 'low', 'base', or 'high'"
        )

    factor = factors[scenario]

    result = profile.copy()

    load_columns = [
        "stall_load_kw",
        "lighting_kw",
        "refrigeration_kw",
        "water_pump_kw",
        "security_kw",
        "other_fixed_kw",
        "total_load_kw",
    ]

    for column in load_columns:
        if column in result.columns:
            result[column] = result[column] * factor

    result["demand_scenario"] = scenario
    result["scenario_factor"] = factor

    return result

if __name__ == "__main__":
    base_profile = generate_year_profile(
        num_stalls=80,
        stall_load_kw=0.35,
        lighting_kw=5.0,
        refrigeration_kw=3.0,
        water_pump_kw=2.0,
        security_kw=1.0,
        other_fixed_kw=2.0,
        open_hour=6,
        close_hour=19,
        market_days=[0, 1, 2, 3, 4, 5],
        periods_days=365,
    )

    for scenario in ["low", "base", "high"]:
        profile = apply_demand_scenario(
            base_profile,
            scenario=scenario,
        )

        print(
            f"{scenario.capitalize()} scenario:"
        )

        print(
            "  Peak demand (kW):",
            round(profile["total_load_kw"].max(), 2),
        )

        print(
            "  Annual energy (kWh):",
            round(profile["total_load_kw"].sum(), 0),
        )

        print()
