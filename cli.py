"""Reproducible paired experiments with CSV and JSON exports."""
import argparse
import csv
import json
import statistics
from dataclasses import asdict
from pathlib import Path
from .model import Config, TrafficModel, STRATEGIES


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def experiment(config, delays, seeds, steps, warmup, output):
    output = Path(output)
    rows = []
    for strategy in STRATEGIES:
        for delay in delays:
            for seed in seeds:
                values = {**asdict(config), "strategy": strategy, "communication_delay": delay, "seed": seed}
                model = TrafficModel(Config(**values))
                rows.append(model.run(steps, warmup))
    write_csv(output / "runs.csv", rows)
    summary = []
    metrics = list(TrafficModel(config).metrics())
    for strategy in STRATEGIES:
        for delay in delays:
            group = [r for r in rows if r["strategy"] == strategy and r["communication_delay"] == delay]
            item = {"strategy": strategy, "communication_delay": delay, "replications": len(group)}
            for metric in metrics:
                values = [r[metric] for r in group]
                item[metric + "_mean"] = statistics.mean(values)
                item[metric + "_sd"] = statistics.stdev(values) if len(values) > 1 else 0
            summary.append(item)
    write_csv(output / "summary.csv", summary)
    output.mkdir(parents=True, exist_ok=True)
    (output / "experiment.json").write_text(json.dumps({"config": asdict(config), "delays": delays, "seeds": seeds,
        "steps": steps, "warmup": warmup, "mesa": "3.3.1", "time_unit": "second"}, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["run", "compare", "dashboard"], nargs="?", default="dashboard")
    parser.add_argument("--strategy", choices=STRATEGIES, default="broker")
    parser.add_argument("--trucks", type=int, default=18)
    parser.add_argument("--manual", type=int, default=8)
    parser.add_argument("--delay", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=1800)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--delays", type=int, nargs="+", default=[0, 2, 5, 10])
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 22, 33, 44, 55])
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    if args.mode == "dashboard":
        from .dashboard import main as dashboard
        dashboard()
        return
    try:
        config = Config(strategy=args.strategy, trucks=args.trucks, manual_vehicles=args.manual,
                        communication_delay=args.delay, seed=args.seed)
        if args.steps < 1 or args.warmup < 0 or min(args.delays) < 0 or min(args.seeds) < 0:
            raise ValueError("Invalid step, warmup, delay or seed value")
        if args.mode == "compare":
            rows = experiment(config, sorted(set(args.delays)), sorted(set(args.seeds)), args.steps, args.warmup, args.output)
            for r in rows:
                print(f"{r['strategy']:12} delay={r['communication_delay']:2} throughput={r['throughput_per_hour_mean']:.1f}/h wait={r['mean_admission_wait_mean']:.1f}s")
        else:
            model = TrafficModel(config)
            result = model.run(args.steps, args.warmup)
            write_csv(args.output / "timeseries.csv", model.history)
            write_csv(args.output / "run.csv", [result])
            print(json.dumps(result, indent=2))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
