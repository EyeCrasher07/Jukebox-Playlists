#!/usr/bin/env python3
"""Compare release packaging with the archived JARs used in gameplay checks."""
import argparse
import datetime
import hashlib
import io
import json
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LICENSES = {
    'LICENSE_jukebox-playlists.txt': 'LICENSE',
    'COPYING_GPL-3.0.txt': 'COPYING',
    'NOTICE_jukebox-playlists.txt': 'NOTICE',
}


def gameplay_metadata(data, fabric, expected_version):
    metadata = json.loads(data) if fabric else tomllib.loads(data.decode())
    if fabric:
        assert metadata.pop('version') == expected_version, 'Unexpected Fabric mod version'
    else:
        assert len(metadata['mods']) == 1, 'Unexpected mod list'
        assert metadata['mods'][0].pop('version') == expected_version, 'Unexpected Forge/NeoForge mod version'
    for name in (('license', 'authors', 'contact') if fabric else ('license', 'issueTrackerURL')):
        metadata.pop(name, None)
    if not fabric:
        for mod in metadata['mods']:
            mod.pop('authors', None)
            mod.pop('displayURL', None)
    return metadata


def compare(target, baseline, previous_release, previous_version, release_version):
    receipt = json.loads((ROOT / 'build/results' / (target['id'] + '-build.json')).read_text())['result']
    path = ROOT / receipt['artifact']
    current = path.read_bytes()
    digest = hashlib.sha256(current).hexdigest()
    assert receipt['success'] and digest == receipt['sha256'], 'Stale build receipt: ' + target['id']
    previous = baseline.read(previous_release['file'])
    assert hashlib.sha256(previous).hexdigest() == previous_release['sha256'], 'Stale baseline manifest: ' + target['id']
    fabric = target['loader'] == 'fabric'
    with zipfile.ZipFile(io.BytesIO(previous)) as old, zipfile.ZipFile(io.BytesIO(current)) as new:
        old_names = {n for n in old.namelist() if not n.endswith('/')}
        new_names = {n for n in new.namelist() if not n.endswith('/')}
        assert old_names <= new_names, 'Removed entries: ' + target['id']
        assert new_names - old_names == set(LICENSES), 'Unexpected new entries: ' + target['id']
        metadata = 'fabric.mod.json' if fabric else next(n for n in old_names if n.endswith('mods.toml'))
        assert gameplay_metadata(old.read(metadata), fabric, previous_version) == gameplay_metadata(new.read(metadata), fabric, release_version), 'Changed loader/dependency metadata: ' + target['id']
        payload = hashlib.sha256()
        classes = 0
        for name in sorted(old_names - {metadata}):
            content = old.read(name)
            assert content == new.read(name), 'Changed runtime entry: ' + target['id'] + '/' + name
            payload.update(name.encode() + b'\0' + hashlib.sha256(content).digest())
            classes += name.endswith('.class')
        assert classes > 0, 'No classes compared: ' + target['id']
        for member, source in LICENSES.items():
            assert new.read(member) == (ROOT / source).read_bytes(), 'Wrong license: ' + target['id']
    return {
        'success': True,
        'artifact': receipt['artifact'],
        'sha256': digest,
        'tested_baseline_sha256': hashlib.sha256(previous).hexdigest(),
        'runtime_payload_sha256': payload.hexdigest(),
        'unchanged_class_count': classes,
        'changed_entries': sorted([metadata, *LICENSES]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True, help='Archived all.zip used for earlier gameplay checks')
    parser.add_argument('--baseline-sha256', required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
    if digest != args.baseline_sha256:
        parser.error('Baseline archive does not match its expected SHA-256')
    matrix = json.loads((ROOT / 'versions.json').read_text())
    results = {}
    with zipfile.ZipFile(args.baseline) as baseline:
        manifest = json.loads(baseline.read('manifest.json'))
        previous_releases = {r['id']: r for r in manifest['releases']}
        assert set(previous_releases) == {t['id'] for t in matrix['targets']}, 'Different target matrix in baseline'
        for target in matrix['targets']:
            result = compare(target, baseline, previous_releases[target['id']], manifest['version'], matrix['mod_version'])
            result['baseline_archive_sha256'] = digest
            results[target['id']] = result
    # Write receipts only after every target passed the comparison.
    for target, result in results.items():
        (ROOT / 'build/results' / (target + '-packaging.json')).write_text(json.dumps({
            'target': target, 'kind': 'packaging', 'result': result,
        }, indent=2) + '\n')
    (ROOT / 'docs/PACKAGING-VERIFICATION.json').write_text(json.dumps({
        'version': matrix['mod_version'],
        'verified_at': datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'),
        'baseline_archive_sha256': digest,
        'scope': 'Identical classes and runtime resources; only release version, license, author and contact metadata changed.',
        'targets': results,
    }, indent=2) + '\n')
    print(f'Verified {len(results)} release JARs: every class and runtime resource matches the gameplay-tested baseline.')


if __name__ == '__main__':
    main()
