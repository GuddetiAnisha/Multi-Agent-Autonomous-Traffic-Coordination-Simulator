"""Discrete-time industrial traffic; queues are off-resource holding buffers."""
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
import random
from mesa import Agent, Model
from mesa.datacollection import DataCollector

STRATEGIES = ("local", "centralized", "broker")

@dataclass(frozen=True)
class Config:
    strategy: str = "broker"
    trucks: int = 18
    manual_vehicles: int = 8
    communication_delay: int = 2
    seed: int = 42
    service_seconds: int = 12
    central_grants_per_tick: int = 2

    def __post_init__(self):
        if self.strategy not in STRATEGIES:
            raise ValueError(f"strategy must be one of {STRATEGIES}")
        for name in ("trucks", "manual_vehicles", "communication_delay", "seed", "service_seconds", "central_grants_per_tick"):
            value = getattr(self, name)
            minimum = 1 if name in ("service_seconds", "central_grants_per_tick") else 0
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if self.trucks + self.manual_vehicles < 1:
            raise ValueError("At least one vehicle is required")

@dataclass
class Resource:
    name: str
    zone: str
    kind: str
    x: int
    y: int
    capacity: int = 1
    busy_seconds: int = 0

class Vehicle(Agent):
    def __init__(self, model, index, autonomous):
        super().__init__(model)
        self.index = index
        self.autonomous = autonomous
        self.route = (["load", "west", "junction_a", "cross", "junction_b", "east", "unload", "return"]
                      if autonomous else ["gate", "junction_a", "cross", "junction_b", "exit", "outer"])
        self.leg = 0
        self.remaining = 0
        self.active = False
        self.release_at = index % 7
        self.request_at = None
        self.ready_at = None
        self.wait_seconds = 0
        self.deliveries = 0
        self.visits = Counter()
        self.previous_zone = None

    @property
    def target(self):
        return self.route[self.leg]

    @property
    def loaded(self):
        return self.autonomous and 1 <= self.leg <= 6

    def duration(self):
        r = self.model.resources[self.target]
        # Paired scenarios draw the same service time for each vehicle/visit.
        rng = random.Random(f"{self.model.config.seed}:{self.index}:{self.target}:{self.visits[self.target]}")
        base = self.model.config.service_seconds if r.kind == "bay" else (3 if r.kind == "intersection" else 5)
        return base + (rng.randint(1, 4) if not self.autonomous else rng.randint(0, 1))

