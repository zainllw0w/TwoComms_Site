# Management Bot: 100 визуальных и интерактивных улучшений

Дата: 2026-08-05  
Область: management Instagram bot  
Статус: рекомендации для выбора, не реализованный backlog

## Как проходил отбор

Список собран после проверки текущего `bot.html`, API-контрактов, рабочих
состояний клиентов, responsive-поведения и уже выпущенных срезов. В него не
включены уже сделанные изменения: коммерческие цвета, сворачиваемый контекст,
компактные фильтры, симметричные action-кнопки и новая Overview-сетка.

Каждый пункт прошёл четыре фильтра: помогает ли он оператору принять решение;
не дублирует ли существующий control; можно ли проверить его тестом или
метрикой; не создаёт ли он постоянный визуальный шум. `P0` означает заметный
операционный эффект и низкую неоднозначность, `P1` — полезное улучшение после
P0, `P2` — polish при наличии измеримого эффекта. Стоимость: `S` до дня,
`M` один-два спринта, `L` больше двух спринтов.

## 1. Коммерческое состояние и сканирование

**1. Легенда состояний по запросу** — Приоритет: P1. Rationale: цвета уже несут
операторский смысл, но новый сотрудник не должен угадывать его. Benefit: одна
иконка «Легенда» объясняет зелёный, фиолетовый и янтарный без постоянной панели.
Cost: S. Risk: лишний control; открывать только по клику и хранить preference.

**2. Всплывающая доказательная подсказка состояния** — Приоритет: P0. Rationale:
цвет должен приводить к факту оплаты или TTN, а не к предположению. Benefit:
hover/focus показывает источник, время и order id. Cost: S. Risk: раскрытие PII;
показывать только менеджеру с правом просмотра.

**3. Явная последовательность приоритета состояний** — Приоритет: P0. Rationale:
paid и shipped могут существовать одновременно. Benefit: tooltip объясняет,
почему выбран один статус, и исключает спорные ручные трактовки. Cost: S. Risk:
несогласованность с backend; брать готовое поле `commercial_visual_state`.

**4. Дублирование цвета текстовым маркером** — Приоритет: P0. Rationale: один
цвет недоступен при дальтонизме и плохом мониторе. Benefit: короткие labels
«Оплачено»/«Відправлено» делают список понятным без палитры. Cost: S. Risk:
переполнение; ограничить label и проверять 320px.

**5. Таймер ожидания оплаты внутри янтарного чипа** — Приоритет: P0. Rationale:
менеджеру важнее срок действия, чем сам факт ожидания. Benefit: видно, кому
нужно написать сейчас. Cost: M. Risk: неверная timezone; сервер должен отдавать
ISO-время и локализованный countdown.

**6. Лента переходов коммерческого состояния** — Приоритет: P1. Rationale:
цвет показывает только итог, но не объясняет изменение. Benefit: компактная
история «очікуємо → оплачено → відправлено» сокращает расследование. Cost: M.
Risk: перегруз списка; открывать в detail popover.

**7. Спокойное отображение завершённого заказа** — Приоритет: P1. Rationale:
done не требует тех же акцентов, что активная доставка. Benefit: completed
клиенты не конкурируют с текущими задачами. Cost: S. Risk: потеря видимости
повторной покупки; оставить отдельный count.

**8. Индикатор действия рядом с риском** — Приоритет: P0. Rationale: «потрібна
увага» без следующего шага не ускоряет работу. Benefit: одна строка «Перевірити
чек» или «Запросити TTN» превращает цвет в action cue. Cost: M. Risk: stale
рекомендация; пересчитывать на каждом API refresh.

**9. Единые design tokens для коммерческих цветов** — Приоритет: P1. Rationale:
цвета сейчас распределены по inline CSS и классам. Benefit: одна таблица токенов
держит контраст и одинаковые hover/focus оттенки. Cost: M. Risk: случайный
сдвиг старых warning-цветов; мигрировать постепенно.

