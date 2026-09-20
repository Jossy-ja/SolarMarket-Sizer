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


def generate_daily_shape(
    open_hour: int = 6,
    close_hour: int = 19,
    ramp_hours: int = 1,
    base_load_frac: float = 0.15,
    covered_market: bool = False,
    evening_extra_hours: int = 0,
) -> np.ndarray:
    """
    Build a normalized 24-hour demand shape (values between ~0 and 1).

    Parameters
    ----------
    open_hour, close_hour : market operating hours (24h clock)
    ramp_hours : how many hours it takes to ramp up/down at open/close
    base_load_frac : fraction of peak load present even when "closed"
                      (security lighting, refrigeration, etc.)
    covered_market : if True, adds refrigeration + indoor lighting load
                      (flatter daytime curve, higher base load)
    evening_extra_hours : hours after close_hour with reduced but
                           non-zero activity (e.g. cleaning, night market stalls)

    Returns
    -------
    np.ndarray of length 24, values roughly in [base_load_frac, 1.0]
    """
    hours = np.arange(24)
    shape = np.full(24, base_load_frac, dtype=float)

    for h in hours:
        if open_hour <= h < close_hour:
            # ramp up
            hours_since_open = h - open_hour
            hours_to_close = close_hour - h
            ramp_factor = min(
                1.0,
                hours_since_open / max(ramp_hours, 1),
                hours_to_close / max(ramp_hours, 1),
            )
            shape[h] = base_load_frac + (1 - base_load_frac) * max(ramp_factor, 0.3)
        elif close_hour <= h < close_hour + evening_extra_hours:
            shape[h] = base_load_frac + 0.25 * (1 - base_load_frac)

    if covered_market:
        # refrigeration/lighting keeps a higher floor all day
        shape = np.maximum(shape, base_load_frac + 0.1)

    return shape


def generate_year_profile(
    peak_load_kw: float,
    open_hour: int = 6,
    close_hour: int = 19,
    covered_market: bool = False,
    weekend_factor: float = 0.6,
    market_days: list | None = None,
    start_date: str = "2025-01-01",
    periods_days: int = 365,
) -> pd.DataFrame:
    """
    Generate an hourly load profile for a full year (or any period_days).

    Parameters
    ----------
    peak_load_kw : the assumed peak demand of the market (kW), e.g.
                   (number_of_stalls * avg_kw_per_stall) + fixed_loads
    open_hour, close_hour, covered_market : passed to generate_daily_shape
    weekend_factor : demand multiplier on non-market days (0-1)
    market_days : list of weekday ints that are FULL market days
                  (0=Mon ... 6=Sun). Default: every day is a market day.
    start_date : ISO date string for the first day of the profile
    periods_days : number of days to generate (365 = one year)

    Returns
    -------
    pd.DataFrame indexed by hourly timestamp with column 'load_kw'
    """
    if market_days is None:
        market_days = list(range(7))  # every day

    daily_shape = generate_daily_shape(
        open_hour=open_hour, close_hour=close_hour, covered_market=covered_market
    )

    idx = pd.date_range(start=start_date, periods=periods_days * 24, freq="h")
    df = pd.DataFrame(index=idx)
    df["hour"] = df.index.hour
    df["weekday"] = df.index.weekday

    shape_lookup = pd.Series(daily_shape, index=range(24))
    df["shape"] = df["hour"].map(shape_lookup)

    is_market_day = df["weekday"].isin(market_days)
    day_multiplier = np.where(is_market_day, 1.0, weekend_factor)

    df["load_kw"] = df["shape"] * peak_load_kw * day_multiplier
    return df[["load_kw"]]


if __name__ == "__main__":
    # quick self-test with example assumptions
    profile = generate_year_profile(
        peak_load_kw=33,        # e.g. 80 stalls x 0.35 kW + fixed loads
        open_hour=6,
        close_hour=19,
        covered_market=True,
        market_days=[0, 1, 2, 3, 4, 5],  # closed Sundays
        periods_days=365,
    )
    print(profile.describe())
    print("Total annual energy (kWh):", round(profile["load_kw"].sum(), 0))
