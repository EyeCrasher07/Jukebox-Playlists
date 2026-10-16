#!/usr/bin/env python3
"""Pin released Minecraft/loader pairs in the requested inclusive range."""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "minecraft": "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
    "fabric": "https://meta.fabricmc.net/v2/versions/loader",
    "forge": "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml",
    "neoforge": "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml",
    "neoforge_legacy": "https://maven.neoforged.net/releases/net/neoforged/forge/maven-metadata.xml",
}


def numeric(version):
    return tuple(map(int, re.findall(r"\d+", version)))


def main():
    cache = ROOT / "build/metadata"
    cache.mkdir(parents=True, exist_ok=True)
    raw = {}
    for name, url in SOURCES.items():
        request = urllib.request.Request(url, headers={"User-Agent": "JukeboxPlaylists-build/0.1"})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw[name] = response.read()
        (cache / name).write_bytes(raw[name])
    manifest = json.loads(raw["minecraft"])
    times = {v["id"]: v["releaseTime"] for v in manifest["versions"]}
    releases = [v["id"] for v in reversed(manifest["versions"])
                if v["type"] == "release" and times["1.16.5"] <= v["releaseTime"] <= times["26.3"]]
    loader = next(v["version"] for v in json.loads(raw["fabric"]) if v.get("stable"))
    available = {name: [v.text for v in ET.fromstring(raw[name]).findall("./versioning/versions/version")]
                 for name in ("forge", "neoforge", "neoforge_legacy")}
    targets = []
    missing = []
    fabric_api_pins = json.loads((ROOT / "fabric-api-pins.json").read_text())
    for mc in releases:
        java = 25 if mc.startswith("26.") else 21 if numeric(mc) >= (1, 20, 5) else 17 if numeric(mc) >= (1, 18) else 16 if mc.startswith("1.17") else 8
        for name in ("fabric", "forge", "neoforge"):
            if name == "fabric":
                candidates = [loader]
            elif name == "forge":
                candidates = [v for v in available[name] if v.startswith(mc + "-")]
            elif mc == "1.20.1":
                candidates = [v for v in available["neoforge_legacy"] if v.startswith(mc + "-")]
            else:
                parts = mc.split(".") if mc.startswith("26.") else mc.split(".")[1:]
                prefix = ".".join(parts + ["0"] if len(parts) == (2 if mc.startswith("26.") else 1) else parts) + "."
                candidates = [v for v in available[name] if v.startswith(prefix) and "+" not in v]
            if candidates:
                targets.append({"id": name + "-" + mc, "minecraft": mc, "loader": name,
                                "loader_version": max(candidates, key=numeric), "java": java})
                if name == "fabric":
                    targets[-1]["fabric_api"] = fabric_api_pins[mc]
            else:
                missing.append({"minecraft": mc, "loader": name})
    result = {"mod_version": "0.1.0", "first_minecraft": "1.16.5", "last_minecraft": "26.3",
              "sources": SOURCES, "targets": targets, "unavailable": missing}
    (ROOT / "versions.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(releases)} releases, {len(targets)} available loader pairs")


if __name__ == "__main__":
    main()