**10. Мягкий transition при смене коммерческого факта** — Приоритет: P1.
Rationale: резкая смена border выглядит как перерисовка. Benefit: короткий
crossfade rail/chip делает live-изменение заметным, но не отвлекает. Cost: S.
Risk: motion fatigue; отключать при `prefers-reduced-motion`.

## 2. Список клиентов и фильтрация

**11. Сохранённые рабочие пресеты фильтров** — Приоритет: P1. Rationale: разные
менеджеры повторяют один и тот же набор фильтров. Benefit: «Сегодняшние оплаты»
и «Нужна доставка» открываются одним кликом. Cost: M. Risk: устаревший preset;
показывать дату последней синхронизации.

**12. Deep-link текущего фильтра и клиента** — Приоритет: P0. Rationale: ссылка
на конкретный разговор сейчас не обязана восстановить view. Benefit: менеджер
может передать задачу коллеге с сохранённым filter/client. Cost: M. Risk: утечка
username через URL; использовать существующую auth-проверку.

**13. Глобальная command palette** — Приоритет: P2. Rationale: частые действия
разбросаны между фильтрами, карточкой и вкладками. Benefit: `Ctrl/Cmd+K`
открывает поиск клиента, фильтр и безопасные действия. Cost: L. Risk: скрытие
функций от новичка; palette не должна заменять видимые controls.

**14. Счётчики прямо в disclosure-фильтрах** — Приоритет: P1. Rationale: один
label не сообщает объём работы до открытия меню. Benefit: `Потрібна увага · 4`
помогает выбрать очередь. Cost: S. Risk: stale numbers; помечать время ответа.

**15. Клавиатурное перемещение между строками** — Приоритет: P0. Rationale:
таблица используется повторно весь день. Benefit: стрелки и Enter ускоряют
просмотр без мыши. Cost: M. Risk: конфликт с прокруткой; активная строка должна
забирать фокус только после явного входа.

**16. Чипы активных условий поиска** — Приоритет: P1. Rationale: disclosure
скрывает часть состояния. Benefit: компактная строка под search показывает
«Оплачені + з реклами» и позволяет убрать один constraint. Cost: S. Risk:
дублирование segmented control; отображать только advanced-условия.

**17. Сортировка по следующему действию** — Приоритет: P0. Rationale: алфавитный
порядок не оптимален для работы с очередью. Benefit: сортировка «SLA / payment /
last inbound» поднимает действительно срочных клиентов. Cost: M. Risk: потеря
привычного порядка; сохранить «Останні» как default.

**18. Переключатель плотности списка** — Приоритет: P2. Rationale: 9–12px cards
подходят не каждому дисплею. Benefit: compact/comfortable режимы поддерживают
сканирование и accessibility. Cost: M. Risk: несогласованная высота; токены
должны менять только spacing, не смысл.

**19. Закреплённые клиенты с отдельным разделителем** — Приоритет: P1. Rationale:
оператор возвращается к нескольким активным диалогам. Benefit: pin удерживает
важные conversations сверху без изменения commercial state. Cost: M. Risk:
вечный stale pin; добавить автоматическое снятие по TTL.

**20. Индикатор свежести списка** — Приоритет: P0. Rationale: live refresh без
времени последней синхронизации вызывает сомнение. Benefit: «Оновлено 12:41» и
цвет stale показывают, можно ли доверять очереди. Cost: S. Risk: лишняя строка;
держать её в header, не в каждой строке.

## 3. Переписка и ежедневная работа

**21. Закреплённая строка composer с безопасными быстрыми ответами** — Приоритет:
P1. Rationale: менеджеру часто нужно отправить короткое уточнение. Benefit:
готовые snippets снижают ручной набор. Cost: L. Risk: случайный send; required
preview и явная отправка, без автоответов.

**22. Кнопка «К последнему сообщению»** — Приоритет: P0. Rationale: длинный
transcript прячет новые inbound-сообщения. Benefit: один action возвращает
оператора к актуальной точке. Cost: S. Risk: прыжок при live update; сохранять
anchor message id.

