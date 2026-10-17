#!/usr/bin/env python3
"""Fetch pinned public LazoDiscs/Plasmo Voice test dependencies with hash checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def dependency(info, kind):
    destination = ROOT / 'build/lazo-deps' / kind / info['filename']
    def valid(path):
        return path.is_file() and hashlib.sha512(path.read_bytes()).hexdigest() == info['hashes']['sha512']
    if valid(destination):
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if kind == 'plasmo':
        candidate = Path.home() / 'mod-audit/LazoDiscs/.cache/compatibility/plasmo-voice' / (info['hashes']['sha512'] + '.jar')
        if valid(candidate):
            shutil.copyfile(candidate, destination)
            return destination
    temporary = destination.with_suffix('.' + str(os.getpid()) + '.part')
    request = urllib.request.Request(info['url'], headers={'User-Agent': 'JukeboxPlaylists/0.2.0 (compatibility verification)'})
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as output:
        shutil.copyfileobj(response, output)
    if not valid(temporary):
        raise ValueError('Dependency hash mismatch: ' + info['filename'])
    temporary.replace(destination)
    return destination


def pins():
    return json.loads((ROOT / 'lazodiscs-compatibility.json').read_text())['targets']


def files(target):
    entry = next(p for p in pins() if p['target'] == target)
    return [dependency(entry[kind], kind) for kind in ('lazodiscs', 'plasmo')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', action='append')
    args = parser.parse_args()
    selected = [p for p in pins() if not args.target or p['target'] in args.target]
    unique = {(kind, p[kind]['filename']): p[kind] for p in selected for kind in ('lazodiscs', 'plasmo')}
    jobs = [(kind, info) for (kind, name), info in unique.items()]
    def fetch(job):
        kind, info = job
        path = dependency(info, kind)
        print('Verified ' + path.name, flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, jobs))
    print('Dependencies verified for ' + str(len(selected)) + ' target combinations')


if __name__ == '__main__':
    main()
