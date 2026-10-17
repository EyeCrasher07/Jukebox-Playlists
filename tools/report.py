#!/usr/bin/env python3
"""Render recorded build and gameplay evidence, keeping each topology explicit."""
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assertions(result, marker):
    if not result.get('success'):
        return 0
    match = re.search(marker + r': (\d+) assertions', (ROOT / result['log']).read_text(errors='replace'))
    return int(match.group(1)) if match else 0


def main():
    matrix = json.loads((ROOT / 'versions.json').read_text())
    pins = json.loads((ROOT / 'lazodiscs-compatibility.json').read_text())
    status = {}
    for path in (ROOT / 'build/results').glob('*.json'):
        item = json.loads(path.read_text())
        status.setdefault(item['target'], {})[item['kind']] = item['result']
    # Keep the original tested SHA. A separate strict comparison can establish
    # that only release version/license/author/contact packaging changed.
    for item in status.values():
        proof = item.get('packaging', {})
        if proof.get('success'):
            artifact = ROOT / proof['artifact']
            if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != proof['sha256']:
                proof['success'] = False
        for kind in ('client_runtime', 'legacy_discs_client_runtime', 'pair_runtime', 'lazo_runtime', 'lazo_dependency_runtime', 'lazo_pair_runtime', 'lazo_client_runtime'):
            result = item.get(kind, {})
            if result.get('success') and result.get('artifact'):
                artifact = ROOT / item.get('build', {}).get('artifact', result['artifact'])
                current = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None
                if current != result.get('sha256') and proof.get('success') and ROOT / proof['artifact'] == artifact and proof['sha256'] == current and result.get('sha256') in proof.get('equivalent_tested_sha256', [proof['tested_baseline_sha256']]):
                    result['packaging_only_update'] = True
                    result['release_sha256'] = current
                elif current != result.get('sha256'):
                    result['success'] = False
                    result['stale_artifact'] = True
    (ROOT / 'build/status.json').write_text(json.dumps(status, indent=2) + '\n')
    def passes(kind):
        return {key: item[kind] for key, item in status.items() if item.get(kind, {}).get('success')}
    built, runtime, clients = passes('build'), passes('runtime'), passes('client_runtime')
    clients.update(passes('legacy_discs_client_runtime'))
    pairs, lazo, lazo_pairs = passes('pair_runtime'), passes('lazo_runtime'), passes('lazo_pair_runtime')
    patched = {}
    for pin in pins['targets']:
        if not pin.get('dependency_patch'):
            continue
        expected = ROOT / 'build/compat-deps' / pin['dependency_patch']['filename']
        result = passes('lazo_dependency_runtime').get(pin['target'], {})
        if expected.is_file() and result.get('audio_verified') and any(d.get('sha256') == hashlib.sha256(expected.read_bytes()).hexdigest() for d in result.get('dependencies', [])):
            patched[pin['target']] = result
    # Earlier exploratory SDK runs lack an artifact hash and are not counted here.
    lazo = {key: r for key, r in lazo.items() if r.get('sha256') and r.get('audio_verified')}
    count = sum(assertions(r, 'PLAYLIST TESTS PASSED') for r in runtime.values())
    lazo_count = sum(assertions(r, 'PLAYLIST LAZO TESTS PASSED') for r in [*lazo.values(), *patched.values()])
    lines = ['# Проверки', '', 'Обновлено: ' + datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'), '',
             f"Версия мода: **{matrix['mod_version']}**. Производственных JAR: **{len(built)}/{len(matrix['targets'])}**.", '',
             f'Обычные плейлисты: серверы SDK **{len(runtime)}/90**, **{count} assertions**; точный JAR в клиенте **{len(clients)}** сочетаний.',
             f'LazoDiscs 1.0.7 + Plasmo Voice 2.1.17: **{len(lazo) + len(patched)}/{len(pins["targets"])}** сочетаний, **{lazo_count} assertions**. Из них **{len(lazo)}** с неизменёнными опубликованными зависимостями и **{len(patched)}** с локальным исправлением метаданных Plasmo Voice.',
             f'Выделенный сервер и две отдельные клиентские JVM: обычные диски **{len(pairs)}**, LazoDiscs **{len(lazo_pairs)}** сочетаний.', '',
             'Серверная матрица обычных плейлистов проверяет исходники в SDK и ускоряет длительные треки вызовами тикера.',
             'Клиентские сценарии используют готовый JAR из `dist/`, обычные тики мира и звуковой движок Minecraft. SHA-256 проверенного файла сохраняется в каждой записи.',
             'Неудачные попытки сохраняются отдельно; PASS одного сочетания не переносится на остальные.', '',
             '## Обычные плейлисты', '',
             '`Сервер` — пройден SDK; `Клиент` — дополнительно 15 проверок точного JAR; `2 клиента` — отдельный сетевой сценарий с перезапуском.',
             '`JAR` означает только сборку, `—` — загрузчик отсутствует для этого релиза.', '',
             '| Minecraft | Fabric | Forge | NeoForge |', '| --- | --- | --- | --- |']
    packaging = passes('packaging')
    if packaging:
        position = lines.index('## Обычные плейлисты')
        lines[position:position] = [
            '## Подготовка выпуска', '',
            f'После игровых проверок **{len(packaging)}** JAR пересобраны из отдельных проектов `fabric/<версия>`, `forge/<версия>` и `neoforge/<версия>`.',
            'В метаданных загрузчика установлены номер первого выпуска 1.0.0, GPL-3.0-only, автор и ссылки; в JAR включён текст GPL.',
            'Все классы, mixin-конфигурации, refmap, теги и прочие игровые ресурсы побайтно совпадают с проверенными JAR. Зависимости и ограничения загрузчиков также совпадают.',
            'Это сравнение упаковки, а не повторный игровой прогон всей матрицы. Исходные SHA-256 игровых запусков сохранены; соответствие новым файлам: `.agents/reports/PACKAGING-VERIFICATION.json`.', '',
        ]
    targets = {t['id']: t for t in matrix['targets']}
    for mc in dict.fromkeys(t['minecraft'] for t in matrix['targets']):
        row = [mc]
        for loader in ('fabric', 'forge', 'neoforge'):
            key = loader + '-' + mc
            row.append('—' if key not in targets else 'Ожидает' if key not in built else '2 клиента' if key in pairs else 'Клиент' if key in clients else 'Сервер' if key in runtime else 'JAR')
        lines.append('| ' + ' | '.join(row) + ' |')
    lines += ['', '## LazoDiscs', '',
              'Проверяются точные файлы, закреплённые в `lazodiscs-compatibility.json`; зависимости сверены по SHA-512.',
              'В сервере установлен неизменённый JAR плейлистов, опубликованные LazoDiscs/Plasmo Voice и отдельный тестовый мод.',
              'Fabric использует production launcher. Forge 1.16.5–1.20.4 — официальный установщик и обычный сервер; остальные Forge/NeoForge — SDK с готовыми модами.',
              'Каждая попытка получает новый мир, loopback HTTP/UDP и собственные WAV-сигналы 440/880 Гц.',
              'Успех требует 16 проверок, реальных HTTP-запросов обоих файлов и запуска декодера; сообщение об ошибке аудио запрещает PASS.',
              'Проверяются сохранность всех данных записи, естественный переход, повтор, ручное извлечение, смешанная очередь, устаревший callback и разрушение блока.', '',
              '| Загрузчик | Minecraft | Точный JAR + аудио |', '| --- | --- | --- |']
    for pin in pins['targets']:
        key = pin['target']
        outcome = 'PASS, фикс метаданных PV' if key in patched else 'PASS' if key in lazo else 'Ожидает'
        lines.append(f"| {pin['loader']} | {pin['minecraft']} | {outcome} |")
    lines += ['', 'Для Fabric/Forge 1.16.5 добавлен обход вызова недоступного серверного форматтера координат в LazoDiscs.',
              'Для Forge 1.21 добавляется отсутствующий конструктор без аргументов, делегирующий исходному конструктору LazoDiscs с текущим FML-контекстом. Исходный JAR LazoDiscs не меняется.',
              'Для Forge 1.20.2 опубликованный PV 2.1.17 требует Forge/FML 49, хотя Minecraft-диапазон включает 1.20.2. Готовый исправленный JAR с минимумом 48 включён в `compat/forge-1.20.2/` полного ZIP и находится в `dist/compat/forge-1.20.2/`. Классы и библиотеки сохранены; приложены лицензия, исходники и воспроизводимый патчер. Отклонение исходной зависимости сохранено в истории попыток.',
              'Собственный таймер пластинки отключается только для записей LazoDiscs; переход происходит по завершению аудио с паузой 20 тиков.', '',
              '## Клиенты и звук', '']
    for key, result in clients.items():
        lines.append(f"- `{key}`: SHA-256 `{result['sha256']}`; лог `{result['log']}`.")
        if result.get('packaging_only_update'):
            lines.append(f"  SHA-256 выпуска после изменения упаковки: `{result['release_sha256']}`.")
    for key, result in passes('lazo_client_runtime').items():
        lines += ['', f"**LazoDiscs, одиночный клиент {key}**: SHA-256 `{result['sha256']}`; лог `{result['log']}`.",
                  'Настоящая команда `/lazodisc burn` создаёт записи 440/880 Гц. Проверяются активный источник Plasmo Voice с положительной громкостью, отсутствие ванильного звука, естественный переход и сохранение всех данных записей; затем 15 проверок обычных пластинок. Микрофон отключён.']
        if key == 'forge-1.20.2':
            lines.append('Использован обычный клиент официально установленного Forge 48.1.0 на Java 17, готовый исправленный PV и неизменённые JAR LazoDiscs/плейлистов. Переименован только независимый тестовый мод.')
    for label, results in (('Обычные пластинки', pairs), ('LazoDiscs', lazo_pairs)):
        for key, result in results.items():
            lines += ['', f"**{label}, {key}**: SHA-256 `{result['sha256']}`.",
                      f"Доказательства: `{result['evidence']}`.",
                      'Выделенный сервер, владелец и наблюдатель запускаются отдельными JVM. Проверяются действия владельца, звук у обоих игроков и полный перезапуск.']
            if label == 'LazoDiscs':
                lines += ['Пластинки записываются настоящей командой `/lazodisc burn`. Запись A длится 104 с поверх ванильной пластинки «11» (71 с).',
                          'Оба клиента подтверждают непрерывное воспроизведение дольше ванильного таймера, переход к B, затем к обычной «13» и обратно к сохранённой A.',
                          'После перезапуска проверяются запись B и сохранённый слот очереди. Микрофонные входы отключены в тестовых настройках.']
                if result.get('long_recording_server_ticks'):
                    lines.append(f"Запись A продолжала звучать спустя **{result['long_recording_server_ticks']} серверных тиков**, дольше ванильного таймера и паузы (1440 тиков).")
            if result.get('tone_captures'):
                lines += ['Выход каждого тестового клиента направлен в собственный временный PulseAudio sink; записывается только его PCM.',
                          'Проверены частота и ненулевая амплитуда: ' + '; '.join(stage + ': ' + ', '.join(f"{role} {v['frequency_hz']:.1f} Гц, RMS {v['rms']:.1f}" for role, v in recordings.items()) for stage, recordings in result['tone_captures'].items()) + '.']
            elif result.get('audio_rms'):
                lines.append('Ненулевой PCM у обоих клиентов: ' + ', '.join(f'{role} RMS {value:.1f}' for role, value in result['audio_rms'].items()) + '.')
    review = ROOT / 'build/evidence/visual-review.json'
    if review.exists():
        reviewed = json.loads(review.read_text())
        lines += ['', f"При подготовке выпуска открыто и осмотрено оригинальных кадров: **{len(reviewed['screenshots'])}**. Перечень и хеши: `build/evidence/visual-review.json`."]
    lines += ['', '## Границы проверки', '',
              f'Серверная проверка с LazoDiscs выполнена для {len(lazo) + len(patched)} перечисленных PASS; полный сетевой и звуковой сценарий — на Fabric 26.3. Вариант с исправленным PV проверяется отдельно от опубликованных файлов.',
              'Остальные сочетания основной матрицы не имеют опубликованного LazoDiscs 1.0.7. Модпаки, шейдеры, OptiFine, ресурспаки и прочие интеграции LazoDiscs отдельно не проверялись.',
              'Проверены стандартные Fabric/Forge/NeoForge. Vanilla/Paper не загружают эти моды; гибридные ядра и прокси отдельно не проверялись.',
              'Проверяется декодирование локальных WAV и реальная передача Plasmo Voice; доступность YouTube и других внешних сервисов зависит от LazoDiscs и не проверяется этим сценарием.',
              'Forge 1.20.6 использует совместимость Mixin JAVA_17 из-за встроенной Mixin 0.8.5; игровая JVM остаётся Java 21.', '',
              '## Команды', '', '```bash', 'python3 tools/sync_projects.py --check', 'python3 tools/build_matrix.py', 'python3 tools/verify_artifacts.py',
              'python3 tools/runtime_matrix.py --eula-file /path/to/accepted/eula.txt',
              'python3 tools/client_test.py --target fabric-26.3',
              'python3 tools/lazo_deps.py',
              'python3 tools/lazo_matrix.py --eula-file /path/to/accepted/eula.txt',
              'python3 tools/client_test.py --target forge-1.20.2 --lazo-startup --java-path /path/to/java8 --java-path /path/to/java17',
              'python3 tools/pair_test.py --lazo --audio --eula-file /path/to/accepted/eula.txt',
              'python3 tools/report.py', 'python3 tools/package.py', '```', '',
              'Дополнительные Java передаются через `--java-path`; установленному Forge 1.16.5 нужна Java 8.',
              'Локальные логи, хеши JAR, результаты и история попыток находятся в `build/results`, `build/status.json` и `build/evidence`; эти рабочие каталоги не входят в исходники или полный ZIP.', '']
    output = ROOT / '.agents/reports/VERIFICATION.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines))
    print(f'Builds {len(built)}/90; SDK {len(runtime)}/90; clients {len(clients)}; LazoDiscs {len(lazo) + len(patched)}/52 (published {len(lazo)}, metadata fix {len(patched)}); paired {len(pairs)}; Lazo paired {len(lazo_pairs)}')


if __name__ == '__main__':
    main()
