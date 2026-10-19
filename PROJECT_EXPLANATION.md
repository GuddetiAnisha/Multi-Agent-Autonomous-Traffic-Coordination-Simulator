# Multi-Agent Autonomous Traffic Coordination Simulator — Project Explanation

## 1. Project overview

This is an independent Python-based research and portfolio project for experimenting with how autonomous trucks and manually driven vehicles can share a simulated industrial traffic network. It uses the Mesa agent-based simulation framework to model vehicles, shared road resources, intersection queues and transport operations.

The main project compares three coordination strategies: local priority, centralized control, and broker/mediator coordination. A separate extension introduces a small **tabular Q-learning** controller and explanations of its decisions.

The project is a **synthetic software simulation**, not a deployed vehicle-control system and not an Ericsson or Volvo project. No claim is made that its outputs are validated against a real industrial facility.

## 2. The problem it studies

When multiple vehicles share narrow roads or intersections, they cannot always move at the same time. Some must wait while others use limited-capacity resources. How access is managed affects queue lengths, waiting time, deliveries and congestion.

For example, imagine an autonomous truck transporting goods and a manual vehicle approaching the same single-vehicle intersection. A coordinator needs to decide which request is admitted first. Giving every vehicle immediate access would violate the intersection's capacity. Making all vehicles wait unnecessarily would reduce transport efficiency.

This project creates a controlled way to compare different admission and communication rules.

## 3. Why multi-agent simulation?

In an agent-based simulation, separate entities make requests and change state over time. Instead of calculating only one average traffic value, the model represents vehicles moving through a network of constrained resources.

The simulator uses **Mesa 3.3.1**. Its agents and resources model a closed fleet of trucks and manual vehicles. Trucks follow routes that include loading, travel, unloading and return. Manual vehicles share intersections and recirculate.

A simulation tick corresponds to one second. The map is schematic, not a continuous physical driving environment. Vehicles reserve or request resources rather than following precise geometric positions.

## 4. Main simulated environment

The project describes Logistics, Transit and Production areas, resource-limited roads, intersections and service bays.

Examples of model assumptions include:

- Roads and intersections have finite occupancy capacity.
- Service bays admit a limited number of vehicles simultaneously.
- Vehicles may need to wait for authorization or an available resource.
- Trucks perform repeated transport cycles.
- Manual vehicles have different modeled travel and reaction times.
- Network delays influence policies that use coordinator messages.

Released vehicles may wait in off-road queues. These queues are modeled as unlimited. The model also excludes hold-and-wait deadlock by having vehicles release one resource before requesting the next.

This environment is useful for studying allocation and queuing behavior, but it does not simulate full vehicle dynamics, collision avoidance geometry, physical near misses or car-following.

## 5. The three main coordination policies

### Local priority

Local priority uses predefined admission rules at each resource. Manual vehicles ordinarily receive priority over trucks, while truck load status and aging of queued requests can affect the outcome. This strategy does **not** depend on network communication delays.

It provides a useful simple baseline: vehicles can be managed locally without waiting for a remote coordinator.

### Centralized coordination

A central coordinator considers requests using a scoring rule that accounts for waiting age and gives loaded trucks a bonus. The implementation also limits the total number of central grants per simulation tick.

Request-and-response communication takes time. As modeled network delay increases, vehicle requests may be authorized later, potentially increasing waiting time and lowering throughput.

### Broker / mediator coordination

The broker strategy makes resource-level admission decisions using waiting age, loaded-truck bonuses, upstream queue pressure and downstream queue pressure. It also models extra communication when vehicles cross zone boundaries.

The broker is a **rule-based arbitration heuristic**. It is not an independently trained AI model, a mathematical optimization solver, or a collection of separate Mesa broker agents.

All three policies share capacity constraints.

## 6. Typical simulation workflow

1. Configure fleet size, policy, network delay, service time and random seed.
2. Initialize the virtual vehicles and resources.
3. Vehicles follow defined routes and request access to shared resources.
4. The selected policy decides which eligible requests may proceed.
5. The model advances in one-second steps.
6. Waiting, occupancy, throughput and communication measurements are collected.
7. Results are exported so different policies can be compared under similar conditions.

Using paired random seeds and service-time draws makes policy comparisons more controlled. It does not remove all uncertainty or make the model representative of every real traffic system.

## 7. How performance is measured

| Metric | What it means |
| --- | --- |
| Waiting vehicle-seconds | Total modeled waiting accumulated by vehicles |
| Mean and p95 admission wait | Typical waiting and the longer-wait tail for admitted requests |
| Throughput | Completed truck unload operations per observed hour |
| Conflicts | Competing intersection request pairs, not actual collisions |
| Queue length | How many released vehicles are waiting for resources |
| Utilization | Share of available resource slot-time that is occupied |
| Communication messages | Logical request/reply/handover messages generated |

