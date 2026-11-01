#!/usr/bin/env python3
"""v62 evidence pipeline: loss-tolerant console importer and conservative capability catalog.

This tool does not invoke remotes or infer server-side action contracts from names.
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

MARK = "LYCOLES_V54_BATCH "
START = "LYCOLES_V54_BATCH_STREAM_BEGIN "
HEADER = "LYCOLES_V54_BATCH_BEGIN "
END = "LYCOLES_V54_BATCH_END "
ROOTS = ("Workspace", "Players", "ReplicatedStorage", "ReplicatedFirst",
         "Lighting", "StarterGui", "StarterPack", "StarterPlayer", "SoundService", "Teams")
KINDS = {"Tool": "standard_tool", "ProximityPrompt": "proximity_prompt",
         "ClickDetector": "click_detector", "TextButton": "gui_control",
         "ImageButton": "gui_control", "RemoteEvent": "remote_observed",
         "RemoteFunction": "remote_observed", "BindableEvent": "bindable_observed",
         "BindableFunction": "bindable_observed"}
MAX_FILE = 50_000_000
MAX_LINE = 250_000

def import_console(text):
    if not isinstance(text, str):
        raise TypeError("Console text required")
    place = None
    expected_samples = None
    headers, batches, ends, conflicts, warnings = {}, defaultdict(dict), set(), [], []
    inferred_counts = {}
    for line_no, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_LINE:
            warnings.append(f"line {line_no}: oversized; skipped")
            continue
        if START in line:
            match = re.search(re.escape(START) + r"(\d+)\s+(\d+)", line)
            if match:
                next_place, next_samples = map(int, match.groups())
                if place is not None and (place, expected_samples) != (next_place, next_samples):
                    conflicts.append(f"line {line_no}: conflicting stream header")
                else:
                    place, expected_samples = next_place, next_samples
        elif HEADER in line:
            match = re.search(re.escape(HEADER) + r"(\d+)\s+(\d+)", line)
            if match:
                index, total = map(int, match.groups())
                if 1 <= index <= 24 and 1 <= total <= 1000:
                    if index in headers and headers[index] != total:
                        conflicts.append(f"sample {index}: conflicting batch count")
                    headers[index] = total
        elif MARK in line:
            payload = line.split(MARK, 1)[1]
            match = re.match(r"(\d+)/(\d+)/(\d+)\s+(.*)", payload)
            if not match:
                warnings.append(f"line {line_no}: malformed batch")
                continue
            i, j, n = map(int, match.groups()[:3])
            if not (1 <= i <= 24 and 1 <= j <= n <= 1000):
                warnings.append(f"line {line_no}: invalid batch index")
                continue
            try:
                record = json.loads(match.group(4))
                if not isinstance(record, dict) or record.get("index") != i or not isinstance(record.get("entries"), list):
                    raise ValueError("invalid batch contents")
            except (ValueError, TypeError):
                warnings.append(f"line {line_no}: invalid JSON")
                continue
            if i in inferred_counts and inferred_counts[i] != n:
                conflicts.append(f"sample {i}: conflicting inferred batch totals")
            inferred_counts[i] = n
            if j in batches[i] and batches[i][j] != record:
                conflicts.append(f"sample {i} batch {j}: conflicting duplicates")
            else:
                batches[i][j] = record
        elif END in line:
            match = re.search(re.escape(END) + r"(\d+)", line)
            if match:
                ends.add(int(match.group(1)))
    if conflicts:
        raise ValueError("; ".join(conflicts[:10]))
    samples = []
    missing = {}
    for index in sorted(set(headers) | set(batches) | ends):
        expected = headers.get(index, inferred_counts.get(index))
        parts = batches[index]
        if expected is None:
            missing[str(index)] = {"reason": "missing_begin", "received": len(parts)}
            continue
        gaps = [j for j in range(1, expected + 1) if j not in parts]
        if gaps or index not in ends or index not in headers:
            missing[str(index)] = {"missingBatches": gaps, "hasEnd": index in ends,
                                   "missingBegin": index not in headers,
                                   "received": len(parts), "expected": expected}
        entries = []
        for j in sorted(parts):
            if j <= expected:
                entries.extend(parts[j]["entries"])
        samples.append({"index": index, "complete": not gaps and index in ends and index in headers,
                        "entries": entries, "receivedBatches": len(parts), "expectedBatches": expected})
    return {"schemaVersion": "62.partial", "placeId": place,
            "expectedSamples": expected_samples, "samples": samples,
            "completeSamples": sum(s["complete"] for s in samples),
            "missing": missing, "warnings": warnings[:200],
            "streamEndSeen": "LYCOLES_V54_BATCH_STREAM_END" in text,
            "placeIdSource": "stream_header" if place is not None else "missing",
            "recoveredPartialBatches": sum(len(batches[i]) for i in batches if i not in headers)}

def catalog(receipt):
    observations = defaultdict(list)
    for sample in receipt["samples"]:
        for entry in sample["entries"]:
            if not isinstance(entry, dict):
                continue
            path, cls = entry.get("path"), entry.get("className")
            if not isinstance(path, str) or not path or not isinstance(cls, str):
                continue
            if not any(path == r or path.startswith(r + "/") for r in ROOTS):
                continue
            observations[(path, cls)].append((sample["index"], entry.get("value")))
    items = []
    for (path, cls), events in observations.items():
        if cls not in KINDS and not cls.endswith("Value"):
            continue
        values = [str(v) for _, v in events if v is not None]
        unique = list(dict.fromkeys(values))
        kind = KINDS.get(cls, "observable_value")
        # GUI, remote, bindable and tool names are never evidence of successful action.
        items.append({"path": path, "className": cls, "kind": kind,
                      "samplesObserved": sorted({i for i, _ in events}),
                      "valueChanged": len(unique) > 1,
                      "valuesPreview": unique[:3],
                      "actionStatus": "unverified",
                      "serverOutcomeVerified": False,
                      "causalityVerified": False,
                      "requires": "authorized action contract and independent outcome verification"
                          if kind != "observable_value" else "read-only observation"})
    items.sort(key=lambda x: (x["kind"], x["path"]))
    return {"schemaVersion": "62.catalog", "placeId": receipt["placeId"],
            "sourceComplete": bool(receipt["streamEndSeen"] and
              receipt["expectedSamples"] and receipt["completeSamples"] == receipt["expectedSamples"]),
            "countsByKind": dict(Counter(x["kind"] for x in items)),
            "capabilities": items, "actionContractsGenerated": 0,
            "notes": ["Names and stat changes do not establish callable server actions.",
                      "Partial evidence is retained and explicitly marked incomplete."]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--console", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/release-v62"))
    parser.add_argument("--place-id", type=int)
    args = parser.parse_args()
    if args.console.stat().st_size > MAX_FILE:
        parser.error("console file exceeds 50 MB")
    receipt = import_console(args.console.read_text(encoding="utf-8-sig", errors="replace"))
    if args.place_id is not None and receipt["placeId"] not in (None, args.place_id):
        parser.error("place ID mismatch")
    result = catalog(receipt)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("partial-receipt-v62.json", receipt), ("capability-catalog-v62.json", result)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v62 imported", len(receipt["samples"]), "samples;",
          receipt["completeSamples"], "complete;", len(result["capabilities"]), "capabilities;",
          "full stream" if result["sourceComplete"] else "partial stream")

if __name__ == "__main__":
    main()
