#!/usr/bin/env python3
"""v105 independent verifier and quality gate for v104 observation releases."""
import argparse
import hashlib
import json
from pathlib import Path

FILES = ('report-v104.json', 'LycolesObserverV104.client.lua')

def verify(directory, minimum=1, maximum_rejection_rate=0.5):
    if type(minimum) is not int or minimum < 0:
        raise ValueError('minimum must be a nonnegative integer')
    if not isinstance(maximum_rejection_rate, (int, float)) or isinstance(maximum_rejection_rate, bool) or not 0 <= maximum_rejection_rate <= 1:
        raise ValueError('invalid rejection threshold')
    root = Path(directory)
    issues = []
    try:
        paths = [root / n for n in (*FILES, 'manifest-v104.json')]
        if any(p.is_symlink() or not p.is_file() for p in paths):
            raise ValueError('missing or symlinked release file')
        manifest = json.loads(paths[2].read_text(encoding='utf-8'))
        report = json.loads(paths[0].read_text(encoding='utf-8'))
        if manifest.get('schemaVersion') != '104.manifest' or set(manifest.get('files', {})) != set(FILES):
            issues.append('manifest_schema')
        for name in FILES:
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest.get('files', {}).get(name):
                issues.append('hash_mismatch:' + name)
        if report.get('schemaVersion') != '104.release' or report.get('placeId') != manifest.get('placeId'):
            issues.append('report_schema_or_place')
        if report.get('readOnly') is not True or report.get('verifiedInGame') is not False or report.get('gameplayFunctionsGenerated') != 0:
            issues.append('unsupported_verification_claim')
        if manifest.get('readOnly') is not True or manifest.get('verifiedInGame') is not False:
            issues.append('manifest_claim')
        accepted, rejected, total = (report.get(k) for k in ('acceptedCount', 'rejectedCount', 'inputCount'))
        if any(type(n) is not int or n < 0 for n in (accepted, rejected, total)) or accepted + rejected != total:
            issues.append('invalid_accounting')
        elif accepted < minimum:
            issues.append('insufficient_observations')
        elif total and rejected / total > maximum_rejection_rate:
            issues.append('excessive_rejections')
        objects = report.get('objects')
        if not isinstance(objects, list) or len(objects) != accepted:
            issues.append('object_count_mismatch')
        else:
            for obj in objects:
                if not isinstance(obj, dict) or obj.get('canAutomate') is not False:
                    issues.append('unsupported_action_claim')
                    break
        if not issues:
            from release_pipeline_v104 import canonical, luau
            if paths[0].read_bytes() != canonical(report) or paths[1].read_bytes() != luau(report).encode('utf-8'):
                issues.append('not_reproducible')
    except (OSError, ValueError, TypeError, KeyError, ImportError, AttributeError) as exc:
        issues.append('verification_error:' + type(exc).__name__)
    return {'schemaVersion': '105.gate', 'ok': not issues, 'issues': sorted(set(issues)), 'verifiedInGame': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--minimum', type=int, default=1)
    p.add_argument('--max-rejection-rate', type=float, default=0.5)
    args = p.parse_args()
    result = verify(args.directory, args.minimum, args.max_rejection_rate)
    print(json.dumps(result, sort_keys=True))
    if not result['ok']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