A warm-up period lets traffic state develop before observation begins. The observation metrics are then recorded separately.

## 8. Results from the repository's documented experiment

The repository's `FINDINGS.md` describes a comparison involving:

- Three strategies
- One-way communication delays of 0, 2, 5 and 10 seconds
- Five paired seeds
- 18 trucks and eight manual vehicles
- 300 seconds of warm-up and 1,800 seconds of observation

That is **60 simulation runs** in total.

The reported mean throughput, in completed deliveries per observed hour, is:

| Policy | 0 s delay | 2 s delay | 5 s delay | 10 s delay |
| --- | ---: | ---: | ---: | ---: |
| Local priority | 495.2 | 495.2 | 495.2 | 495.2 |
| Centralized | 568.8 | 563.6 | 459.6 | 294.0 |
| Broker | 569.2 | 546.8 | 386.0 | 228.4 |

In this particular simulation, local priority throughput does not change with network delay because it does not rely on the communication network. The centralized and broker policies perform similarly without delay, but their throughput falls as delay increases. The broker policy incurs additional communication during zone handovers.

These are **results reported by the repository**, not newly executed experiments. They depend on the specific synthetic assumptions. The README and findings do not claim statistical significance or general superiority of one policy across real environments.

## 9. Is it a machine-learning project?

**Partly, yes.** The core Mesa simulation uses rule-based decision policies. The repository also includes a genuine reinforcement-learning extension based on Q-learning.

It is accurate to describe the overall work as a **multi-agent simulation project with a tabular reinforcement-learning and explainability extension**.

It would be misleading to describe all three main coordination policies as trained ML models or claim that the Q-learning policy has already outperformed them in the full traffic simulator.

## 10. What is reinforcement learning?

Reinforcement learning is a way for an agent to improve sequential decisions using feedback.

The agent observes a state, chooses an action, receives a reward and enters a new state. By repeating this process, it learns which actions tend to produce better long-term outcomes.

For example, a controller may have to choose whether to hold traffic or grant a waiting vehicle access. Reward rules can encourage shorter queues while penalizing congestion or high resource load.

Unlike supervised learning, the Q-learning extension does not learn from a CSV of human-provided correct action labels. It updates its action values from simulated experiences and rewards.

## 11. The tabular Q-learning extension

The file `rl_explainability.py` contains a small independent traffic-control environment and a `QLearningAgent`.

The state has three discrete features:

- `queue_level`: an abstract indication of queue pressure;
- `conflict_level`: an abstract indication of resource contention;
- `utilization_level`: an abstract indication of how heavily resources are used.

Each takes a value from 0 to 2. The available actions are:

- `hold`
- `grant_autonomous`
- `grant_manual`

The environment calculates the next abstract state and reward according to predefined transition formulas. It is a simplified synthetic environment, **not the same environment as the full Mesa fleet model**.

The agent maintains a table of values for state-action pairs and updates them as it trains:

```text
Updated Q = Current Q + alpha × (reward + gamma × best next Q − Current Q)
```

This means the agent gradually adjusts how valuable it thinks each action is in each state.

Its default learning parameters are:

| Setting | Default | Meaning |
| --- | ---: | --- |
| alpha | 0.25 | Learning rate |
| gamma | 0.90 | Weight of future reward |
| epsilon | 0.20 | Chance of trying a random action |
| seed | 7 | Reproducibility setting |

The included demo explicitly trains for **300 episodes** using epsilon 0.25 and a 20-step episode horizon. These demo settings override some constructor defaults.

## 12. Explainable reinforcement learning

A decision-support model is easier to inspect when it can show why an action was chosen and what might happen next.

This extension provides two forms of explanation.

### Feature importance

The program changes one state feature at a time and checks how the selected action's Q-value changes. The differences are normalized to create a local importance summary.

For instance, it can indicate whether changing queue pressure affects the learned action value more than changing utilization.

This is a local perturbation calculation on a simple Q-table, not a formal causal explanation.

### Temporal outcome explanation

The program performs a short simulated rollout: it applies an action, looks at the predicted next state and reward, and then selects subsequent actions using the learned policy.

The output lists predicted future queue, conflict and utilization levels over a small horizon.

These outcomes are based on the simplified environment's transition formulas. They are **model predictions**, not observed real-world consequences.

## 13. Explainability comparison conditions

The extension supplies a structure for comparing four presentation conditions:

1. No explanation
2. Feature importance only
3. Temporal outcomes only
4. Feature importance plus temporal outcomes

These conditions can support a future user study about how people interpret AI-agent decisions. The repository does not establish that any one explanation method improves trust, comprehension or decision quality in a completed human-subject study.

## 14. Run the main simulation in VS Code

Install Python 3.11 or newer, Git and Visual Studio Code. On Windows, use a normal Python installation with working Tk support for the desktop dashboard.