**23. Полоса непрочитанных сообщений** — Приоритет: P0. Rationale: badge вкладки
показывает число, но не границу чтения. Benefit: разделитель «3 нових» делает
новую часть transcript очевидной. Cost: M. Risk: неверный read marker;
фиксировать его серверным message id.

**24. Группировка подряд идущих сообщений одной роли** — Приоритет: P1.
Rationale: отдельные пузырьки удлиняют ленту. Benefit: меньше вертикального
шума, время показывается один раз на группу. Cost: M. Risk: потеря контекста;
оставить раскрываемый timestamp.

**25. Дата-разделители в длинном transcript** — Приоритет: P1. Rationale:
локальные timestamps недостаточны при паузах в несколько дней. Benefit: чёткая
временная ориентация без прокрутки к началу. Cost: S. Risk: лишняя линия;
использовать только при смене календарной даты.

**26. Поиск по текущей переписке** — Приоритет: P1. Rationale: оператор ищет
размер, цену или обещание доставки вручную. Benefit: подсветка совпадений ускоряет
проверку факта. Cost: M. Risk: PII в client-side index; очищать index при
смене клиента.

**27. Контекстная кнопка копирования message id/TTN** — Приоритет: P0.
Rationale: ручное выделение технических значений ошибочно. Benefit: copy action
с подтверждением снижает ошибки в поддержке. Cost: S. Risk: clipboard permission;
иметь text fallback.

**28. Безопасный preview ссылок и медиа** — Приоритет: P1. Rationale: сейчас
оператору приходится открывать URL вслепую. Benefit: домен, тип и размер видны до
перехода. Cost: M. Risk: SSRF/внешний tracking; preview строить из доверенного
метаданных и не fetch-ить URL на сервере.

**29. Медиа-галерея с lazy loading** — Приоритет: P1. Rationale: фото товара
важны для решения, но не должны сдвигать transcript. Benefit: стабильная
thumbnail grid и просмотр оригинала по запросу. Cost: M. Risk: большие файлы;
лимитировать размер и использовать responsive images.

**30. Явный режим передачи менеджеру** — Приоритет: P0. Rationale: takeover
сейчас читается из контекста, а не из conversation header. Benefit: заметный
chip «Менеджер веде діалог» предотвращает автоматический ответ поверх ручной
работы. Cost: S. Risk: alarm fatigue; показывать только при active takeover.

## 4. Контекст клиента и действия

**31. Сворачиваемые секции контекста** — Приоритет: P1. Rationale: order history,
UGC и analysis растягивают drawer. Benefit: открытыми остаются только нужные
facts. Cost: M. Risk: скрытая важная информация; сохранять раскрытые секции.

**32. Фокус на первом действии после открытия drawer** — Приоритет: P0.
Rationale: focus trap уже существует, но оператору приходится искать action.
Benefit: при наличии needs-action фокус попадает на него, иначе на close. Cost:
S. Risk: неожиданное перемещение; применять только при keyboard-open.

**33. Причина disabled рядом с недоступным действием** — Приоритет: P0.
Rationale: disabled-кнопка без объяснения выглядит сломанной. Benefit: короткая
подсказка показывает, чего не хватает для действия. Cost: S. Risk: длинный текст;
использовать tooltip и `aria-describedby`.

**34. Единый подтверждающий диалог для destructive actions** — Приоритет: P0.
Rationale: reset/lost имеют разный визуальный ритм. Benefit: единый modal с
описанием последствий снижает ошибочные клики. Cost: M. Risk: confirmation fatigue;
применять только к необратимым действиям.

**35. Undo-toast для reversible hide/restore** — Приоритет: P1. Rationale:
confirmation для временного hide замедляет работу. Benefit: «Скрыто · Отменить»
даёт безопасное восстановление в коротком окне. Cost: M. Risk: race с reload;
undo должен проверять expected version.

