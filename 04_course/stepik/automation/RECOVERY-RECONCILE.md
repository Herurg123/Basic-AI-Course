# Recovery / reconcile

## Назначение

Recovery отвечает только на вопрос: можно ли безопасно продолжить или завершить уже начатую операцию, не угадывая происхождение live state.

## Автоматически допустимо

- commit gap после доказанного final read-back: закрыть machine/history state без Stepik write;
- доказанный partial prefix: продолжить только ещё не dispatched operations;
- prewrite event без dispatch: вернуться в normal guarded route при неизменных source/baseline/live guards.

## STOP

- ambiguous dispatch;
- failed/unavailable read-back;
- manual/unknown live drift;
- conflicting events;
- stale source SHA;
- неизвестный existing live без baseline;
- structural/destructive mutation, для которой нет отдельного доказанного route.

Reconcile не превращает совпадение `live == canonical` в автоматический rebaseline. Origin должен быть доказан.
