#!/usr/bin/env python3
"""Materialize ordinary loader/version Gradle projects from the shared sources."""
import argparse
import json
from pathlib import Path
import shutil

from build import project
from generate import ROOT, prepare, write


def sync(target, check=False):
    staging = ROOT / 'build/project-layout' / target['id']
    sdk, gv = project(target, folder_name='layout-' + target['id'])
    if staging.exists():
        shutil.rmtree(staging)
    prepare(target, staging / 'src/main')
    for source in (staging / 'src/main/java').rglob('*.java'):
        source.write_text('\n'.join(line.rstrip(' \t') for line in source.read_text().split('\n')))
    build = (sdk / 'build.gradle').read_text()
    build = build.replace('ext.playlistRoot = ' + json.dumps(str(ROOT)), "ext.playlistRoot = file('../..').absolutePath")
    build = build.replace('gradle/common.gradle', 'gradle/release.gradle')
    write(staging / 'build.gradle', build)
    settings = (sdk / 'settings.gradle').read_text().replace("rootProject.name = 'jukebox-playlists'", "rootProject.name = 'jukebox-playlists-" + target['id'] + "'")
    write(staging / 'settings.gradle', settings)
    write(staging / 'gradle.properties', 'org.gradle.jvmargs=-Xmx2G\norg.gradle.workers.max=2\n')
    for name in ('gradlew', 'gradlew.bat'):
        shutil.copyfile(ROOT / 'gradle/wrappers' / name, staging / name)
    for name in ('gradle-wrapper.jar', 'gradle-wrapper.properties'):
        dest = staging / 'gradle/wrapper' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'gradle/wrappers' / gv / name, dest)
    destination = ROOT / target['loader'] / target['minecraft']
    mismatches = []
    for source in staging.rglob('*'):
        if not source.is_file():
            continue
        dest = destination / source.relative_to(staging)
        if not dest.is_file() or dest.read_bytes() != source.read_bytes():
            if check:
                mismatches.append(str(dest.relative_to(ROOT)))
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
    if not check:
        (destination / 'gradlew').chmod(0o755)
    return mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', action='append')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    targets = [t for t in json.loads((ROOT / 'versions.json').read_text())['targets'] if not args.target or t['id'] in args.target]
    if args.target and len(targets) != len(set(args.target)):
        parser.error('Unknown target')
    mismatches = []
    for target in targets:
        mismatches.extend(sync(target, args.check))
    if mismatches:
        raise SystemExit('Out-of-sync project files:\n' + '\n'.join(mismatches))
    print(('Verified' if args.check else 'Prepared') + ' ' + str(len(targets)) + ' loader/version projects')


if __name__ == '__main__':
    main()
