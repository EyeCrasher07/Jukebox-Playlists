#!/usr/bin/env python3
"""Package only verified production artifacts and their installation evidence."""
import json
import zipfile
from pathlib import Path

import report
import verify_artifacts

ROOT = Path(__file__).resolve().parents[1]


def main():
    report.main()
    verify_artifacts.main()
    matrix = json.loads((ROOT / "versions.json").read_text())
    status = json.loads((ROOT / "build/status.json").read_text())
    releases = []
    for target in matrix["targets"]:
        result = status[target["id"]]
        releases.append({**target, "file": str(Path(result["build"]["artifact"]).relative_to("dist")),
                         "sha256": result["build"]["sha256"],
                         "runtime_tested": result.get("runtime", {}).get("success", False),
                         "production_runtime_tested": result.get("production_runtime", {}).get("success", False)})
    manifest = {"version": matrix["mod_version"], "releases": releases}
    (ROOT / "dist/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    install = '''# Jukebox Playlists

Перенос плейлистов проигрывателя из Minecraft 26.4 Snapshot 4 в версии 1.16.5–26.3.

1. Выберите папку загрузчика: fabric, forge или neoforge.
2. Поместите ровно один JAR для своей версии Minecraft в папку mods.
3. Для Fabric также нужна совместимая Fabric API; версии перечислены в fabric-api-pins.json.
4. Поставьте одиночный сундук прямо над проигрывателем и положите туда пластинки.

Пластинки запускаются автоматически, меняются местами со следующей по порядку слотов и проигрываются по кругу.
Пустые слоты и другие предметы пропускаются. Извлечение пластинки переключает трек.
Подходят обычные сундуки, сундуки-ловушки и медные сундуки в версиях, где они есть.
Двойные сундуки исключены. Устанавливайте мод на сервер и клиенты.

В 1.16.5–1.19 длительность нестандартных пластинок задаётся в
config/jukebox-playlists-song-lengths.properties, например:

```properties
item.example.my_music_disc=4200
```

Значение — тики, 20 тиков = 1 секунда. Для ванильных пластинок настройки не нужны.
После изменения конфигурации перезапустите игру или сервер.

Результаты проверок: docs/VERIFICATION.md. Подробности механики: docs/MECHANICS.md.
SHA256SUMS содержит контрольные суммы каждого JAR; manifest.json — версии загрузчиков и результаты игровых проверок.
'''
    (ROOT / "dist/INSTALL-RU.md").write_text(install)
    archive = ROOT / "dist" / ("jukebox-playlists-" + matrix["mod_version"] + "-all.zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for release in releases:
            output.write(ROOT / "dist" / release["file"], release["file"])
        for path, name in [(ROOT / "dist/INSTALL-RU.md", "README.md"),
                           (ROOT / "docs/MECHANICS.md", "docs/MECHANICS.md"),
                           (ROOT / "docs/VERIFICATION.md", "docs/VERIFICATION.md"),
                           (ROOT / "fabric-api-pins.json", "fabric-api-pins.json"),
                           (ROOT / "versions.json", "versions.json"),
                           (ROOT / "dist/SHA256SUMS", "SHA256SUMS"),
                           (ROOT / "dist/manifest.json", "manifest.json")]:
            output.write(path, name)
    print(f"Packaged {len(releases)} jars: {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
