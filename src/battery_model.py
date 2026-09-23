"""
battery_model.py
-----------------
A deliberately simple PV + battery dispatch simulation and sizing
sensitivity sweep. This is NOT an optimal dispatch controller — it's a
greedy, physically sensible rule:

    1. Serve load directly from PV first.
    2. Charge the battery with any PV surplus.
    3. If PV is insufficient, discharge the battery to cover the gap.
    4. Anything still unmet is counted as grid import / unmet demand.
    5. Any PV surplus left after the battery is full is counted as
       curtailed / exported generation.

This is sufficient to compare system sizes and demonstrate the tradeoffs
your program cares about (renewable fraction, self-sufficiency, rough cost).
It intentionally does NOT model battery degradation, variable efficiency
curves, or grid tariffs — note these as simplifications in your writeup.
"""

import numpy as np
import pandas as pd


def simulate_pv_battery(
    load_kw: pd.Series,
    pv_gen_kw: pd.Series,
    battery_capacity_kwh: float,
    battery_power_kw: float,
    round_trip_efficiency: float = 0.90,
    initial_soc_frac: float = 0.50,
    min_soc_frac: float = 0.10,
) -> pd.DataFrame:
    """
    Run an hourly greedy PV + battery dispatch simulation.

    Dispatch priority:
        1. PV serves the load directly.
        2. Surplus PV charges the battery.
        3. Remaining surplus is curtailed.
        4. When PV is insufficient, the battery discharges.
        5. Remaining unmet demand is supplied by the grid.

    Parameters
    ----------
    load_kw : pd.Series
        Hourly electricity demand in kW.

    pv_gen_kw : pd.Series
        Hourly PV generation in kW.

    battery_capacity_kwh : float
        Total usable battery energy capacity in kWh.

    battery_power_kw : float
        Maximum battery charge/discharge power in kW.

    round_trip_efficiency : float, default=0.90
        Battery round-trip efficiency.

    initial_soc_frac : float, default=0.50
        Initial battery state of charge as a fraction of capacity.

    min_soc_frac : float, default=0.10
        Minimum allowable state of charge as a fraction of capacity.

    Returns
    -------
    pd.DataFrame
        Hourly simulation results containing:
        load_kw
        pv_gen_kw
        soc_kwh
        battery_charge_kw
        battery_discharge_kw
        grid_import_kw
        curtailed_kw
    """

    # -----------------------------
    # Input validation
    # -----------------------------

    if not isinstance(load_kw, pd.Series):
        raise TypeError("load_kw must be a pandas Series.")

    if not isinstance(pv_gen_kw, pd.Series):
        raise TypeError("pv_gen_kw must be a pandas Series.")

    if len(load_kw) != len(pv_gen_kw):
        raise ValueError("load and PV series must have the same length.")

    if not load_kw.index.equals(pv_gen_kw.index):
        raise ValueError("load and PV series must have the same index.")

    if battery_capacity_kwh < 0:
        raise ValueError("battery_capacity_kwh must be >= 0.")

    if battery_power_kw < 0:
        raise ValueError("battery_power_kw must be >= 0.")

    if not 0 < round_trip_efficiency <= 1:
        raise ValueError("round_trip_efficiency must be between 0 and 1.")

    if not 0 <= initial_soc_frac <= 1:
        raise ValueError("initial_soc_frac must be between 0 and 1.")

    if not 0 <= min_soc_frac < 1:
        raise ValueError("min_soc_frac must be between 0 and 1.")

    if initial_soc_frac < min_soc_frac:
        raise ValueError(
            "initial_soc_frac cannot be lower than min_soc_frac."
        )

    if (load_kw < 0).any():
        raise ValueError("load_kw cannot contain negative values.")

    if (pv_gen_kw < 0).any():
        raise ValueError("pv_gen_kw cannot contain negative values.")

    # Split round-trip efficiency equally between
    # charging and discharging.
    charge_efficiency = np.sqrt(round_trip_efficiency)
    discharge_efficiency = np.sqrt(round_trip_efficiency)

    n = len(load_kw)

    soc = np.zeros(n)
    charge = np.zeros(n)
    discharge = np.zeros(n)
    grid_import = np.zeros(n)
    curtailed = np.zeros(n)

    load_arr = load_kw.to_numpy(dtype=float)
    pv_arr = pv_gen_kw.to_numpy(dtype=float)

    # Initial state of charge
    current_soc = initial_soc_frac * battery_capacity_kwh

    # Minimum allowable state of charge
    min_soc = min_soc_frac * battery_capacity_kwh

    for t in range(n):

        # Net PV after serving the load
        net = pv_arr[t] - load_arr[t]

        if net >= 0:

            # --------------------------------
            # PV surplus → charge battery
            # --------------------------------

            room_kwh = battery_capacity_kwh - current_soc

            if room_kwh > 0 and battery_power_kw > 0:

                # Maximum PV-side power that can be accepted
                # without exceeding battery capacity.
                max_charge_kw = min(
                    battery_power_kw,
                    room_kwh / charge_efficiency
                )

                charge_kw = min(net, max_charge_kw)

                # Energy actually stored in the battery
                current_soc += charge_kw * charge_efficiency

                charge[t] = charge_kw

                # Any remaining PV is curtailed
                curtailed[t] = net - charge_kw

            else:
                # Battery already full
                curtailed[t] = net

        else:

            # --------------------------------
            # PV deficit → discharge battery
            # --------------------------------

            deficit_kw = -net

            # Energy that can actually be removed from
            # the battery while respecting minimum SOC.
            available_energy_kwh = max(
                0.0,
                current_soc - min_soc
            )

            if available_energy_kwh > 0 and battery_power_kw > 0:

                # Maximum load-side discharge power
                max_discharge_kw = min(
                    battery_power_kw,
                    available_energy_kwh * discharge_efficiency
                )

                discharge_kw = min(
                    deficit_kw,
                    max_discharge_kw
                )

                # Energy removed from battery
                current_soc -= (
                    discharge_kw / discharge_efficiency
                )

                discharge[t] = discharge_kw

                # Remaining demand comes from the grid
                grid_import[t] = deficit_kw - discharge_kw

            else:
                # Battery has reached its minimum SOC
                grid_import[t] = deficit_kw

        # Numerical safety
        current_soc = np.clip(
            current_soc,
            min_soc,
            battery_capacity_kwh
        )

        soc[t] = current_soc

    return pd.DataFrame(
        {
            "load_kw": load_arr,
            "pv_gen_kw": pv_arr,
            "soc_kwh": soc,
            "battery_charge_kw": charge,
            "battery_discharge_kw": discharge,
            "grid_import_kw": grid_import,
            "curtailed_kw": curtailed,
        },
        index=load_kw.index,
    )