**36. Sticky action rail в длинном контексте** — Приоритет: P1. Rationale:
кнопки управления исчезают ниже order history. Benefit: primary action всегда
доступен в drawer footer. Cost: M. Risk: перекрытие контента; учитывать safe
area и scroll padding.

**37. История действий менеджеров как timeline** — Приоритет: P0. Rationale:
оператору важно знать, кто уже менял state. Benefit: actor/time/action рядом
с order audit сокращают дубли. Cost: M. Risk: PII и объём; пагинировать.

**38. Отдельный payment-evidence popover** — Приоритет: P0. Rationale: зелёный
state должен быть проверяемым без поиска по нескольким секциям. Benefit: сумма,
provider receipt и verifier доступны в одном месте. Cost: M. Risk: секреты;
никогда не показывать токены и полный webhook payload.

**39. Компактная карточка связанного заказа** — Приоритет: P0. Rationale:
несколько order fields сейчас конкурируют за место. Benefit: номер, сумма,
payment и TTN имеют устойчивую иерархию. Cost: M. Risk: скрытие деталей;
вторичный row раскрывается по клику.

**40. Профиль плотности контекста** — Приоритет: P2. Rationale: support и sales
нуждаются в разном объёме facts. Benefit: compact/expanded preference снижает
прокрутку без удаления данных. Cost: M. Risk: расхождение команд; сохранять
только per-user UI preference.

## 5. Overview и операционные метрики

**41. Динамика KPI относительно предыдущего окна** — Приоритет: P1. Rationale:
абсолютные числа не показывают ухудшение. Benefit: маленький delta у replies,
queue и clients объясняет тренд. Cost: M. Risk: ложные выводы на малой выборке;
показывать baseline и размер окна.

**42. Локальное время обновления каждой группы метрик** — Приоритет: P0.
Rationale: статус обновляется live, но его возраст не виден. Benefit: «дані 8 с
тому» помогает отличить stale API от реального нуля. Cost: S. Risk: noise;
одна timestamp line на группу.

**43. Сводный health score только с объяснением** — Приоритет: P1. Rationale:
несколько diagnostics трудно оценить одновременно. Benefit: `Здоров'я: увага`
ссылкой открывает составляющие. Cost: M. Risk: непрозрачная оценка; формулу и
пороговые значения показывать в tooltip.

**44. Переключатель «Метрики / Инциденти»** — Приоритет: P1. Rationale: ошибки и
обычная статистика имеют разные задачи. Benefit: incidents view убирает нулевые
счётчики и оставляет только actionable alerts. Cost: M. Risk: потеря visibility;
badge сохраняет число инцидентов.

**45. Быстрая ссылка из Meta-диагностики в настройки** — Приоритет: P0. Rationale:
предупреждение без next step увеличивает время реакции. Benefit: action ведёт к
точному полю/режиму, сохраняя вкладку. Cost: S. Risk: доступ reviewer-mode;
проверять permissions перед переходом.

**46. Модель Gemini как chip с policy tooltip** — Приоритет: P1. Rationale:
длинное имя модели переносится, но не объясняет источник. Benefit: chip показывает
effective model, alias policy и время последнего успешного вызова. Cost: M. Risk:
внутренние alias names; скрывать секретные key identifiers.

**47. Разделение outbox по retry/manual/unknown** — Приоритет: P0. Rationale:
общее «Сповіщення» не говорит, что делать. Benefit: три компактных числа ведут к
правильной процедуре без ручного чтения логов. Cost: S. Risk: over-alerting;
manual unknown должен иметь самый сильный акцент.

**48. Meta capability в compact status strip** — Приоритет: P0. Rationale:
несколько длинных строк визуально равны, хотя их важность различна. Benefit:
permission/access/delivery идут в фиксированном порядке с severity. Cost: M.
Risk: неправильный вывод из одного probe; сохранять исходные facts.