class TrafficModel(Model):
    def __init__(self, config=None):
        self.config = config or Config()
        super().__init__(seed=self.config.seed)
        self.tick = 0
        self.observed_ticks = 0
        self.observation_start = 0
        self.resources = {r.name: r for r in [
            Resource("load", "Logistics", "bay", 110, 150, 2),
            Resource("west", "Logistics", "road", 260, 150, 3),
            Resource("junction_a", "Transit", "intersection", 410, 150),
            Resource("cross", "Transit", "road", 560, 150, 3),
            Resource("junction_b", "Transit", "intersection", 710, 150),
            Resource("east", "Production", "road", 860, 150, 3),
            Resource("unload", "Production", "bay", 1010, 150, 2),
            Resource("return", "Logistics", "road", 560, 360, 8),
            Resource("gate", "Transit", "road", 410, 40, 3),
            Resource("exit", "Transit", "road", 710, 270, 3),
            Resource("outer", "Transit", "road", 560, 460, 8),
        ]}
        self.fleet = [Vehicle(self, i, i < self.config.trucks)
                      for i in range(self.config.trucks + self.config.manual_vehicles)]
        self.completed = self.manual_passages = self.wait_total = self.conflicts = 0
        self.messages = self.queue_sum = self.queue_peak = self.grants = 0
        self.admission_waits = []
        self.history = []
        self.datacollector = self._collector()

    def _collector(self):
        return DataCollector(model_reporters={
            "waiting_vehicle_seconds": "wait_total", "deliveries": "completed",
            "conflict_pairs": "conflicts", "queue_length": lambda m: m.queue_length,
            "utilization": lambda m: m.metrics()["resource_utilization"],
        })

    @property
    def queue_length(self):
        return sum(not v.active and v.release_at <= self.tick for v in self.fleet)

    def _request(self, v):
        v.request_at = self.tick
        delay = self.config.communication_delay
        if self.config.strategy == "local":
            latency, messages = 0, 0
        elif self.config.strategy == "centralized":
            latency, messages = 2 * delay, 2
        else:
            cross_zone = v.previous_zone is not None and v.previous_zone != self.resources[v.target].zone
            latency, messages = (4 * delay, 4) if cross_zone else (2 * delay, 2)
        # Roadside gateway represents manual drivers, with one-second reaction time.
        v.ready_at = self.tick + latency + (not v.autonomous)
        self.messages += messages

    def _rank(self, v, queues):
        age = self.tick - v.request_at
        if self.config.strategy == "local":
            return (age // 30, not v.autonomous, v.loaded, age, -v.index)
        if self.config.strategy == "centralized":
            return (age + 8 * v.loaded, -v.index)
        downstream = v.route[(v.leg + 1) % len(v.route)]
        bid = age + 5 * v.loaded + 2 * len(queues[v.target]) - len(queues[downstream])
        return (bid, -v.index)

    def step(self):
        for v in self.fleet:
            if v.active:
                v.remaining -= 1
                if v.remaining == 0:
                    v.active = False
                    if v.target == "unload":
                        self.completed += 1
                        v.deliveries += 1
                    elif v.target == "exit":
                        self.manual_passages += 1
                    v.previous_zone = self.resources[v.target].zone
                    v.leg = (v.leg + 1) % len(v.route)
                    v.request_at = v.ready_at = None
                    v.release_at = self.tick
        queues = defaultdict(list)
        occupied = Counter(v.target for v in self.fleet if v.active)
        for v in self.fleet:
            if not v.active and v.release_at <= self.tick:
                if v.request_at is None:
                    self._request(v)
                queues[v.target].append(v)
        # Exposure counts competing intersection request pairs each second.
        for name, queue in queues.items():
            if self.resources[name].kind == "intersection":
                n = len(queue)
                self.conflicts += n * (n - 1) // 2
        candidates = [v for queue in queues.values() for v in queue if v.ready_at <= self.tick]
        candidates.sort(key=lambda v: self._rank(v, queues), reverse=True)
        budget = self.config.central_grants_per_tick if self.config.strategy == "centralized" else len(candidates)
        for v in candidates:
            if budget and occupied[v.target] < self.resources[v.target].capacity:
                v.active = True
                v.remaining = v.duration()
                v.visits[v.target] += 1
                occupied[v.target] += 1
                self.admission_waits.append(self.tick - max(v.request_at, self.observation_start))
                self.grants += 1
                budget -= 1
        waiting = [v for v in self.fleet if not v.active and v.release_at <= self.tick]
        for v in waiting:
            v.wait_seconds += 1
        self.wait_total += len(waiting)
        self.queue_sum += len(waiting)
        self.queue_peak = max(self.queue_peak, len(waiting))
        for name, n in occupied.items():
            if n > self.resources[name].capacity:
                raise RuntimeError(f"Safety interlock violated at {name}")
            self.resources[name].busy_seconds += n
        self.observed_ticks += 1
        self.datacollector.collect(self)
        self.history.append({"tick": self.tick, **self.metrics()})
        self.tick += 1

    def reset_metrics(self):
        """Begin observation without changing policy state after warm-up."""
        self.observed_ticks = self.completed = self.manual_passages = 0
        self.wait_total = self.conflicts = self.messages = self.queue_sum = self.queue_peak = self.grants = 0
        self.observation_start = self.tick
        self.admission_waits.clear()
        self.history.clear()
        self.datacollector = self._collector()
        for r in self.resources.values():
            r.busy_seconds = 0
        for v in self.fleet:
            v.wait_seconds = 0

    def metrics(self):
        t = max(1, self.observed_ticks)
        samples = sorted(self.admission_waits)
        return {
            "deliveries": self.completed,
            "throughput_per_hour": self.completed * 3600 / t,
            "manual_passages": self.manual_passages,
            "waiting_vehicle_seconds": self.wait_total,
            "mean_wait_per_vehicle": self.wait_total / len(self.fleet),
            "mean_admission_wait": sum(samples) / max(1, len(samples)),
            "p95_admission_wait": samples[min(len(samples)-1, int(.95 * len(samples)))] if samples else 0,
            "conflict_pair_seconds": self.conflicts,
            "queue_length": self.queue_length,
            "mean_queue_length": self.queue_sum / t,
            "peak_queue_length": self.queue_peak,
            "resource_utilization": sum(r.busy_seconds for r in self.resources.values()) / (t * sum(r.capacity for r in self.resources.values())),
            "messages": self.messages,
            **{f"utilization_{r.name}": r.busy_seconds / (t * r.capacity) for r in self.resources.values()},
        }

    def run(self, steps, warmup=0):
        if steps < 1 or warmup < 0:
            raise ValueError("steps must be positive and warmup nonnegative")
        for _ in range(warmup):
            self.step()
        if warmup:
            self.reset_metrics()
        for _ in range(steps):
            self.step()
        return {**asdict(self.config), "steps": steps, "warmup": warmup, **self.metrics()}
