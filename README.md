# Jukebox Playlists

Плейлисты проигрывателя из Minecraft 26.4 для **1.16.5–26.3**, Fabric, Forge и NeoForge.

[Скачать](https://github.com/EyeCrasher07/Jukebox-Playlists/releases) · [Изменения](CHANGELOG.md)

Поставь подходящий JAR на сервер и клиенты. Для Fabric нужна Fabric API.
Поставь одиночный сундук прямо над проигрывателем и положи в него пластинки — очередь запускается и повторяется автоматически.
Ванильные и модовые пластинки работают без настройки длительности. Для записей LazoDiscs нужны LazoDiscs и Plasmo Voice.
Для LazoDiscs на Forge 1.20.2 используй исправленный Plasmo Voice из полного ZIP релиза.

Каждая папка версии — отдельный проект: `cd fabric/1.16.5`, затем `./gradlew build` (`gradlew.bat build` в Windows).
Для сборки Forge и Minecraft 26.x нужен JDK 25; остальных проектов — JDK 21. Также установи JDK компилятора, указанный в `build.gradle`.

Лицензия: [GPL-3.0-only](LICENSE).
