#!/usr/bin/env python3
"""v36: evidence match retaining duplicate object paths and scan ordinals."""
import argparse
import collections
import json
import pathlib

def match(features, scan, audit=None):
    if features.get('schemaVersion') != '32.0' or scan.get('schemaVersion') != '36.0':
        raise ValueError('Expected v32 features and v36 scan')
    if not scan.get('integrity', {}).get('scanComplete'):
        raise ValueError('Incomplete scan')
    objects = scan.get('objects')
    if not isinstance(objects, list) or len(objects) > 2000000:
        raise ValueError('Invalid object list')
    by_path = collections.defaultdict(list)
    by_name = collections.defaultdict(list)
    for obj in objects:
        if not isinstance(obj, dict) or not isinstance(obj.get('path'), str):
            raise ValueError('Invalid object')
        by_path[obj['path']].append(obj)
        by_name[obj.get('name')].append(obj)
    verified = {}
    if audit is not None:
        if audit.get('schemaVersion') != '34.0':
            raise ValueError('Invalid lexical audit')
        verified = {x['featureId']: x.get('status') for x in audit.get('features', [])}
    results = []
    for f in features.get('features', []):
        dep = f.get('dependencies') or {}
        required = sorted(set(dep.get('paths') or []))
        lookups = sorted(set(dep.get('lookups') or []))
        exact = [p for p in required if len(by_path[p]) == 1]
        ambiguous = {p: len(by_path[p]) for p in required if len(by_path[p]) > 1}
        missing = [p for p in required if not by_path[p]]
        status = ('no-path-evidence' if not required else
                  'unique-paths-observed' if not ambiguous and not missing else
                  'ambiguous-paths' if ambiguous else
                  'partial' if exact else 'missing')
        results.append({'featureId': f.get('id'), 'name': f.get('name'),
                        'status': status, 'uniquePaths': exact,
                        'ambiguousPaths': ambiguous, 'missingPaths': missing,
                        'nameHints': {n: len(by_name[n]) for n in lookups if by_name[n]},
                        'lexicalStatus': verified.get(f.get('id'), 'not-checked'),
                        'reviewed': False, 'runtimeVerified': False,
                        'serverOutcomeVerified': False})
    return {'schemaVersion': '36.0', 'source': 'multipart-feature-evidence-match',
            'placeId': scan['placeId'], 'scanId': scan['scanId'],
            'featureCount': len(results), 'features': results,
            'pathCollisions': sum(len(v) - 1 for v in by_path.values()),
            'gameplayAutomationApproved': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('features', type=pathlib.Path)
    p.add_argument('scan', type=pathlib.Path)
    p.add_argument('--audit', type=pathlib.Path)
    p.add_argument('--output', type=pathlib.Path, default=pathlib.Path('build/feature-match-v36.json'))
    a = p.parse_args()
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    result = match(read(a.features), read(a.scan), read(a.audit) if a.audit else None)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Matched', result['featureCount'], 'features; path collisions:', result['pathCollisions'])

if __name__ == '__main__':
    main()
