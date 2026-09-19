# SolarMarket-Sizer

**Renewable Energy Sizing & Sensitivity Analysis for an Urban Market**

A small, self-contained study that sizes a PV + battery system against the
estimated electricity demand of an urban market, and quantifies the
tradeoff between system size, renewable energy fraction, and rough capex.

Built as an independent project sitting at the intersection of **renewable
energy systems** and **urban infrastructure planning** — the overlap
between Erasmus Mundus programmes like RESCO (Renewable Energy and
Sustainable Construction) and SMACCs (Smart Cities and Communities, which
covers Energy, Transport, Buildings, ICT, and Urban Planning as core
pillars).

## What this project does

1. **Estimates market electricity demand** as an hourly profile, built from
   explicit, stated assumptions (number of stalls, load per stall, fixed
   loads, operating hours) — not real metered data, which isn't publicly
   available for markets at this granularity.
2. **Pulls real solar resource data** from [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/en/)
   (the European Commission's free Photovoltaic Geographical Information
   System) for a chosen location.
3. **Simulates a PV + battery dispatch strategy** hour by hour: serve load
   from PV first, charge the battery with surplus, discharge to cover
   deficits, and track unmet demand (grid import) and curtailment.
4. **Sweeps across PV and battery sizes** to show how renewable fraction
   and estimated cost change with system size.
5. **Identifies two candidate systems** — a cost-efficient pick (best
   renewable-fraction gain per €1,000 spent, above a minimum viability
   floor) and a renewable-maximizing pick (highest achievable renewable
   fraction in the sweep) — rather than forcing a single fixed target,
   since a naive "hit 75% renewable" goal may not be reachable at all
   once nighttime/off-hours demand is accounted for.

## Project structure

```
SolarMarket-Sizer/
├── README.md
├── requirements.txt
├── src/
│   ├── load_profile.py    # synthetic hourly market demand generator
│   ├── pvgis.py            # PVGIS API wrapper + CSV parser
│   └── battery_model.py    # dispatch simulation + sensitivity sweep
├── notebooks/
│   └── SolarMarket_Sizer.ipynb   # main analysis, run top to bottom
├── data/                    # place manually-downloaded PVGIS CSVs here (gitignored)
└── outputs/                 # generated plots/results land here (gitignored)
```

## How to run it

```bash
git clone <your-repo-url>
cd SolarMarket-Sizer
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
jupyter notebook notebooks/SolarMarket_Sizer.ipynb
```

Update the site coordinates and market assumptions in **Section 1** of the
notebook, then run all cells. If you don't have live internet access to
`re.jrc.ec.europa.eu`, download the hourly CSV manually from the
[PVGIS web tool](https://re.jrc.ec.europa.eu/pvg_tools/en/) for your
coordinates, save it to `data/pvgis_raw.csv`, and use `load_pvgis_csv()`
instead of `fetch_pvgis_hourly()` (both are shown in the notebook).

## Methodology & key assumptions

| Component | Approach | Why |
|---|---|---|
| Load profile | Synthetic hourly shape from stated stall count, load-per-stall, and operating hours | No public dataset of real market electricity demand exists at hourly resolution; a transparent estimate is more honest than fabricating false precision |
| Solar resource | PVGIS satellite-derived hourly irradiance/PV output for a chosen year and location | Free, no API key, no scraping, widely used in industry and academic feasibility studies |
| Dispatch strategy | Greedy rule-based (PV → battery → grid), not an optimizer | Sufficient to compare system sizes and demonstrate tradeoffs; a full optimal dispatch controller (e.g. MILP-based) is out of scope for this timeframe |
| Battery model | Simple state-of-charge tracking with round-trip efficiency, no degradation | Keeps the model tractable; degradation/cycling effects are noted as future work |
| Cost figures | Placeholder €/kWp and €/kWh figures in the notebook | **Must be updated** with current benchmark costs (e.g. IRENA, NREL cost reports) before citing capex results anywhere formal |
| System recommendation | Two picks (cost-efficient vs. renewable-maximizing) instead of one fixed target | Battery storage adds essentially no value below a PV-size threshold (nothing to charge from), and renewable fraction plateaus well short of 100% due to nighttime/off-hours demand — a single target obscures this tradeoff |

## Known limitations / explicit scope cuts

This project was deliberately scoped down to be finishable in a few days
rather than attempting a full smart-city energy system:

- **No siting/GIS analysis** — roof area, shading, and grid connection
  feasibility are not modeled. A logical next step would be a QGIS-based
  siting study.
- **No demand forecasting/ML** — the load profile is a static estimated
  shape, not learned from historical data or weather-correlated.
- **Single representative year** of PVGIS data, not a multi-year
  variability/resilience analysis.
- **No real-time control or IoT layer** — this is a planning-stage sizing
  tool, not an operational energy management system.

These are natural directions to extend the project, and are called out
here on purpose to be transparent about what this analysis can and can't
support.

## Data & attribution

- Solar resource and PV output data: [PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en),
  © European Union, Joint Research Centre.
- All other data (market load profile, cost placeholders) are stated
  assumptions for illustrative/academic purposes, not measured values.

## License

MIT — see below. Adapt freely for your own coursework, portfolio, or
research.

```
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```
