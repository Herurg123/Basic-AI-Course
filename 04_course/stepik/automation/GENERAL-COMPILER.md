# General learner-content compiler

Compiler преобразует canonical learner-facing материалы в Stepik steps для всех 21 lessons.

## Источники

- `lesson.md`;
- `stepik-plan.md`;
- learner assets/dependencies;
- `stepik-platform-profile.v1.json` для platform-specific block conventions;
- `asset-publication.v1.json` для asset routes.

Platform profile не содержит lesson identities и не является content baseline.

## Инварианты

- author-only content не попадает ученику;
- порядок learner steps соответствует Stepik plan;
- free-answer source берётся только из confirmed platform profile;
- repo-relative learner dependencies должны быть resolved до write;
- learner-visible internal IDs не должны утекать в итоговый HTML;
- compiled result проходит verified rendering до Stepik mutation.

## Single-source rule для learner-facing Markdown

Repo-relative ссылка на локальный `.md` в learner-facing тексте **не является обычной ссылкой**: verified renderer использует режим `inline-source` и физически встраивает содержимое Markdown в текущий Stepik step.

Поэтому один и тот же learner-facing Markdown source нельзя повторно ссылать repo-relative из нескольких мест курса. Иначе ученик получает несколько независимых копий одной и той же памятки.

Правило:

- полный текст справочного/технического Markdown встраивается ровно в одном каноническом Stepik step;
- повторное обращение к уже показанной справке использует обычную HTTPS-ссылку на этот канонический Stepik step;
- текст ссылки должен объяснять, куда ученик вернётся и зачем;
- нельзя писать «материал ниже», если материал фактически находится в другом шаге;
- изменение канонического source автоматически меняет единственный встроенный экземпляр; вторичных копий быть не должно.

Regression-test обязан блокировать повторные repo-relative ссылки на один и тот же `.md` source в learner graph.

