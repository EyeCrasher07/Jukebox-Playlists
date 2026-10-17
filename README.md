# Jukebox Playlists

[English](#jukebox-playlists) · [Русский](#русский)

Backports jukebox chest playlists from [Minecraft 26.4 Snapshot 4](https://www.minecraft.net/en-us/article/minecraft-26-4-snapshot-4) to **Minecraft 1.16.5–26.3**. Includes optional support for recorded [LazoDiscs](https://github.com/EyeCrasher07/LazoDiscs).

[Downloads](https://github.com/EyeCrasher07/Jukebox-Playlists/releases) · [Issues](https://github.com/EyeCrasher07/Jukebox-Playlists/issues) · [Verification](docs/VERIFICATION.md)

## Getting started

1. Download **one** JAR for your exact Minecraft version and loader: `jukebox-playlists-<loader>-<minecraft>-1.0.0.jar`. The full ZIP contains all variants; install only the matching file.
2. Install it in `mods` on the server and clients, or in your single-player installation. Fabric also needs Fabric Loader **0.19.5+** and the matching Fabric API listed below.
3. Place a **single chest directly above a jukebox** and put music discs in it.

The jukebox starts automatically, swaps its disc with the next occupied disc slot, and loops through the chest. Empty slots and other items are skipped. If there is no next disc, the current one repeats. Right-clicking to eject a disc advances the playlist; the manually ejected disc drops as usual. Automatic transitions keep discs in the jukebox and chest.

Normal chests, trapped chests and copper chests present in the selected game version work. Double chests are excluded. Custom names, item data and the playlist position survive swaps and world reloads.

## LazoDiscs

Install **LazoDiscs 1.0.7** and the matching **Plasmo Voice 2.1.17** on the server and clients. Burn discs with LazoDiscs and place them in the same chest. Recorded and native discs can be mixed. The next track starts one second after the recording actually finishes; the underlying vanilla disc's duration does not cut it off. The recording's URL, title, UUID, volume and radius are preserved.

The pinned dependency matrix contains **52 combinations**: 25 Fabric, 15 Forge and 12 NeoForge. Other Minecraft versions in the main matrix do not have a LazoDiscs 1.0.7 release. Exact files and hashes: [lazodiscs-compatibility.json](lazodiscs-compatibility.json).

**Forge 1.20.2:** use `compat/forge-1.20.2/plasmovoice-forge-1.20.2-2.1.17-metadata-fix.jar` from the full ZIP instead of the original PV file, on both server and clients. The original declares Forge/FML 49 while this game version uses 48. The supplied copy changes those two minimums only; classes and libraries are unchanged. Its notice, license, upstream source archive and checksums are included. This is a local metadata correction. Installation does not require Python.

This integration is optional. Standard discs work without LazoDiscs. Use a matching Fabric, Forge or NeoForge server; Vanilla/Paper cannot load these mods. Hybrid servers and arbitrary modpacks have not been verified.

## Supported builds

The first release, **1.0.0**, provides **90 builds** across **35 Minecraft releases**: 35 Fabric, 32 Forge and 23 NeoForge. A dash means no build for that pair. These are the pinned build and verification targets.

| Minecraft | Fabric API | Forge | NeoForge |
| --- | --- | --- | --- |
| 1.16.5 | 0.42.0+1.16 | 1.16.5-36.2.42 | — |
| 1.17 | 0.36.0+1.17 | — | — |
| 1.17.1 | 0.46.1+1.17 | 1.17.1-37.1.1 | — |
| 1.18 | 0.44.0+1.18 | 1.18-38.0.17 | — |
| 1.18.1 | 0.46.6+1.18 | 1.18.1-39.1.2 | — |
| 1.18.2 | 0.77.0+1.18.2 | 1.18.2-40.3.12 | — |
| 1.19 | 0.58.0+1.19 | 1.19-41.1.0 | — |
| 1.19.1 | 0.58.5+1.19.1 | 1.19.1-42.0.9 | — |
| 1.19.2 | 0.77.0+1.19.2 | 1.19.2-43.5.2 | — |
| 1.19.3 | 0.76.1+1.19.3 | 1.19.3-44.1.23 | — |
| 1.19.4 | 0.87.2+1.19.4 | 1.19.4-45.4.5 | — |
| 1.20 | 0.83.0+1.20 | 1.20-46.0.14 | — |
| 1.20.1 | 0.92.12+1.20.1 | 1.20.1-47.4.28 | 1.20.1-47.1.106 |
| 1.20.2 | 0.91.6+1.20.2 | 1.20.2-48.1.0 | 20.2.93 |
| 1.20.3 | 0.91.1+1.20.3 | 1.20.3-49.0.2 | 20.3.8-beta |
| 1.20.4 | 0.97.3+1.20.4 | 1.20.4-49.2.13 | 20.4.253 |
| 1.20.5 | 0.97.8+1.20.5 | — | 20.5.21-beta |
| 1.20.6 | 0.100.8+1.20.6 | 1.20.6-50.2.14 | 20.6.144 |
| 1.21 | 0.102.0+1.21 | 1.21-51.0.33 | 21.0.167 |
| 1.21.1 | 0.116.17+1.21.1 | 1.21.1-52.1.20 | 21.1.262 |
| 1.21.2 | 0.106.1+1.21.2 | — | 21.2.1-beta |
| 1.21.3 | 0.114.1+1.21.3 | 1.21.3-53.1.16 | 21.3.100 |
| 1.21.4 | 0.119.4+1.21.4 | 1.21.4-54.1.22 | 21.4.161 |
| 1.21.5 | 0.128.2+1.21.5 | 1.21.5-55.1.18 | 21.5.101 |
| 1.21.6 | 0.128.2+1.21.6 | 1.21.6-56.0.9 | 21.6.20-beta |
| 1.21.7 | 0.129.0+1.21.7 | 1.21.7-57.0.3 | 21.7.25-beta |
| 1.21.8 | 0.136.1+1.21.8 | 1.21.8-58.1.26 | 21.8.57 |
| 1.21.9 | 0.134.1+1.21.9 | 1.21.9-59.0.5 | 21.9.16-beta |
| 1.21.10 | 0.138.4+1.21.10 | 1.21.10-60.1.18 | 21.10.64 |
| 1.21.11 | 0.141.6+1.21.11 | 1.21.11-61.2.4 | 21.11.48 |
| 26.1 | 0.155.3+26.1.2 | 26.1-62.0.9 | 26.1.0.19-beta |
| 26.1.1 | 0.155.3+26.1.2 | 26.1.1-63.0.2 | 26.1.1.15-beta |
| 26.1.2 | 0.155.3+26.1.2 | 26.1.2-64.1.5 | 26.1.2.122 |
| 26.2 | 0.161.0+26.2 | 26.2-65.1.5 | 26.2.0.93 |
| 26.3 | 0.162.0+26.3 | 26.3-66.0.12 | 26.3.0.86 |

## Building from source

Each `fabric/<minecraft>`, `forge/<minecraft>` and `neoforge/<minecraft>` directory contains its version-specific Java sources, resources, Gradle configuration and wrapper. Shared archive settings are in `gradle/release.gradle`. Python and private development files are not required for a normal build.

Run Gradle on **JDK 25** for Forge and Minecraft 26.x, and **JDK 21** for the other Fabric/NeoForge projects. Also install the compiler toolchains selected by the project: JDK 17 for early versions, 21 for 1.20.5–1.21.11 and 25 for 26.x. For example, from the repository root:

```sh
cd fabric/26.3
./gradlew build
```

On Windows use `gradlew.bat build`. The installable JAR is in that project's `build/libs/`; choose the file without a `-dev` suffix. Matrix scripts, development templates and gameplay test instructions: [docs/BUILDING.md](docs/BUILDING.md).

## Verification

The recorded gameplay checks cover all 90 SDK servers, 52 LazoDiscs server/audio combinations, six native client combinations, LazoDiscs clients on Forge 1.20.2/1.21, and a dedicated Fabric 26.3 server with two separate clients, captured sound and a full restart. The LazoDiscs checks use recordings made with `/lazodisc burn`, including audio longer than its vanilla base disc.

The initial release packaging sets version 1.0.0 and adds LGPL texts and author/contact metadata. Every class and runtime resource in all 90 rebuilt JARs is compared byte for byte with the gameplay-tested baseline. Original test hashes and packaging changes are recorded separately in [the verification report](docs/VERIFICATION.md) and [packaging comparison](docs/PACKAGING-VERIFICATION.json).

Created by **EyeCrasher07**. Licensed under [LGPL-3.0-only](LICENSE); the incorporated GPL text is in [COPYING](COPYING). [Third-party notices](THIRD-PARTY-NOTICES.md).

---

## Русский

Перенос плейлистов проигрывателя из **Minecraft 26.4 Snapshot 4** на **1.16.5–26.3**. Доступны 90 отдельных сборок: Fabric, Forge и NeoForge там, где загрузчик существует. Таблица выше показывает точные версии.

### Установка и использование

1. Скачай **один** JAR для своей версии игры и загрузчика из [GitHub Releases](https://github.com/EyeCrasher07/Jukebox-Playlists/releases). Из полного ZIP нужен только соответствующий файл.
2. Положи его в `mods` сервера и клиентов либо одиночной игры. Для Fabric также нужны Fabric Loader **0.19.5+** и подходящая Fabric API из таблицы.
3. Поставь **одиночный сундук прямо над проигрывателем** и положи туда пластинки.

Первая пластинка запускается сама. После окончания трека проигрыватель меняет её местами со следующей по порядку слотов и обходит сундук по кругу. Пустые слоты и другие предметы пропускаются. Если следующей пластинки нет, текущая повторяется. Извлечение правым кликом переключает дальше; извлечённая вручную пластинка выпадает обычным способом. При автоматическом переходе пластинки остаются в сундуке и проигрывателе.

Подходят обычные сундуки, сундуки-ловушки и медные сундуки в версиях, где они есть. Двойные сундуки исключены. Имена, данные предметов и позиция плейлиста сохраняются.

### Записи LazoDiscs

Поставь LazoDiscs **1.0.7** и подходящий Plasmo Voice **2.1.17** на сервер и клиенты. Запиши пластинки обычной командой LazoDiscs и положи их в тот же сундук. Записи можно смешивать с ванильными треками. Переход происходит через секунду после завершения настоящего аудио; длина исходной ванильной пластинки запись не обрывает. URL, название, UUID, громкость и радиус сохраняются.

Для **Forge 1.20.2** замени исходный Plasmo Voice готовым `compat/forge-1.20.2/plasmovoice-forge-1.20.2-2.1.17-metadata-fix.jar` из полного ZIP на сервере и клиентах. Python для установки не нужен. В копии исправлены два минимальных номера Forge/FML с 49 на 48, классы и библиотеки сохранены. Рядом приложены уведомление, лицензия, исходники и контрольные суммы.

Закреплены 52 сочетания LazoDiscs и PV; на остальных версиях из основной матрицы нет выпуска LazoDiscs 1.0.7. Без LazoDiscs обычные пластинки работают самостоятельно. Нужен совместимый Fabric/Forge/NeoForge-сервер. Vanilla/Paper эти моды не загружают; гибридные ядра и произвольные модпаки отдельно не проверялись.

### Старые модовые пластинки

В 1.16.5–1.19 у пластинок нет серверной длительности. Для ванильных треков она уже задана; для записей LazoDiscs используется настоящее завершение аудио. Для других модовых пластинок создай `config/jukebox-playlists-song-lengths.properties`:

```properties
item.example.my_music_disc=4200
```

Ключ — translation key предмета, значение — длительность в тиках: 20 тиков = 1 секунда. Перезапусти игру или сервер после изменения. Без известной длительности трек звучит, но сервер не сможет автоматически перейти дальше. С 1.19.1 используется штатная длительность, а с 1.21 поддерживается компонент `jukebox_playable`.

### Исходники и проверки

Структура соответствует WIGO: `fabric/<версия>`, `forge/<версия>`, `neoforge/<версия>`. Внутри каждой папки есть свои исходники, ресурсы и `gradlew`. Для обычной сборки перейди в нужную папку и выполни `./gradlew build` (`gradlew.bat build` в Windows); готовый JAR без `-dev` будет в `build/libs/`. Требования к JDK указаны выше, подробные команды — в [docs/BUILDING.md](docs/BUILDING.md).

Проверки в настоящем Minecraft, звук записей LazoDiscs и границы совместимости описаны в [docs/VERIFICATION.md](docs/VERIFICATION.md). При подготовке выпуска отдельно сверено совпадение всех игровых классов и ресурсов с проверенными файлами: изменение лицензии и метаданных не выдаётся за повторный игровой прогон.

Автор — **EyeCrasher07**. Лицензия — [LGPL-3.0-only](LICENSE).
