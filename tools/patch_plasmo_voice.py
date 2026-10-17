#!/usr/bin/env python3
"""Prepare the verified, local Forge 1.20.2 metadata fix for Plasmo Voice."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILENAME = 'plasmovoice-forge-1.20.2-2.1.17-metadata-fix.jar'


def patch(source, destination):
    pin = next(p for p in json.loads((ROOT / 'lazodiscs-compatibility.json').read_text())['targets'] if p['target'] == 'forge-1.20.2')['plasmo']
    original = source.read_bytes()
    if hashlib.sha512(original).hexdigest() != pin['hashes']['sha512']:
        raise ValueError('Expected the pinned, original Plasmo Voice 2.1.17 Forge 1.20.4 JAR')
    notice = ('Local metadata fix for Forge 1.20.2, prepared 2026-10-17.\n'
              'Upstream Plasmo Voice 2.1.17 declares Minecraft 1.20.2-1.20.4, but requires FML/Forge 49.\n'
              'Changed only these minimum versions to 48; all upstream classes remain byte-for-byte identical.\n'
              'This is a local compatibility copy, not an official Plasmo Voice release.\n'
              'Original license and notices retained. Source: https://github.com/plasmoapp/plasmo-voice/tree/2.1.17\n'
              'Original SHA-512: ' + pin['hashes']['sha512'] + '\n')
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as archive, zipfile.ZipFile(output, 'w') as patched:
        for entry in archive.infolist():
            data = archive.read(entry.filename)
            if entry.filename == 'META-INF/mods.toml':
                text = data.decode()
                if text.count('[49,)') != 2 or 'versionRange="[1.20.2,1.20.4]"' not in text:
                    raise ValueError('Unexpected upstream metadata')
                data = ('# Local Forge 1.20.2 metadata fix; see META-INF/jukebox-playlists-patch.txt\n' + text.replace('[49,)', '[48,)')).encode()
            patched.writestr(entry, data)
        entry = zipfile.ZipInfo('META-INF/jukebox-playlists-patch.txt', (2026, 10, 17, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        patched.writestr(entry, notice)
    content = output.getvalue()
    if destination.exists() and destination.read_bytes() != content:
        raise FileExistsError('Refusing to overwrite a different file: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = patch(args.source, args.output or args.source.parent / FILENAME)
    print(str(result) + '\nSHA-256 ' + hashlib.sha256(result.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
