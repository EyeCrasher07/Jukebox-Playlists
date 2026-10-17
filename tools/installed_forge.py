"""Normal Forge 1.16.5 client launch, isolated from the development mappings."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GRADLE = Path.home() / '.gradle'


def download(url, destination, sha1=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and (not sha1 or hashlib.sha1(destination.read_bytes()).hexdigest() == sha1):
        return
    temporary = destination.with_suffix(destination.suffix + '.part')
    urllib.request.urlretrieve(url, temporary)
    if sha1 and hashlib.sha1(temporary.read_bytes()).hexdigest() != sha1:
        raise RuntimeError('Downloaded file hash mismatch: ' + url)
    temporary.replace(destination)


def library_file(library, install):
    group, artifact, v, *classifier = library['name'].split(':')
    name = artifact + '-' + v + (('-' + classifier[0]) if classifier else '') + '.jar'
    info = library.get('downloads', {}).get('artifact', {})
    relative = info.get('path', group.replace('.', '/') + '/' + artifact + '/' + v + '/' + name)
    destination = install / 'libraries' / relative
    if not destination.is_file():
        candidates = [Path.home() / '.local/share/PrismLauncher/libraries' / relative]
        candidates += list((GRADLE / 'caches/modules-2/files-2.1' / group / artifact / v).glob('*/' + name))
        for candidate in candidates:
            if candidate.is_file() and (not info.get('sha1') or hashlib.sha1(candidate.read_bytes()).hexdigest() == info['sha1']):
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(candidate, destination)
                break
    if not destination.is_file():
        download(info.get('url') or library.get('url', 'https://libraries.minecraft.net/').rstrip('/') + '/' + relative, destination, info.get('sha1'))
    return destination


def allowed(value):
    rules = value.get('rules')
    if not rules:
        return True
    result = False
    for rule in rules:
        os_rule = rule.get('os', {})
        if os_rule.get('name', 'linux') != 'linux' or rule.get('features'):
            continue
        if os_rule.get('arch') and not re.fullmatch(os_rule['arch'], 'x86_64'):
            continue
        result = rule['action'] == 'allow'
    return result


def run_client(folder, release, loader_pin, java_paths, output):
    java8 = next((Path(p) / 'bin/java' for p in java_paths if (Path(p) / 'release').is_file() and '1.8.' in (Path(p) / 'release').read_text()), None)
    if java8 is None:
        raise RuntimeError('Pass the Java 8 runtime through --java-path for installed Forge 1.16.5')
    install = folder / 'build/installed'
    install.mkdir(parents=True, exist_ok=True)
    (install / 'launcher_profiles.json').write_text('{"profiles":{}}\n')
    base = json.loads((GRADLE / 'caches/fabric-loom/1.16.5/mojang_minecraft_info.json').read_text())
    version_dir = install / 'versions/1.16.5'
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / '1.16.5.json').write_text(json.dumps(base))
    shutil.copyfile(GRADLE / 'caches/fabric-loom/1.16.5/minecraft-client.jar', version_dir / '1.16.5.jar')
    installer = ROOT / 'build' / ('forge-' + loader_pin + '-installer.jar')
    download(f'https://maven.minecraftforge.net/net/minecraftforge/forge/{loader_pin}/forge-{loader_pin}-installer.jar', installer)
    with zipfile.ZipFile(installer) as jar:
        forge = json.loads(jar.read('version.json'))
        profile = json.loads(jar.read('install_profile.json'))
    # Seed ordinary Maven libraries from caches before the official installer runs.
    for library in profile['libraries']:
        if library.get('downloads', {}).get('artifact', {}).get('url'):
            library_file(library, install)
    marker = install / 'installed-successfully'
    if not marker.is_file():
        # The old installer verifies exact hashes of processor output JARs.
        # Java 8 supplies the ZIP implementation those hashes were generated with.
        subprocess.run([str(java8), '-jar', str(installer), '--installClient', str(install)], stdout=output, stderr=subprocess.STDOUT, timeout=300, check=True)
        marker.write_text(forge['id'] + '\n')
    libraries = {}
    for library in base['libraries'] + forge['libraries']:
        if allowed(library):
            libraries[':'.join(library['name'].split(':')[:2])] = library
    classpath = [library_file(library, install) for library in libraries.values()]
    classpath.append(version_dir / '1.16.5.jar')
    run = folder / 'build/run/client'
    run.mkdir(parents=True, exist_ok=True)
    seed = ROOT / 'build/targets/test-fabric-1.16.5/build/run/server/world'
    shutil.copytree(seed, run / 'saves/playlist-client-fixture', dirs_exist_ok=True, ignore=shutil.ignore_patterns('session.lock'))
    mods = run / 'mods'
    mods.mkdir(exist_ok=True)
    probe = [p for p in (folder / 'build/libs').glob('*.jar') if not p.name.endswith(('-dev.jar', '-sources.jar'))]
    if len(probe) != 1:
        raise RuntimeError('Expected one remapped check JAR: ' + str(probe))
    shutil.copyfile(release, mods / release.name)
    # Renamer's default main source set exports main.refmap.json. Give this
    # independent fixture its own resource name to avoid shadowing the mod's map.
    with zipfile.ZipFile(probe[0]) as original, zipfile.ZipFile(mods / probe[0].name, 'w') as installed:
        for entry in original.infolist():
            data = original.read(entry.filename)
            if entry.filename == 'main.refmap.json':
                entry.filename = 'playlist-client-checks.refmap.json'
            installed.writestr(entry, data)
    (run / 'options.txt').write_text('guiScale:2\nrenderDistance:3\nmaxFps:60\nenableVsync:false\nlang:en_us\ntutorialStep:none\nsoundCategory_music:0.0\nsoundCategory_master:0.35\nsoundCategory_record:1.0\npauseOnLostFocus:false\n')
    replacements = {'auth_player_name': 'PlaylistTester', 'version_name': forge['id'], 'game_directory': str(run),
                    'assets_root': str(GRADLE / 'caches/fabric-loom/assets'), 'assets_index_name': '1.16.5-1.16',
                    'auth_uuid': '00000000000030008000000000000001', 'auth_access_token': '0',
                    'user_type': 'legacy', 'version_type': 'release'}
    arguments = []
    for argument in base['arguments']['game'] + forge['arguments']['game']:
        if isinstance(argument, dict):
            if not allowed(argument):
                continue
            argument = argument['value']
        for value in argument if isinstance(argument, list) else [argument]:
            for name, replacement in replacements.items():
                value = value.replace('${' + name + '}', replacement)
            arguments.append(value)
    command = [str(java8), '-Xmx2G', '-Djava.library.path=' + str(folder / 'build/run/legacy-natives'),
               '-cp', os.pathsep.join(map(str, classpath)), forge['mainClass'], *arguments, '--width', '960', '--height', '540']
    output.flush()
    return subprocess.run(command, cwd=run, stdout=output, stderr=subprocess.STDOUT, timeout=360)