**49. Фильтры онлайн-консоли по severity и event** — Приоритет: P1. Rationale:
400 строк live-log быстро становятся нечитаемыми. Benefit: manager видит только
errors или shipment events. Cost: M. Risk: скрытая причина; заметный clear-filter
и сохранение полного log на сервере.

**50. Пауза автоскролла консоли при ручной прокрутке** — Приоритет: P0.
Rationale: новый log сейчас может увести оператора от строки, которую он читает.
Benefit: auto-follow отключается до «К последнему». Cost: S. Risk: пропуск новых
событий; показать unread count на кнопке.

## 6. Live-синхронизация

**51. Server-sent events для событий бота** — Приоритет: P1. Rationale: polling
даёт задержку и лишние запросы. Benefit: новые сообщения, state и outbox приходят
сразу. Cost: L. Risk: connection management; fallback на текущий polling.

**52. Optimistic update только для локальных UI preferences** — Приоритет: P1.
Rationale: drawer/filter toggles не должны ждать сети. Benefit: интерфейс ощущается
мгновенным. Cost: S. Risk: расходится между вкладками; rollback при storage error.

**53. Маркер stale при потере refresh** — Приоритет: P0. Rationale: молча старый
список выглядит актуальным. Benefit: amber «Оновлення призупинено» сообщает о
неполном состоянии. Cost: S. Risk: тревога при коротком лаге; debounce 2–3
интервала.

**54. Reconnect countdown с ручным retry** — Приоритет: P0. Rationale: ошибка
polling сейчас требует догадки. Benefit: виден следующий retry и доступна кнопка
немедленного восстановления. Cost: S. Risk: retry storm; применять exponential
backoff и jitter.

**55. Presence indicator менеджеров в текущем клиенте** — Приоритет: P1. Rationale:
два менеджера могут открыть один диалог одновременно. Benefit: видна конкуренция
за работу и активный takeover. Cost: L. Risk: privacy/team policy; только
агрегированный first name и TTL.

**56. Мягкий pulse для нового inbound** — Приоритет: P1. Rationale: badge не
показывает, какая строка изменилась. Benefit: один pulse на row и conversation
header направляет внимание. Cost: S. Risk: flashing; ограничить одной анимацией
и respect reduced motion.

**57. Coalescing частых live-событий** — Приоритет: P0. Rationale: пачка API
updates вызывает layout thrash. Benefit: батчирование за 100–200 ms сохраняет
плавность и уменьшает запросы. Cost: M. Risk: микрозадержка; не коалесцировать
destructive actions.

**58. Центр уведомлений с unread/read state** — Приоритет: P1. Rationale: toast
исчезает, а incident может остаться без владельца. Benefit: история уведомлений
позволяет вернуться к задаче. Cost: L. Risk: второй inbox; хранить только
actionable events и link to source.

**59. Идемпотентные event ids в UI-слое** — Приоритет: P0. Rationale: reconnect
может повторно добавить одну строку или badge. Benefit: dedupe по server event id
делает live-изменения устойчивыми. Cost: M. Risk: память клиента; ограничить
кольцевым буфером.

**60. Онлайн-история изменений клиента** — Приоритет: P1. Rationale: список и
context могут обновляться независимо. Benefit: маленькая timeline marker показывает,
что именно изменилось после открытия карточки. Cost: M. Risk: шум; группировать
однотипные изменения.

## 7. Анимации и micro-interactions

**61. FLIP-переход при reflow списка** — Приоритет: P1. Rationale: фильтр сейчас
переставляет rows скачком. Benefit: 160ms перемещение сохраняет spatial memory.
Cost: M. Risk: конфликт с virtualized list; применять до внедрения virtualization.

**62. Drawer transition с одним направлением** — Приоритет: P1. Rationale:
desktop и mobile должны ощущаться разными режимами. Benefit: mobile slides from
right, desktop fades context width без лишнего bounce. Cost: S. Risk: motion
fatigue; respect reduced-motion.

