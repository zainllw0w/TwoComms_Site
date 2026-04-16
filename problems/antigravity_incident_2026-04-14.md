# Antigravity: разбор поломок, причин и восстановление

Дата инцидента: 2026-04-14
Рабочая папка проекта: `/Users/zainllw0w/TwoComms/site`
Цель документа: зафиксировать, что именно ломалось в Antigravity, почему это происходило, как это диагностировали, что именно было исправлено, и как следующему агенту быстро пройти тот же путь без повторного хаотичного дебага.

## Что именно ломалось

На этой машине было несколько связанных, но не одинаковых проблем Antigravity:

1. Antigravity не видел Python.
2. MCP `sequential-thinking` не стартовал.
3. Сообщение в чате визуально добавлялось в UI, но ответ не приходил, как будто запрос не отправлялся.
4. В некоторых состояниях Antigravity открывал чат, начинал работу с backend, но дальше зависал на внутренней подготовке контекста или восстановлении старой траектории чата.

Это были не одна и та же ошибка, а цепочка локальных поломок в окружении, state-файлах Antigravity и его несовместимости с частью локальной Git-конфигурации.

## Короткий итог

Финально были найдены и обработаны следующие реальные причины:

1. Неправильный запуск `sequential-thinking` из GUI-окружения Antigravity.
2. Битые Python env tools (`pet`) внутри расширений Antigravity.
3. Отсутствие стабильной команды `python` в shell-окружении Antigravity.
4. Несовместимость Antigravity language server с `extensions.worktreeConfig` в локальном `.git/config`.
5. Битый workspace state с путями `.../TwoComms/SITE/...` вместо `.../TwoComms/site`.
6. Падение на попытке построить patch по локальной директории `.claude/worktrees/...`.
7. Раздутый локальный state `antigravityUnifiedStateSync.trajectorySummaries`, из-за которого Antigravity начинал биться о truncation на refresh старой траектории.

После зачистки этих пунктов свежий запуск Antigravity больше не показывал:

- `core.repositoryformatversion does not support extension: worktreeconfig`
- `workspace infos is nil`
- `failed to create patch for untracked file`
- `invalid document ... isn't relative to ...`
- `could not convert a single message before hitting truncation`

## Важное различие: что было корнем, а что было шумом

В логах Antigravity есть сообщения, которые повторяются почти всегда и не являются доказанным корнем именно этой поломки:

- `Hre depends on UNKNOWN service agentSessions`
- `Menu item references a command ... which is not defined in the 'commands' section`
- предупреждения про API proposals у Python extension
- предупреждения про `punycode`

Эти строки видны и в старых сессиях, включая те, где `streamGenerateContent` реально вызывался. Поэтому их нельзя автоматически считать главной причиной молчания чата.

Реальными блокерами здесь были другие ошибки, перечисленные ниже.

## Симптомы и их смысл

### Симптом 1: Python не определяется

Практический эффект:

- Antigravity не понимал локальный Python interpreter.
- Python-related tooling и часть агентного поведения не могли опереться на окружение проекта.

Реальная причина:

- В расширениях Antigravity для Python отсутствовал рабочий `pet` бинарник, который ищет и валидирует Python-окружения.
- В логах была ошибка `ENOENT` на запуск `.../python-env-tools/bin/pet`.

### Симптом 2: `sequential-thinking` не работает

Практический эффект:

- MCP сервер либо не стартовал, либо падал до инициализации.

Реальная причина:

- В `~/.gemini/antigravity/mcp_config.json` использовался запуск через голый `npx` без надёжного `PATH`.
- В GUI-окружении Antigravity это приводило к ситуации, когда сначала не находился `npx`, а при некоторых вариантах поведения не находился и `node`.

### Симптом 3: сообщение в чате есть, но ответа нет

Практический эффект:

- Пользователь отправляет запрос.
- Сообщение визуально появляется в чате.
- Ответ не начинает рисоваться.
- Создаётся впечатление, что кнопка отправки не работает.

Это был самый коварный симптом, потому что он возникал из разных причин на разных стадиях.

Сначала казалось, что запрос "не отправляется".
По логам выяснилось, что на самом деле было несколько режимов сбоя:

1. Antigravity вообще ломал workspace context ещё до нормального построения запроса.
2. Затем он уже умел доходить до `streamGenerateContent`, но падал на подготовке repo context.
3. Затем он уже уходил в backend, но ломался на refresh старой chat trajectory.

То есть визуально симптом один, а корни у него были разные.

## Хронология и что было найдено по логам

### Сессия `20260414T175657`