Open a PowerShell terminal:

```powershell
git clone https://github.com/GuddetiAnisha/Multi-Agent-Autonomous-Traffic-Coordination-Simulator.git
cd Multi-Agent-Autonomous-Traffic-Coordination-Simulator
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

The README documents this project as an installable Python package. To start the desktop UI using the project entry point:

```powershell
.\.venv\Scripts\traffic-dashboard.exe
```

If the desktop launcher is unavailable, consult the package entry point and ensure the installation succeeded. On systems with a working Tk installation, you can also use the documented Python module entry point after activating the virtual environment.

The dashboard allows adjustment of fleet size, strategy, delay, service time and seed, along with actions to run, pause, step and compare scenarios.

### Run a single experiment without the dashboard

```powershell
.\.venv\Scripts\python.exe -m traffic_sim.cli run --strategy broker --delay 2 --steps 1800 --warmup 300 --output results/single
```

### Compare coordination policies

```powershell
.\.venv\Scripts\python.exe -m traffic_sim.cli compare --delays 0 2 5 10 --seeds 11 22 33 44 55 --steps 1800 --warmup 300 --output results/comparison
```

The comparison exports `runs.csv`, `summary.csv`, and `experiment.json`. Results contain per-run measurements and aggregate means and sample standard deviations.

## 15. Run the reinforcement-learning demo

The RL extension is a standalone Python module at the repository root. Run:

```powershell
.\.venv\Scripts\python.exe rl_explainability_demo.py
```

The script creates a synthetic environment, trains a Q-learning agent for 300 episodes, and displays the mean reward over the last 50 episodes along with an example chosen action, feature-importance values and short-term predicted outcomes.

To run its dedicated tests, install pytest if needed and execute:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q tests/test_rl_explainability.py
```

For the original simulator tests, use:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The earlier `VALIDATION.md` records nine passing model tests and successful CLI experiments. It also reports that the GUI could not be validated in that environment because of a Tk initialization problem. Do not interpret successful simulation tests as proof that every desktop configuration will work.

## 16. Important source files

| File | Main responsibility |
| --- | --- |
| `model.py` | Core multi-agent traffic and resource simulation |
| `cli.py` | Single and comparison experiment commands |
| `dashboard.py` | Desktop visualization and controls |
| `run_dashboard.py` | Dashboard launcher |
| `rl_explainability.py` | Tabular Q-learning environment, agent and explanation functions |
| `rl_explainability_demo.py` | Standalone RL training and explanation example |
| `tests/` | Automated tests |
| `FINDINGS.md` | Documented comparison results |
| `VALIDATION.md` | Executed checks and known limitations |
| `summary.csv`, `runs.csv` | Stored example comparison data |
| `pyproject.toml` | Python package metadata and entry points |

## 17. Strengths and limitations

**Strengths:** The project supports reproducible experiments, comparative policy analysis, explainable model assumptions, queue/resource measurement and a genuinely trainable tabular RL demonstration. It also distinguishes observations from model assumptions.

**Limitations:** The base simulator is resource-level rather than physically realistic; communication faults and continuous driving behavior are absent; the core policies are hand-written heuristics; and the Q-learning controller currently trains in its own simplified environment rather than operating the full Mesa fleet.

The conflict metric represents competing requests, not collisions. Reported standard deviations are not confidence intervals, and the available results should not be extrapolated to real autonomous transport operations without further modeling and validation.

## 18. Future improvements

A stronger research version could:

- integrate the learned RL policy into the same Mesa resource-allocation interface used by the rule-based policies;
- train and evaluate on separate random seeds and traffic configurations;
- compare RL, local priority, centralized and broker policies with identical metrics;
- introduce variable arrival rates, communication loss, faults and more realistic limits;
- investigate fairness and unusually long vehicle waiting times;
- evaluate multiple reward formulations and explainability methods;
- document model sensitivity and statistical uncertainty;
- validate assumptions against suitable authorized real-world traffic data, if available.

A clear next ML milestone would be to demonstrate that the learned controller works in the full simulation, then measure whether it improves specified metrics without violating capacity constraints.

## 19. Conclusion

The Multi-Agent Autonomous Traffic Coordination Simulator combines agent-based modeling with practical evaluation of resource-allocation rules. It studies how vehicle queues, communication delays and admission policies affect traffic performance in a synthetic network.

The additional Q-learning extension introduces reinforcement learning and interpretable decision summaries, while remaining separate from the main simulator. This distinction matters: the repository demonstrates both multi-agent simulation and an RL prototype, but it does not yet demonstrate a fully integrated learning-based traffic coordination system.

The project is an independent research/portfolio prototype. For implementation details and experiment assumptions, see [README.md](README.md), [FINDINGS.md](FINDINGS.md), and [VALIDATION.md](VALIDATION.md).
