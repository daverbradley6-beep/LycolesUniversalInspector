# v80 independent-session evidence gate

v80 reads v76, v78 and v79 event logs, requires two independent capture IDs with at least two observations each, and checks whether the same state change also appears following other inputs. The default maximum other-input rate is 25%. A candidate requires exactly one consistent signal and observed negative-control inputs. This is a heuristic, **not causal proof**.

```powershell
py tools/contract_gate_v80.py --place-id 85896571713843 --event-log events-v78.txt --output build/release-v80
py -m unittest discover -s tests -p "test_contract_gate_v80.py" -v
```

For multiple recording sessions, add `--event-log other-session.txt`. Outputs: `evidence-gate-v80.json`, `action-drafts-v80.json`, and `warnings-v80.json`. All drafts require manual review; no gameplay execution or anti-ban bypass is generated. The validator cannot establish whether observations are independent in time, only whether capture IDs differ. Python tests cannot prove live Roblox compatibility.
