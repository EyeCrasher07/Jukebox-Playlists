#!/usr/bin/env python3
"""Build the public loader/version projects with bounded concurrency."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import sys
import time

from generate import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', action='append')
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--java-path', action='append', default=[])
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--detach', action='store_true')
    args = parser.parse_args()
    if args.detach:
        folder = ROOT / 'build/supervisors'
        folder.mkdir(parents=True, exist_ok=True)
        log = folder / ('build-' + time.strftime('%Y%m%d-%H%M%S') + '.log')
        with log.open('w') as output:
            child = subprocess.Popen([sys.executable, str(ROOT / 'tools/build_matrix.py'), *[a for a in sys.argv[1:] if a != '--detach']], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        log.with_suffix('.pid').write_text(str(child.pid) + '\n')
        print('Build supervisor PID ' + str(child.pid) + '; log ' + str(log.relative_to(ROOT)))
        return
    targets = [t['id'] for t in json.loads((ROOT / 'versions.json').read_text())['targets'] if not args.target or t['id'] in args.target]
    if args.target and len(targets) != len(set(args.target)):
        parser.error('Unknown target')
    def run(key):
        command = [sys.executable, str(ROOT / 'tools/build.py'), '--target', key]
        for path in args.java_path:
            command += ['--java-path', path]
        if args.offline:
            command.append('--offline')
        return key, subprocess.run(command, cwd=ROOT).returncode
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        failures = [key for key, result in pool.map(run, targets) if result]
    if failures:
        raise SystemExit('Failed builds: ' + ', '.join(failures))
    print('Built ' + str(len(targets)) + ' public projects', flush=True)


if __name__ == '__main__':
    main()