def summarize_run(sim_df: pd.DataFrame) -> dict:
    """Compute headline performance metrics from a dispatch simulation."""

    total_load = sim_df["load_kw"].sum()
    total_pv_gen = sim_df["pv_gen_kw"].sum()
    total_grid_import = sim_df["grid_import_kw"].sum()
    total_curtailed = sim_df["curtailed_kw"].sum()
    total_battery_charge = sim_df["battery_charge_kw"].sum()
    total_battery_discharge = sim_df["battery_discharge_kw"].sum()

    # Energy served without grid import
    renewable_served = total_load - total_grid_import

    renewable_fraction = (
        renewable_served / total_load
        if total_load > 0
        else np.nan
    )

    grid_dependency = (
        total_grid_import / total_load
        if total_load > 0
        else np.nan
    )

    curtailment_fraction = (
        total_curtailed / total_pv_gen
        if total_pv_gen > 0
        else 0.0
    )

    # Number of hours where grid import occurs
    shortage_hours = (sim_df["grid_import_kw"] > 1e-9).sum()

    total_hours = len(sim_df)

    loss_of_load_probability = (
        shortage_hours / total_hours
        if total_hours > 0
        else np.nan
    )

    # Maximum continuous period with grid import
    shortage = sim_df["grid_import_kw"] > 1e-9

    groups = shortage.ne(shortage.shift()).cumsum()
    consecutive_shortage_hours = (
        shortage.groupby(groups).sum()
    )

    max_consecutive_shortage_hours = (
        consecutive_shortage_hours.max()
        if len(consecutive_shortage_hours) > 0
        else 0
    )

    return {
        "total_load_kwh": total_load,
        "total_pv_generation_kwh": total_pv_gen,
        "total_grid_import_kwh": total_grid_import,
        "total_curtailed_kwh": total_curtailed,
        "total_battery_charge_kwh": total_battery_charge,
        "total_battery_discharge_kwh": total_battery_discharge,
        "renewable_fraction": renewable_fraction,
        "grid_dependency": grid_dependency,
        "curtailment_fraction": curtailment_fraction,
        "shortage_hours": int(shortage_hours),
        "loss_of_load_probability": loss_of_load_probability,
        "max_consecutive_shortage_hours": int(
            max_consecutive_shortage_hours
        ),
    }
