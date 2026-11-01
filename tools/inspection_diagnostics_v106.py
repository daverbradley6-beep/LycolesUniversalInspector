"""Deterministic, read-only inspection diagnostics for Lycoles releases."""
from collections import Counter
import json

ROOTS = frozenset({'Workspace', 'PlayerGui', 'ReplicatedStorage', 'Players'})
from feature_planner_v106 import SUPPORTED as KNOWN

def analyze(report, plan):
    if not isinstance(report, dict) or not isinstance(plan, dict):
        raise ValueError('expected report and plan dictionaries')
    if report.get('schemaVersion') != '104.release' or plan.get('schemaVersion') != '106.feature-plan':
        raise ValueError('unsupported schema')
    if report.get('placeId') != plan.get('placeId'):
        raise ValueError('place mismatch')
    objects, features, unsupported = report.get('objects'), plan.get('features'), plan.get('unsupported')
    if not all(isinstance(v, list) for v in (objects, features, unsupported)):
        raise ValueError('invalid collection')
    if len(objects) != len(features) + len(unsupported):
        raise ValueError('feature accounting mismatch')
    expected = []
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise ValueError('invalid object')
        path, cls = obj.get('path'), obj.get('className')
        if not isinstance(path, list) or not 2 <= len(path) <= 12 or path[0] not in ROOTS or not all(isinstance(p, str) and p and len(p) <= 80 for p in path):
            raise ValueError('invalid object path')
        if cls in KNOWN and obj.get('property') == KNOWN[cls]:
            expected.append((index, obj))
    if len(expected) != len(features):
        raise ValueError('unsupported feature classification')
    for (index, obj), feature in zip(expected, features):
        if not isinstance(feature, dict) or feature.get('id') != f'observe_{index:04d}' or feature.get('path') != obj['path'] or feature.get('property') != obj['property'] or feature.get('kind') != 'read_property':
            raise ValueError('feature mapping mismatch')
    if report.get('readOnly') is not True or report.get('verifiedInGame') is not False or plan.get('runtimeVerified') is not False:
        raise ValueError('unsupported runtime claim')
    classes = Counter(obj['className'] for obj in objects)
    return {
        'schemaVersion': '106.inspection-diagnostics',
        'placeId': report['placeId'],
        'observations': len(objects),
        'supportedControls': len(features),
        'unsupportedObservations': len(unsupported),
        'coverage': round(len(features) / len(objects), 6) if objects else 0,
        'classCounts': dict(sorted(classes.items())),
        'runtimeVerified': False,
        'gameplayVerified': False,
    }

def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + '\n'
