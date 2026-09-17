from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

WORKFLOWS = {
    "repository-janitor.yml": ("[cleanup]", "Проверить рабочие ветки репозитория и выполнить только доказанно безопасную уборку по действующим защитным правилам."),
    "stepik-bulk-status.yml": ("[tests, bulk_status]", "Провести offline-проверки и read-only сверку статуса всех 21 уроков приватного курса Stepik без записей."),
    "stepik-golden-title-migration.yml": ("[tests, live]", "Проверить golden-title контракт и при явном owner-dispatch безопасно выполнить только разрешённую миграцию заголовков M00-L01/M00-L02."),
    "stepik-learner-hygiene.yml": ("[tests, live]", "Проверить learner-facing hygiene и при явном owner-dispatch выполнить только подтверждённые guarded-изменения с read-back и фиксацией состояния."),
    "stepik-private-release.yml": ("[tests, release]", "Провести полный private-release: offline/preflight проверки, guarded-сборку оставшегося Stepik-состояния, course page, golden-операции и финальную проверку backlog."),
    "stepik-section-position-recovery.yml": ("[tests, live]", "Проверить и при явном owner-dispatch безопасно восстановить section.position по утверждённому recovery-контракту."),
    "stepik-staging-batch.yml": ("[tests, batch-staging]", "Проверить и при явном owner-dispatch последовательно собрать все ordinary PENDING lessons приватного Stepik-стейджинга с read-back и durable history."),
    "stepik-staging-build.yml": ("[tests, staging-build]", "Проверить и при явном owner-dispatch безопасно собрать один выбранный урок приватного Stepik-стейджинга с recovery/read-back защитой."),
    "stepik-uploader.yml": ("[tests, impact, live]", "Проверить Stepik automation, при merge обновить machine-readable impact, а при owner-dispatch выполнить выбранный read-only или guarded write-режим."),
}

SUMMARY_JOB = """

  run_summary:
    name: Русское резюме запуска
    if: ${{{{ always() }}}}
    needs: {needs}
    permissions:
      actions: read
      checks: read
      contents: read
    uses: ./.github/workflows/_russian-run-summary.yml
    with:
      purpose: >-
        {purpose}
"""

