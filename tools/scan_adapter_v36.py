#!/usr/bin/env python3
"""v36: adapt verified multipart scan records to the v35 bridge input.

Read-only, offline. A complete scan is required; no gameplay is executed.
"""
import argparse
import importlib.util
import json
import pathlib

VERSION = '36.0'

def load_compiler(root):
    path = pathlib.Path(root) / 'tools' / 'compile_scan.py'
    spec = importlib.util.spec_from_file_location('lycoles_scan_compiler_v36', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def adapt_parts(parts_dir, compiler):
    """Use the existing integrity validator before extracting object evidence."""
    plan = compiler.compile_scan(parts_dir)
    integrity = plan['integrity']
    place, scan = integrity['placeId'], integrity['scanId']
    files = sorted(pathlib.Path(parts_dir).glob('*.json'))
    by_index = {}
    for path in files:
        if path.stat().st_size > 3_000_000:
            raise ValueError('Oversized scan part')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or not isinstance(data.get('objects'), list):
            continue
        index = data.get('partIndex')
        if index not in by_index:
            by_index[index] = data
    objects = []
    for index in range(1, integrity['parts'] + 1):
        for obj in by_index[index]['objects']:
            path = obj.get('path')
            if not isinstance(path, str) or not path:
                raise ValueError('Missing object path')
            objects.append({'path': path,
                            'name': obj.get('name') if isinstance(obj.get('name'), str) else path.rsplit('.', 1)[-1],
                            'className': obj.get('class', obj.get('className')),
                            'scanOrdinal': obj.get('scanOrdinal')})
    if len(objects) != integrity['objects']:
        raise ValueError('Object accounting changed after validation')
    return {'schemaVersion': VERSION, 'source': 'verified-multipart-scan-adapter',
            'placeId': place, 'scanId': scan, 'objects': objects,
            'integrity': integrity,
            'runtimeVerified': False, 'serverOutcomeVerified': False,
            'notice': 'Client-visible scan evidence only; not proof of gameplay behavior'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parts_dir', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path, default=pathlib.Path('build/scan-objects-v36.json'))
    args = parser.parse_args()
    report = adapt_parts(args.parts_dir, load_compiler(pathlib.Path(__file__).resolve().parents[1]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Verified', report['integrity']['parts'], 'parts and', len(report['objects']), 'objects')

if __name__ == '__main__':
    main()