Это был ключевой лог, где впервые удалось зафиксировать настоящий блокер отправки.

Файл:

- `~/Library/Application Support/Antigravity/logs/20260414T175657/ls-main.log`

Ключевые ошибки:

- `core.repositoryformatversion does not support extension: worktreeconfig`
- `Failed to resolve workspace infos`
- `workspace infos is nil`
- `invalid document: /Users/zainllw0w/TwoComms/SITE/... isn't relative to /Users/zainllw0w/TwoComms/site`

Смысл:

- Antigravity не мог корректно разобрать Git/Workspace метаданные.
- Из-за этого не строился `workspace infos`.
- Без `workspace infos` ломалась часть внутреннего pipeline, связанная с очередями и контекстом чата.
- Отдельно старый state с путями `SITE/...` добивал refresh контекста.

### Сессия `20260414T180903`

После первой частичной правки окно было перезагружено, но проблема вернулась.

Файл:

- `~/Library/Application Support/Antigravity/logs/20260414T180903/ls-main.log`

Ключевые ошибки:

- `core.repositoryformatversion does not support extension: worktreeconfig`
- `workspace infos is nil`

Вывод:

- Поднятие `repositoryformatversion` до `1` само по себе не было достаточным фиксoм.
- Проблема была не просто в номере формата, а в самом наличии `extensions.worktreeConfig`, которое Antigravity language server интерпретировал некорректно.

### Сессия `20260414T181237`

После удаления `extensions.worktreeConfig` и полного рестарта Antigravity стало лучше:

- ошибки `worktreeconfig` исчезли;
- `workspace infos is nil` исчез;
- `invalid document ... isn't relative ...` исчез.

Но всплыла следующая проблема:

- `failed to create patch for untracked file .claude/worktrees/admiring-johnson/: read ... is a directory`

Смысл:

- Antigravity пытался включить `.claude/worktrees/...` в repo context как untracked-изменение.
- Но там не файл, а директория / вспомогательная локальная структура.
- На этом шаге построение контекста ломалось.

Также в этой же стадии уже было видно, что запросы реально уходят в backend:

- в `ls-main.log` появились вызовы `streamGenerateContent?alt=sse`

Это очень важный факт:

- кнопка отправки и сеть уже не были проблемой;
- ломался именно локальный контекст / pipeline вокруг запроса.

### Сессия `20260414T181450`

После локального исключения `.claude/worktrees/` через `.git/info/exclude` ошибка с patch исчезла.

Но дальше появилась новая ошибка:

- `Failed to set trajectory start index for sync refresh: could not convert a single message before hitting truncation`
- `Failed to set trajectory start index for async refresh: could not convert a single message before hitting truncation`

Смысл:

- Antigravity уже запрашивал генерацию у backend;
- но при синхронизации / обновлении локальной траектории чата упирался в сломанный или слишком тяжёлый summary state;
- визуально это снова выглядело как "чат молчит".

### Сессия `20260414T181917`

После очистки `antigravityUnifiedStateSync.trajectorySummaries` и полного рестарта Antigravity старт стал чистым.

В свежем `ls-main.log` больше не было:

- `worktreeconfig`
- `workspace infos is nil`
- `failed to create patch for untracked file`
- `could not convert a single message before hitting truncation`

Это был первый по-настоящему чистый старт после серии локальных исправлений.

## Корневые причины и как они были исправлены

## 1. `sequential-thinking` в Antigravity не стартовал из GUI-окружения

### Причина

Antigravity стартует MCP не из того же окружения, что интерактивный shell пользователя. Если в конфиге стоит просто `npx`, GUI-процесс может не унаследовать нужный `PATH`.

### Где было сломано

- `~/.gemini/antigravity/mcp_config.json`

### Что было сделано

- запуск `sequential-thinking` переведён на абсолютный путь к `npx` из NVM;
- прописан явный `PATH`;
- добавлены `transport: "stdio"` и `autoAllow: true`.

### Почему это помогает

Так Antigravity больше не зависит от того, подхватился ли shell login/profile и какой именно `PATH` видит GUI.

## 2. Python env tools были сломаны внутри расширений

### Причина

Python-расширения Antigravity использовали `pet` для поиска Python-окружений, но у расширения отсутствовал рабочий бинарник, либо лежал не тот артефакт.

### Где было сломано

- `~/.antigravity/extensions/ms-python.python-2026.4.0-universal/python-env-tools/bin/pet`
- `~/.antigravity/extensions/ms-python.vscode-python-envs-1.20.1-universal/python-env-tools/bin/pet`

### Что было сделано

