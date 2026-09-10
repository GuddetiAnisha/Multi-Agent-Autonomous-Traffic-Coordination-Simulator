# Executed comparison

60 runs: 3 policies x 4 one-way delays x 5 paired seeds. Each used 18 trucks, 8 manual vehicles, 300 seconds of warm-up and 1,800 seconds of observation.

| Strategy | Delay (s) | Deliveries/hour, mean | Admission wait (s), mean |
|---|---:|---:|---:|
| local | 0 | 495.2 | 8.8 |
| local | 2 | 495.2 | 8.8 |
| local | 5 | 495.2 | 8.8 |
| local | 10 | 495.2 | 8.8 |
| centralized | 0 | 568.8 | 8.1 |
| centralized | 2 | 563.6 | 8.2 |
| centralized | 5 | 459.6 | 11.4 |
| centralized | 10 | 294.0 | 20.9 |
| broker | 0 | 569.2 | 8.0 |
| broker | 2 | 546.8 | 8.4 |
| broker | 5 | 386.0 | 13.5 |
| broker | 10 | 228.4 | 25.6 |

The local policy is unchanged by network delay because it does not use network communication. Centralized and broker coordination have similar zero-delay throughput in this configuration. Broker throughput declines more at higher delay because crossing zone boundaries adds a second round trip. These outcomes follow the specified policies and synthetic network; they do not establish general superiority of any strategy.

See summary.csv for all metrics and sample standard deviations, runs.csv for replications, experiment.json for configuration, and comparison.svg for charts. No confidence intervals or significance claims are made.