REUSABLE = r'''name: Русское резюме GitHub Actions

on:
  workflow_call:
    inputs:
      purpose:
        description: 'Краткое русское описание того, что должен выполнить вызывающий workflow.'
        required: true
        type: string

permissions:
  actions: read
  checks: read
  contents: read

jobs:
  summary:
    name: Сформировать русское резюме
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Сформировать итог запуска на русском
        uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3
        env:
          RUN_PURPOSE: ${{ inputs.purpose }}
        with:
          github-token: ${{ github.token }}
          script: |
            const runId = Number(process.env.GITHUB_RUN_ID);
            const purpose = String(process.env.RUN_PURPOSE || '').trim();
            const { owner, repo } = context.repo;
            const jobs = await github.paginate(github.rest.actions.listJobsForWorkflowRun, {
              owner, repo, run_id: runId, per_page: 100, filter: 'latest',
            });
            const relevantJobs = jobs.filter((job) =>
              !String(job.name || '').includes('Сформировать русское резюме')
            );
            const statusRu = {
              success: 'выполнено успешно', failure: 'ошибка', cancelled: 'отменено',
              skipped: 'пропущено по условию запуска', timed_out: 'превышен лимит времени',
              action_required: 'требуется действие', neutral: 'нейтральный результат',
              stale: 'устаревший результат', startup_failure: 'ошибка запуска runner',
            };
            const escapeMd = (value) => String(value ?? '')
              .replaceAll('\\', '\\\\').replaceAll('|', '\\|')
              .replaceAll('\r', ' ').replaceAll('\n', ' ').trim();
            const isInfraStep = (name) => {
              const value = String(name || '');
              return value === 'Set up job' || value === 'Complete job'
                || value.startsWith('Post ') || value === 'Сформировать итог запуска на русском';
            };
            async function errorDetail(job, failedStep) {
              const fallback = failedStep
                ? `Этап «${escapeMd(failedStep.name)}» завершился неуспешно.`
                : `Job «${escapeMd(job.name)}» завершился неуспешно.`;
              try {
                const match = String(job.check_run_url || '').match(/\/check-runs\/(\d+)$/);
                if (!match) return fallback;
                const response = await github.rest.checks.listAnnotations({
                  owner, repo, check_run_id: Number(match[1]), per_page: 100,
                });
                const annotation = response.data.find((item) => item.annotation_level === 'failure')
                  || response.data.find((item) => item.annotation_level === 'warning');
                if (!annotation?.message) return fallback;
                return `${fallback} GitHub: ${escapeMd(annotation.message).slice(0, 500)}`;
              } catch (error) { return fallback; }
            }
            const failedJobs = relevantJobs.filter((job) =>
              ['failure', 'cancelled', 'timed_out', 'startup_failure', 'action_required'].includes(job.conclusion)
            );
            const successfulJobs = relevantJobs.filter((job) => job.conclusion === 'success');
            let overall = '✅ УСПЕХ';
            if (failedJobs.length > 0) overall = '❌ ОШИБКА';
            else if (relevantJobs.some((job) => !['success', 'skipped'].includes(job.conclusion)))
              overall = '⚠️ ЧАСТИЧНЫЙ/НЕОПРЕДЕЛЁННЫЙ РЕЗУЛЬТАТ';
            const lines = ['# Итог GitHub Actions', '', `**Итог:** ${overall}`, '',
              `**Что должен был сделать запуск:** ${escapeMd(purpose) || 'описание цели не передано'}`, ''];
            lines.push('## Что должно было быть выполнено');
            if (relevantJobs.length === 0) lines.push('- GitHub не вернул список функциональных jobs.');
            for (const job of relevantJobs) {
              lines.push(`- **${escapeMd(job.name)}**`);
              for (const step of (job.steps || []).filter((step) => !isInfraStep(step.name)))
                lines.push(`  - ${escapeMd(step.name)}`);
            }
            lines.push('', '## Что выполнено');
            if (successfulJobs.length === 0) lines.push('- Успешно завершённых функциональных jobs нет.');
            for (const job of successfulJobs) {
              lines.push(`- ✅ **${escapeMd(job.name)}** — выполнено успешно.`);
              for (const step of (job.steps || []).filter((step) => !isInfraStep(step.name) && step.conclusion === 'success'))
                lines.push(`  - ✅ ${escapeMd(step.name)}`);
            }
            lines.push('', '## Что не выполнено');
            const notDoneJobs = relevantJobs.filter((job) => job.conclusion !== 'success');
            if (notDoneJobs.length === 0) lines.push('- Невыполненных этапов нет.');
            for (const job of notDoneJobs) {
              lines.push(`- ${job.conclusion === 'skipped' ? '⏭️' : '❌'} **${escapeMd(job.name)}** — ${statusRu[job.conclusion] || escapeMd(job.conclusion || job.status)}.`);
              for (const step of (job.steps || []).filter((step) => !isInfraStep(step.name) && step.conclusion !== 'success')) {
                const mark = step.conclusion === 'skipped' ? '⏭️' : '❌';
                lines.push(`  - ${mark} ${escapeMd(step.name)} — ${statusRu[step.conclusion] || escapeMd(step.conclusion || step.status)}.`);
              }
            }
            lines.push('', '## Ошибки');
            if (failedJobs.length === 0) lines.push('- Ошибок не зафиксировано.');
            for (const job of failedJobs) {
              const failedStep = (job.steps || []).find((step) =>
                ['failure', 'cancelled', 'timed_out'].includes(step.conclusion));
              lines.push(`- ❌ **${escapeMd(job.name)}**: ${await errorDetail(job, failedStep)}`);
            }
            lines.push('', '> Для принятия обычного следующего решения достаточно этой сводки. Логи нужны только для углублённой диагностики или исправления кода.');
            await core.summary.addRaw(lines.join('\n')).write();
'''