**63. Анимация rail/chip вместо полной карточки** — Приоритет: P1. Rationale:
полная подсветка выглядит как рекламный сигнал. Benefit: переходит только rail,
border и chip, сохраняя спокойный фон. Cost: S. Risk: недостаточная заметность;
добавить live announcement.

**64. Crossfade для смены значения KPI** — Приоритет: P2. Rationale: цифры live
меняются без контекста. Benefit: 120ms fade помогает заметить обновление без
прыжка layout. Cost: S. Risk: раздражение при частом poll; анимировать только
изменившиеся значения.

**65. Skeleton вместо «—» на initial load** — Приоритет: P1. Rationale: набор
прочерков выглядит как отсутствие данных. Benefit: нейтральный skeleton сообщает,
что запрос ещё идёт. Cost: S. Risk: fake progress; максимум 800ms, дальше честный
unavailable state.

**66. Busy-state внутри action-кнопки** — Приоритет: P0. Rationale: disabled без
объяснения не показывает прогресс POST. Benefit: icon/spinner и сохранённая ширина
предотвращают двойной submit. Cost: S. Risk: зависший spinner; timeout и error
recovery обязательны.

**67. Очередь toast-сообщений с приоритетом** — Приоритет: P1. Rationale: несколько
ответов могут перекрывать друг друга. Benefit: success складываются, errors
останавливаются до подтверждения. Cost: M. Risk: notification overload; лимит
видимых toasts до трёх.

**68. Централизованный reduced-motion режим** — Приоритет: P0. Rationale:
отдельные animation rules легко забывают про accessibility. Benefit: одна policy
отключает pulse, FLIP и drawer transition. Cost: S. Risk: потеря feedback;
оставлять цвет/aria/live signal.

**69. Hover elevation только для интерактивных строк** — Приоритет: P2. Rationale:
сейчас hover transform может конкурировать с state rail. Benefit: тонкий border
highlight различает clickable row без движения всего списка. Cost: S. Risk:
визуальный шум; запретить постоянный box-shadow.

**70. Ясный scroll affordance для длинных панелей** — Приоритет: P1. Rationale:
фиксированная высота conversation/context скрывает продолжение. Benefit: мягкий
fade и «ещё» marker дают сигнал прокрутки. Cost: S. Risk: overlay перекрывает
текст; ставить только на край scroll container.

## 8. Accessibility и responsive UX

**71. Проверка landmark-иерархии** — Приоритет: P0. Rationale: три панели и
несколько `main` требуют ясной структуры для screen reader. Benefit: оператор
быстрее прыгает к list/conversation/context. Cost: S. Risk: дублирующие landmarks;
оставить один page main и labelled regions.

**72. Roving tabindex для всех tablists** — Приоритет: P0. Rationale: вкладки
должны вести себя одинаково на desktop/mobile. Benefit: Arrow/Home/End работают
предсказуемо и уменьшают Tab-путь. Cost: M. Risk: JS regression; contract tests
на selected/focus state.

**73. Severity-aware aria-live** — Приоритет: P0. Rationale: live region не
различает информационный update и ошибку. Benefit: screen reader получает только
важное с корректной politeness. Cost: S. Risk: пропуск incident; errors всегда
assertive, counters polite.

**74. Полный focus audit при открытии/закрытии drawer** — Приоритет: P0.
Rationale: Escape уже проверен, но mouse/touch и nested dialogs могут менять
focus. Benefit: ни один пользователь не теряется в DOM. Cost: M. Risk: focus
trap блокирует assistive tech; тестировать VoiceOver-путь.

**75. Автоматическая проверка контраста коммерческих токенов** — Приоритет: P0.
Rationale: green/violet/amber должны читаться в dark theme. Benefit: CI ловит
недостаточный text/border contrast до production. Cost: S. Risk: false positives
для decorative borders; разные пороги для text и non-text.

**76. Visual regression matrix 320/375/768/1440** — Приоритет: P0. Rationale:
один viewport не ловит tablet breakpoint. Benefit: снимки подтверждают сетку,
overflow, drawer и filter popover. Cost: M. Risk: flaky fonts; фиксировать browser
version и wait for network idle.

