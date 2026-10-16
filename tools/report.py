#!/usr/bin/env python3
"""Render recorded build/runtime evidence without treating compilation as gameplay."""
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    matrix = json.loads((ROOT / "versions.json").read_text())
    status = {}
    for path in (ROOT / "build/results").glob("*.json"):
        item = json.loads(path.read_text())
        status.setdefault(item["target"], {})[item["kind"]] = item["result"]
    (ROOT / "build/status.json").write_text(json.dumps(status, indent=2) + "\n")
    built = sum(t.get("build", {}).get("success", False) for t in status.values())
    tested = sum(t.get("runtime", {}).get("success", False) for t in status.values())
    production_tested = sum(t.get("production_runtime", {}).get("success", False) for t in status.values())
    lines = ["# Проверки", "", "Обновлено: " + datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"), "",
             f"Собрано производственных JAR: **{built}/{len(matrix['targets'])}**. Игровые проверки пройдены на **{tested} сочетаниях**.", "",
             f"Дополнительно проверено через обычный установщик Fabric с переименованным JAR: **{production_tested} сочетания**.", "",
             "В таблице `JAR` означает успешную сборку; `JAR + игра` — дополнительно проверки механики внутри запущенного Minecraft.",
             "`—` означает, что загрузчик для этого релиза не выпускался. `Ожидает` означает отсутствие успешной сборки.", "",
             "| Minecraft | Fabric | Forge | NeoForge |", "| --- | --- | --- | --- |"]
    targets = {t["id"]: t for t in matrix["targets"]}
    for mc in dict.fromkeys(t["minecraft"] for t in matrix["targets"]):
        row = [mc]
        for loader in ("fabric", "forge", "neoforge"):
            key = loader + "-" + mc
            item = status.get(key, {})
            row.append("—" if key not in targets else "Ожидает" if not item.get("build", {}).get("success") else
                       "JAR + игра" if item.get("runtime", {}).get("success") else "JAR")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Команды", "", "```bash", "python3 tools/build.py", "python3 tools/verify_artifacts.py",
              "python3 tools/build.py --target fabric-26.3 --smoke --eula-file /path/to/accepted/eula.txt", "python3 tools/report.py", "```", "",
              "Игровые проверки используют отдельные сборки и временные миры в `build/targets/test-*/build/run/server`.",
              "Для игровых проверок Forge дополнительно нужна Java 8 для служебного загрузчика Gradle; путь можно передать через `--java-path`.",
              "Логи находятся в `build/logs/`, подробные результаты — в `build/results/` и `build/status.json`.", ""]
    (ROOT / "docs/VERIFICATION.md").write_text("\n".join(lines))
    print(f"Builds: {built}/{len(matrix['targets'])}; runtime passes: {tested}; production runtime passes: {production_tested}")


if __name__ == "__main__":
    main()
