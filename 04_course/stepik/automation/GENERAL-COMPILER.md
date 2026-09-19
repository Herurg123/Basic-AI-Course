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