def check_energy_balance(sim_df: pd.DataFrame) -> float:
    """
    Check the hourly energy balance of the dispatch simulation.

    Returns
    -------
    float
        Maximum absolute energy-balance error in kWh.

    The model should approximately satisfy:

        PV + Grid + Battery Discharge
        =
        Load + Battery Charge + Curtailment

    Note:
        Battery charge/discharge columns represent load-side/PV-side
        electrical power flows, while battery SOC accounts for efficiency.
    """

    lhs = (
        sim_df["pv_gen_kw"]
        + sim_df["grid_import_kw"]
        + sim_df["battery_discharge_kw"]
    )

    rhs = (
        sim_df["load_kw"]
        + sim_df["battery_charge_kw"]
        + sim_df["curtailed_kw"]
    )

    error = lhs - rhs

    return float(np.abs(error).max())

def sensitivity_sweep(
    load_kw: pd.Series,
    pv_gen_per_kwp: pd.Series,
    pv_sizes_kwp: list,
    battery_sizes_kwh: list,
    battery_power_ratio: float = 0.5,
    round_trip_efficiency: float = 0.90,
    initial_soc_frac: float = 0.50,
    min_soc_frac: float = 0.10,
    pv_cost_per_kwp: float = 700.0,
    battery_cost_per_kwh: float = 300.0,
) -> pd.DataFrame:
    """
    Sweep across combinations of PV size and battery size, running a full
    simulation for each, and return a tidy results table.

    Parameters
    ----------
    load_kw : hourly load series (kW)
    pv_gen_per_kwp : hourly PV output for a 1 kWp reference system (kW),
                     same length/index as load_kw (scale with scale_pv_output
                     from pvgis.py before calling this, or pass W and divide
                     by 1000 yourself)
    pv_sizes_kwp : list of PV system sizes to test (kWp)
    battery_sizes_kwh : list of battery capacities to test (kWh)
    battery_power_ratio : battery power (kW) as a fraction of its capacity
                          (kWh) — e.g. 0.5 means a 2-hour battery
    pv_cost_per_kwp, battery_cost_per_kwh : rough capex figures (USD or EUR,
                      pick one and be consistent) for the cost estimate.
                      *** UPDATE THESE with current benchmark figures from
                      IRENA / NREL cost reports before citing results ***

    Returns
    -------
    pd.DataFrame, one row per (pv_size, battery_size) combination, with
    KPI columns plus a rough capex estimate.
    """
    results = []
    for pv_kwp in pv_sizes_kwp:
        pv_series = pv_gen_per_kwp * pv_kwp
        for batt_kwh in battery_sizes_kwh:
            batt_kw = batt_kwh * battery_power_ratio
            sim = simulate_pv_battery(
    load_kw=load_kw,
    pv_gen_kw=pv_series,
    battery_capacity_kwh=batt_kwh,
    battery_power_kw=batt_kw,
    round_trip_efficiency=round_trip_efficiency,
    initial_soc_frac=initial_soc_frac,
    min_soc_frac=min_soc_frac,
)
            kpis = summarize_run(sim)
            capex = pv_kwp * pv_cost_per_kwp + batt_kwh * battery_cost_per_kwh
            results.append(
                {
                    "pv_size_kwp": pv_kwp,
                    "battery_size_kwh": batt_kwh,
                    **kpis,
                    "capex_estimate": capex,
                }
            )

    return pd.DataFrame(results)


if __name__ == "__main__":
    # Minimal self-test with synthetic data (no PVGIS call needed)
    idx = pd.date_range("2025-01-01", periods=24 * 7, freq="h")
    rng = np.random.default_rng(42)

    load = pd.Series(10 + 5 * np.sin(np.linspace(0, 14 * np.pi, len(idx))) ** 2, index=idx)
    pv_1kwp = pd.Series(
        np.clip(np.sin(np.linspace(0, 14 * np.pi, len(idx))), 0, None) * 0.8, index=idx
    )

    sweep = sensitivity_sweep(
        load_kw=load,
        pv_gen_per_kwp=pv_1kwp,
        pv_sizes_kwp=[5, 10, 20],
        battery_sizes_kwh=[0, 10, 20],
    )
    print(sweep)