- восстановлены нативные `darwin-arm64` `pet` бинарники в оба каталога.

### Почему это помогает

Antigravity снова может корректно находить локальные Python interpreters и `.venv`.

## 3. В Antigravity не было надёжной команды `python`

### Причина

На машине был рабочий `python3`, но не везде был доступен `python`. Некоторые части Antigravity и tooling полагаются на наличие `python`.

### Что было сделано

- добавлен shim:
  - `~/.antigravity/antigravity/bin/python`
- обновлены shell-конфиги:
  - `~/.zshrc`
  - `~/.zprofile`

### Почему это помогает

GUI и shell-процессы Antigravity теперь стабильно видят `python`, а не только `python3`.

## 4. Несовместимость Antigravity с `extensions.worktreeConfig`

### Симптом

- `core.repositoryformatversion does not support extension: worktreeconfig`
- `workspace infos is nil`

### Настоящая причина

Git-репозиторий использовал `extensions.worktreeConfig = true`, но Antigravity language server некорректно переваривал эту комбинацию и ломал разбор workspace.

Изначально была промежуточная гипотеза:

- повысить `core.repositoryformatversion` до `1`

Это дало полезную информацию, но не решило проблему надёжно. После перезагрузки ошибка всё равно возвращалась.

### Окончательное исправление

В локальном `.git/config` было сделано следующее:

- убрать `extensions.worktreeConfig`;
- вернуть `core.repositoryformatversion = 0`;
- перенести нужную настройку `core.longpaths = true` в общий `.git/config`.

Итоговое рабочее состояние:

```ini
[core]
    repositoryformatversion = 0
    longpaths = true
```

При этом локальный worktree продолжил работать.

### Почему это помогает

Мы не заставляем Antigravity понимать функцию Git, с которой он не справляется. Вместо этого убираем несовместимую extension-настройку и переносим реально нужное поведение в основной config.

## 5. Битый workspace state с `SITE/...` вместо `site/...`

### Симптом

- `invalid document: /Users/zainllw0w/TwoComms/SITE/... isn't relative to /Users/zainllw0w/TwoComms/site`

### Причина

На macOS файловая система обычно case-insensitive, поэтому физически путь работает и с `SITE`, и с `site`. Но Antigravity сравнивал строки путей буквально и считал их разными workspace roots.

### Где это жило

- `~/Library/Application Support/Antigravity/User/workspaceStorage/85c83a9219527aa0e5fa97c3baa01f2f/state.vscdb`
- `~/Library/Application Support/Antigravity/User/History/7b542c38/entries.json`

### Что было сделано

- сделаны бэкапы state-файлов;
- все вхождения `.../TwoComms/SITE/` заменены на `.../TwoComms/site/`.

### Почему это помогает

Antigravity перестаёт считать активный документ "не относящимся" к текущему workspace.

## 6. Antigravity ломался на `.claude/worktrees/...`

### Симптом

- `failed to create patch for untracked file .claude/worktrees/admiring-johnson/: ... is a directory`

### Причина

Внутри проекта есть локальная вспомогательная директория `.claude/worktrees/...`, которую Git видел как untracked path. Antigravity пытался обработать её как patchable change и ломался на том, что это директория, а не файл.

### Что было сделано

В локальный файл:

- `/Users/zainllw0w/TwoComms/site/.git/info/exclude`

добавлено:

```gitignore
.claude/worktrees/
```

### Почему это помогает

Это локальное исключение только для этой машины. Оно не меняет репозиторий для остальных, но убирает мусор из видимости Antigravity при построении repo context.

## 7. Раздутый `trajectorySummaries` ломал refresh старого чата

### Симптом

- `Failed to set trajectory start index ... could not convert a single message before hitting truncation`

### Причина

В глобальном state Antigravity был большой ключ:

- `antigravityUnifiedStateSync.trajectorySummaries`

Его длина на момент инцидента была около `101960` символов/байтов представления в storage.

Когда Antigravity пытался восстановить или обновить старую траекторию чата, он упирался в truncation и ломал refresh.

### Где это жило

- `~/Library/Application Support/Antigravity/User/globalStorage/state.vscdb`

### Что было сделано

- сделан бэкап базы;
- удалён только ключ `antigravityUnifiedStateSync.trajectorySummaries`.

### Почему это помогает

Мы не сносим весь пользовательский state Antigravity, а убираем только сломанную summary-траекторию, которая мешала восстановлению чатов.

## Какие файлы и state были изменены

Ниже список локальных изменений, сделанных не в коде проекта, а в окружении/состоянии Antigravity.

### Конфиги и окружение

