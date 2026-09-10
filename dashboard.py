"""Native desktop dashboard; the displayed state comes directly from Mesa."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from collections import Counter
from dataclasses import asdict
import threading
import queue
from .model import Config, TrafficModel, STRATEGIES
from .cli import write_csv, experiment

BG = "#0c1421"
PANEL = "#131f30"
TEXT = "#e5edf6"
MUTED = "#92a6bd"
TEAL = "#48d8c0"
AMBER = "#ffbc68"

class Dashboard:
    def __init__(self, root):
        self.root = root
        root.title("CAVE | Traffic coordination laboratory")
        root.geometry("1360x900")
        root.minsize(1100, 760)
        root.configure(bg=BG)
        self.running = False
        self.results_queue = queue.Queue()
        self.model = TrafficModel()
        self.variables = {}
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", background="#243851", foreground=TEXT, padding=(12, 8), borderwidth=0)
        style.map("TButton", background=[("active", "#355272")])
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=28)
        style.configure("Treeview.Heading", background="#243851", foreground=TEXT)
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=25, pady=(20, 12))
        tk.Label(header, text="CAVE / TRAFFIC LAB", bg=BG, fg=TEAL, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(header, text="Autonomous traffic coordination", bg=BG, fg=TEXT, font=("Segoe UI", 23, "bold")).pack(side="left")
        self.clock = tk.Label(header, text="", bg=BG, fg=MUTED, font=("Consolas", 12))
        self.clock.pack(side="right")
        controls = tk.Frame(root, bg=PANEL, padx=16, pady=12)
        controls.pack(fill="x", padx=25)
        for label, key, value, options in [
            ("Coordination", "strategy", "broker", STRATEGIES),
            ("Trucks", "trucks", "18", None), ("Manual", "manual_vehicles", "8", None),
            ("Delay / s", "communication_delay", "2", None), ("Seed", "seed", "42", None),
            ("Bay service / s", "service_seconds", "12", None),
        ]:
            box = tk.Frame(controls, bg=PANEL)
            box.pack(side="left", padx=(0, 14))
            tk.Label(box, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            var = tk.StringVar(value=value)
            self.variables[key] = var
            if options:
                ttk.Combobox(box, textvariable=var, values=options, state="readonly", width=13).pack()
            else:
                tk.Entry(box, textvariable=var, width=7, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11)).pack(ipady=3)
        ttk.Button(controls, text="Apply / Reset", command=self.reset).pack(side="left", padx=5)
        self.play = ttk.Button(controls, text="Run", command=self.toggle)
        self.play.pack(side="left", padx=5)
        ttk.Button(controls, text="+1 second", command=self.single_step).pack(side="left", padx=5)
        cards = tk.Frame(root, bg=BG)
        cards.pack(fill="x", padx=25, pady=14)
        self.cards = {}
        for label in ["Deliveries / hour", "Mean admission wait", "Current queue", "Conflict pair-seconds", "Resource utilization"]:
            box = tk.Frame(cards, bg=PANEL, padx=16, pady=10)
            box.pack(side="left", expand=True, fill="both", padx=(0, 7))
            tk.Label(box, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
            value = tk.Label(box, text="0", bg=PANEL, fg=TEXT, font=("Segoe UI", 22, "bold"))
            value.pack(anchor="w")
            self.cards[label] = value
        self.canvas = tk.Canvas(root, bg=PANEL, height=370, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=25)
        self.canvas.bind("<Configure>", lambda _: self.draw())
        legend = tk.Frame(root, bg=BG)
        legend.pack(fill="x", padx=25, pady=8)
        tk.Label(legend, text="TEAL  autonomous truck     AMBER  manual vehicle     Dots = occupying resource     Q = off-road queue", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        ttk.Button(legend, text="Export live run", command=self.export).pack(side="right")
        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill="x", padx=25, pady=(0, 10))
        self.chart = tk.Canvas(bottom, bg=PANEL, width=360, height=145, highlightthickness=0)
        self.chart.pack(side="left", fill="both", expand=True, padx=(0, 12))
        comparison = tk.Frame(bottom, bg=PANEL, padx=12, pady=8)
        comparison.pack(side="right", fill="both", expand=True)
        self.compare_button = ttk.Button(comparison, text="Compare strategies + delays (3 seeds)", command=self.compare)
        self.compare_button.pack(anchor="w", pady=(0, 7))
        self.table = ttk.Treeview(comparison, columns=("strategy", "delay", "flow", "wait"), show="headings", height=3)
        for key, title, width in [("strategy", "Strategy", 110), ("delay", "Delay / s", 70), ("flow", "Deliveries / h", 115), ("wait", "Wait / s", 90)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(comparison, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Ready. Edit parameters, then Apply / Reset. Each tick represents one second.")
        tk.Label(root, textvariable=self.status, bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 10)).pack(fill="x", padx=25, pady=(0, 12))
        self.refresh()
        root.after(100, self.loop)

    def config(self):
        values = {key: var.get() if key == "strategy" else int(var.get()) for key, var in self.variables.items()}
        config = Config(**values)
        if config.trucks + config.manual_vehicles > 500:
            raise ValueError("Dashboard supports up to 500 vehicles; use the CLI for larger fleets")
        return config

    def reset(self):
        try:
            config = self.config()
        except ValueError as exc:
            messagebox.showerror("Check parameters", str(exc))
            return
        self.running = False
        self.play.configure(text="Run")
        self.model = TrafficModel(config)
        self.status.set(f"New {config.strategy} scenario. One-way communication delay: {config.communication_delay}s.")
        self.refresh()

    def toggle(self):
        self.running = not self.running
        self.play.configure(text="Pause" if self.running else "Run")

    def single_step(self):
        self.running = False
        self.play.configure(text="Run")
        self.model.step()
        self.refresh()

    def loop(self):
        if self.running:
            self.model.step()
            self.refresh()
        try:
            result, folder, error = self.results_queue.get_nowait()
            self.compare_button.configure(state="normal")
            if error:
                self.status.set(f"Comparison failed: {error}")
            else:
                self.table.delete(*self.table.get_children())
                for r in result:
                    self.table.insert("", "end", values=(r["strategy"], r["communication_delay"], f"{r['throughput_per_hour_mean']:.1f}", f"{r['mean_admission_wait_mean']:.1f}"))
                self.status.set(f"Comparison complete: 27 runs, 300s warm-up + 900s observation. Saved to {folder}")
        except queue.Empty:
            pass
        self.root.after(100, self.loop)

    def refresh(self):
        m = self.model.metrics()
        values = [f"{m['throughput_per_hour']:.0f}", f"{m['mean_admission_wait']:.1f} s", str(m["queue_length"]),
                  f"{m['conflict_pair_seconds']:,}", f"{m['resource_utilization']:.0%}"]
        for label, value in zip(self.cards.values(), values):
            label.configure(text=value)
        self.clock.configure(text=f"{self.model.config.strategy.upper()}  |  T + {self.model.tick:05d} s")
        self.draw()
        self.chart.delete("all")
        self.chart.create_text(16, 16, anchor="w", text="QUEUE LENGTH / last 180 seconds", fill=MUTED, font=("Segoe UI", 9))
        history = self.model.history[-180:]
        width = max(300, self.chart.winfo_width())
        if len(history) > 1:
            maximum = max(1, max(r["queue_length"] for r in history))
            points = []
            for i, row in enumerate(history):
                points.extend([16 + i / (len(history)-1) * (width-36), 125 - row["queue_length"] / maximum * 80])
            self.chart.create_line(*points, fill=TEAL, width=2)
            self.chart.create_text(width-18, 30, anchor="e", text=f"max {maximum}", fill=MUTED)

    def draw(self):
        c = self.canvas
        c.delete("all")
        sx = max(1, c.winfo_width()) / 1120
        sy = max(1, c.winfo_height()) / 540
        def line(a, b, color="#30475e", width=8):
            c.create_line(a[0]*sx, a[1]*sy, b[0]*sx, b[1]*sy, fill=color, width=width, arrow="last")
        for x1, x2, title, color in [(25, 325, "01  LOGISTICS", "#122d35"), (345, 775, "02  TRANSIT", "#1b293e"), (795, 1095, "03  PRODUCTION", "#2a2733")]:
            c.create_rectangle(x1*sx, 12*sy, x2*sx, 520*sy, fill=color, outline="")
            c.create_text((x1+18)*sx, 500*sy, text=title, fill=MUTED, anchor="w", font=("Segoe UI", 10, "bold"))
        resources = self.model.resources
        edges = set()
        for route in (["load", "west", "junction_a", "cross", "junction_b", "east", "unload", "return"], ["gate", "junction_a", "cross", "junction_b", "exit", "outer"]):
            for a, b in zip(route, route[1:] + route[:1]):
                edges.add((a, b))
        for a, b in sorted(edges):
            ra, rb = resources[a], resources[b]
            line((ra.x, ra.y), (rb.x, rb.y))
        occupancy = Counter(v.target for v in self.model.fleet if v.active)
        waiting = Counter(v.target for v in self.model.fleet if not v.active and v.release_at <= self.model.tick)
        for r in resources.values():
            x, y = r.x*sx, r.y*sy
            color = TEAL if occupancy[r.name] else "#52718b"
            c.create_rectangle(x-39*sx, y-23*sy, x+39*sx, y+23*sy, fill=PANEL, outline=color, width=2)
            title = r.name.replace("junction_", "JCT ").replace("_", " ").upper()
            c.create_text(x, y-38*sy, text=title, fill=TEXT, font=("Segoe UI", 9, "bold"))
            c.create_text(x, y+39*sy, text=f"{occupancy[r.name]}/{r.capacity}   Q {waiting[r.name]}", fill=MUTED, font=("Consolas", 9))
            agents = [v for v in self.model.fleet if v.active and v.target == r.name]
            for i, v in enumerate(agents):
                px = x + ((i % 4)-1.5)*14*sx
                py = y + (i//4)*12*sy - 5*sy
                c.create_oval(px-4, py-4, px+4, py+4, fill=TEAL if v.autonomous else AMBER, outline="")

    def export(self):
        if not self.model.history:
            messagebox.showinfo("No observations", "Run at least one simulation step before exporting.")
            return
        folder = filedialog.askdirectory(title="Save live run")
        if folder:
            write_csv(Path(folder)/"timeseries.csv", self.model.history)
            write_csv(Path(folder)/"run.csv", [{**asdict(self.model.config), "steps": self.model.observed_ticks, **self.model.metrics()}])
            self.status.set(f"Live run exported to {folder}")

    def compare(self):
        folder = filedialog.askdirectory(title="Save experiment results")
        if not folder:
            return
        config = self.model.config
        self.compare_button.configure(state="disabled")
        self.status.set("Comparing active scenario across all strategies, delays 0/2/5s, and seeds 11/22/33...")
        def worker():
            try:
                rows = experiment(config, [0, 2, 5], [11, 22, 33], 900, 300, folder)
                self.results_queue.put((rows, folder, None))
            except Exception as exc:
                self.results_queue.put((None, folder, str(exc)))
        threading.Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    Dashboard(root)
    root.mainloop()

if __name__ == "__main__":
    main()
