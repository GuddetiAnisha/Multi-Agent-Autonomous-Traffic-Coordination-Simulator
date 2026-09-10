# Validation

Validated with Python 3.12 and Mesa 3.3.1 in the supplied environment.

- All 9 automated model tests passed.
- The command-line single-run path executed and exported scenario metrics and a time series.
- A 60-run comparison completed: 3 strategies, 4 delays, 5 paired seeds, with 300 seconds warm-up and 1,800 seconds observation per run.
- All Python source files compiled successfully.
- Results are saved in example-results, including per-run data, grouped means and standard deviations, configuration, findings and comparison charts.

## Desktop interface limitation

The dashboard source is implemented and compiles, but its live behavior could not be validated in this environment. The supplied Python runtime's Tk initialization fails with `Can't find a usable init.tcl`, even though its Tcl support files exist. Use a standard Python installation with functioning Tk support to launch the dashboard. The simulation and experiment runner do not require Tk.

## Scope

Conflicts measure competing intersection request pairs, not physical collisions. The safety interlock enforces resource capacity. This is a synthetic resource-level model with unlimited off-resource queues; it has not been calibrated against a CAVE facility dataset. See README.md for policy assumptions and metric definitions.