- `~/.gemini/antigravity/mcp_config.json`
- `~/.zshrc`
- `~/.zprofile`
- `~/.antigravity/antigravity/bin/python`
- `~/.antigravity/extensions/ms-python.python-2026.4.0-universal/python-env-tools/bin/pet`
- `~/.antigravity/extensions/ms-python.vscode-python-envs-1.20.1-universal/python-env-tools/bin/pet`

### Локальные файлы репозитория

- `/Users/zainllw0w/TwoComms/site/.git/config`
- `/Users/zainllw0w/TwoComms/site/.git/info/exclude`

### State Antigravity

- `~/Library/Application Support/Antigravity/User/workspaceStorage/85c83a9219527aa0e5fa97c3baa01f2f/state.vscdb`
- `~/Library/Application Support/Antigravity/User/History/7b542c38/entries.json`
- `~/Library/Application Support/Antigravity/User/globalStorage/state.vscdb`

## Какие бэкапы были созданы

Перед правками создавались локальные бэкапы, чтобы можно было откатить изменение state вручную.

Из известных:

- `/Users/zainllw0w/TwoComms/site/.git/config.bak-antigravity-20260414-180456`
- `/Users/zainllw0w/TwoComms/site/.git/config.bak-antigravity-20260414-1812`
- `~/Library/Application Support/Antigravity/User/workspaceStorage/85c83a9219527aa0e5fa97c3baa01f2f/state.vscdb.bak-antigravity-20260414-180456`
- `~/Library/Application Support/Antigravity/User/History/7b542c38/entries.json.bak-antigravity-20260414-180456`
- `~/Library/Application Support/Antigravity/User/globalStorage/state.vscdb.bak-antigravity-20260414-1819`

## Как это проверялось

Проверки были не "на глаз", а по факту логов и системного состояния.

### Проверка Python

- `pet find -l -w .` находил `.venv/bin/python`
- `python -V` и `python3 -V` стали доступны в окружении Antigravity

### Проверка MCP

- `sequential-thinking` стартовал через `stdio` без падения на `npx/node`

### Проверка Git / worktree

- `git status --short --branch` работает
- `git worktree list --porcelain` работает
- локальный worktree не сломался

### Проверка state

- в текущем workspace-state больше нет путей `.../TwoComms/SITE/...`
- `.claude/worktrees/...` перестал появляться в `git status`

### Проверка логов Antigravity

На чистом запуске `20260414T181917` больше нет:

- `worktreeconfig`
- `workspace infos is nil`
- `failed to create patch for untracked file`
- `hitting truncation`

## Что делать другому ИИ-агенту, если проблема повторится

Ниже краткий playbook без лишнего гадания.

### Шаг 1. Сразу определить тип поломки

Сначала понять, что именно происходит:

- Python не определяется?
- MCP не стартует?
- Чат визуально молчит?
- Ответ не приходит только в старом треде или и в новом чате тоже?

Это важно, потому что разные симптомы здесь уже были вызваны разными причинами.

### Шаг 2. Открыть самый свежий каталог логов

Идти сюда:

- `~/Library/Application Support/Antigravity/logs`

Внутри смотреть самый свежий каталог вида:

- `20260414T181917`

Главные файлы:

- `ls-main.log`
- `window1/exthost/google.antigravity/Antigravity.log`
- `window1/renderer.log`
- `window1/exthost/exthost.log`

### Шаг 3. Искать сигнатуры, а не просто "error"

#### Если видишь:

```text
core.repositoryformatversion does not support extension: worktreeconfig
workspace infos is nil
```

Проверить локальный `.git/config`.

Ожидаемое безопасное состояние:

- нет `extensions.worktreeConfig`
- `core.repositoryformatversion = 0`
- при необходимости есть `core.longpaths = true`

#### Если видишь:

```text
invalid document ... isn't relative to /Users/.../site
```

Искать case mismatch в state:

- `workspaceStorage/.../state.vscdb`
- `User/History/.../entries.json`

#### Если видишь:

```text
failed to create patch for untracked file ... is a directory
```

Проверить локальные untracked-папки, особенно:

- `.claude/worktrees/`

И при необходимости добавить в:

- `.git/info/exclude`

#### Если видишь:

```text
could not convert a single message before hitting truncation
```

Проверить и, при необходимости, локально сбросить ключ:

- `antigravityUnifiedStateSync.trajectorySummaries`

в:

- `~/Library/Application Support/Antigravity/User/globalStorage/state.vscdb`

#### Если Python не виден

Проверить:

