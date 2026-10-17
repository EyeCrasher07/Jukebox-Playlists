#!/usr/bin/env python3
"""Exercise an unchanged release JAR in a real Minecraft client and audio engine."""
import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import traceback
import zipfile

from build import gradle
from generate import ROOT, adapt_forge1165, version, write


def prepare(target, java_paths=(), lazo=False, audio_base=None, legacy_discs=False):
    mc, loader = target['minecraft'], target['loader']
    modern = mc == '26.3'
    legacy = mc == '1.16.5'
    if not modern and not (loader in ('fabric', 'forge') and mc in ('1.16.5', '1.20.6')) and not (lazo and target['id'] in ('forge-1.20.2', 'forge-1.21')):
        raise ValueError('Client fixture supports 26.3, 1.16.5 and Fabric/Forge 1.20.6')
    folder = ROOT / 'build/targets' / (('client-lazo-' if lazo else 'client-') + target['id'])
    folder.mkdir(parents=True, exist_ok=True)
    original = ROOT / loader / mc
    for name in ('settings.gradle', 'gradle.properties'):
        shutil.copyfile(original / name, folder / name)
    if java_paths:
        properties = (folder / 'gradle.properties').read_text()
        marker = 'org.gradle.java.installations.paths='
        existing = next((line[len(marker):] for line in properties.splitlines() if line.startswith(marker)), '')
        properties = '\n'.join(line for line in properties.splitlines() if not line.startswith(marker)) + '\n'
        properties += marker + ','.join(filter(None, [existing, *map(str, java_paths)])) + '\n'
        write(folder / 'gradle.properties', properties)
    mod_version = json.loads((ROOT / 'versions.json').read_text())['mod_version']
    release = ROOT / 'dist' / loader / f'jukebox-playlists-{loader}-{mc}-{mod_version}.jar'
    if not release.is_file():
        raise FileNotFoundError(release)
    src = folder / 'probe/java/dev/eyecrasher/playlistchecks'
    resources = folder / 'probe/resources'
    hit = lambda pos: f'new BlockHitResult(Vec3.atCenterOf({pos}), Direction.SOUTH, {pos}, false)'
    use = lambda pos: f'mc.gameMode.useItemOn(mc.player, ' + ('mc.level, ' if legacy else '') + f'InteractionHand.MAIN_HAND, {hit(pos)})'
    source = (ROOT / 'tools/templates/clienttest/ClientChecks.java.in').read_text()
    replacements = {
        'LAZO_AUDIO_CHECK': 'lazoScenario();' if lazo else '',
        'LAZO_CLIENT_METHODS': (ROOT / 'tools/templates/clienttest/LazoClientScenario.java.in').read_text() if lazo else '',
        'EXECUTE_COMMAND': 'performCommand' if legacy else 'performPrefixedCommand',
        'ENVIRONMENT_COMMANDS': ', '.join(map(json.dumps, ['time set day', 'weather clear', 'difficulty peaceful'] + (['gamerule advance_time false', 'gamerule advance_weather false', 'gamerule spawn_mobs false'] if modern else ['gamerule doDaylightCycle false', 'gamerule doWeatherCycle false', 'gamerule doMobSpawning false']))),
        'SOUND_ID': 'getIdentifier' if modern else 'getLocation',
        'OPEN_WORLD': 'if (!opened && ticks > 100 && mc.screen instanceof net.minecraft.client.gui.screens.TitleScreen && mc.getOverlay() == null) { opened = true; mc.loadLevel("playlist-client-fixture"); }' if legacy else 'if (!opened && ticks > 100 && mc.screen instanceof net.minecraft.client.gui.screens.TitleScreen && mc.getOverlay() == null) { opened = true; mc.createWorldOpenFlows().loadLevel(mc.screen, "playlist-client-fixture"); }' if lazo and version(mc) < (1, 20, 5) else 'if (!opened && ticks > 100 && mc.screen instanceof net.minecraft.client.gui.screens.TitleScreen && mc.getOverlay() == null) { opened = true; mc.createWorldOpenFlows().openWorld("playlist-client-fixture", () -> {}); }' if lazo else '',
        'CLOSE_SCREEN': 'mc.gui.setScreen(null)' if modern else 'mc.setScreen(null)',
        'CLOSE_CONTAINER': 'mc.player.closeContainer()',
        'SCREEN': 'mc.gui.screen()' if modern else 'mc.screen',
        'USE_CHEST': use('POS.above()'),
        'USE_JUKEBOX': use('POS'),
        'NAME_STACK': 'named.setHoverName(new net.minecraft.network.chat.TextComponent("Playlist named cat"));' if legacy else 'named.setHoverName(net.minecraft.network.chat.Component.literal("Playlist named cat"));' if version(mc) < (1, 20, 5) else 'named.set(net.minecraft.core.component.DataComponents.CUSTOM_NAME, net.minecraft.network.chat.Component.literal("Playlist named cat"));',
        'CLEAR_INVENTORY': 'player.inventory.clearContent();' if legacy else 'player.getInventory().clearContent();',
        'CLEAR_DROPS': 'for (var entity : world.getEntitiesOfClass(net.minecraft.world.entity.item.ItemEntity.class, new net.minecraft.world.phys.AABB(POS).inflate(32))) entity.' + ('remove' if legacy else 'discard') + '();',
        'SCREENSHOT': 'Screenshot.grab(mc, false)' if modern else 'Screenshot.grab(new File("."), mc.getWindow().getWidth(), mc.getWindow().getHeight(), mc.getMainRenderTarget(), text -> {})' if legacy else 'Screenshot.grab(new File("."), mc.getMainRenderTarget(), text -> {})',
    }
    for key, value in replacements.items():
        source = source.replace('@' + key + '@', value)
    if legacy_discs:
        source = source.replace('        // Place records only', '        legacyDiscs();\n        // Place records only')
        source = source.replace('    private static PlaylistJukebox box()', (ROOT / 'tools/templates/clienttest/LegacyDiscClientScenario.java.in').read_text() + '\n    private static PlaylistJukebox box()')
    write(src / 'ClientChecks.java', source)
    write(src / 'ClientTickMixin.java', '''package dev.eyecrasher.playlistchecks.mixin;
import dev.eyecrasher.playlistchecks.ClientChecks;
import net.minecraft.client.Minecraft;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(Minecraft.class) public abstract class ClientTickMixin {
 @Inject(method="tick",at=@At("TAIL")) private void checks$tick(CallbackInfo ci) { ClientChecks.tick(); }
}
''')
    callback = 'CallbackInfoReturnable<?> ci' if modern else 'CallbackInfo ci'
    write(src / 'SoundMixin.java', '''package dev.eyecrasher.playlistchecks.mixin;
import dev.eyecrasher.playlistchecks.ClientChecks;
import net.minecraft.client.sounds.SoundEngine;
import net.minecraft.client.resources.sounds.SoundInstance;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.*;
@Mixin(SoundEngine.class) public abstract class SoundMixin {
 @Inject(method="play",at=@At("HEAD")) private void checks$sound(SoundInstance sound, ''' + callback + ''') { ClientChecks.sound(sound); }
}
''')
    config = {'required': True, 'minVersion': '0.8', 'package': 'dev.eyecrasher.playlistchecks.mixin', 'compatibilityLevel': 'JAVA_21' if modern else 'JAVA_8' if loader == 'forge' and legacy else 'JAVA_17', 'client': ['ClientTickMixin', 'SoundMixin'], 'injectors': {'defaultRequire': 1}}
    if loader == 'forge' and mc in ('1.16.5', '1.20.2'):
        config['refmap'] = 'playlist-client-checks.refmap.json'
    write(resources / 'playlist-client-checks.mixins.json', json.dumps(config, indent=2) + '\n')
    if loader == 'fabric':
        write(resources / 'fabric.mod.json', json.dumps({'schemaVersion': 1, 'id': 'playlist_client_checks', 'version': '1.0', 'name': 'Playlist client checks', 'environment': 'client', 'mixins': ['playlist-client-checks.mixins.json'], 'depends': {'jukebox_playlists': '*'}}, indent=2) + '\n')
    else:
        annotation = 'net.neoforged.fml.common.Mod' if loader == 'neoforge' else 'net.minecraftforge.fml.common.Mod'
        write(src / 'ClientCheckMod.java', f'package dev.eyecrasher.playlistchecks;\n@{annotation}("playlist_client_checks") public final class ClientCheckMod {{}}\n')
        metadata = 'META-INF/neoforge.mods.toml' if loader == 'neoforge' else 'META-INF/mods.toml'
        with zipfile.ZipFile(release) as jar:
            text = jar.read(metadata).decode().replace('jukebox_playlists', 'playlist_client_checks').replace('Jukebox Playlists', 'Playlist Client Checks')
            write(resources / 'pack.mcmeta', jar.read('pack.mcmeta').decode())
        text = text.replace('jukebox-playlists.mixins.json', 'playlist-client-checks.mixins.json')
        write(resources / metadata, text)
    if legacy_discs:
        from legacy_audio import prepare_fixture
        prepare_fixture(target, folder / 'probe/java', resources)
    if loader == 'forge' and mc == '1.16.5':
        for generated in ('classes', 'resources', 'libs'):
            shutil.rmtree(folder / 'build' / generated, ignore_errors=True)
        adapt_forge1165(src)
        classes = {
            'net.minecraft.client.sounds.SoundEngine': 'net.minecraft.client.audio.SoundEngine',
            'net.minecraft.client.resources.sounds.SoundInstance': 'net.minecraft.client.audio.ISound',
            'net.minecraft.sounds.SoundSource': 'net.minecraft.util.SoundCategory',
            'net.minecraft.client.Screenshot': 'net.minecraft.util.ScreenShotHelper',
            'net.minecraft.world.level.GameType': 'net.minecraft.world.GameType',
            'net.minecraft.client.gui.screens.TitleScreen': 'net.minecraft.client.gui.screen.MainMenuScreen',
            'net.minecraft.client.gui.screens.inventory.ContainerScreen': 'net.minecraft.client.gui.screen.inventory.ChestScreen',
            'net.minecraft.world.entity.item.ItemEntity': 'net.minecraft.entity.item.ItemEntity',
            'net.minecraft.world.phys.AABB': 'net.minecraft.util.math.AxisAlignedBB',
            'net.minecraft.server.level.ServerLevel': 'net.minecraft.world.server.ServerWorld',
            'net.minecraft.server.level.ServerPlayer': 'net.minecraft.entity.player.ServerPlayerEntity',
        }
        for path in src.rglob('*.java'):
            text = path.read_text()
            text = text.replace('var world =', 'net.minecraft.server.level.ServerLevel world =').replace('var player =', 'net.minecraft.server.level.ServerPlayer player =').replace('var entity :', 'net.minecraft.world.entity.item.ItemEntity entity :')
            for old, new in classes.items():
                text = text.replace(old, new)
            for old, new in classes.items():
                text = re.sub(r'\b' + old.rsplit('.', 1)[1] + r'\b', new.rsplit('.', 1)[1], text)
            write(path, text)
        services = {
            'cpw.mods.modlauncher.api.ILaunchHandlerService': 'net.minecraftforge.userdev.FMLUserdevClientLaunchProvider',
            'cpw.mods.modlauncher.api.INameMappingService': 'net.minecraftforge.userdev.MCPNamingService',
            'net.minecraftforge.forgespi.locating.IModLocator': 'net.minecraftforge.userdev.ClasspathLocator',
        }
        for service in services:
            # The installed client uses Forge's normal launcher, not userdev.
            (resources / 'META-INF/services' / service).unlink(missing_ok=True)
    build = (original / 'build.gradle').read_text().split("apply from: new File(playlistRoot, 'gradle/release.gradle')")[0]
    build = build.replace("file('../..').absolutePath", json.dumps(str(ROOT)))
    build = build.replace('jukebox_playlists { source sourceSets.main }', 'playlist_client_checks { source sourceSets.main }').replace('jukebox_playlists { sourceSet(sourceSets.main) }', 'playlist_client_checks { sourceSet(sourceSets.main) }')
    build = build.replace("args '--mixin.config=jukebox-playlists.mixins.json'", "args '--mixin.config=playlist-client-checks.mixins.json'")
    build = build.replace('jukebox-playlists.mixins.json', 'playlist-client-checks.mixins.json')
    build += '''
version = 'client-checks'
base { archivesName = 'playlist-client-checks' }
sourceSets.main { java.setSrcDirs(['probe/java']); resources.setSrcDirs(['probe/resources']) }
tasks.withType(JavaCompile).configureEach { options.encoding='UTF-8' }
jar { manifest { attributes 'MixinConfigs': 'playlist-client-checks.mixins.json' } }
'''
    named_classes = original / 'build/classes/java/main'
    build += 'dependencies { compileOnly files(' + json.dumps(str(named_classes)) + ') }\n'
    if loader == 'forge':
        build += '''sourceSets.main.output.resourcesDir = layout.buildDirectory.dir('classes/java/main').get().asFile
tasks.named('processResources') { dependsOn tasks.named('compileJava'); destinationDir = sourceSets.main.output.resourcesDir }
'''
        if mc == '1.16.5':
            build += "tasks.withType(JavaCompile).configureEach { options.release=8 }\n"
    # Prepare a copy of the already-created isolated server world, not owner saves.
    seed = ROOT / 'build/targets' / ('test-fabric-' + mc) / 'build/run/server/world'
    if not seed.is_dir():
        raise FileNotFoundError('Prepare a Fabric smoke-test seed first: ' + str(seed))
    args = ['--username', 'PlaylistTester', '--accessToken', '0', '--version', 'Playlist-test', '--width', '960', '--height', '540']
    if not legacy and not lazo:
        args += ['--quickPlaySingleplayer', 'playlist-client-fixture']
    if loader != 'fabric':
        args[args.index('--version'):args.index('--version') + 2] = []
    options = 'onboardAccessibility:false\nguiScale:2\nrenderDistance:3\nsimulationDistance:5\nmaxFps:60\nenableVsync:false\nlang:en_us\ntutorialStep:none\nsoundCategory_music:0.0\nsoundCategory_master:0.35\nsoundCategory_record:1.0\npauseOnLostFocus:false\n'
    fixture = '''
def prepareClientFixture = {
    def run = file('build/run/client')
    copy { from file(SEED); into new File(run, 'saves/playlist-client-fixture'); exclude 'session.lock' }
    new File(run, 'options.txt').text = OPTIONS
    new File(run, 'mods').mkdirs()
    copy { from file(RELEASE); into new File(run, 'mods') }
}
'''.replace('SEED', json.dumps(str(seed))).replace('RELEASE', json.dumps(str(release))).replace('OPTIONS', json.dumps(options))
    build += fixture
    if loader == 'fabric':
        build = build.replace("    copy { from file(" + json.dumps(str(release)) + "); into new File(run, 'mods') }", '')
        # Older Fabric API artifacts use separate modules rather than nested JARs.
        build += f"dependencies {{ productionRuntimeMods('net.fabricmc.fabric-api:fabric-api:{target['fabric_api']}') {{ exclude group: 'net.fabricmc', module: 'fabric-loader' }} }}\n"
        build += '''tasks.register('runPlaylistClient', net.fabricmc.loom.task.prod.ClientProductionRunTask) {
    mods.setFrom(tasks.named(PROBE_JAR), configurations.productionRuntimeMods, file(RELEASE))
    runDir = layout.buildDirectory.dir('run/client')
    jvmArgs.addAll('-Xmx2G')
    programArgs.addAll(ARGS)
    doFirst { prepareClientFixture() }
}
'''.replace('PROBE_JAR', "'jar'" if modern else "'remapJar'").replace('RELEASE', json.dumps(str(release))).replace('ARGS', ', '.join(json.dumps(a) for a in args))
    elif loader == 'neoforge':
        build += 'neoForge.runs { client { client(); gameDirectory = file("build/run/client"); programArguments.addAll(' + ', '.join(json.dumps(a) for a in args) + "); jvmArgument '-Xmx2G' } }\n"
        build += "tasks.configureEach { if (name == 'runClient') doFirst { prepareClientFixture() } }\n"
    else:
        build += 'minecraft.runs { register("client") { workingDir = layout.buildDirectory.dir("run/client"); args ' + ', '.join(json.dumps(a) for a in args) + "; jvmArgs '-Xmx2G' } }\n"
        build += "tasks.configureEach { if (name == 'runClient') doFirst { prepareClientFixture() } }\n"
        if mc in ('1.20.6', '1.21'):
            build += "configurations.configureEach { resolutionStrategy.force 'net.sf.jopt-simple:jopt-simple:5.0.4' }\n"
        if lazo and audio_base:
            build += 'minecraft.runs.named("client") { systemProperty "playlist.audioBase", ' + json.dumps(audio_base) + ' }\n'
        if mc == '1.16.5':
            build += '''
def legacyNatives = configurations.create('playlistLegacyNatives') { transitive=false }
def os = System.getProperty('os.name').toLowerCase(Locale.ROOT)
def classifier = os.contains('win') ? 'natives-windows' : os.contains('mac') ? 'natives-macos' : 'natives-linux'
['lwjgl','lwjgl-glfw','lwjgl-opengl','lwjgl-openal','lwjgl-stb','lwjgl-jemalloc','lwjgl-tinyfd'].each {
    dependencies.add(legacyNatives.name, "org.lwjgl:${it}:3.2.2:${classifier}")
}
def nativeDirectory=layout.buildDirectory.dir('run/legacy-natives')
tasks.register('preparePlaylistNatives', Sync) {
    from { legacyNatives.collect { zipTree(it) } }
    include '**/*.so','**/*.dll','**/*.dylib'
    into nativeDirectory
}
minecraft.runs.named('client') {
    client=true
    systemProperty 'org.lwjgl.librarypath',nativeDirectory.get().asFile.absolutePath
    environment 'assetDirectory',new File(gradle.gradleUserHomeDir, 'caches/fabric-loom/assets').absolutePath
    environment 'assetIndex','1.16.5-1.16'
    environment 'nativesDirectory',nativeDirectory.get().asFile.absolutePath
}
tasks.configureEach { if (name == 'runClient') { getClient().set(true); dependsOn tasks.named('preparePlaylistNatives') } }
'''
    write(folder / 'build.gradle', build)
    if lazo:
        from lazo_deps import files
        run = folder / 'build/run/client'
        mods = run / 'mods'
        mods.mkdir(parents=True, exist_ok=True)
        dependencies = files(target['id'])
        if target['id'] == 'forge-1.20.2':
            from patch_plasmo_voice import patch, FILENAME
            dependencies[1] = patch(dependencies[1], ROOT / 'build/compat-deps' / FILENAME)
        for dependency in dependencies:
            shutil.copyfile(dependency, mods / dependency.name)
        write(run / 'config/plasmovoice/client.toml', 'check_for_updates=false\n[voice]\nmicrophone_disabled=true\ndisable_input_device=true\n')
        write(run / 'config/lazodiscs/config.toml', '[security]\nallowHttp=true\nallowedDomains=["127.0.0.1"]\n')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        write(run / 'config/plasmovoice/server/config.toml', '[host]\nip="127.0.0.1"\nport=' + str(port) + '\n')
    gv = '9.7.1' if loader == 'fabric' and modern else '8.14.5' if loader == 'fabric' else '9.5.1'
    return folder, gv, release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--offline', action='store_true', help='Resolve Gradle dependencies from cache')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--lazo-startup', action='store_true', help='Forge 1.20.2/1.21: burn and play LazoDiscs through Plasmo Voice, then run the native regression')
    parser.add_argument('--legacy-discs', action='store_true', help='1.16.5: genuine modded RecordItems, bundled OGG and automatic transitions')
    parser.add_argument('--java-path', action='append', type=Path, default=[])
    args = parser.parse_args()
    target = next(t for t in json.loads((ROOT / 'versions.json').read_text())['targets'] if t['id'] == args.target)
    if args.lazo_startup and target['id'] not in ('forge-1.20.2', 'forge-1.21'):
        parser.error('--lazo-startup currently covers Forge 1.20.2 and 1.21')
    if args.legacy_discs and (target['minecraft'] != '1.16.5' or args.lazo_startup):
        parser.error('--legacy-discs currently covers Fabric/Forge 1.16.5 without --lazo-startup')
    if args.prepare_only:
        folder, _, _ = prepare(target, args.java_path, args.lazo_startup, legacy_discs=args.legacy_discs)
        print(folder)
        return
    attempt = time.strftime('%Y%m%d-%H%M%S')
    evidence = ROOT / 'build/evidence' / (('lazo-client-' if args.lazo_startup else 'legacy-discs-client-' if args.legacy_discs else '') + target['id']) / attempt
    evidence.mkdir(parents=True)
    http = None
    if args.lazo_startup:
        from lazo_test import audio_fixtures
        audio = evidence / 'audio'
        audio_fixtures(audio, (18, 12))
        class Handler(SimpleHTTPRequestHandler):
            def copyfile(self, source, output):
                try:
                    super().copyfile(source, output)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Removing the jukebox intentionally closes its stream.

            def log_message(self, message, *values):
                with (evidence / 'http.log').open('a') as output:
                    output.write((message % values) + '\n')
        http = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(audio)))
        threading.Thread(target=http.serve_forever, daemon=True).start()
    folder, gv, release = prepare(target, args.java_path, args.lazo_startup,
                                 'http://127.0.0.1:' + str(http.server_port) if http else None, args.legacy_discs)
    # Retain older test installations without loading two versions together.
    for old in (folder / 'build/run/client/mods').glob('jukebox-playlists-*.jar'):
        if old.name != release.name or old.read_bytes() != release.read_bytes():
            previous = folder / 'build/previous-mods' / attempt / old.name
            previous.parent.mkdir(parents=True, exist_ok=True)
            old.rename(previous)
    before = hashlib.sha256(release.read_bytes()).hexdigest()
    log = evidence / 'minecraft.log'
    command = gradle(gv) + ['--console=plain', '--max-workers=2']
    if args.offline:
        command += ['--offline']
    installed = target['id'] in ('forge-1.16.5', 'forge-1.20.2')
    command += ['renameJar', 'preparePlaylistNatives'] if target['id'] == 'forge-1.16.5' else ['renameJar'] if installed else ['runPlaylistClient' if target['loader'] == 'fabric' else 'runClient']
    started = time.monotonic()
    with log.open('w') as output:
        try:
            result = subprocess.run(command, cwd=folder, stdout=output, stderr=subprocess.STDOUT, timeout=720)
            if installed and result.returncode == 0:
                if target['id'] == 'forge-1.20.2':
                    from installed_forge import run_client1202
                    result = run_client1202(folder, release, target['loader_version'], args.java_path, output, 'http://127.0.0.1:' + str(http.server_port))
                else:
                    from installed_forge import run_client
                    result = run_client(folder, release, target['loader_version'], args.java_path, output)
            success = result.returncode == 0 and 'PLAYLIST CLIENT TESTS PASSED' in log.read_text(errors='replace')
            if success and args.lazo_startup:
                import tomllib
                config = tomllib.loads((folder / 'build/run/client/config/plasmovoice/client.toml').read_text())
                text = log.read_text(errors='replace')
                requests = (evidence / 'http.log').read_text() if (evidence / 'http.log').exists() else ''
                success = config['voice']['microphone_disabled'] and config['voice']['disable_input_device'] and 'LazoDiscs Plasmo Voice addon initialized' in text and text.count('Streaming LazoDisc audio sender started') >= 2 and 'Failed to start streaming LazoDisc' not in text and all(name in requests for name in ('/a.wav', '/b.wav'))
        except subprocess.TimeoutExpired:
            success = False
        except Exception:
            traceback.print_exc(file=output)
            success = False
        finally:
            if http:
                http.shutdown()
                http.server_close()
    assert before == hashlib.sha256(release.read_bytes()).hexdigest(), 'Release JAR changed during the test'
    screenshots = []
    if success:
        evidence.mkdir(parents=True, exist_ok=True)
        stages = ('01-playing-11', '02-chest', '03-natural-transition-cat', '04-repeat-11')
        if args.lazo_startup:
            stages = ('00-lazodiscs-a', '00-lazodiscs-b', *stages)
        if args.legacy_discs:
            stages = ('00-modded-slow', '00-modded-short', *stages)
        images = sorted((folder / 'build/run/client/screenshots').glob('*.png'), key=lambda p: p.stat().st_mtime)[-len(stages):]
        for stage, screenshot in zip(stages, images):
            dest = evidence / (stage + '.png')
            shutil.copyfile(screenshot, dest)
            screenshots.append(str(dest.relative_to(ROOT)))
        shutil.copyfile(folder / 'build/run/client/client-checks.txt', evidence / 'checks.txt')
    kind = 'lazo_client_runtime' if args.lazo_startup else 'legacy_discs_client_runtime' if args.legacy_discs else 'client_runtime'
    record = {'target': target['id'], 'kind': kind, 'result': {'success': success, 'seconds': round(time.monotonic() - started, 1), 'loader_version': target['loader_version'], 'artifact': str(release.relative_to(ROOT)), 'sha256': before, 'log': str(log.relative_to(ROOT)), 'screenshots': screenshots}}
    write(evidence / 'result.json', json.dumps(record, indent=2) + '\n')
    write(ROOT / 'build/results' / (target['id'] + '-' + kind + '.json'), json.dumps(record, indent=2) + '\n')
    print(('PASS ' if success else 'FAIL ') + target['id'], flush=True)
    if not success:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-70:]))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
