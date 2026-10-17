#!/usr/bin/env python3
"""Audit the actual production artifacts, including remapping and target metadata."""
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from generate import prepare

ROOT = Path(__file__).resolve().parents[1]


def main():
    matrix = json.loads((ROOT / "versions.json").read_text())
    status = json.loads((ROOT / "build/status.json").read_text())
    checksums = []
    for target in matrix["targets"]:
        entry = status.get(target["id"], {}).get("build", {})
        assert entry.get("success"), "Unbuilt target: " + target["id"]
        path = ROOT / entry["artifact"]
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        assert checksum == entry["sha256"], "Artifact changed after build: " + str(path)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            for license_file, member in [('LICENSE', 'LICENSE_jukebox-playlists.txt')]:
                assert archive.read(member) == (ROOT / license_file).read_bytes(), 'Missing or stale release license: ' + target['id']
            project = ROOT / target['loader'] / target['minecraft']
            for name in ('build.gradle', 'settings.gradle', 'gradle.properties', 'gradlew', 'gradlew.bat', 'gradle/wrapper/gradle-wrapper.jar', 'gradle/wrapper/gradle-wrapper.properties'):
                assert (project / name).is_file(), 'Missing standalone project file: ' + str(project / name)
            assert (project / 'src/main/java').is_dir() and (project / 'src/main/resources').is_dir()
            assert str(ROOT) not in (project / 'build.gradle').read_text(), 'Nonportable build path'
            expected = ROOT / "build/artifact-audit" / target["id"]
            prepare(target, expected)
            for resource in (expected / "resources").rglob("*"):
                if resource.is_file():
                    name = str(resource.relative_to(expected / "resources"))
                    assert archive.read(name) == resource.read_bytes(), "Stale generated resource: " + target["id"] + "/" + name
            assert "pack.mcmeta" in names, "Missing mod data pack metadata"
            assert not any(n.startswith("net/minecraft/") for n in names), "Minecraft classes in mod jar"
            assert not any(n.startswith(('com/eyecrasher/lazodiscs/', 'su/plo/voice/', 'com/sedmelluq/')) for n in names), "Bundled optional audio dependency"
            assert not any("Smoke" in n or "ServerTestMixin" in n or n.startswith(("dev/eyecrasher/playlistchecks/", "dev/eyecrasher/playlistpair/", "dev/eyecrasher/playlistlazochecks/"))
                           for n in names), "Test code in production jar"
            config = json.loads(archive.read("jukebox-playlists.mixins.json"))
            assert config["required"] and config["injectors"]["defaultRequire"] == 1
            for mixin in config["mixins"]:
                assert config["package"].replace(".", "/") + "/" + mixin + ".class" in names
            if config.get('plugin'):
                assert config['plugin'].replace('.', '/') + '.class' in names
            if "refmap" in config:
                refmap = json.loads(archive.read(config["refmap"]))
                assert refmap.get("mappings"), "Empty production refmap for " + target["id"]
            for name in names:
                if name.endswith(".class"):
                    bytecode = archive.read(name)
                    assert struct.unpack(">H", bytecode[6:8])[0] <= target["java"] + 44, "Wrong Java version in " + name
            if target["loader"] == "fabric":
                metadata = json.loads(archive.read("fabric.mod.json"))
                assert metadata['license'] == 'GPL-3.0-only'
                assert metadata['authors'] == ['EyeCrasher07']
                assert metadata["depends"]["minecraft"] == "=" + target["minecraft"]
                assert not any(n.endswith("mods.toml") for n in names)
                if not target["minecraft"].startswith("26."):
                    code = archive.read("dev/eyecrasher/jukeboxplaylists/mixin/JukeboxMixin.class")
                    assert b"net/minecraft/class_" in code, "Unmapped Fabric game references"
                    assert b"net/minecraft/world/level/" not in code, "Named references in Fabric production jar"
                    assert "refmap" not in config, "Fabric uses direct annotation remapping"
            else:
                metadata = archive.read(next(n for n in names if n.endswith("mods.toml"))).decode()
                assert 'license="GPL-3.0-only"' in metadata
                assert f'versionRange="[{target["minecraft"]}]"' in metadata
                assert "fabric.mod.json" not in names
            tag_path = next(n for n in names if n.endswith("/jukebox_containers.json"))
            tag = json.loads(archive.read(tag_path))
            assert tag["values"][:2] == ["minecraft:chest", "minecraft:trapped_chest"]
            assert len(tag["values"]) == 10
            mc = tuple(map(int, target["minecraft"].split(".")))
            if (1, 17) <= mc < (1, 19, 1) and target["loader"] in ("fabric", "forge"):
                code = archive.read("dev/eyecrasher/jukeboxplaylists/mixin/JukeboxBlockMixin.class")
                expected = b"method_31645" if target["loader"] == "fabric" else b"m_142354_"
                assert expected in code, "Added ticker must be remapped in production: " + target["id"]
        checksums.append(checksum + "  " + str(path.relative_to(ROOT / "dist")))
    (ROOT / "dist/SHA256SUMS").write_text("\n".join(checksums) + "\n")
    print(f"Verified {len(checksums)} production jars: target metadata, Java versions, mixins, refmaps, data, no game/test classes.")


if __name__ == "__main__":
    main()
