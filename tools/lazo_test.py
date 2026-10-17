#!/usr/bin/env python3
"""Run real LazoDiscs/Plasmo Voice audio and playlist integration on an isolated server."""
import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import threading
import time
import wave

from build import gradle, project
from generate import ROOT, version, write, prepare as generate
from lazo_deps import files, pins


def audio_fixtures(folder, durations=(5, 7)):
    folder.mkdir(parents=True, exist_ok=True)
    for name, seconds, frequency in (('a', durations[0], 440), ('b', durations[1], 880)):
        with wave.open(str(folder / (name + '.wav')), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(48000)
            output.writeframes(b''.join(struct.pack('<h', round(6000 * math.sin(2 * math.pi * frequency * i / 48000))) for i in range(seconds * 48000)))


def prepare(target, java_paths, eula, base_url, attempt, plasmo_jar=None):
    folder, gv = project(target, False, java_paths, folder_name='lazo-test-' + target['id'])
    jars = files(target['id'])
    if plasmo_jar:
        jars[1] = plasmo_jar.resolve()
    mod_version = json.loads((ROOT / 'versions.json').read_text())['mod_version']
    release = ROOT / 'dist' / target['loader'] / f"jukebox-playlists-{target['loader']}-{target['minecraft']}-{mod_version}.jar"
    if not release.is_file():
        raise FileNotFoundError('Build the production JAR first: ' + str(release))
    generated = folder / 'build/fixture-source'
    generate(target, generated, tests=True, lazo_tests=True)
    original_package = Path('dev/eyecrasher/jukeboxplaylists')
    package = Path('dev/eyecrasher/playlistlazochecks')
    old_probe = folder / 'probe/java' / original_package
    if old_probe.exists():
        previous = folder / 'build/previous-probes' / attempt
        previous.parent.mkdir(parents=True, exist_ok=True)
        old_probe.rename(previous)
    for name in ('LazoSmoke.java', 'mixin/ServerTestMixin.java'):
        source = (generated / 'java' / original_package / name).read_text().replace('dev.eyecrasher.jukeboxplaylists', 'dev.eyecrasher.playlistlazochecks')
        if name == 'LazoSmoke.java':
            source = source.replace('package dev.eyecrasher.playlistlazochecks;', 'package dev.eyecrasher.playlistlazochecks;\nimport dev.eyecrasher.jukeboxplaylists.PlaylistJukebox;\nimport dev.eyecrasher.jukeboxplaylists.LazoDiscsCompat;')
        write(folder / 'probe/java' / package / name, source)
    resources = folder / 'probe/resources'
    mixins = json.loads((generated / 'resources/jukebox-playlists.mixins.json').read_text())
    mixins['mixins'] = ['ServerTestMixin']
    mixins['package'] = 'dev.eyecrasher.playlistlazochecks.mixin'
    mixins.pop('plugin', None)
    if 'refmap' in mixins:
        mixins['refmap'] = 'playlist-lazo-checks.refmap.json'
    write(resources / 'playlist-lazo-checks.mixins.json', json.dumps(mixins, indent=2))
    write(resources / 'pack.mcmeta', (generated / 'resources/pack.mcmeta').read_text())
    if target['loader'] == 'fabric':
        write(resources / 'fabric.mod.json', json.dumps({'schemaVersion': 1, 'id': 'playlist_lazo_checks', 'version': '1', 'environment': 'server', 'mixins': ['playlist-lazo-checks.mixins.json'], 'depends': {'jukebox_playlists': '*', 'lazodiscs': '*'}}))
    else:
        namespace = 'net.neoforged.fml.common' if target['loader'] == 'neoforge' else 'net.minecraftforge.fml.common'
        write(folder / 'probe/java' / package / 'LazoChecksMod.java', 'package dev.eyecrasher.playlistlazochecks;\n@' + namespace + '.Mod("playlist_lazo_checks") public final class LazoChecksMod {}\n')
        metadata = next((generated / 'resources/META-INF').glob('*mods.toml'))
        write(resources / 'META-INF' / metadata.name, metadata.read_text().replace('jukebox_playlists', 'playlist_lazo_checks').replace('jukebox-playlists.mixins.json', 'playlist-lazo-checks.mixins.json'))
    run_name = 'build/run/lazo/' + attempt
    run = folder / run_name
    run.mkdir(parents=True, exist_ok=True)
    fixture = folder / 'build/fixture-config' / attempt
    fixture.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(eula, fixture / 'eula.txt')
    settings = {'layers': [{'height': 1, 'block': 'minecraft:bedrock'}, {'height': 3, 'block': 'minecraft:dirt'}, {'height': 1, 'block': 'minecraft:grass_block'}], 'biome': 'minecraft:plains'}
    if version(target['minecraft']) < (1, 19):
        settings['structures'] = {'structures': {}}
    level_type = 'flat' if version(target['minecraft']) < (1, 19) else 'minecraft:flat'
    write(fixture / 'server.properties', f'online-mode=false\nwhite-list=false\nserver-ip=127.0.0.1\nserver-port=0\nlevel-type={level_type}\ngenerator-settings=' + json.dumps(settings) + '\ngamemode=creative\ndifficulty=peaceful\nspawn-protection=0\ngenerate-structures=false\nspawn-monsters=false\nspawn-animals=false\nspawn-npcs=false\nview-distance=2\nsimulation-distance=2\npause-when-empty-seconds=0\n')
    pv = fixture / 'config/plasmovoice/server'
    pv.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        udp = sock.getsockname()[1]
    write(pv / 'config.toml', '[host]\nip="127.0.0.1"\nport=' + str(udp) + '\n')
    write(fixture / 'config/lazodiscs/config.toml', '[security]\nallowHttp=true\nallowedDomains=["127.0.0.1"]\n')
    shutil.copytree(fixture, run, dirs_exist_ok=True)
    build = (folder / 'build.gradle').read_text().split("apply from: new File(playlistRoot, 'gradle/common.gradle')")[0]
    build = build.replace('build/run/server', run_name).replace('jukebox_playlists {', 'playlist_lazo_checks {').replace('jukebox-playlists.mixins.json', 'playlist-lazo-checks.mixins.json')
    build = build.replace("layout.buildDirectory.dir('run/server')", 'layout.projectDirectory.dir(' + json.dumps(run_name) + ')')
    build += "\nversion='checks'\nbase { archivesName='playlist-lazo-checks' }\nsourceSets.main { java.setSrcDirs(['probe/java']); resources.setSrcDirs(['probe/resources']) }\n"
    build += 'dependencies { compileOnly files(' + json.dumps(str(ROOT / 'build/targets' / target['id'] / 'build/classes/java/main')) + ') }\n'
    build += "tasks.withType(JavaCompile).configureEach { options.encoding='UTF-8'; options.release=" + str(min(target['java'], 21)) + " }\njar { manifest { attributes 'MixinConfigs':'playlist-lazo-checks.mixins.json' } }\n"
    build += 'configurations.matching { it.name.endsWith("CompileClasspath") || it.name.endsWith("RuntimeClasspath") || it.name in ["compileClasspath", "runtimeClasspath"] }.configureEach { attributes.attribute(org.gradle.api.attributes.java.TargetJvmVersion.TARGET_JVM_VERSION_ATTRIBUTE, ' + str(target['java']) + ') }\n'
    if target['loader'] == 'forge':
        build += "sourceSets.main.output.resourcesDir=layout.buildDirectory.dir('classes/java/main').get().asFile\ntasks.named('processResources') { dependsOn compileJava; destinationDir=sourceSets.main.output.resourcesDir }\n"
        if target['minecraft'] == '1.21':
            build += "configurations.configureEach { resolutionStrategy.force 'net.sf.jopt-simple:jopt-simple:5.0.4' }\n"
    if target['loader'] == 'fabric':
        # Published mods use intermediary names and can carry a newer Loom
        # marker. Load them unchanged with the normal production installer.
        build += "dependencies { productionRuntimeMods('net.fabricmc.fabric-api:fabric-api:" + target['fabric_api'] + "') { exclude group: 'net.fabricmc', module: 'fabric-loader' } }\n"
        build += '''tasks.register('runLazo', net.fabricmc.loom.task.prod.ServerProductionRunTask) {
    mods.setFrom(tasks.named(PROBE), configurations.productionRuntimeMods, DEPS)
    runDir=layout.projectDirectory.dir(RUN)
    jvmArgs.addAll('-Xmx1500M', '-XX:ActiveProcessorCount=2', BASE)
    outputs.upToDateWhen { false }
    doFirst { copy { from file(FIXTURE); into runDir } }
}
'''.replace('PROBE', "'jar'" if target['minecraft'].startswith('26.') else "'remapJar'").replace('DEPS', ', '.join('file(' + json.dumps(str(p)) + ')' for p in [release, *jars])).replace('RUN', json.dumps(run_name)).replace('BASE', json.dumps('-Dplaylist.audioBase=' + base_url)).replace('FIXTURE', json.dumps(str(fixture)))
    else:
        mods = run / 'mods'
        mods.mkdir(exist_ok=True)
        for jar in [release, *jars]:
            shutil.copyfile(jar, mods / jar.name)
        if target['loader'] == 'forge':
            build += 'minecraft.runs.named("server") { jvmArgs "-Xmx1500M", "-XX:ActiveProcessorCount=2"; systemProperty "playlist.audioBase", ' + json.dumps(base_url) + ' }\n'
        elif target['minecraft'] == '1.20.1':
            build += 'legacyForge.runs.server { jvmArgument "-Xmx1500M"; jvmArgument "-XX:ActiveProcessorCount=2"; systemProperty "playlist.audioBase", ' + json.dumps(base_url) + ' }\n'
        else:
            build += 'neoForge.runs.server { jvmArgument "-Xmx1500M"; jvmArgument "-XX:ActiveProcessorCount=2"; systemProperty "playlist.audioBase", ' + json.dumps(base_url) + ' }\n'
    write(folder / 'build.gradle', build)
    return folder, gv, jars, release, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--eula-file', required=True, type=Path)
    parser.add_argument('--java-path', action='append', default=[], type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--plasmo-jar', type=Path, help='Separate dependency experiment; never counted as the pinned published combination')
    parser.add_argument('--unmodified-dependency', action='store_true', help='Reproduce the upstream Forge 1.20.2 metadata rejection')
    args = parser.parse_args()
    if not args.eula_file.is_file() or 'eula=true' not in args.eula_file.read_text().lower():
        parser.error('An existing accepted Minecraft EULA file is required')
    target = next(t for t in json.loads((ROOT / 'versions.json').read_text())['targets'] if t['id'] == args.target)
    pin = next(p for p in pins() if p['target'] == target['id'])
    if pin.get('dependency_patch') and not args.plasmo_jar and not args.unmodified_dependency:
        from patch_plasmo_voice import patch, FILENAME
        args.plasmo_jar = patch(files(target['id'])[1], ROOT / 'build/compat-deps' / FILENAME)
    attempt = time.strftime('%Y%m%d-%H%M%S')
    evidence = ROOT / 'build/evidence/lazo' / target['id'] / attempt
    evidence.mkdir(parents=True)
    audio = evidence / 'audio'
    audio_fixtures(audio)
    class Handler(SimpleHTTPRequestHandler):
        def copyfile(self, source, output):
            try:
                super().copyfile(source, output)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A decoder can close its download when playback stops.

        def log_message(self, text, *values):
            with (evidence / 'http.log').open('a') as output:
                output.write((text % values) + '\n')
    http = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(audio)))
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    kind = 'lazo_dependency_runtime' if args.plasmo_jar else 'lazo_runtime'
    metadata_fix = bool(args.plasmo_jar and pin.get('dependency_patch') and hashlib.sha256(args.plasmo_jar.read_bytes()).hexdigest() == pin['dependency_patch']['sha256'])
    dependency_topology = ' + prepared Plasmo Voice Forge 1.20.2 metadata fix' if metadata_fix else ' + separate Plasmo Voice dependency experiment' if args.plasmo_jar else ' + unchanged pinned Plasmo Voice JAR'
    record = {'target': target['id'], 'kind': kind, 'result': {'success': False, 'evidence': str(evidence.relative_to(ROOT)), 'lazodiscs': pin['lazodiscs']['version'], 'plasmo': pin['plasmo']['version'], 'dependency_override': str(args.plasmo_jar) if args.plasmo_jar else None, 'topology': 'unchanged production playlist/LazoDiscs JARs + independent server probe' + dependency_topology}}
    started = time.monotonic()
    try:
        base_url = 'http://127.0.0.1:' + str(http.server_port)
        folder, gv, jars, release, run = prepare(target, args.java_path, args.eula_file, base_url, attempt, args.plasmo_jar)
        before = hashlib.sha256(release.read_bytes()).hexdigest()
        installed_forge = target['loader'] == 'forge' and version(target['minecraft']) < (1, 20, 5)
        argv = gradle(gv) + ['--console=plain', '--max-workers=2']
        if args.offline:
            argv.append('--offline')
        argv.append('renameJar' if installed_forge else 'runLazo' if target['loader'] == 'fabric' else 'runServer')
        log = evidence / 'server.log'
        with log.open('w') as output:
            result = subprocess.run(argv, cwd=folder, stdout=output, stderr=subprocess.STDOUT, timeout=480)
            if installed_forge and result.returncode == 0:
                from installed_forge import run_server
                result = run_server(folder, run, target, base_url, args.java_path, output)
        assert hashlib.sha256(release.read_bytes()).hexdigest() == before, 'Release JAR changed during test'
        record['result'].update(artifact=str(release.relative_to(ROOT)), sha256=before)
        text = log.read_text(errors='replace')
        requests = (evidence / 'http.log').read_text() if (evidence / 'http.log').exists() else ''
        audio_ok = all(name in requests for name in ('/a.wav', '/b.wav')) and text.count('Streaming LazoDisc audio sender started') >= 3 and 'Failed to start streaming LazoDisc' not in text
        record['result'].update(success=result.returncode == 0 and 'PLAYLIST LAZO TESTS PASSED' in text and 'PLAYLIST LAZO TESTS FAILED' not in text and audio_ok, log=str(log.relative_to(ROOT)), audio_verified=audio_ok, dependencies=[{'file': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in jars])
        if not record['result']['success']:
            print('\n'.join(text.splitlines()[-65:]))
    finally:
        http.shutdown()
        http.server_close()
        record['result']['seconds'] = round(time.monotonic() - started, 1)
        write(evidence / 'result.json', json.dumps(record, indent=2) + '\n')
        write(ROOT / 'build/results' / (target['id'] + '-' + kind + '.json'), json.dumps(record, indent=2) + '\n')
    print(('PASS ' if record['result']['success'] else 'FAIL ') + 'LazoDiscs ' + target['id'], flush=True)
    if not record['result']['success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
