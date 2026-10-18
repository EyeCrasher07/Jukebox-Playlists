# Jukebox Playlists

Brings Minecraft 26.4 jukebox playlists to **1.16.5–26.3**, supporting Fabric, Forge, and NeoForge.

[Download](https://github.com/EyeCrasher07/Jukebox-Playlists/releases) · [Changelog](CHANGELOG.md)

Install the appropriate JAR on both the server and clients. Fabric requires Fabric API.
Place a single chest directly above a Jukebox and fill it with Music Discs — the playlist will play and loop automatically.
Vanilla and modded Music Discs work without manually configuring their durations. LazoDiscs recordings require both LazoDiscs and Plasmo Voice.
For LazoDiscs on Forge 1.20.2, use the patched version of Plasmo Voice included in the full release ZIP.

Each version folder is a separate project: `cd fabric/1.16.5`, then run `./gradlew build` (`gradlew.bat build` on Windows).
Building Forge and Minecraft 26.x projects requires JDK 25; all other projects require JDK 21. You must also install the compiler JDK specified in `build.gradle`.

License: [GPL-3.0-only](LICENSE).
