#!/usr/bin/env python3
"""Fabric 26.3: unchanged release JAR, dedicated server, two client JVMs and restart."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import functools
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import time
import traceback
import threading
import wave

from build import gradle
from generate import ROOT, write


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def rcon(port, password, command):
    def receive(sock):
        def read(size):
            data = b''
            while len(data) < size:
                chunk = sock.recv(size - len(data))
                if not chunk:
                    raise ConnectionError('RCON closed')
                data += chunk
            return data
        size = struct.unpack('<i', read(4))[0]
        if not 10 <= size <= 4 * 1024 * 1024:
            raise ValueError('Invalid RCON frame')
        data = read(size)
        return struct.unpack('<ii', data[:8]), data[8:-2].decode()
    def send(sock, kind, text):
        data = struct.pack('<ii', 31, kind) + text.encode() + b'\0\0'
        sock.sendall(struct.pack('<i', len(data)) + data)
    with socket.create_connection(('127.0.0.1', port), timeout=5) as sock:
        send(sock, 3, password)
        for _ in range(4):
            (request, kind), _ = receive(sock)
            if request == -1:
                raise PermissionError('RCON authentication failed')
            if kind == 2:
                break
        else:
            raise ValueError('No RCON authentication response')
        send(sock, 2, command)
        return receive(sock)[1]


def until(condition, seconds, message):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.2)
    raise TimeoutError(message)


def prepare(target, folder, role, coord, port, release, java_paths, lazo=False, voice_port=None):
    original = ROOT / target['loader'] / target['minecraft']
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original / 'settings.gradle', folder / 'settings.gradle')
    properties = 'org.gradle.jvmargs=-Xmx1G\norg.gradle.workers.max=1\n'
    if java_paths:
        properties += 'org.gradle.java.installations.paths=' + ','.join(map(str, java_paths)) + '\n'
    write(folder / 'gradle.properties', properties)
    build = (original / 'build.gradle').read_text().split("apply from: new File(playlistRoot, 'gradle/release.gradle')")[0]
    build = build.replace("file('../..').absolutePath", json.dumps(str(ROOT)))
    build += "\nversion='pair-probe'\nsourceSets.main { java.setSrcDirs(['probe/java']); resources.setSrcDirs(['probe/resources']) }\n"
    build += "dependencies { productionRuntimeMods 'net.fabricmc.fabric-api:fabric-api:" + target['fabric_api'] + "' }\n"
    mods = "configurations.productionRuntimeMods, file(" + json.dumps(str(release)) + ")"
    if lazo:
        from lazo_deps import files
        mods += ', ' + ', '.join('file(' + json.dumps(str(p)) + ')' for p in files(target['id']))
    run = folder / 'game'
    run.mkdir(exist_ok=True)
    write(run / '.modtest-owned', '')
    if lazo:
        if role == 'server':
            config = run / 'config/plasmovoice/server/config.toml'
            if not config.exists():
                write(config, '[host]\nip="127.0.0.1"\nport=' + str(voice_port) + '\n')
            config = run / 'config/lazodiscs/config.toml'
            if not config.exists():
                write(config, '[security]\nallowHttp=true\nallowedDomains=["127.0.0.1"]\n')
        else:
            config = run / 'config/plasmovoice/client.toml'
            if not config.exists():
                write(config, 'check_for_updates=false\n[voice]\nmicrophone_disabled=true\ndisable_input_device=true\n')
    if role == 'server':
        build += '''tasks.register('runPair', net.fabricmc.loom.task.prod.ServerProductionRunTask) {
    mods.setFrom(MODS)
    runDir=layout.projectDirectory.dir('game')
    jvmArgs.addAll('-Xmx1500M')
    programArgs.addAll('nogui')
    outputs.upToDateWhen { false }
}
'''.replace('MODS', mods)
    else:
        src = folder / 'probe/java/dev/eyecrasher/playlistpair'
        write(src / 'PairChecks.java', (ROOT / 'tools/templates/clienttest/PairChecks.java').read_text())
        write(src / 'ClientTickMixin.java', '''package dev.eyecrasher.playlistpair.mixin;
import dev.eyecrasher.playlistpair.PairChecks;
import net.minecraft.client.Minecraft;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(Minecraft.class) public abstract class ClientTickMixin {
 @Inject(method="tick",at=@At("TAIL")) private void checks$tick(CallbackInfo ci) { PairChecks.tick(); }
}
''')
        write(src / 'SoundMixin.java', '''package dev.eyecrasher.playlistpair.mixin;
import dev.eyecrasher.playlistpair.PairChecks;
import net.minecraft.client.sounds.SoundEngine;
import net.minecraft.client.resources.sounds.SoundInstance;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(SoundEngine.class) public abstract class SoundMixin {
 @Inject(method="play",at=@At("HEAD")) private void checks$sound(SoundInstance sound, CallbackInfoReturnable<?> ci) { PairChecks.sound(sound); }
}
''')
        resources = folder / 'probe/resources'
        write(resources / 'fabric.mod.json', json.dumps({'schemaVersion': 1, 'id': 'playlist_pair_checks', 'version': '1', 'environment': 'client', 'mixins': ['playlist-pair.mixins.json'], 'depends': {'jukebox_playlists': '*'}}))
        write(resources / 'playlist-pair.mixins.json', json.dumps({'required': True, 'package': 'dev.eyecrasher.playlistpair.mixin', 'compatibilityLevel': 'JAVA_21', 'client': ['ClientTickMixin', 'SoundMixin'], 'injectors': {'defaultRequire': 1}}))
        args = ['--username', 'PlaylistOwner' if role == 'owner' else 'PlaylistObserver', '--accessToken', '0', '--version', 'Playlist-pair', '--width', '900', '--height', '600', '--quickPlayMultiplayer', '127.0.0.1:' + str(port)]
        build += '''tasks.register('runPair', net.fabricmc.loom.task.prod.ClientProductionRunTask) {
    mods.setFrom(tasks.named('jar'), MODS)
    runDir=layout.projectDirectory.dir('game')
    jvmArgs.addAll('-Xmx1500M', COORD, ROLE, LAZO)
    programArgs.addAll(ARGS)
    outputs.upToDateWhen { false }
}
'''.replace('MODS', mods).replace('COORD', json.dumps('-Dplaylist.coord=' + str(coord))).replace('ROLE', json.dumps('-Dplaylist.role=' + role)).replace('LAZO', json.dumps('-Dplaylist.lazo=' + str(lazo).lower())).replace('ARGS', ', '.join(map(json.dumps, args)))
        write(run / 'options.txt', 'onboardAccessibility:false\nguiScale:2\nrenderDistance:3\nsimulationDistance:5\nmaxFps:40\nenableVsync:false\nlang:en_us\ntutorialStep:none\nskipMultiplayerWarning:true\nsoundCategory_music:0.0\nsoundCategory_master:0.5\nsoundCategory_record:1.0\npauseOnLostFocus:false\n')
    write(folder / 'build.gradle', build)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eula-file', required=True, type=Path)
    parser.add_argument('--java-path', action='append', default=[], type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--audio', action='store_true', help='Capture each test client through its own temporary PulseAudio sink')
    parser.add_argument('--lazo', action='store_true', help='Exercise LazoDiscs + Plasmo Voice, including a track longer than its vanilla disc')
    args = parser.parse_args()
    if not args.eula_file.is_file() or 'eula=true' not in args.eula_file.read_text().lower():
        parser.error('Use an existing accepted EULA file')
    target = next(t for t in json.loads((ROOT / 'versions.json').read_text())['targets'] if t['id'] == 'fabric-26.3')
    mod_version = json.loads((ROOT / 'versions.json').read_text())['mod_version']
    release = ROOT / f'dist/fabric/jukebox-playlists-fabric-26.3-{mod_version}.jar'
    digest = hashlib.sha256(release.read_bytes()).hexdigest()
    attempt = datetime.now().strftime('%Y%m%d-%H%M%S')
    case = 'lazo-pair-fabric-26.3' if args.lazo else 'pair-fabric-26.3'
    folder = ROOT / 'build/targets' / case / attempt
    evidence = ROOT / 'build/evidence' / case / attempt
    evidence.mkdir(parents=True)
    write(evidence / 'supervisor.pid', str(os.getpid()))
    port, rcon_port = free_port(), free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        voice_port = sock.getsockname()[1]
    password = secrets.token_hex(16)
    processes, sinks, outputs = [], {}, []
    client_pids, copied_frames = {}, set()
    checks = []
    kind = 'lazo_pair_runtime' if args.lazo else 'pair_runtime'
    http = None
    receipt = {'target': target['id'], 'kind': kind, 'result': {'success': False, 'artifact': str(release.relative_to(ROOT)), 'sha256': digest, 'evidence': str(evidence.relative_to(ROOT)), 'topology': 'production dedicated server + two production client JVMs', 'loader_version': target['loader_version']}}
    def interrupted(number, frame):
        raise InterruptedError('Pair supervisor received signal ' + str(number))
    signal.signal(signal.SIGTERM, interrupted)
    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        checks.append(message)
        receipt['result']['checks'] = checks
        write(evidence / 'progress.json', json.dumps(receipt, indent=2) + '\n')
        print('PAIR CHECK: ' + message, flush=True)
    def command(text):
        response = rcon(rcon_port, password, text)
        with (evidence / 'rcon.log').open('a') as out:
            out.write(text + '\n' + response + '\n')
        if any(error in response for error in ('Unknown or incomplete', 'Incorrect argument', 'Expected ', 'Unknown rule', 'That position is not loaded')):
            raise AssertionError('Fixture command: ' + text + ': ' + response)
        return response
    def launch(role, phase, coord):
        project = folder / role
        prepare(target, project, role, coord, port, release, args.java_path, args.lazo, voice_port)
        logfile = evidence / f'{phase}-{role}.log'
        output = logfile.open('w')
        outputs.append(output)
        env = os.environ.copy()
        if role in sinks:
            env.update(PULSE_SINK=sinks[role]['name'], ALSOFT_DRIVERS='pulse')
        argv = gradle('9.7.1') + ['--console=plain', '--max-workers=1', '--no-daemon']
        if args.offline:
            argv.append('--offline')
        argv.append('runPair')
        process = subprocess.Popen(argv, cwd=project, env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        return process
    def ready_server(server):
        def ready():
            if server.poll() is not None:
                raise AssertionError('Dedicated server exited before ready')
            try:
                return 'players online' in rcon(rcon_port, password, 'list')
            except (OSError, ValueError):
                return False
        until(ready, 180, 'Dedicated server readiness')
    def ready_clients(coord, clients):
        def ready():
            if any(p.poll() is not None for p in clients):
                raise AssertionError('Client exited before joining')
            return all((coord / (role + '-ready.json')).exists() for role in ('owner', 'observer'))
        until(ready, 180, 'Both client JVMs join')
        records = [json.loads((coord / (role + '-ready.json')).read_text()) for role in ('owner', 'observer')]
        client_pids.update({role: record['pid'] for role, record in zip(('owner', 'observer'), records)})
        check(records[0]['pid'] != records[1]['pid'], 'owner and observer are separate client JVMs: ' + ', '.join(str(r['pid']) for r in records))
        check(all(r['java'].startswith('25.') for r in records), 'both game JVMs use Java 25')
        if args.lazo:
            import tomllib
            for role in ('owner', 'observer'):
                config = tomllib.loads((folder / role / 'game/config/plasmovoice/client.toml').read_text())
                check(config['voice']['microphone_disabled'] and config['voice']['disable_input_device'], role + ' microphone input stays disabled')
        if args.audio:
            for role, record in zip(('owner', 'observer'), records):
                until(lambda: route_audio(role), 15, 'Find only the test client audio stream: ' + role)
        for role, x in (('Owner', .5), ('Observer', 2.5)):
            command(f'gamemode creative Playlist{role}')
            command(f'tp Playlist{role} {x} 100 3.3 ' + ('180' if role == 'Owner' else '145') + ' 15')
        if shutil.which('hyprctl'):
            for role, x in (('owner', 10), ('observer', 930)):
                code = 'for _,w in ipairs(hl.get_windows()) do if w.pid==' + str(client_pids[role]) + ' then hl.dispatch(hl.dsp.window.float({action="set",window=w}));hl.dispatch(hl.dsp.window.resize({x=900,y=600,window=w}));hl.dispatch(hl.dsp.window.move({x=' + str(x) + ',y=80,window=w})) end end'
                subprocess.run(['hyprctl', 'eval', code], check=True, stdout=subprocess.DEVNULL)
        time.sleep(2)
    def route_audio(role):
        inputs = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sink-inputs'], text=True))
        owned = [stream for stream in inputs if str(stream.get('properties', {}).get('application.process.id')) == str(client_pids[role])]
        for stream in owned:
            subprocess.run(['pactl', 'move-sink-input', str(stream['index']), sinks[role]['name']], check=True)
            subprocess.run(['pactl', 'set-sink-input-mute', str(stream['index']), '0'], check=True)
            subprocess.run(['pactl', 'set-sink-input-volume', str(stream['index']), '100%'], check=True)
        with (evidence / 'audio-routing.jsonl').open('a') as output:
            output.write(json.dumps({'role': role, 'pid': client_pids[role], 'sink': sinks[role]['name'], 'streams_before_move': owned}) + '\n')
        return bool(owned)
    step_id = 0
    def step(coord, actions):
        nonlocal step_id
        step_id += 1
        for role, action in actions.items():
            temporary = coord / (role + '-request.tmp')
            write(temporary, json.dumps({'id': step_id, **action}))
            temporary.replace(coord / (role + '-request.json'))
        def done():
            failures = list(coord.glob('*-failure.json'))
            if failures:
                raise AssertionError(failures[0].read_text())
            return all((coord / f'{step_id}-{role}.json').exists() for role in actions)
        until(done, 125, 'Pair step ' + str(step_id))
        for role in actions:
            result = json.loads((coord / f'{step_id}-{role}.json').read_text())
            check(result['success'], f'{coord.name} step {step_id}, {role}: {actions[role]}')
    def finish_clients(coord, clients):
        step(coord, {r: {'action': 'quit'} for r in ('owner', 'observer')})
        for role, process in zip(('owner', 'observer'), clients):
            check(process.wait(timeout=45) == 0, role + ' exits normally')
    def collect(phase):
        for role in ('owner', 'observer'):
            for screenshot in (folder / role / 'game/screenshots').glob('*.png'):
                if screenshot in copied_frames:
                    continue
                destination = evidence / 'screenshots' / (phase + '-' + role + '-' + screenshot.name)
                destination.parent.mkdir(exist_ok=True)
                shutil.copyfile(screenshot, destination)
                copied_frames.add(screenshot)
    def capture_tones(label, frequency):
        for role in ('owner', 'observer'):
            check(route_audio(role), role + ' test audio routing before ' + label)
        def capture(role):
            path = evidence / (role + '-' + label + '.wav')
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'pulse', '-i', sinks[role]['name'] + '.monitor', '-t', '6', '-ar', '22050', '-ac', '1', '-c:a', 'pcm_s16le', str(path)], check=True, timeout=20)
            with wave.open(str(path)) as wav:
                rate = wav.getframerate()
                values = struct.unpack('<' + 'h' * wav.getnframes(), wav.readframes(wav.getnframes()))
            rms = (sum(v * v for v in values) / len(values)) ** .5
            crossings = sum((a < 0) != (b < 0) for a, b in zip(values, values[1:]))
            return {'rms': rms, 'frequency_hz': crossings * rate / (2 * len(values))}
        with ThreadPoolExecutor(max_workers=2) as pool:
            recordings = dict(zip(('owner', 'observer'), pool.map(capture, ('owner', 'observer'))))
        receipt['result'].setdefault('tone_captures', {})[label] = recordings
        for role, result in recordings.items():
            check(result['rms'] > 10 and abs(result['frequency_hz'] - frequency) < 25, role + ' receives the expected ' + str(frequency) + ' Hz LazoDiscs tone')
    try:
        if args.audio:
            for role in ('owner', 'observer'):
                name = 'playlist_' + role + '_' + attempt.replace('-', '')
                module = subprocess.check_output(['pactl', 'load-module', 'module-null-sink', 'sink_name=' + name], text=True).strip()
                sinks[role] = {'name': name, 'module': module}
        coord = evidence / 'phase1'
        coord.mkdir()
        server_run = prepare(target, folder / 'server', 'server', coord, port, release, args.java_path, args.lazo, voice_port)
        shutil.copyfile(args.eula_file, server_run / 'eula.txt')
        settings = {'layers': [{'height': 1, 'block': 'minecraft:bedrock'}, {'height': 3, 'block': 'minecraft:dirt'}, {'height': 1, 'block': 'minecraft:grass_block'}], 'biome': 'minecraft:plains'}
        write(server_run / 'server.properties', f'online-mode=false\nwhite-list=false\nserver-ip=127.0.0.1\nserver-port={port}\nenable-rcon=true\nrcon.port={rcon_port}\nrcon.password={password}\nlevel-type=minecraft:flat\ngenerator-settings=' + json.dumps(settings) + '\ngamemode=creative\ndifficulty=peaceful\nspawn-protection=0\nview-distance=3\nsimulation-distance=5\nallow-flight=true\nenforce-secure-profile=false\npause-when-empty-seconds=0\n')
        server = launch('server', 'phase1', coord)
        ready_server(server)
        command('forceload add -6 -6 6 6')
        until(lambda: 'Test passed' in command('execute if loaded 0 100 0'), 30, 'Fixture chunks load')
        for text in ('time set day', 'gamerule advance_time false', 'weather clear', 'gamerule advance_weather false', 'gamerule spawn_mobs false', 'fill -6 99 -6 6 99 6 stone', 'fill -6 100 -6 6 105 6 air', 'setworldspawn 0 100 3', 'setblock 0 100 0 jukebox', 'setblock 0 101 0 chest'):
            command(text)
        clients = [launch(role, 'phase1', coord) for role in ('owner', 'observer')]
        ready_clients(coord, clients)
        if args.lazo:
            from lazo_test import audio_fixtures
            audio = evidence / 'audio'
            audio_fixtures(audio, durations=(104, 24))
            class Handler(SimpleHTTPRequestHandler):
                def copyfile(self, source, output):
                    try:
                        super().copyfile(source, output)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

                def log_message(self, message, *values):
                    with (evidence / 'http.log').open('a') as output:
                        output.write(message % values + '\n')
            http = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(audio)))
            threading.Thread(target=http.serve_forever, daemon=True).start()
            base = 'http://127.0.0.1:' + str(http.server_port)
            command('setblock 0 100 0 air')
            command('op PlaylistOwner')
            for name, title, slot in (('a', 'Playlist Lazo A', 3), ('b', 'Playlist Lazo B', 7)):
                command('item replace entity PlaylistOwner weapon.mainhand with music_disc_11')
                command('execute as PlaylistOwner run lazodisc burn ' + base + '/' + name + '.wav ' + title)
                predicate = 'execute if items entity PlaylistOwner weapon.mainhand music_disc_11[custom_data~{lazodiscs:{title:"' + title + '"}}]'
                until(lambda: 'Test passed' in command(predicate), 60, 'LazoDiscs burn completes: ' + title)
                command('item replace block 0 101 0 container.' + str(slot) + ' from entity PlaylistOwner weapon.mainhand')
                command('clear PlaylistOwner')
            command('item replace block 0 101 0 container.0 with stone')
            command('item replace block 0 101 0 container.15 with music_disc_13')
            recording_started = int(re.findall(r'\d+', command('time query gametime'))[-1])
            command('setblock 0 100 0 jukebox')
            step(coord, {r: {'action': 'lazo', 'track': 'Playlist Lazo A'} for r in ('owner', 'observer')})
            saved_a = command('data get block 0 100 0')
            check(base + '/a.wav' in saved_a and 'Playlist Lazo A' in saved_a, 'burned disc A reaches the playlist unchanged')
            step(coord, {'owner': {'action': 'chest'}})
            step(coord, {r: {'action': 'lazo-hold', 'track': 'Playlist Lazo A', 'millis': 78000} for r in ('owner', 'observer')})
            elapsed = int(re.findall(r'\d+', command('time query gametime'))[-1]) - recording_started
            receipt['result']['long_recording_server_ticks'] = elapsed
            check(elapsed > 1440, '104-second custom audio survives the underlying vanilla timer: ' + str(elapsed) + ' server ticks')
            if args.audio:
                capture_tones('custom-a', 440)
            step(coord, {r: {'action': 'lazo', 'track': 'Playlist Lazo B'} for r in ('owner', 'observer')})
            saved_b = command('data get block 0 100 0')
            check(base + '/b.wav' in saved_b and 'Playlist Lazo B' in saved_b, 'real custom audio end exchanges A for B')
            if args.audio:
                capture_tones('custom-b', 880)
            check(command('data get block 0 100 0 playlist_position').rstrip().endswith(': 7'), 'recorded playlist cursor before restart is slot 7')
            command('forceload remove all')
            finish_clients(coord, clients)
            collect('phase1')
            command('stop')
            check(server.wait(timeout=60) == 0, 'LazoDiscs dedicated server saves and exits normally')
            coord = evidence / 'phase2'
            coord.mkdir()
            server = launch('server', 'phase2', coord)
            ready_server(server)
            clients = [launch(role, 'phase2', coord) for role in ('owner', 'observer')]
            ready_clients(coord, clients)
            step(coord, {r: {'action': 'lazo', 'track': 'Playlist Lazo B'} for r in ('owner', 'observer')})
            restored = command('data get block 0 100 0')
            check(base + '/b.wav' in restored and 'Playlist Lazo B' in restored, 'recorded disc resumes after a full server/client restart')
            check(command('data get block 0 100 0 playlist_position').rstrip().endswith(': 7'), 'custom-disc restart retains the playlist cursor')
            step(coord, {'owner': {'action': 'skip', 'track': '13'}, 'observer': {'action': 'track', 'track': '13'}})
            check(command('data get block 0 100 0 playlist_position').rstrip().endswith(': 15'), 'owner eject switches both clients from Plasmo audio to the next vanilla disc')
            step(coord, {'owner': {'action': 'lazo-skip', 'track': 'Playlist Lazo A'}, 'observer': {'action': 'lazo', 'track': 'Playlist Lazo A'}})
            check(base + '/a.wav' in command('data get block 0 100 0'), 'vanilla eject returns to the preserved recording A')
            check('minecraft:stone' in command('data get block 0 101 0'), 'unrelated chest item survives the entire mixed playlist')
            finish_clients(coord, clients)
            collect('phase2')
            command('stop')
            check(server.wait(timeout=60) == 0, 'restarted LazoDiscs server exits normally')
            check(hashlib.sha256(release.read_bytes()).hexdigest() == digest, 'installed playlist JAR hash is unchanged')
            receipt['result']['success'] = True
            print('PLAYLIST LAZO PAIR TESTS PASSED', flush=True)
            return
        for text in ('item replace block 0 101 0 container.0 with stone', 'item replace block 0 101 0 container.3 with music_disc_11', 'item replace block 0 101 0 container.7 with music_disc_cat[custom_name={text:"Playlist named cat"}]'):
            command(text)
        step(coord, {r: {'action': 'track', 'track': '11'} for r in ('owner', 'observer')})
        step(coord, {'owner': {'action': 'chest'}})
        step(coord, {r: {'action': 'track', 'track': 'cat'} for r in ('owner', 'observer')})
        check('Playlist named cat' in command('data get block 0 100 0'), 'natural transition retains the custom name on the server')
        check('music_disc_11' in command('data get block 0 101 0'), 'previous record returns to chest')
        if args.audio:
            for role in ('owner', 'observer'):
                check(route_audio(role), role + ' audio stream is routed to its own test sink before capture')
            time.sleep(1)
            def capture(role):
                path = evidence / (role + '-cat.wav')
                subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'pulse', '-i', sinks[role]['name'] + '.monitor', '-t', '6', '-ar', '22050', '-ac', '1', '-c:a', 'pcm_s16le', str(path)], check=True, timeout=20)
                with wave.open(str(path)) as wav:
                    values = struct.unpack('<' + 'h' * wav.getnframes(), wav.readframes(wav.getnframes()))
                rms = (sum(v * v for v in values) / len(values)) ** .5
                return rms
            with ThreadPoolExecutor(max_workers=2) as pool:
                rms = dict(zip(('owner', 'observer'), pool.map(capture, ('owner', 'observer'))))
            receipt['result']['audio_rms'] = rms
            for role, value in rms.items():
                check(value > 10, role + ' has non-silent PCM output from its own audio sink')
        step(coord, {'owner': {'action': 'skip', 'track': '11'}, 'observer': {'action': 'track', 'track': '11'}})
        check('music_disc_11' in command('data get block 0 100 0'), 'owner skip changes the dedicated server record')
        check(command('data get block 0 100 0 playlist_position').rstrip().endswith(': 7'), 'cursor before restart is chest slot 7')
        command('item replace block 0 101 0 container.2 with music_disc_cat')
        command('item replace block 0 101 0 container.15 with music_disc_13')
        finish_clients(coord, clients)
        collect('phase1')
        command('stop')
        check(server.wait(timeout=60) == 0, 'dedicated server saves the world and exits normally')
        coord = evidence / 'phase2'
        coord.mkdir()
        server = launch('server', 'phase2', coord)
        ready_server(server)
        clients = [launch(role, 'phase2', coord) for role in ('owner', 'observer')]
        ready_clients(coord, clients)
        step(coord, {r: {'action': 'track', 'track': '13'} for r in ('owner', 'observer')})
        check('music_disc_13' in command('data get block 0 100 0'), 'restart uses the saved cursor and selects slot 15 before slot 2')
        chest = command('data get block 0 101 0')
        check('music_disc_cat' in chest and 'music_disc_11' in chest and 'music_disc_13' not in chest and 'minecraft:stone' in chest, 'restart preserves all chest records and unrelated stone')
        check(command('data get block 0 100 0 playlist_position').rstrip().endswith(': 15'), 'cursor after restart points to slot 15')
        finish_clients(coord, clients)
        collect('phase2')
        command('stop')
        check(server.wait(timeout=60) == 0, 'restarted dedicated server exits normally')
        receipt['result']['success'] = True
        print('PLAYLIST PAIR TESTS PASSED', flush=True)
    except BaseException:
        receipt['result']['error'] = traceback.format_exc()
        print(receipt['result']['error'], flush=True)
        raise
    finally:
        receipt['result']['checks'] = checks
        receipt['result']['jar_unchanged'] = hashlib.sha256(release.read_bytes()).hexdigest() == digest
        if not receipt['result']['success']:
            try:
                rcon(rcon_port, password, 'stop')
            except (OSError, ValueError):
                pass
            for role in ('owner', 'observer'):
                if role in client_pids:
                    temporary = coord / (role + '-request.tmp')
                    write(temporary, json.dumps({'id': 9999, 'action': 'quit'}))
                    temporary.replace(coord / (role + '-request.json'))
            time.sleep(3)
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        for sink in sinks.values():
            subprocess.run(['pactl', 'unload-module', sink['module']], check=False)
        for output in outputs:
            output.close()
        if http is not None:
            http.shutdown()
            http.server_close()
        write(evidence / 'result.json', json.dumps(receipt, indent=2) + '\n')
        write(ROOT / 'build/results' / ('fabric-26.3-' + kind + '.json'), json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
