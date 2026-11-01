#!/usr/bin/env python3
"""v103 independent inspection quality gate: client-visible evidence only."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOTS = frozenset(('Workspace', 'PlayerGui', 'ReplicatedStorage', 'Players'))
SEGMENT = re.compile(r'^[A-Za-z0-9_ .:-]{1,80}$')
CLASSES = frozenset(('TextLabel', 'TextButton', 'ImageButton', 'TextBox', 'IntValue', 'NumberValue', 'BoolValue', 'StringValue', 'ProximityPrompt', 'ClickDetector', 'Tool', 'ScreenGui'))

def normalize_path(path):
    if isinstance(path, str):
        parts = path.split('.')
        if parts and parts[0] == 'game':
            parts = parts[1:]
    elif isinstance(path, list):
        parts = path
    else:
        return None
    if not 2 <= len(parts) <= 12 or parts[0] not in ROOTS:
        return None
    if any(not isinstance(p, str) or not SEGMENT.fullmatch(p) for p in parts):
        return None
    return parts

def inspect(source, place_id):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError('invalid place ID')
    if isinstance(source, list):
        rows = source
    elif isinstance(source, dict):
        rows = next((source[k] for k in ('observations', 'objects', 'instances', 'entries') if isinstance(source.get(k), list)), None)
    else:
        rows = None
    if rows is None:
        raise ValueError('no supported object collection')
    counts = Counter()
    selected = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            counts['invalid_record'] += 1
            continue
        path = normalize_path(row.get('path', row.get('fullName', row.get('fullPath'))))
        if path is None:
            counts['invalid_path'] += 1
            continue
        cls = row.get('className', row.get('class'))
        if not isinstance(cls, str) or cls not in CLASSES:
            counts['unsupported_class'] += 1
            continue
        key = tuple(path)
        if key in seen:
            counts['duplicate_path'] += 1
            continue
        seen.add(key)
        selected.append({'path': path, 'className': cls, 'evidence': 'client_visible_instance', 'canAutomate': False})
    selected.sort(key=lambda item: (item['path'], item['className']))
    return {'schemaVersion': '103.quality', 'placeId': place_id, 'inputCount': len(rows),
            'acceptedCount': len(selected), 'rejectedCount': sum(counts.values()),
            'rejections': dict(sorted(counts.items())), 'objects': selected,
            'verifiedInGame': False, 'gameplayFunctionsGenerated': 0}

def emit(source, place_id, output):
    report = inspect(source, place_id)
    data = (json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {'output': str(output), 'sha256': hashlib.sha256(data).hexdigest(), 'accepted': report['acceptedCount'], 'verifiedInGame': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspection', type=Path, required=True)
    parser.add_argument('--place-id', type=int, required=True)
    parser.add_argument('--output', type=Path, default=Path('build/inspection-quality-v103.json'))
    args = parser.parse_args()
    source = json.loads(args.inspection.read_text(encoding='utf-8-sig'))
    print(json.dumps(emit(source, args.place_id, args.output)))

if __name__ == '__main__':
    main()