GOVERNANCE = r'''name: Project Governance

on:
  pull_request:
    paths:
      - '.github/workflows/**'
      - '00_governance/project-instructions/**'
      - 'AGENTS.md'
      - 'README.md'
  push:
    branches: [main]
    paths:
      - '.github/workflows/**'
      - '00_governance/project-instructions/**'
      - 'AGENTS.md'
      - 'README.md'

permissions:
  contents: read

jobs:
  action-summary-contract:
    name: Проверить контракт русских Actions Summary
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Получить репозиторий
        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
      - name: Проверить все workflow
        shell: bash
        run: |
          set -euo pipefail
          python - <<'PY'
          from pathlib import Path
          workflows = Path('.github/workflows')
          reusable = workflows / '_russian-run-summary.yml'
          problems = []
          if not reusable.is_file():
              problems.append('Отсутствует обязательный reusable workflow _russian-run-summary.yml')
          for path in sorted(workflows.glob('*.yml')):
              if path.name == '_russian-run-summary.yml':
                  continue
              text = path.read_text(encoding='utf-8')
              if '  run_summary:' not in text:
                  problems.append(f'{path}: отсутствует job run_summary')
              if 'always()' not in text:
                  problems.append(f'{path}: run summary не гарантирован через always()')
              if 'uses: ./.github/workflows/_russian-run-summary.yml' not in text:
                  problems.append(f'{path}: не используется общий русскоязычный summary workflow')
              if 'purpose: >-' not in text:
                  problems.append(f'{path}: не передано русское описание цели запуска')
          instruction = Path('00_governance/project-instructions/project-instructions-v1.5.md')
          if not instruction.is_file():
              problems.append('Нет project-instructions-v1.5.md')
          elif 'Обязательная русскоязычная GitHub Actions Summary' not in instruction.read_text(encoding='utf-8'):
              problems.append('В инструкции v1.5 отсутствует нормативный раздел Actions Summary')
          if problems:
              raise SystemExit('\n'.join(problems))
          print('PASS: все workflow соблюдают обязательный русскоязычный Actions Summary contract')
          PY

  run_summary:
    name: Русское резюме запуска
    if: ${{ always() }}
    needs: [action-summary-contract]
    permissions:
      actions: read
      checks: read
      contents: read
    uses: ./.github/workflows/_russian-run-summary.yml
    with:
      purpose: >-
        Проверить, что все GitHub Actions workflow соблюдают обязательный проектный контракт русскоязычной сводки запуска.
'''


def patch_workflow(path: Path, needs: str, purpose: str) -> None:
    text = path.read_text(encoding='utf-8')
    if '  run_summary:' not in text:
        path.write_text(text.rstrip() + SUMMARY_JOB.format(needs=needs, purpose=purpose) + '\n', encoding='utf-8')


def build_v15() -> None:
    src = ROOT / '00_governance/project-instructions/project-instructions-v1.4.md'
    dst = ROOT / '00_governance/project-instructions/project-instructions-v1.5.md'
    text = src.read_text(encoding='utf-8')
    text = text.replace('**Версия:** 1.4', '**Версия:** 1.5', 1)
    text = text.replace('**Дата:** 13 сентября 2026 года', '**Дата:** 17 сентября 2026 года', 1)
    marker = '\n## Короткий обязательный workflow\n'
    section = '''\n\n## 14. Обязательная русскоязычная GitHub Actions Summary\n\nДля каждого действующего и вновь создаваемого GitHub Actions workflow обязательна итоговая русскоязычная сводка в интерфейсе GitHub Actions Summary. Владелец проекта не должен открывать внутренние логи обычного запуска, чтобы понять его результат и следующий шаг.\n\nИтоговая сводка должна формироваться автоматически после функциональных jobs через финальный summary-job с `if: always()` и содержать как минимум:\n\n1. **что должно было быть выполнено** — краткую цель запуска и перечень основных jobs/этапов;\n2. **что выполнено** — jobs и этапы, завершившиеся успешно;\n3. **что не выполнено** — пропущенные, отменённые, не дошедшие до выполнения или завершившиеся неуспешно jobs/этапы с понятным статусом;\n4. **ошибки** — при failure/timeout/cancelled краткое русское пояснение: какой job/этап остановился и, если GitHub предоставляет диагностическую аннотацию, её краткий смысл;\n5. **явный общий итог** — успех, ошибка либо частичный/неопределённый результат.\n\nВ штатном успешном запуске раздел ошибок явно сообщает, что ошибок не зафиксировано. Условно пропущенный job не маскируется под ошибку: сводка должна объяснять, что он пропущен условиями данного типа запуска.\n\nПодробные логи остаются техническим evidence для расследования, но не заменяют Summary. Для обычного решения владельцу должно быть достаточно Summary; открытие логов требуется только для углублённой диагностики или исправления.\n\nДля единообразия workflow репозитория используют общий reusable workflow `.github/workflows/_russian-run-summary.yml` либо эквивалент, явно одобренный отдельным проектным решением. Наличие summary-контракта для всех workflow автоматически проверяется `.github/workflows/project-governance.yml`; новый workflow без такого summary считается нарушением проектных правил и не должен попадать в `main`.\n\nСтарые уже завершённые GitHub Actions runs не могут быть задним числом дополнены `$GITHUB_STEP_SUMMARY`; это правило действует для запусков после принятия v1.5. Если пользователь принудительно отменил весь workflow или сама инфраструктура GitHub не запустила финальный summary-job, отсутствие Summary считается платформенным ограничением конкретного run и явно отмечается при расследовании.\n'''
    if marker not in text:
        raise SystemExit('Не найден маркер для раздела Actions Summary')
    text = text.replace(marker, section + marker, 1)
    text = text.rstrip() + '\n\n**v1.5** — для всех действующих и будущих GitHub Actions workflow введена обязательная русскоязычная Summary: цель запуска, выполненное, невыполненное, явный итог и краткая ошибка; добавлен общий reusable summary и автоматическая governance-проверка этого контракта.\n'
    dst.write_text(text, encoding='utf-8')


