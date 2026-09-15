# D-2026-09-15-STEPIK-ATTACHMENTS — рабочее допущение о загрузке файлов в Stepik

**Дата:** 15 сентября 2026 года  
**Статус:** OWNER-APPROVED WORKING ASSUMPTION  
**Область:** курс Stepik `299189`, learner-facing downloadable files

## Решение владельца

До отдельной отмены владельцем проекта либо до появления фактического ограничения API считать Stepik attachments доступным production-маршрутом для загрузки и выдачи learner-facing файлов курса.

Это решение используется для завершения `asset-publication-resolution` и проектирования следующего verified rendering / first-upload gate.

## Основание

Решение принято не только по документации, а по фактическому состоянию курса и API:

1. владелец вручную успешно загрузил в lesson `2591710` два файла: `M00-L02-A01.docx` и `M00-L02-A02.png`;
2. авторизованный read-only API probe для бесплатного курса `299189` подтвердил `is_paid=false`, `price=null` и наличие attachment actions у course/lesson;
3. `GET /api/attachments?lesson=2591710` вернул оба фактически загруженных файла;
4. `OPTIONS /api/attachments` вернул `Allow: GET, POST, HEAD, OPTIONS`;
5. metadata API объявляет `POST`, принимает `multipart/form-data`, а поле `file` имеет тип `file upload` и `required=true`.

Диагностические GitHub Actions runs:

- `34955808296` — базовый read-only capability probe;
- `34955920959` — чтение существующих attachment objects и POST metadata;
- `34956046044` — upload schema (`multipart/form-data`, `file upload`).

Во всех трёх probes `stepik_content_writes=0`.

## Что доказано и что пока не доказано

Практически подтверждено, что текущий аккаунт/курс видит attachment collection, существующие файлы и API-схему создания attachment.

Автоматизированный `POST /api/attachments` из production safety-контура пока не выполнялся. Поэтому это решение является **рабочим production-допущением**, а не обещанием неизменности платформы.

## Fail-closed условия отмены допущения

Допущение немедленно перестаёт считаться действующим для автоматической записи, если любой preflight/write/read-back обнаруживает хотя бы одно из следующего:

- `/api/attachments` больше не объявляет `POST`;
- multipart upload или обязательное поле `file` больше не поддерживаются;
- API возвращает тарифный/permission blocker для курса `299189`;
- upload принят, но attachment нельзя доказуемо прочитать через API или открыть по learner-facing URL;
- Stepik меняет контракт так, что стабильный learner download-route больше не подтверждается;
- владелец проекта отменяет это решение.

При таком событии automation должна остановиться (`STOP`), не подменять Stepik URL выдуманным внешним URL и вернуть `asset-publication-resolution` в незакрытое состояние.

## Производственные последствия

- `M04-L01-A01.txt` получает route `stepik-attachment-upload`;
- route считается архитектурно разрешённым, но сам файл должен быть материализован только внутри будущей защищённой write-транзакции;
- write должен использовать owner dispatch, write-ahead history, отсутствие blind retry, read-back и доказуемую привязку к точному source SHA-256;
- существующие golden attachments `M00-L02` остаются `READ_ONLY` и не дают права автоматически перезаписывать golden lesson;
- успешность attachment API не разблокирует bulk write сама по себе: следующий gate — verified rendering / controlled first upload.

## Связь с манифестом

Решение не вводит платную подписку и не меняет learner-facing компетенции. Оно использует фактически доступный бесплатному курсу платформенный маршрут и поэтому не конфликтует с требованием бесплатной проходимости базового курса.
