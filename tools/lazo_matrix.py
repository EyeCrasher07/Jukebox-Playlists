#!/usr/bin/env python3
"""Verify the published LazoDiscs combinations against unchanged playlist JARs."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from generate import ROOT
from lazo_deps import pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eula-file', required=True, type=Path)
    parser.add_argument('--java-path', action='append', default=[])
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--target', action='append')
    parser.add_argument('--exclude', action='append', default=[])
    args = parser.parse_args()
    if not args.eula_file.is_file() or 'eula=true' not in args.eula_file.read_text().lower():
        parser.error('An existing accepted Minecraft EULA file is required')
    matrix = json.loads((ROOT / 'versions.json').read_text())
    targets = {t['id']: t for t in matrix['targets']}
    pending = []
    for pin in pins():
        key = pin['target']
        if key in args.exclude or (args.target and key not in args.target):
            continue
        target = targets[key]
        release = ROOT / 'dist' / target['loader'] / f"jukebox-playlists-{key}-{matrix['mod_version']}.jar"
        digest = hashlib.sha256(release.read_bytes()).hexdigest()
        kind = 'lazo_dependency_runtime' if pin.get('dependency_patch') else 'lazo_runtime'
        path = ROOT / 'build/results' / (key + '-' + kind + '.json')
        result = json.loads(path.read_text())['result'] if path.exists() else {}
        dependency_ok = True
        if pin.get('dependency_patch'):
            expected = ROOT / 'build/compat-deps' / pin['dependency_patch']['filename']
            dependency_ok = expected.is_file() and any(d.get('sha256') == hashlib.sha256(expected.read_bytes()).hexdigest() for d in result.get('dependencies', []))
        if not (result.get('success') and result.get('sha256') == digest and result.get('audio_verified') and dependency_ok):
            pending.append(key)
    print(f'Pending LazoDiscs integration checks: {len(pending)}', flush=True)

    def run(key):
        command = [sys.executable, str(ROOT / 'tools/lazo_test.py'), '--target', key,
                   '--eula-file', str(args.eula_file.resolve())]
        for path in args.java_path:
            command += ['--java-path', path]
        if args.offline:
            command.append('--offline')
        return key, subprocess.run(command, cwd=ROOT).returncode == 0

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(run, key) for key in pending]
        for job in as_completed(jobs):
            key, success = job.result()
            if not success:
                failed.append(key)
    if failed:
        raise SystemExit('Failed LazoDiscs checks: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
