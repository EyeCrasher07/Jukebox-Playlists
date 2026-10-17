#!/usr/bin/env python3
"""Build isolated, pinned loader projects and collect production jars."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from generate import ROOT, version, write


def project(target, tests=False, java_paths=(), production=False, folder_name=None):
    loader, mc, pin = target["loader"], target["minecraft"], target["loader_version"]
    v = version(mc)
    folder = ROOT / "build/targets" / (folder_name or (("production-test-" if production else "test-" if tests else "") + target["id"]))
    folder.mkdir(parents=True, exist_ok=True)
    repositories = '''maven { url = 'https://maven.fabricmc.net/' }
        maven { url = 'https://maven.minecraftforge.net/' }
        maven { url = 'https://maven.neoforged.net/releases/' }
        gradlePluginPortal()
        mavenCentral()'''
    write(folder / "settings.gradle", "pluginManagement { repositories { " + repositories + " } }\nrootProject.name = 'jukebox-playlists'\n")
    properties = "org.gradle.jvmargs=-Xmx2G\norg.gradle.daemon=true\norg.gradle.workers.max=2\n"
    # Let Gradle discover installed JDKs. Explicit locations are a local build option.
    installations = [p for p in [os.environ.get("PLAYLIST_JAVA_PATHS"), *map(str, java_paths)] if p]
    if installations:
        properties += "org.gradle.java.installations.paths=" + ",".join(installations) + "\n"
    write(folder / "gradle.properties", properties)
    # JSON string literals are also valid Groovy string literals for these values.
    header = "ext.playlistRoot = " + json.dumps(str(ROOT)) + "\next.playlistTarget = new groovy.json.JsonSlurper().parseText('" + json.dumps(target) + "')\n"
    shared = "\napply from: new File(playlistRoot, 'gradle/common.gradle')\n"
    toolchain = max(17, target["java"])
    common = f"\njava {{ toolchain.languageVersion = JavaLanguageVersion.of({toolchain}) }}\n"
    if loader == "fabric":
        modern = mc.startswith("26.")
        plugin = "net.fabricmc.fabric-loom" if modern else "fabric-loom"
        plugin_version = "1.17.21" if modern else "1.13.6"
        plugins = f"plugins {{ id '{plugin}' version '{plugin_version}' }}\n"
        body = common + "repositories { mavenCentral() }\ndependencies {\n" + f"minecraft 'com.mojang:minecraft:{mc}'\n"
        if not modern:
            body += "mappings loom.officialMojangMappings()\n"
        body += f"{'implementation' if modern else 'modImplementation'} 'net.fabricmc:fabric-loader:{pin}'\n}}\n"
        body += f"dependencies {{ {'implementation' if modern else 'modImplementation'} 'net.fabricmc.fabric-api:fabric-api:{target['fabric_api']}' }}\n"
        body += "loom.runs { server { runDir 'build/run/server'; programArg 'nogui' } }\n"
        if production:
            body += f"dependencies {{ productionRuntimeMods 'net.fabricmc.fabric-api:fabric-api:{target['fabric_api']}' }}\n"
            body += '''tasks.register('runPlaylistProduction', net.fabricmc.loom.task.prod.ServerProductionRunTask) {
    runDir = layout.buildDirectory.dir('run/server')
    jvmArgs.addAll('-Xmx2G')
    doFirst {
        copy { from file(providers.gradleProperty('playlistEula').get()); into runDir }
        copy { from file('server.properties.fixture'); into runDir; rename { 'server.properties' } }
    }
}
'''
        gradle_version = "9.7.1" if modern else "8.14.5"
    elif loader == "forge":
        remap = v < (1, 20, 5)
        plugins = "plugins { id 'java'; id 'net.minecraftforge.gradle' version '7.0.17'"
        if remap:
            plugins += "; id 'net.minecraftforge.renamer' version '1.0.14'"
        plugins += " }\n"
        mappings = f"mappings channel: 'official', version: '{mc}'\n" if not mc.startswith("26.") else ""
        body = common + "minecraft {\n" + mappings + '''runs {
    configureEach { mods { jukebox_playlists { source sourceSets.main } }; args '--mixin.config=jukebox-playlists.mixins.json' }
    register('server') { workingDir = layout.buildDirectory.dir('run/server'); args '--nogui' }
} }
repositories { minecraft.mavenizer(it); maven fg.forgeMaven; maven fg.minecraftLibsMaven; mavenCentral() }
''' + f"dependencies {{ implementation minecraft.dependency('net.minecraftforge:forge:{pin}') }}\n"
        if remap:
            body += '''renamer.enableMixinRefmaps { config 'jukebox-playlists.mixins.json' }
renamer.mappings(minecraft.dependency.toSrg)
tasks.named('jar') { archiveClassifier = 'dev' }
def productionJar = renamer.classes(tasks.named('jar', Jar)) {
    archiveClassifier = ''
    mappings renamer.mixin.generatedMappings
    output = layout.buildDirectory.file('libs/' + base.archivesName.get() + '-' + project.version + '.jar')
}
tasks.named('assemble') { dependsOn productionJar }
def playlistRenamerLauncher = javaToolchains.launcherFor { languageVersion = JavaLanguageVersion.of(17) }
tasks.named('renameJar') { javaLauncher.set(playlistRenamerLauncher) }
dependencies { annotationProcessor 'org.spongepowered:mixin:0.8.5:processor' }
'''
        gradle_version = "9.5.1"
    elif mc == "1.20.1":
        plugins = "plugins { id 'java-library'; id 'net.neoforged.moddev.legacyforge' version '2.0.148' }\n"
        body = common + f"legacyForge {{ enable {{ neoForgeVersion = '{pin}'; disableRecompilation = true }}\n" + '''mods { jukebox_playlists { sourceSet(sourceSets.main) } }
    runs { server { server(); gameDirectory = file('build/run/server'); programArgument '--nogui' } }
}
repositories { mavenCentral() }
dependencies { annotationProcessor 'org.spongepowered:mixin:0.8.5:processor' }
mixin { add sourceSets.main, 'main.refmap.json'; config 'jukebox-playlists.mixins.json' }
'''
        gradle_version = "9.5.1"
    elif v < (1, 20, 4) or mc == "1.20.5":
        plugins = "plugins { id 'java-library'; id 'net.neoforged.gradle.userdev' version '7.1.39' }\n"
        body = common + f"dependencies {{ implementation 'net.neoforged:neoforge:{pin}' }}\n" + '''repositories { mavenCentral() }
runs {
    configureEach { workingDirectory file('build/run/server'); modSources { add('jukebox_playlists', sourceSets.main) } }
    server { argument '--nogui' }
}
tasks.withType(net.neoforged.gradle.common.runtime.tasks.JavaSourceTransformer).configureEach {
    javaLauncher.set(javaToolchains.launcherFor { languageVersion = JavaLanguageVersion.of(21) })
}
'''
        gradle_version = "8.14.5"
    else:
        plugins = "plugins { id 'java-library'; id 'net.neoforged.moddev' version '2.0.148' }\n"
        body = common + f"neoForge {{ version = '{pin}'\n" + '''mods { jukebox_playlists { sourceSet(sourceSets.main) } }
    runs { server { server(); gameDirectory = file('build/run/server'); programArgument '--nogui' } }
}
repositories { mavenCentral() }
'''
        gradle_version = "9.5.1"
    if tests:
        # Several isolated servers share this workstation during the matrix.
        if loader == 'fabric':
            body += "loom.runs.server { vmArg '-Xmx1500M'; vmArg '-XX:ActiveProcessorCount=2' }\n"
        elif loader == 'forge':
            body += "minecraft.runs.named('server') { jvmArgs '-Xmx1500M', '-XX:ActiveProcessorCount=2' }\n"
        elif mc == '1.20.1':
            body += "legacyForge.runs.server { jvmArgument '-Xmx1500M'; jvmArgument '-XX:ActiveProcessorCount=2' }\n"
        elif v < (1, 20, 4) or mc == '1.20.5':
            body += "runs.server { jvmArguments.addAll('-Xmx1500M', '-XX:ActiveProcessorCount=2') }\n"
        else:
            body += "neoForge.runs.server { jvmArgument '-Xmx1500M'; jvmArgument '-XX:ActiveProcessorCount=2' }\n"
    write(folder / "build.gradle", plugins + header + body + shared)
    return folder, gradle_version


def gradle(version_number):
    override = os.environ.get("PLAYLIST_GRADLE_" + version_number.replace(".", "_"))
    if override:
        return [override]
    paths = list((Path.home() / ".gradle/wrapper/dists" / ("gradle-" + version_number + "-bin")).glob("*/gradle-*/bin/gradle"))
    if paths:
        return [str(paths[0])]
    executable = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.environ.get("JAVA_HOME") else "java"
    return [str(executable), "-classpath", str(ROOT / "gradle/wrappers" / version_number / "gradle-wrapper.jar"), "org.gradle.wrapper.GradleWrapperMain"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", action="append", help="loader-version; can be repeated; defaults to all")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--production-smoke", action="store_true", help="Fabric: run the remapped test jar through the normal server installer")
    parser.add_argument("--eula-file", type=Path, help="Existing accepted Minecraft EULA file for the test server")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--java-path", action="append", type=Path, default=[], help="Additional installed Java runtime/JDK; repeatable")
    args = parser.parse_args()
    if args.production_smoke:
        args.smoke = True
    if args.smoke and (not args.eula_file or not args.eula_file.is_file()
                       or not any(line.strip().lower() == 'eula=true' for line in args.eula_file.read_text().splitlines())):
        parser.error("Server tests need --eula-file pointing to an already accepted Minecraft EULA file")
    data = json.loads((ROOT / "versions.json").read_text())
    targets = [t for t in data["targets"] if not args.target or t["id"] in args.target]
    if args.target and len(targets) != len(set(args.target)):
        parser.error("Unknown target")
    if args.production_smoke and any(t["loader"] != "fabric" for t in targets):
        parser.error("--production-smoke currently supports Fabric targets")
    report_path = ROOT / "build/status.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    failures = []
    for target in targets:
        folder, gradle_version = project(target, args.smoke, args.java_path, args.production_smoke)
        if args.prepare_only:
            print(folder, flush=True)
            continue
        log = ROOT / "build/logs" / (("production-test-" if args.production_smoke else "test-" if args.smoke else "") + target["id"] + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        command = gradle(gradle_version) + ["--console=plain", "--max-workers=2"]
        if args.offline:
            command.append("--offline")
        command += ["-PplaylistTest", "runPlaylistProduction" if args.production_smoke else "runServer"] if args.smoke else ["build"]
        if args.production_smoke:
            command.append("-PplaylistEula=" + str(args.eula_file.resolve()))
        started = time.monotonic()
        print(("TEST " if args.smoke else "BUILD ") + target["id"], flush=True)
        if args.smoke:
            run = folder / "build/run/server"
            run.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.eula_file, run / "eula.txt")
            settings = {"layers": [{"height": 1, "block": "minecraft:bedrock"}, {"height": 3, "block": "minecraft:dirt"}, {"height": 1, "block": "minecraft:grass_block"}], "biome": "minecraft:plains"}
            level_type = "flat" if version(target["minecraft"]) < (1, 19) else "minecraft:flat"
            write(run / "server.properties", f"online-mode=false\nserver-ip=127.0.0.1\nserver-port=0\nlevel-type={level_type}\ngenerator-settings=" + json.dumps(settings) + "\nspawn-protection=0\nview-distance=2\nsimulation-distance=2\n")
            if args.production_smoke:
                shutil.copyfile(run / "server.properties", folder / "server.properties.fixture")
        with log.open("w") as output:
            try:
                result = subprocess.run(command, cwd=folder, stdout=output, stderr=subprocess.STDOUT, timeout=900 if args.smoke else 600)
                success = result.returncode == 0
            except subprocess.TimeoutExpired:
                success = False
        if args.smoke:
            success = success and "PLAYLIST TESTS PASSED" in log.read_text(errors="replace")
        entry = {"success": success, "seconds": round(time.monotonic() - started, 1), "loader_version": target["loader_version"], "log": str(log.relative_to(ROOT))}
        if success and not args.smoke:
            artifact_name = f"jukebox-playlists-{target['loader']}-{target['minecraft']}-{data['mod_version']}.jar"
            jars = [p for p in (folder / "build/libs").glob(artifact_name) if p.is_file()]
            if len(jars) != 1:
                raise RuntimeError(f"Expected one production artifact for {target['id']}: {jars}")
            dest = ROOT / "dist" / target["loader"] / jars[0].name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(jars[0], dest)
            entry.update(artifact=str(dest.relative_to(ROOT)), sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
        kind = "production_runtime" if args.production_smoke else "runtime" if args.smoke else "build"
        write(ROOT / "build/results" / (target["id"] + "-" + kind + ".json"),
              json.dumps({"target": target["id"], "kind": kind, "result": entry}, indent=2) + "\n")
        # Separate result files let independent build/test processes retain both results.
        for result_file in (ROOT / "build/results").glob("*.json"):
            item = json.loads(result_file.read_text())
            report.setdefault(item["target"], {})[item["kind"]] = item["result"]
        temporary = report_path.with_suffix("." + str(os.getpid()) + ".tmp")
        write(temporary, json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)
        print(("PASS " if success else "FAIL ") + target["id"] + f" ({entry['seconds']}s)", flush=True)
        if not success:
            failures.append(target["id"])
            print("\n".join(log.read_text(errors="replace").splitlines()[-25:]), flush=True)
    if failures:
        raise SystemExit("Failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
