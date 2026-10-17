#!/usr/bin/env python3
"""Package only verified production artifacts and their installation evidence."""
import json
import hashlib
import shutil
import zipfile
from pathlib import Path

import report
import verify_artifacts

ROOT = Path(__file__).resolve().parents[1]


def prepare_dependency_fix(pin):
    from lazo_deps import dependency
    from patch_plasmo_voice import patch
    info = pin['dependency_patch']
    fixed = patch(dependency(pin['plasmo'], 'plasmo'), ROOT / 'build/compat-deps' / info['filename'])
    digest = hashlib.sha256(fixed.read_bytes()).hexdigest()
    if digest != info['sha256']:
        raise ValueError('Unexpected Plasmo Voice fix hash')
    path = ROOT / 'dist' / info['artifact']
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixed, path)
    source = dependency(info['source'], 'sources')
    source_path = path.parent / 'source' / source.name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, source_path)
    with zipfile.ZipFile(fixed) as jar:
        (path.parent / 'LICENSE-PlasmoVoice.txt').write_bytes(jar.read('META-INF/licenses/LICENSE'))
        (path.parent / 'NOTICE.txt').write_bytes(jar.read('META-INF/jukebox-playlists-patch.txt'))
    (path.parent / 'README-RU.md').write_text('''# Plasmo Voice для Forge 1.20.2

Готовый JAR: plasmovoice-forge-1.20.2-2.1.17-metadata-fix.jar.

Замените им старый Plasmo Voice в mods сервера и всех клиентов Minecraft 1.20.2 / Forge 48.
Рядом нужны Jukebox Playlists для Forge 1.20.2 и LazoDiscs 1.0.7 для той же версии.
После замены перезапустите игру или сервер. Запускать Python для установки не требуется.

В опубликованном PV указан диапазон Minecraft 1.20.2–1.20.4, но минимальный Forge/FML 49.
В этой копии два минимальных номера исправлены на 48; классы и библиотеки не менялись.
Это локальное исправление Plasmo Voice 2.1.17. Уведомление об изменении и лицензия сохранены.
Исходники исходного выпуска находятся в source/. В корне полного комплекта есть
tools/patch_plasmo_voice.py для воспроизведения исправления из исходного опубликованного JAR.
Контрольные суммы файлов находятся в SHA256SUMS. Подробности проверок — в docs/VERIFICATION.md полного комплекта.
''')
    contents = [path, source_path, path.parent / 'LICENSE-PlasmoVoice.txt', path.parent / 'NOTICE.txt', path.parent / 'README-RU.md']
    sums = path.parent / 'SHA256SUMS'
    sums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(path.parent)) + '\n' for p in contents))
    return contents + [sums], {'target': pin['target'], 'file': info['artifact'], 'sha256': digest,
                              'source': str(source_path.relative_to(ROOT / 'dist')), 'license': 'LGPL-3.0'}


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
    compatibility_files, fixes = [], []
    for pin in pins.values():
        if pin.get('dependency_patch'):
            result = next(r for r in releases if r['id'] == pin['target'])
            if not result['lazodiscs_patched_dependency_runtime_tested']:
                raise ValueError('Dependency fix needs a passing server audio check: ' + pin['target'])
            if not result['lazodiscs_client_runtime_tested']:
                raise ValueError('Dependency fix needs a passing client audio check: ' + pin['target'])
            paths, fix = prepare_dependency_fix(pin)
            compatibility_files.extend(paths)
            fixes.append(fix)
    manifest = {"version": matrix["mod_version"], "releases": releases, "dependency_fixes": fixes}
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

Для Forge 1.20.2 готовый исправленный Plasmo Voice находится в compat/forge-1.20.2/.
Замените старый PV в mods сервера и клиентов файлом plasmovoice-forge-1.20.2-2.1.17-metadata-fix.jar.
Запускать Python для установки не требуется. Рядом приложены лицензия, описание изменения, исходники и контрольные суммы.
Исправлены только два минимальных номера Forge/FML с 49 на 48; классы и библиотеки сохранены.
Это локальная копия, не официальный выпуск PV. Утилита tools/patch_plasmo_voice.py оставлена для воспроизведения исправления.
Другие сочетания используют опубликованные зависимости без изменений.

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
        for path in compatibility_files:
            output.write(path, str(path.relative_to(ROOT / 'dist')))
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
    archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    print(f"Packaged {len(releases)} playlist jars and {len(fixes)} dependency fix: {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
