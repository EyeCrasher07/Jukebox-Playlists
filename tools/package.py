#!/usr/bin/env python3
"""Package only verified production artifacts and their installation evidence."""
import json
import hashlib
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
    pins = {p['target']: p for p in json.loads((ROOT / 'lazodiscs-compatibility.json').read_text())['targets']}
    releases = []
    for target in matrix["targets"]:
        result = status[target["id"]]
        dependency_patch = pins.get(target['id'], {}).get('dependency_patch')
        dependency_result = result.get('lazo_dependency_runtime', {})
        expected = ROOT / 'build/compat-deps' / dependency_patch['filename'] if dependency_patch else None
        dependency_verified = bool(expected and expected.is_file() and dependency_result.get('success') and dependency_result.get('audio_verified') and dependency_result.get('sha256') == result['build']['sha256'] and any(d.get('sha256') == hashlib.sha256(expected.read_bytes()).hexdigest() for d in dependency_result.get('dependencies', [])))
        releases.append({**target, "file": str(Path(result["build"]["artifact"]).relative_to("dist")),
                         "sha256": result["build"]["sha256"],
                         "runtime_tested": result.get("runtime", {}).get("success", False),
                         "client_runtime_tested": result.get("client_runtime", {}).get("success", False),
                         "pair_runtime_tested": result.get("pair_runtime", {}).get("success", False),
                         "lazodiscs_runtime_tested": result.get("lazo_runtime", {}).get("success", False) and result.get("lazo_runtime", {}).get("audio_verified", False) and result.get("lazo_runtime", {}).get("sha256") == result["build"]["sha256"],
                         "lazodiscs_pair_runtime_tested": result.get("lazo_pair_runtime", {}).get("success", False),
                         "lazodiscs_client_runtime_tested": result.get("lazo_client_runtime", {}).get("success", False),
                         "lazodiscs_dependency_patch": dependency_patch,
                         "lazodiscs_patched_dependency_runtime_tested": dependency_verified,
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

Для записей LazoDiscs установите также LazoDiscs 1.0.7 и соответствующий Plasmo Voice 2.1.17
на сервер и клиенты. Совместимые опубликованные версии и хеши: lazodiscs-compatibility.json.
Положите записанные диски в тот же сундук; их можно смешивать с обычными.
Переход происходит через секунду после завершения аудио, без ограничения длительностью ванильного трека.
URL, название, UUID, громкость и радиус записи сохраняются при обмене.
Если LazoDiscs сообщает об ошибке загрузки, очередь продолжает поиск через ту же паузу.

Для Forge 1.20.2 нужна отдельная копия Plasmo Voice с исправленными метаданными.
Скачайте исходный plasmovoice-forge-1.20.4-2.1.17.jar по URL из lazodiscs-compatibility.json,
затем из распакованного комплекта выполните (нужен Python 3):

```bash
python3 tools/patch_plasmo_voice.py /path/to/plasmovoice-forge-1.20.4-2.1.17.jar
```

В mods сервера и клиентов установите полученный plasmovoice-forge-1.20.2-2.1.17-metadata-fix.jar вместо исходного PV.
Оригинал не изменяется. Исправляются только два минимальных номера Forge/FML с 49 на 48;
классы и лицензии сохраняются, добавляется уведомление. Это локальная копия, не официальный выпуск PV.
Другие сочетания используют опубликованные зависимости без изменений. Сторонние моды в этот ZIP не входят.

В 1.16.5–1.19 длительность нестандартных пластинок задаётся в
config/jukebox-playlists-song-lengths.properties, например:

```properties
item.example.my_music_disc=4200
```

Значение — тики, 20 тиков = 1 секунда. Для ванильных пластинок и записей LazoDiscs настройки не нужны.
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
                           (ROOT / "lazodiscs-compatibility.json", "lazodiscs-compatibility.json"),
                           (ROOT / "tools/patch_plasmo_voice.py", "tools/patch_plasmo_voice.py"),
                           (ROOT / "versions.json", "versions.json"),
                           (ROOT / "dist/SHA256SUMS", "SHA256SUMS"),
                           (ROOT / "dist/manifest.json", "manifest.json")]:
            output.write(path, name)
    print(f"Packaged {len(releases)} jars: {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
