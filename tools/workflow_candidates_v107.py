"""Derive deterministic review-only workflow candidates from observed interactions."""

MAX_EVENTS = 2000
MAX_CHANGES = 24
SCHEMA = "107.workflow-candidates.1"


def _text(value, limit=240):
    return isinstance(value, str) and 0 < len(value) <= limit and all(ord(c) >= 32 for c in value)


def _scalar(value):
    return type(value) in (int, float, str, bool) and len(str(value)) <= 120


def _changes(item):
    raw = item.get("stateChanges")
    if not isinstance(raw, list):
        raw = item.get("guiStateChanges")
    if not isinstance(raw, list):
        return []
    result = []
    for delta in raw[:MAX_CHANGES]:
        if not isinstance(delta, dict):
            continue
        key = delta.get("key") or delta.get("path")
        before = delta.get("before")
        after = delta.get("after")
        if not _text(key, 200) or not _scalar(before) or not _scalar(after):
            continue
        result.append({"key": key, "before": before, "after": after})
    return result


def _normalize_history(history):
    if not isinstance(history, list) or len(history) > MAX_EVENTS:
        raise ValueError("invalid observed interaction history")
    events = []
    rejected = 0
    for index, item in enumerate(history):
        if not isinstance(item, dict):
            rejected += 1
            continue
        path = item.get("path")
        if not _text(path, 400):
            rejected += 1
            continue
        sequence = item.get("sequence") if type(item.get("sequence")) is int else (
            item.get("eventIndex") if type(item.get("eventIndex")) is int else index + 1
        )
        transaction = item.get("transactionId")
        transaction = str(transaction) if type(transaction) in (int, str) and _text(str(transaction), 80) else f"unlinked-{index+1}"
        feature = item.get("featureCandidate")
        action = item.get("actionCandidate")
        events.append({
            "path": path,
            "sequence": sequence,
            "transactionId": transaction,
            "featureCandidate": feature if _text(feature, 120) else "unattributed",
            "actionCandidate": action if _text(action, 120) else None,
            "stateChanges": _changes(item),
        })
    events.sort(key=lambda event: (event["transactionId"], event["sequence"], event["path"]))
    return events, rejected


def build(report):
    if not isinstance(report, dict) or report.get("schemaVersion") != "104.release":
        raise ValueError("expected v104 release report")
    place_id = report.get("placeId")
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("invalid place ID")
    events, rejected = _normalize_history(report.get("observedInteractionHistory", []))
    grouped = {}
    for event in events:
        grouped.setdefault(event["transactionId"], []).append(event)
    candidates = []
    singleton = 0
    for transaction_id in sorted(grouped):
        steps = sorted(grouped[transaction_id], key=lambda event: (event["sequence"], event["path"]))
        if len(steps) < 2:
            singleton += 1
            continue
        observed_changes = sum(len(step["stateChanges"]) for step in steps)
        completed = observed_changes > 0
        candidate = {
            "id": f"workflow-{len(candidates)+1:04d}",
            "transactionId": transaction_id,
            "featureCandidate": next((step["featureCandidate"] for step in steps if step["featureCandidate"] != "unattributed"), "unattributed"),
            "stepCount": len(steps),
            "observedStateChanges": observed_changes,
            "completedCandidate": completed,
            "steps": [{
                "sequence": step["sequence"],
                "path": step["path"],
                "actionCandidate": step["actionCandidate"],
                "stateChanges": step["stateChanges"],
            } for step in steps],
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
        }
        candidates.append(candidate)
    completed = sum(1 for candidate in candidates if candidate["completedCandidate"])
    return {
        "schemaVersion": SCHEMA,
        "placeId": place_id,
        "observedEvents": len(events),
        "workflowCandidates": candidates,
        "summary": {
            "workflowCandidates": len(candidates),
            "completedCandidates": completed,
            "reviewOnlyCandidates": len(candidates) - completed,
            "singletonTransactions": singleton,
            "rejectedEvents": rejected,
        },
        "runtimeVerified": False,
        "gameplayVerified": False,
        "causalityProven": False,
    }


def validate(document):
    if not isinstance(document, dict) or document.get("schemaVersion") != SCHEMA:
        raise ValueError("invalid workflow candidate schema")
    if type(document.get("placeId")) is not int or document["placeId"] <= 0:
        raise ValueError("invalid workflow place")
    if document.get("runtimeVerified") is not False or document.get("gameplayVerified") is not False or document.get("causalityProven") is not False:
        raise ValueError("invalid workflow verification claim")
    if type(document.get("observedEvents")) is not int or document["observedEvents"] < 0:
        raise ValueError("invalid observed event count")
    summary = document.get("summary")
    candidates = document.get("workflowCandidates")
    if not isinstance(summary, dict) or not isinstance(candidates, list):
        raise ValueError("invalid workflow collections")
    expected_keys = {"workflowCandidates", "completedCandidates", "reviewOnlyCandidates", "singletonTransactions", "rejectedEvents"}
    if set(summary) != expected_keys:
        raise ValueError("invalid workflow summary fields")
    if any(type(summary[key]) is not int or summary[key] < 0 for key in expected_keys):
        raise ValueError("invalid workflow summary counts")
    if summary["workflowCandidates"] != len(candidates):
        raise ValueError("workflow summary mismatch")
    completed = 0
    for index, candidate in enumerate(candidates, 1):
        if not isinstance(candidate, dict):
            raise ValueError("invalid workflow candidate")
        if candidate.get("id") != f"workflow-{index:04d}":
            raise ValueError("invalid workflow identifier")
        if not _text(candidate.get("transactionId"), 80) or not _text(candidate.get("featureCandidate"), 120):
            raise ValueError("invalid workflow identity")
        if type(candidate.get("stepCount")) is not int or candidate["stepCount"] < 2:
            raise ValueError("invalid workflow step count")
        if type(candidate.get("observedStateChanges")) is not int or candidate["observedStateChanges"] < 0:
            raise ValueError("invalid workflow state change count")
        if candidate.get("runtimeVerified") is not False or candidate.get("gameplayVerified") is not False or candidate.get("causalityProven") is not False:
            raise ValueError("invalid workflow candidate claims")
        if type(candidate.get("completedCandidate")) is not bool:
            raise ValueError("invalid completed candidate flag")
        if candidate["completedCandidate"]:
            completed += 1
        steps = candidate.get("steps")
        if not isinstance(steps, list) or len(steps) != candidate["stepCount"]:
            raise ValueError("invalid workflow steps")
        observed_changes = 0
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("invalid workflow step")
            if type(step.get("sequence")) is not int or not _text(step.get("path"), 400):
                raise ValueError("invalid workflow step identity")
            action = step.get("actionCandidate")
            if action is not None and not _text(action, 120):
                raise ValueError("invalid workflow action candidate")
            changes = step.get("stateChanges")
            if not isinstance(changes, list):
                raise ValueError("invalid workflow state changes")
            for delta in changes:
                if not isinstance(delta, dict) or not _text(delta.get("key"), 200) or not _scalar(delta.get("before")) or not _scalar(delta.get("after")):
                    raise ValueError("invalid workflow state change entry")
            observed_changes += len(changes)
        if observed_changes != candidate["observedStateChanges"]:
            raise ValueError("workflow state change mismatch")
    if summary["completedCandidates"] != completed or summary["reviewOnlyCandidates"] != len(candidates) - completed:
        raise ValueError("workflow completion summary mismatch")
    return document