**77. Touch target audit** — Приоритет: P0. Rationale: compact controls легко
становятся меньше 44px на телефоне. Benefit: action/filter/close можно нажать без
ошибки. Cost: S. Risk: уменьшение плотности; увеличивать hit area без роста
видимой кнопки.

**78. Тест zoom 200% без горизонтального overflow** — Приоритет: P1. Rationale:
responsive viewport не заменяет text zoom. Benefit: длинные Ukrainian labels
остаются читаемыми. Cost: M. Risk: вертикальная длина; разрешить scroll, но не
обрезать кнопки.

**79. Полная клавиатурная работа disclosure-фильтра** — Приоритет: P0.
Rationale: Escape/outside click уже есть, но focus order нужно закрепить. Benefit:
Enter/Space открывают, стрелки выбирают, focus возвращается. Cost: S. Risk:
конфликт с global shortcuts; scope events к disclosure.

**80. Альтернативный текст для state icons** — Приоритет: P1. Rationale: rail и
точка не объясняются screen reader. Benefit: aria-label повторяет коммерческий
state и urgency. Cost: S. Risk: дублирование visible text; icon-only элементы
должны иметь label, text chips — `aria-hidden` у декора.

## 9. Производительность, надёжность и безопасность

**81. Вынести inline UI script в versioned asset** — Приоритет: P1. Rationale:
большой inline script усложняет cache и CSP. Benefit: browser cache, lint и
source maps улучшают отладку. Cost: L. Risk: template URL/cache drift;
использовать manifest/static versioning.

**82. Виртуализация списка при росте базы** — Приоритет: P2. Rationale: flex-list
сотен клиентов увеличит DOM и scroll cost. Benefit: стабильный FPS при 1k+
clients. Cost: L. Risk: accessibility и anchor complexity; внедрять только после
measurement.

**83. AbortController для устаревших поисковых запросов** — Приоритет: P0.
Rationale: debounce не отменяет уже отправленный request. Benefit: быстрый набор
не даёт старому ответу перезаписать новый список. Cost: S. Risk: abort treated as
error; классифицировать отдельно.

**84. Стабильный memo для render status** — Приоритет: P1. Rationale: polling
перерисовывает неизменившиеся строки и diagnostics. Benefit: меньше DOM work и
visual flicker. Cost: M. Risk: пропустить field; сравнивать explicit schema keys.

**85. Contract lint для API display fields** — Приоритет: P0. Rationale:
frontend зависит от `commercial_visual_state` и runtime labels. Benefit: CI ловит
переименование поля до broken UI. Cost: M. Risk: brittle snapshot; проверять
семантическую схему, не весь JSON.

**86. Ошибка CSRF/403 с recoverable UI** — Приоритет: P0. Rationale: expired
session сейчас может выглядеть как generic action error. Benefit: понятная
«сессія завершена» и link повторного входа. Cost: S. Risk: утечка auth state;
не раскрывать response body.

**87. Permission-aware rendering до запроса данных** — Приоритет: P0.
Rationale: reviewer-mode не должен загружать скрытые secrets/actions. Benefit:
меньше риска и меньше лишнего network traffic. Cost: M. Risk: frontend-only
security; backend authorization остаётся обязательной.

**88. Redacted client-side telemetry** — Приоритет: P1. Rationale: ошибки UI
нужны для улучшения, но username/message нельзя отправлять в analytics. Benefit:
видны JS failures, viewport и action type без PII. Cost: M. Risk: accidental
leak; schema allowlist и automated redaction tests.

**89. Error boundary для каждого live-потока** — Приоритет: P1. Rationale:
ошибка notifications не должна ломать clients. Benefit: изолированные fallback
blocks сохраняют основную работу. Cost: M. Risk: скрытая общая ошибка; показывать
correlation id и retry.

