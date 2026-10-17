# Third-party notices

Jukebox Playlists is Copyright (C) 2026 EyeCrasher07 and is distributed under **LGPL-3.0-only**. See [LICENSE](LICENSE), the incorporated GPL text in [COPYING](COPYING), and [NOTICE](NOTICE).

## Gradle Wrapper

The wrapper JARs and launcher scripts in `gradle/wrappers/` and each loader/version project are from Gradle and retain their original notices. They use the Apache License, Version 2.0. Its text and the Gradle notice are included in [gradle/wrappers/LICENSE.txt](gradle/wrappers/LICENSE.txt) and [gradle/wrappers/NOTICE.txt](gradle/wrappers/NOTICE.txt).

## Optional Plasmo Voice copy

The full binary ZIP separately includes a modified copy of **Plasmo Voice 2.1.17** for Forge 1.20.2. Plasmo Voice is an independent project by its upstream authors, distributed under LGPL-3.0. The copy changes two minimum Forge/FML versions from 49 to 48 and adds a patch notice. Its classes, libraries and existing license entries are unchanged.

`compat/forge-1.20.2/` inside that ZIP contains the corrected JAR, its upstream license, change notice, checksums and the upstream 2.1.17 source archive. The upstream source revision is `4c717b85c4bbfa286c7809a4018137142798986b` in [plasmoapp/plasmo-voice](https://github.com/plasmoapp/plasmo-voice/tree/4c717b85c4bbfa286c7809a4018137142798986b). [tools/patch_plasmo_voice.py](tools/patch_plasmo_voice.py) reproduces the metadata correction from the original pinned JAR. File URLs and SHA-512 hashes are recorded in [lazodiscs-compatibility.json](lazodiscs-compatibility.json).

The corrected Plasmo Voice copy is an optional dependency file, separate from the Jukebox Playlists mod JARs.

## Minecraft and LazoDiscs

Minecraft is a separate product by Mojang/Microsoft. Minecraft classes and game assets are not included in this repository or the mod JARs. The playlist behavior was independently implemented against the game's APIs.

[LazoDiscs](https://github.com/EyeCrasher07/LazoDiscs) is an optional, separately installed mod. Its source, audio libraries and binaries are not bundled in Jukebox Playlists mod JARs. [The compatibility pins](lazodiscs-compatibility.json) identify the published LazoDiscs and Plasmo Voice files used in verification.
