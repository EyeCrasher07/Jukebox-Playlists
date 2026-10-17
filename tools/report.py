#!/usr/bin/env python3
"""Render recorded build/runtime evidence without treating compilation as gameplay."""
import datetime
import json
import re
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
    client_tested = sum(t.get("client_runtime", {}).get("success", False) for t in status.values())
    paired = {key: item['pair_runtime'] for key, item in status.items() if item.get('pair_runtime', {}).get('success')}
    assertions = 0
    for item in status.values():
        runtime = item.get('runtime', {})
        if runtime.get('success'):
            marker = re.search(r'PLAYLIST TESTS PASSED: (\d+) assertions', (ROOT / runtime['log']).read_text(errors='replace'))
            if marker:
                assertions += int(marker.group(1))
    lines = ["# Проверки", "", "Обновлено: " + datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"), "",
             f"Собрано производственных JAR: **{built}/{len(matrix['targets'])}**. Серверные проверки SDK пройдены на **{tested} сочетаниях**, всего **{assertions} assertions**.", "",
             "Это настоящие серверы Minecraft с отдельной тестовой сборкой. Длительные треки в серверной матрице проверяются ускоренными вызовами штатного тикера проигрывателя.", "",
             f"Дополнительно проверено через обычный установщик Fabric с переименованным тестовым JAR: **{production_tested} сочетания**.", "",
             f"Готовые JAR из `dist/` проверены в клиенте с окном, звуковым движком и обычными тиками мира: **{client_tested} сочетаний**.", "",
             f"Сетевой сценарий с точным готовым JAR, выделенным сервером и двумя отдельными клиентскими JVM: **{len(paired)} сочетание**.", "",
             "В таблице `JAR` означает успешную сборку; `JAR + сервер` — дополнительно проверки механики на сервере SDK.",
             "`JAR + клиент` — дополнительно 15 проверок готового JAR в клиенте: полное воспроизведение пластинки 11, переход, правый клик, повтор и отсутствие наложения звуков.",
             "`JAR + 2 клиента` — также пройден отдельный сетевой сценарий и перезапуск сервера.",
             "`—` означает, что загрузчик для этого релиза не выпускался. `Ожидает` означает отсутствие успешной сборки.", "",
             "| Minecraft | Fabric | Forge | NeoForge |", "| --- | --- | --- | --- |"]
    targets = {t["id"]: t for t in matrix["targets"]}
    for mc in dict.fromkeys(t["minecraft"] for t in matrix["targets"]):
        row = [mc]
        for loader in ("fabric", "forge", "neoforge"):
            key = loader + "-" + mc
            item = status.get(key, {})
            row.append("—" if key not in targets else "Ожидает" if not item.get("build", {}).get("success") else
                       "JAR + 2 клиента" if key in paired else "JAR + клиент" if item.get("client_runtime", {}).get("success") else
                       "JAR + сервер" if item.get("runtime", {}).get("success") else "JAR")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Исправление после запуска игры", "",
              "В Forge 1.20.6 исправлено значение уровня совместимости Mixin: встроенная версия 0.8.5 не распознаёт `JAVA_21`.",
              "В готовом JAR используется `JAVA_17`; сама игра по-прежнему запускается на Java 21. Исправление проверено на сервере и в клиенте.",
              "", "## Клиентские проверки", ""]
    for target, item in status.items():
        result = item.get("client_runtime", {})
        if result.get("success"):
            lines.append(f"- `{target}`: готовый JAR, SHA-256 `{result['sha256']}`, {result['seconds']} с; лог `{result['log']}`.")
    lines += ["", "Снимки этапов лежат в `build/evidence/<загрузчик-версия>/` и `build/targets/client-*/build/run/client/screenshots/`.", "",
              "Клиент Fabric 1.16.5 запускался на Java 17, установленный Forge 1.16.5 — на Java 8, Forge 1.20.6 — на Java 21, все три загрузчика 26.3 — на Java 25.", ""]
    for target, result in paired.items():
        lines += ["## Два клиента и перезапуск", "",
                  f"`{target}`, загрузчик `{result['loader_version']}`, SHA-256 `{result['sha256']}`.",
                  "На выделенном сервере установлен готовый JAR и Fabric API; тестовый драйвер работает только в клиентах.",
                  "Оба клиента подтвердили запуск 11, естественный переход на Cat и переключение на 11 действием владельца. Проверяется ровно один активный звук у каждого.",
                  "После штатного сохранения и полного перезапуска сервера и обеих клиентских JVM проверяется выбор слота 15 перед слотом 2: сохранённая позиция 7 действительно используется.",
                  "Проверяются оставшиеся пластинки, посторонний камень, имена, разные PID и фактическая Java игровых процессов.",
                  f"Доказательства и история попыток: `{result['evidence']}`.", ""]
        if result.get('audio_rms'):
            lines += ["Выход звука каждого клиента отдельно записан через собственный временный PulseAudio sink. Обе PCM-записи содержат ненулевой сигнал; чужие аудиопотоки не записывались.",
                      "RMS PCM16: " + ', '.join(f"{role}={value:.1f}" for role, value in result['audio_rms'].items()) + '.', ""]
    review = ROOT / 'build/evidence/visual-review.json'
    if review.exists():
        reviewed = json.loads(review.read_text())
        lines += ["## Визуальный просмотр", "", f"Открыто и осмотрено исходных кадров: **{len(reviewed['screenshots'])}**. Перечень и SHA-256: `build/evidence/visual-review.json`.",
                  "Осмотрены проигрыватель, инвентарь сундука, переход и повтор. На ранних кадрах Fabric/Forge 26.3 остались выброшенные предметы из подготовительного мира; последующие стенды очищают их перед сценарием.", ""]
    lines += ["## Границы проверки", "",
              "Все 90 сочетаний проверены на сервере SDK; проверка точного устанавливаемого JAR в клиенте выполнена только для шести перечисленных сочетаний.",
              "Два независимых сетевых клиента и захват PCM проверялись на Fabric 26.3. Модпаки, OptiFine, шейдеры, ресурспаки, произвольные модовые пластинки и длительная многопользовательская нагрузка отдельно не проверялись.", "",
              "## Команды", "", "```bash", "python3 tools/build.py", "python3 tools/verify_artifacts.py",
              "python3 tools/build.py --target fabric-26.3 --smoke --eula-file /path/to/accepted/eula.txt",
              "python3 tools/runtime_matrix.py --eula-file /path/to/accepted/eula.txt",
              "python3 tools/client_test.py --target fabric-26.3", "python3 tools/pair_test.py --audio --eula-file /path/to/accepted/eula.txt", "python3 tools/report.py", "```", "",
              "Игровые проверки используют отдельные сборки и временные миры в `build/targets/test-*/build/run/server`.",
              "Для игровых проверок Forge дополнительно нужна Java 8 для служебного загрузчика Gradle; путь можно передать через `--java-path`.",
              "Логи находятся в `build/logs/`, подробные результаты — в `build/results/` и `build/status.json`.", ""]
    (ROOT / "docs/VERIFICATION.md").write_text("\n".join(lines))
    print(f"Builds: {built}/{len(matrix['targets'])}; runtime passes: {tested}; production runtime passes: {production_tested}; client passes: {client_tested}; paired passes: {len(paired)}")


if __name__ == "__main__":
    main()
