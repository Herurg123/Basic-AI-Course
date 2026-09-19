# Автоматизация GitHub → Stepik

**Курс:** `299189`  
**Источник learner-facing содержания:** текущий `main`  
**Главный принцип:** все 21 урок обрабатываются одинаково.

## Production-модель

Единственный all-course write entry point: `.github/workflows/stepik-private-release.yml`.

Для каждого PENDING lesson planner выбирает один из трёх общих режимов:

1. **initial** — baseline отсутствует; запись разрешена только из доказанного безопасного initial state;
2. **refresh** — baseline есть; live обязан совпасть с baseline до изменения;
3. **recovery** — есть доказуемый незавершённый deployment event; продолжение возможно только из подтверждённого состояния.

Отдельных runtime-классов для M00-L01/M00-L02 и других исторически особых уроков нет.

## Источники состояния

- canonical GitHub `main`;
- current machine state в Issue #54;
- immutable deployment history;
- fresh live Stepik read-back.

Ни один из источников в одиночку не разрешает write.

## Platform conventions

`stepik-platform-profile.v1.json` хранит только подтверждённые соглашения рендеринга Stepik, например `free_answer_source`. Он не содержит Lesson ID, content baseline или write authority.

## Assets

`asset-publication.v1.json` задаёт способы публикации learner assets. Подтверждённые attachments/images имеют отдельные machine baselines. Изменение bytes без доказанного replacement route блокируется fail-closed.

## Safety

- только current `main`;
- курс должен оставаться private во время release;
- единый mutex `stepik-live-course-299189`;
- no blind retry;
- durable write-ahead history;
- per-operation read-back;
- final read-back до изменения machine state;
- `DELETE` и destructive rollback запрещены;
- unknown/manual drift = STOP.

Подробности: `SYNC-POLICY.md`, `LIVE-SAFETY.md`, `DEPLOYMENT-HISTORY.md`, `RECOVERY-RECONCILE.md`.

## Педагогические проверки

Эта автоматизация не заменяет педагогические gates. Проверки «педагог» + «нулевой ученик» запускаются при изменении learner-facing контента, демо-файлов и других материалов, с которыми непосредственно сталкивается ученик. Чисто технические изменения uploader/runtime этих проверок не требуют.
