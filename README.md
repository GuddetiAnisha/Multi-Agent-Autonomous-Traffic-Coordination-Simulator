# Traffic Coordination Laboratory

Python + Mesa 3.3.1 simulator with a native desktop dashboard, three coordination policies, repeatable experiments, CSV exports and tests.

## Install and run

Requires Python 3.11+ with Tk support. From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
traffic-dashboard
```

On macOS/Linux use `source .venv/bin/activate`; Linux may need `python3-tk`. Alternatively run `python -m traffic_sim.dashboard`. This is a local desktop application. In constrained environments, set OPENBLAS_NUM_THREADS to 1 if numerical libraries report allocation errors.

Edit fleet size, strategy, delay, service time or seed, then Apply / Reset. Run advances ten simulation seconds per real second. Pause, step, inspect queues and occupancy, or export live-run CSVs. Compare runs all strategies at delays 0/2/5s with seeds 11/22/33, 300s warm-up and 900s observation, using the active fleet and service settings.

## Experiments

```powershell
python -m traffic_sim.cli run --strategy broker --delay 2 --steps 1800 --warmup 300 --output results/single
python -m traffic_sim.cli compare --delays 0 2 5 10 --seeds 11 22 33 44 55 --steps 1800 --warmup 300 --output results/comparison
python -m unittest discover -s tests -v
```

Single runs export run.csv and timeseries.csv. Comparisons export runs.csv, summary.csv (mean and sample standard deviation), and experiment.json. Seeds and per-vehicle/per-resource/per-visit service draws are paired across policies. Standard deviations are not confidence intervals. See example-results for an executed comparison and requirements-lock.txt for validated dependencies.

## Model

One tick equals one second. A fixed closed fleet follows directed routes. Trucks start empty, load, traverse two shared intersections, unload and return. Manual vehicles share the intersections and recirculate along the perimeter. Initial releases are staggered over seven seconds.

Logistics, Transit and Production zones contain two one-vehicle intersections, two two-slot service bays and capacity-limited roads. Truck travel takes 5-6s per road, 3-4s per intersection, and service_seconds plus 0-1s per bay. Manual travel adds 1-4s to base durations and one second of reaction time per request.

This is a resource-level simulation. Queues are unlimited off-road buffers; vehicles release a resource before requesting the next, so hold-and-wait deadlock is excluded. Road slots have no continuous positions or car-following. Zones affect handover messages, without aggregate zone capacity limits. Map routes are schematic.

| Policy | Admission rule | Communication |
|---|---|---|
| Local priority | Manual, then loaded trucks; 30s age bands override priority | No network dependence |
| Centralized | Age plus 8s loaded-truck bonus; maximum two grants network-wide per tick | Request/reply, twice one-way delay |
| Broker / mediator | Age + loaded bonus + upstream pressure - downstream pressure; independent resource grants | Round trip within zone, extra round trip for handover |

All share a capacity safety interlock. Brokers are a queue-based heuristic represented by arbitration and handover rules, not separate Mesa agents or an optimizer. Delay determines grant eligibility; queues are read at arbitration time. Packet loss, stale telemetry, timeouts, bandwidth and faults are not modeled. Message counts represent logical protocol messages per request. The central grant budget is a modeling assumption, configurable through Config.central_grants_per_tick.

## Metrics

- Waiting vehicle-seconds: total communication and resource waiting; also divided by fleet size.
- Mean/p95 admission wait: seconds per admitted request. Pending requests are censored; total waiting includes their ongoing waits. Only the observation part of waits crossing warm-up counts.
- Throughput: completed unloads per observed hour. Manual passages are separate.
- Conflicts: competing intersection request pairs summed each second. Persistent pairs count repeatedly. This is contention exposure, not collisions or physical near misses.
- Queue: current, time-average and peak released vehicles awaiting resources.
- Utilization: occupied slot-seconds divided by capacity times observation duration, per resource and capacity-weighted overall.
- Messages: request/reply/handover messages issued during observation.

Warm-up resets measurements while preserving traffic and pending communication state. Unloads completed during observation count even if loading occurred in warm-up. Mesa DataCollector stores model metrics; model.history stores full exports.

## Research scope

This is a thesis starting point, not a validated CAVE reproduction. No thesis text, facility layout or calibration data was provided. Findings depend on this synthetic network and these policy definitions. Calibrate service/travel distributions, validate queue assumptions, test dispatch capacity and fleet mix, assess warm-up/convergence, and use more paired replications with uncertainty analysis before drawing thesis conclusions. No policy is assumed to win.

Extend resources and vehicle routes together for another layout, _request for communication changes, and _rank for policy changes. Config controls fleet, service, delay, seed and dispatch budget. Tests cover capacity, deterministic replay, latency, warm-up invariance, fleet edge cases and exports.

Mesa API reference: https://mesa.readthedocs.io/stable/mesa.html . The code uses Model, Agent and DataCollector and pins Mesa 3.3.1; Mesa 4 requires API review.


## Reinforcement-learning and explainability extension

A small software-only reinforcement-learning extension has been added to support experiments with human-centred explainability.

### What it adds

- a compact tabular Q-learning traffic controller
- synthetic state features for queue pressure, congestion, and resource load
- a discrete action space for traffic-control decisions
- reproducible training with fixed random seeds
- feature-importance explanations based on local perturbation of the selected action value
- temporal-outcome explanations that summarise predicted short-horizon consequences
- a simple comparison format for four study conditions:
  - no explanation
  - feature importance only
  - temporal outcome only
  - temporal outcome + feature importance
- automated Pytest validation
- a runnable demonstration script

### Why this extension is useful

The purpose is not to claim a production-ready RL controller. It provides a compact experimental platform for comparing explanation styles around sequential decisions and for prototyping user-study infrastructure.

### Run the demo

```bash
python rl_explainability_demo.py
```

### Run the tests

```bash
pytest -q tests/test_rl_explainability.py
```

### CV-safe description

- Extended the traffic simulator with a software-only tabular Q-learning controller for sequential traffic decisions and reproducible policy experiments.
- Added human-readable feature-importance and short-horizon temporal-outcome explanations to support comparison of different explanation conditions for agent decisions.
