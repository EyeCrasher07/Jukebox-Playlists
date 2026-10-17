#!/usr/bin/env python3
"""Run the six supported windowed client regression scenarios sequentially."""
import argparse
import hashlib
import json
import subprocess
import sys
import time

from generate import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-path', action='append', default=[])
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--detach', action='store_true', help='Keep the test supervisor independent of the interactive tool session')
    args = parser.parse_args()
    if args.detach:
        folder = ROOT / 'build/supervisors'
        folder.mkdir(parents=True, exist_ok=True)
        log = folder / ('clients-' + time.strftime('%Y%m%d-%H%M%S') + '.log')
        with log.open('w') as output:
            child = subprocess.Popen([sys.executable, str(ROOT / 'tools/client_matrix.py'), *[a for a in sys.argv[1:] if a != '--detach']], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        log.with_suffix('.pid').write_text(str(child.pid) + '\n')
        print('Client supervisor PID ' + str(child.pid) + '; log ' + str(log.relative_to(ROOT)))
        return
    matrix = json.loads((ROOT / 'versions.json').read_text())
    targets = {t['id']: t for t in matrix['targets']}
    failed = []
    for key in ('fabric-1.16.5', 'forge-1.16.5', 'forge-1.20.6', 'fabric-26.3', 'forge-26.3', 'neoforge-26.3'):
        target = targets[key]
        release = ROOT / 'dist' / target['loader'] / f"jukebox-playlists-{key}-{matrix['mod_version']}.jar"
        path = ROOT / 'build/results' / (key + '-client_runtime.json')
        result = json.loads(path.read_text())['result'] if path.exists() else {}
        if result.get('success') and result.get('sha256') == hashlib.sha256(release.read_bytes()).hexdigest():
            continue
        command = [sys.executable, str(ROOT / 'tools/client_test.py'), '--target', key]
        for home in args.java_path:
            command += ['--java-path', home]
        if args.offline:
            command.append('--offline')
        print('CLIENT ' + key, flush=True)
        if subprocess.run(command, cwd=ROOT).returncode:
            failed.append(key)
    if failed:
        raise SystemExit('Failed client checks: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
