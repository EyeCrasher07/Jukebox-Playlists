# Проверки

Обновлено: 2026-10-16T21:19:46+00:00

Собрано производственных JAR: **90/90**. Игровые проверки пройдены на **12 сочетаниях**.

Дополнительно проверено через обычный установщик Fabric с переименованным JAR: **2 сочетания**.

В таблице `JAR` означает успешную сборку; `JAR + игра` — дополнительно проверки механики внутри запущенного Minecraft.
`—` означает, что загрузчик для этого релиза не выпускался. `Ожидает` означает отсутствие успешной сборки.

| Minecraft | Fabric | Forge | NeoForge |
| --- | --- | --- | --- |
| 1.16.5 | JAR + игра | JAR + игра | — |
| 1.17 | JAR | — | — |
| 1.17.1 | JAR + игра | JAR | — |
| 1.18 | JAR | JAR | — |
| 1.18.1 | JAR | JAR | — |
| 1.18.2 | JAR | JAR | — |
| 1.19 | JAR | JAR | — |
| 1.19.1 | JAR + игра | JAR | — |
| 1.19.2 | JAR | JAR | — |
| 1.19.3 | JAR | JAR | — |
| 1.19.4 | JAR | JAR | — |
| 1.20 | JAR | JAR | — |
| 1.20.1 | JAR | JAR | JAR |
| 1.20.2 | JAR | JAR | JAR + игра |
| 1.20.3 | JAR | JAR | JAR |
| 1.20.4 | JAR + игра | JAR + игра | JAR + игра |
| 1.20.5 | JAR | — | JAR |
| 1.20.6 | JAR | JAR | JAR |
| 1.21 | JAR | JAR | JAR |
| 1.21.1 | JAR + игра | JAR | JAR |
| 1.21.2 | JAR | — | JAR |
| 1.21.3 | JAR | JAR | JAR |
| 1.21.4 | JAR | JAR | JAR |
| 1.21.5 | JAR | JAR | JAR |
| 1.21.6 | JAR | JAR | JAR |
| 1.21.7 | JAR | JAR | JAR |
| 1.21.8 | JAR | JAR | JAR |
| 1.21.9 | JAR | JAR | JAR |
| 1.21.10 | JAR | JAR | JAR |
| 1.21.11 | JAR | JAR | JAR |
| 26.1 | JAR | JAR | JAR |
| 26.1.1 | JAR | JAR | JAR |
| 26.1.2 | JAR | JAR | JAR |
| 26.2 | JAR | JAR | JAR |
| 26.3 | JAR + игра | JAR + игра | JAR + игра |

## Команды

```bash
python3 tools/build.py
python3 tools/verify_artifacts.py
python3 tools/build.py --target fabric-26.3 --smoke --eula-file /path/to/accepted/eula.txt
python3 tools/report.py
```

Игровые проверки используют отдельные сборки и временные миры в `build/targets/test-*/build/run/server`.
Для игровых проверок Forge дополнительно нужна Java 8 для служебного загрузчика Gradle; путь можно передать через `--java-path`.
Логи находятся в `build/logs/`, подробные результаты — в `build/results/` и `build/status.json`.
