#!/usr/bin/env python3
"""Check sound resolution and duration against ffprobe on Java 8 and 17."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import zipfile

from legacy_audio import ROOT, prepare_resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, action='append', required=True)
    args = parser.parse_args()
    folder = ROOT / 'build/tests/legacy-lengths'
    media = folder / 'resources'
    prepare_resources(media)
    durations = {}
    for name in ('short', 'long'):
        file = media / 'assets/playlist_length_fixture/sounds' / (name + '.ogg')
        durations[name] = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(file)], text=True))
    assert durations['short'] == 2.25 and abs(durations['long'] - 3.25) < 1 / 22050, durations
    sounds = {
        'nested_pitch': {'sounds': [{'name': 'playlist_length_fixture:disc.slow', 'type': 'event', 'pitch': 0.5}]},
        'fast': {'sounds': [{'name': 'playlist_length_fixture:long', 'pitch': 2}]},
        'default_namespace': {'sounds': ['default_namespace']},
        'merged': {'sounds': ['playlist_length_fixture:short']},
        'replaced': {'sounds': ['playlist_length_fixture:long']},
        'file_override': {'sounds': ['test:override']},
        'unknown_variant': {'sounds': ['playlist_length_fixture:short', 'test:missing']},
        'cycle_a': {'sounds': [{'name': 'test:cycle_b', 'type': 'event'}]},
        'cycle_b': {'sounds': [{'name': 'test:cycle_a', 'type': 'event'}]},
        'negative_pitch': {'sounds': [{'name': 'playlist_length_fixture:short', 'pitch': -1}]},
        'nan_pitch': {'sounds': [{'name': 'playlist_length_fixture:short', 'pitch': 'NaN'}]},
        'bad_id': {'sounds': ['test:../../outside']},
    }
    for name in ('truncated', 'no_eos', 'not_vorbis', 'chained'):
        sounds[name] = {'sounds': ['test:' + name]}
    short = (media / 'assets/playlist_length_fixture/sounds/short.ogg').read_bytes()
    long = (media / 'assets/playlist_length_fixture/sounds/long.ogg').read_bytes()
    # Remove a complete final page, as well as a partial final page.
    final_page = short.rfind(b'OggS')
    jars = [folder / 'base.jar', folder / 'extra.jar']
    with zipfile.ZipFile(jars[0], 'w') as jar:
        for file in media.rglob('*'):
            if file.is_file(): jar.write(file, file.relative_to(media))
        jar.writestr('assets/test/sounds.json', json.dumps(sounds))
        for name, audio in {'truncated': short[:-1], 'no_eos': short[:final_page],
                'not_vorbis': b'not an ogg file', 'chained': short + long, 'override': short}.items():
            jar.writestr(f'assets/test/sounds/{name}.ogg', audio)
        jar.writestr('assets/minecraft/sounds/default_namespace.ogg', short)
    with zipfile.ZipFile(jars[1], 'w') as jar:
        jar.writestr('assets/test/sounds.json', json.dumps({
            'merged': {'sounds': ['playlist_length_fixture:long']},
            'replaced': {'replace': True, 'sounds': ['playlist_length_fixture:short']}}))
        jar.writestr('assets/test/sounds/override.ogg', long)
    gson = next((Path.home() / '.gradle/caches/modules-2/files-2.1/com.google.code.gson/gson/2.8.0').rglob('gson-2.8.0.jar'))
    sources = [ROOT / 'tools/templates/legacy/java/dev/eyecrasher/jukeboxplaylists/LegacySoundLengths.java',
               ROOT / 'tools/tests/LegacySoundLengthsTest.java']
    for home in args.java_home:
        classes = folder / ('classes-' + home.name)
        classes.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(home / 'bin/javac'), '-source', '8', '-target', '8', '-cp', str(gson),
                        '-d', str(classes), *map(str, sources)], check=True)
        subprocess.run([str(home / 'bin/java'), '-cp', os.pathsep.join(map(str, [classes, gson])),
                        'LegacySoundLengthsTest', *map(str, jars)], check=True)
    print('ffprobe durations verified:', durations)


if __name__ == '__main__':
    main()
