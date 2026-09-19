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
    initial_soc_frac: float = 0.5,
) -> pd.DataFrame:
    """
    Run an hourly greedy dispatch simulation.

    Parameters
    ----------
    load_kw : hourly load series (kW), any length, regular hourly index
    pv_gen_kw : hourly PV generation series (kW), same length/index as load_kw
    battery_capacity_kwh : usable battery energy capacity
    battery_power_kw : max charge/discharge power
    round_trip_efficiency : battery round-trip efficiency (0-1);
                             applied as sqrt(eff) on each direction
    initial_soc_frac : starting state of charge as a fraction of capacity

    Returns
    -------
    pd.DataFrame with columns:
        load_kw, pv_gen_kw, soc_kwh, battery_charge_kw, battery_discharge_kw,
        grid_import_kw, curtailed_kw
    """
    assert len(load_kw) == len(pv_gen_kw), "load and PV series must be the same length"

    n = len(load_kw)
    one_way_eff = np.sqrt(round_trip_efficiency)

    soc = np.zeros(n)
    charge = np.zeros(n)
    discharge = np.zeros(n)
    grid_import = np.zeros(n)
    curtailed = np.zeros(n)

    current_soc = initial_soc_frac * battery_capacity_kwh
    load_arr = load_kw.to_numpy()
    pv_arr = pv_gen_kw.to_numpy()

    for t in range(n):
        net = pv_arr[t] - load_arr[t]  # positive = surplus, negative = deficit

        if net >= 0:
            # surplus PV: charge battery first, curtail the rest
            room_kwh = battery_capacity_kwh - current_soc
            max_charge_kw = min(battery_power_kw, room_kwh / one_way_eff)
            charge_kw = min(net, max_charge_kw)
            current_soc += charge_kw * one_way_eff
            curtailed[t] = net - charge_kw
            charge[t] = charge_kw
        else:
            # deficit: discharge battery to cover it
            deficit_kw = -net
            available_kwh = current_soc
            max_discharge_kw = min(battery_power_kw, available_kwh * one_way_eff)
            discharge_kw = min(deficit_kw, max_discharge_kw)
            current_soc -= discharge_kw / one_way_eff
            grid_import[t] = deficit_kw - discharge_kw
            discharge[t] = discharge_kw

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
    """Compute headline KPIs from a simulate_pv_battery() output."""
    total_load = sim_df["load_kw"].sum()
    total_grid_import = sim_df["grid_import_kw"].sum()
    total_pv_gen = sim_df["pv_gen_kw"].sum()
    total_curtailed = sim_df["curtailed_kw"].sum()

    served_by_renewables = total_load - total_grid_import
    renewable_fraction = served_by_renewables / total_load if total_load > 0 else np.nan
    curtailment_fraction = total_curtailed / total_pv_gen if total_pv_gen > 0 else 0.0

    return {
        "total_load_kwh": total_load,
        "total_pv_generation_kwh": total_pv_gen,
        "total_grid_import_kwh": total_grid_import,
        "total_curtailed_kwh": total_curtailed,
        "renewable_fraction": renewable_fraction,
        "curtailment_fraction": curtailment_fraction,
    }


def sensitivity_sweep(
    load_kw: pd.Series,
    pv_gen_per_kwp: pd.Series,
    pv_sizes_kwp: list,
    battery_sizes_kwh: list,
    battery_power_ratio: float = 0.5,
    round_trip_efficiency: float = 0.90,
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