def update_docs() -> None:
    p = ROOT / '00_governance/project-instructions/README.md'
    text = p.read_text(encoding='utf-8').replace('`project-instructions-v1.4.md`', '`project-instructions-v1.5.md`')
    text = text.replace('Версия v1.4 также закрепляет русский язык', 'Версия v1.5 сохраняет правило русского языка')
    if 'итоговую русскоязычную Summary' not in text:
        text = text.replace('\nDOCX создаётся', '\nВерсия v1.5 дополнительно требует для каждого GitHub Actions workflow итоговую русскоязычную Summary: что планировалось, что выполнено, что не выполнено и какая ошибка произошла. Общий summary-контракт проверяется автоматически.\n\nDOCX создаётся', 1)
    p.write_text(text, encoding='utf-8')

    p = ROOT / 'AGENTS.md'
    text = p.read_text(encoding='utf-8')
    bullet = '- Каждый GitHub Actions workflow обязан завершаться русскоязычной Summary через общий `.github/workflows/_russian-run-summary.yml`: цель запуска, выполненное, невыполненное, явный итог и краткое объяснение ошибки. Новый workflow без этого контракта не принимается в `main`; соблюдение автоматически проверяет `project-governance.yml`.\n'
    anchor = '- После значимого PR актуализируются `README.md` и `AGENTS.md`, если изменилось состояние проекта или рабочие правила.\n'
    if bullet not in text:
        text = text.replace(anchor, bullet + anchor, 1)
    p.write_text(text, encoding='utf-8')

    p = ROOT / 'README.md'
    text = p.read_text(encoding='utf-8').replace('[инструкция проекта v1.4](00_governance/project-instructions/project-instructions-v1.4.md)', '[инструкция проекта v1.5](00_governance/project-instructions/project-instructions-v1.5.md)')
    para = '\nВсе GitHub Actions workflow обязаны завершаться русскоязычной Summary, где без открытия внутренних логов видно: что планировалось, что выполнено, что не выполнено, общий результат и краткая причина ошибки. Для этого используется общий reusable workflow `_russian-run-summary.yml`, а соблюдение правила автоматически проверяется `project-governance.yml`.\n'
    anchor = '\n## Автоматическая гигиена веток\n'
    if 'Все GitHub Actions workflow обязаны завершаться русскоязычной Summary' not in text:
        text = text.replace(anchor, para + anchor, 1)
    p.write_text(text, encoding='utf-8')


def main() -> None:
    wd = ROOT / '.github/workflows'
    for name, (needs, purpose) in WORKFLOWS.items():
        patch_workflow(wd / name, needs, purpose)
    (wd / '_russian-run-summary.yml').write_text(REUSABLE, encoding='utf-8')
    (wd / 'project-governance.yml').write_text(GOVERNANCE, encoding='utf-8')
    build_v15()
    update_docs()
    for path in [ROOT / '.github/workflows/_bootstrap-git-object-migration.yml', Path(__file__).resolve()]:
        if path.exists():
            path.unlink()

if __name__ == '__main__':
    main()
