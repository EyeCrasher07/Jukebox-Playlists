#!/usr/bin/env python3
"""Run each not-yet-verified loader/version inside an isolated Minecraft server."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eula-file', required=True, type=Path)
    parser.add_argument('--java-path', action='append', default=[])
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if not args.eula_file.is_file() or 'eula=true' not in args.eula_file.read_text().splitlines():
        parser.error('An existing accepted Minecraft EULA file is required')
    targets = json.loads((ROOT / 'versions.json').read_text())['targets']
    pending = []
    for target in targets:
        result = ROOT / 'build/results' / (target['id'] + '-runtime.json')
        if not result.is_file() or not json.loads(result.read_text())['result']['success']:
            pending.append(target['id'])
    print(f'Pending server runtime checks: {len(pending)}/{len(targets)}', flush=True)

    def run(target):
        command = [sys.executable, str(ROOT / 'tools/build.py'), '--target', target,
                   '--smoke', '--eula-file', str(args.eula_file.resolve())]
        for path in args.java_path:
            command += ['--java-path', path]
        if args.offline:
            command += ['--offline']
        return target, subprocess.run(command, cwd=ROOT).returncode == 0

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(run, target) for target in pending]
        for job in as_completed(jobs):
            target, success = job.result()
            if not success:
                failed.append(target)
    subprocess.run([sys.executable, str(ROOT / 'tools/report.py')], cwd=ROOT, check=True)
    if failed:
        raise SystemExit('Failed runtime checks: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