**90. Production migration/static drift gate** — Приоритет: P0. Rationale:
UI-поля и compressed templates должны совпадать с deployed code. Benefit:
release script остановится до несовместимого SHA/static состояния. Cost: S. Risk:
дольше deploy; использовать только deterministic checks.

## 10. Измерение, rollout и дальнейшая модернизация

**91. Метрика времени до первого понятного решения** — Приоритет: P0. Rationale:
визуальный polish ценен только если ускоряет оператора. Benefit: сравнение
baseline/variant по задаче «найти оплаченного клиента». Cost: M. Risk: privacy
и observer effect; измерять агрегаты без transcript.

**92. Счётчик использования advanced filters** — Приоритет: P1. Rationale:
disclosure должен подтверждаться поведением, а не вкусом. Benefit: редко
используемые фильтры можно убрать или объединить. Cost: S. Risk: tracking fatigue;
собирать только filter key и role.

**93. Время от alert до завершённого action** — Приоритет: P0. Rationale:
цвет/animation обязаны вести к закрытию задачи. Benefit: видно, помогает ли
«Потрібна увага» или только тревожит. Cost: M. Risk: неверное связывание событий;
использовать operation id.

**94. Telemetry горизонтального overflow** — Приоритет: P0. Rationale: один
сломанный label может быть незаметен на QA viewport. Benefit: production сигнал
об аномальном `scrollWidth-clientWidth` без содержимого страницы. Cost: S. Risk:
privacy; отправлять только route/viewport/selector allowlist.

**95. Персональные UI preferences с прозрачным reset** — Приоритет: P1.
Rationale: drawer/filter/density preferences полезны, но могут запутать. Benefit:
«Скинути вигляд» возвращает предсказуемый default. Cost: S. Risk: потеря удобных
настроек; reset только UI, не business state.

**96. Baseline visual snapshots перед каждым релизом** — Приоритет: P0.
Rationale: CSS-срезы часто ломают соседнюю вкладку. Benefit: diff desktop,
tablet, mobile блокирует регрессию до deploy. Cost: M. Risk: noisy snapshots;
mask timestamps and dynamic counters.

**97. Синтетические fixtures для paid/shipped/attention** — Приоритет: P0.
Rationale: production нельзя загрязнять тестовыми Meta-событиями. Benefit:
локальная QA всегда воспроизводит коммерческую иерархию. Cost: M. Risk: fixture
drift; сверять с backend serializer tests.

**98. Регрессия precedence в одном matrix-тесте** — Приоритет: P0. Rationale:
цвета зависят от нескольких facts и легко меняются случайно. Benefit: matrix
проверяет paid, TTN, done, pending и Direct error отдельно. Cost: S. Risk:
смешение business/UI; тестировать только presentation field.

**99. Feature flag для крупных интерактивных изменений** — Приоритет: P1.
Rationale: SSE, palette и virtualization имеют больший blast radius. Benefit:
поэтапный rollout по manager role и мгновенный rollback. Cost: M. Risk: забытый
старый branch; прописать expiry date для каждого flag.

**100. Ежеквартальный design review с удалением невостребованного** — Приоритет:
P1. Rationale: dashboard постепенно накапливает controls и исключения.
Benefit: usage data превращается в упрощённые решения, а не в бесконечный слой
UI. Cost: S. Risk: субъективность; принимать решение по telemetry, support-
инцидентам и accessibility evidence.

## Рекомендуемый порядок выбора

Сначала брать P0, которые сокращают ошибку или время реакции: 2, 3, 4, 5, 8,
12, 15, 17, 20, 22, 23, 27, 30, 32–34, 37–39, 42, 45, 47, 49–50, 53–54,
57, 59, 66, 68, 71–77, 79, 83, 85–87, 90, 91, 93–94, 96–98. После измерения
эффекта выбирать P1, а P2 внедрять только если telemetry подтверждает реальную
потребность. Ни один пункт из этого документа не должен обходить backend truth,
permission checks, idempotency или безопасный production deploy.
