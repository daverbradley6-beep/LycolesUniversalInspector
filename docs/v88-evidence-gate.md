# v88: cross-session evidence gate

The v87 report provides grouped counts but **cannot** reconstruct independent events. v88 needs raw `LYCOLES_V87_EVENT` lines from each capture.

## Run

```powershell
py tools/evidence_gate_v88.py --place-id 85896571713843 --event-log results-v87-test2.txt --output build/release-v88
```

For the required independent second capture, run the v87 recorder again, perform five E hatches and five W controls, and save the console's `LYCOLES_V87_EVENT` lines as `results-v87-test3.txt`. Then:

```powershell
py tools/evidence_gate_v88.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v88
```

The resulting `build/release-v88/evidence-gate-v88.json` contains counts per capture, Wilson confidence intervals, control comparisons, and a review-only action specification.

A passing gate is **not** causal proof, Roblox execution verification, or an automatic gameplay script. An action implementation requires a supported, authorized execution adapter; no Roblox remote discovery, remote invocation, anti-ban bypass, or input injection is performed.

Run unit tests:

```powershell
py -m unittest discover -s tests -p test_evidence_gate_v88.py -v
```