- наличие `pet` в обоих Python extension каталогах;
- доступность `python` в GUI/shell окружении Antigravity.

#### Если MCP не стартует

Проверить:

- `~/.gemini/antigravity/mcp_config.json`
- абсолютный путь к `npx`
- явный `PATH`
- `transport: "stdio"`

### Шаг 4. Перед правкой state всегда делать бэкап

Минимум:

```sh
cp "<original>" "<original>.bak-antigravity-YYYYMMDD-HHMM"
```

Нельзя редактировать `state.vscdb` или `entries.json` без бэкапа.

### Шаг 5. После локальных правок делать полный рестарт Antigravity

Не ограничиваться частичным reload, если менялись:

- `.git/config`
- state базы Antigravity
- глобальный storage

Лучше:

1. полностью закрыть Antigravity
2. открыть заново
3. смотреть новый каталог логов, а не старый

### Шаг 6. Проверять новый чат отдельно от старого

Если старый чат был испорчен trajectory-state, то даже после исправления системных причин старый тред может вести себя странно.

Поэтому всегда проверять:

1. новый чистый чат;
2. короткий тестовый запрос;
3. появляются ли новые строки `streamGenerateContent?alt=sse`;
4. появляются ли новые ошибки после попытки отправки.

## Что было промежуточной, но не финальной гипотезой

Важно не повторять это как "готовый фикс":

### Гипотеза: достаточно поставить `repositoryformatversion = 1`

Это был полезный диагностический шаг, но не финальное решение.

Почему:

- после reload Antigravity всё равно продолжал падать на `worktreeconfig`;
- финально помогло именно удаление `extensions.worktreeConfig`, а не просто изменение номера формата.

## Остаточный шум, который не надо автоматически считать корнем

Если снова увидишь в `renderer.log`:

- `Hre depends on UNKNOWN service agentSessions`

это надо учитывать, но не считать автоматическим доказательством корня, пока не подтверждено, что:

- в свежем `ls-main.log` нет других реальных блокеров;
- запросы не доходят до `streamGenerateContent`;
- не ломается repo context;
- не ломается trajectory refresh.

На этой машине этот `agentSessions`-шум повторялся и в старых логах, и в новых, даже когда более тяжёлые реальные проблемы уже были убраны.

## Почему вообще это всё произошло

Причина не одна. Здесь совпали несколько факторов:

1. Antigravity чувствителен к GUI-окружению и не всегда видит тот же `PATH`, что shell.
2. Antigravity language server оказался несовместим с частью локальной Git-конфигурации, хотя сам Git репозиторий работал.
3. Antigravity хранит довольно агрессивный локальный state в SQLite/JSON, который со временем может становиться неконсистентным.
4. На macOS case-insensitive filesystem скрывает проблему пути, которую само приложение потом видит как конфликт.
5. В проекте есть локальные вспомогательные директории, которые не должны попадать в контекст репо для Antigravity.
6. Старые chat trajectory summaries могут разрастаться и ломать refresh.

Именно из-за комбинации этих факторов визуально казалось, что "ничего не отправляется", хотя на разных этапах реально ломались разные части цепочки.

## Практическое правило на будущее

Если Antigravity снова "молчит", нельзя сразу делать вывод, что:

- не работает кнопка отправки;
- умер backend;
- умера модель;
- снова сломался Python;
- снова сломался MCP.

Нужно идти по слоям:

1. GUI / renderer
2. `ls-main.log`
3. repo context
4. workspace state
5. trajectory state
6. только потом уже backend / network

Искать нужно не абстрактные `error`, а конкретные сигнатуры из этого документа.

## Самая короткая версия для следующего агента

Если это повторяется, сначала проверь по порядку:

1. `~/.gemini/antigravity/mcp_config.json`
2. наличие `pet` в Python extensions
3. наличие `python` в окружении Antigravity
4. `/Users/zainllw0w/TwoComms/site/.git/config`
5. `/Users/zainllw0w/TwoComms/site/.git/info/exclude`
6. `workspaceStorage/.../state.vscdb` на `SITE` vs `site`
7. `User/History/.../entries.json` на `SITE` vs `site`
8. `User/globalStorage/state.vscdb` на ключ `antigravityUnifiedStateSync.trajectorySummaries`
9. новый запуск Antigravity
10. новый чистый чат, а не старый тред

Если в новом чистом запуске нет:

- `worktreeconfig`
- `workspace infos is nil`
- `failed to create patch for untracked file`
- `hitting truncation`

то основная локальная инфраструктурная поломка уже убрана, и дальше надо разбирать только живой UI/session-баг по свежим логам именно этого нового запуска.
