# SDD - Specification-Driven Development

## Принцип

Спека → Код. Код без спеки = откат. Спека — источник правды.

**Приоритет:** technical.md (approved/committed) > narrative.md. Нарративная спека — набросок и рассуждения для построения технической. Техническая спека — единственный источник правды для реализации.

---

## Структура файлов

```
specs/
├── SPEC_INDEX.md
├── core/
│   ├── <component>.narrative.md    # От Человека
│   ├── <component>.technical.md    # От ИИ
│   └── ...
├── <domain>/
└── ...

tests/spec/
├── core/
│   └── test_<component>_spec.py
├── <domain>/
└── ...
```

---

## Шаблон: narrative.md

```markdown
# [Название]

## Intent
[Свободное нарративное описание от Человека]

## Clarifications
Q1: [Вопрос от ИИ]
A1: [Ответ от Человека]

Status: open  # (open | resolved)
```

Status:
- open — есть неотвеченные вопросы
- resolved — все вопросы закрыты

---

## Шаблон: technical.md

```markdown
# [Название]

Narrative-Hash: [md5 полного файла narrative.md]
Status: draft  # (draft | approved | committed)

## State
[Атрибуты с типами]

## Methods
[Сигнатуры методов]

## Invariants
[Условия всегда истинны]

## Formulas
[Формулы]

## Test Cases
[GIVEN/WHEN/THEN]
```

Status:
- draft — ИИ пишет, Человек проверяет
- approved — Человек одобрил, можно реализовать
- committed — Реализация закоммичена, спека актуальна

---

## Workflow 1: Новая спека (полный цикл)

### Шаг 0: Проверка существования (ОБЯЗАТЕЛЬНО)

```bash
# Перед созданием ЛЮБОГО файла спеки:
ls specs/**/<component>*.md

# Если файлы существуют — НЕ СОЗДАВАТЬ НОВЫЕ
# Если narrative.md есть — работать с существующим
# Если technical.md есть — проверить Status
```

### Шаг 1: Человек создает narrative.md
```bash
# Человек создает specs/<domain>/<component>.narrative.md
# Заполняет Intent
# Status: open
```

### Шаг 2: ИИ задает вопросы
ИИ читает Intent, добавляет вопросы в Clarifications.

**Важно:** Количество итераций Q/A неограничено. ИИ продолжает задавать вопросы пока есть неясности. Чем точнее разобрался — тем лучше technical.md.

### Шаг 3: Человек отвечает
Человек пишет ответы A1, A2...
Когда все вопросы закрыты — ИИ меняет Status: resolved

### Шаг 4: ИИ создает technical.md
```bash
# ИИ вычисляет хэш
md5sum specs/<domain>/<component>.narrative.md

# ИИ создает specs/<domain>/<component>.technical.md
# Narrative-Hash: [хэш]
# Status: draft
# Заполняет State, Methods, Invariants, Formulas, Test Cases
```

### Шаг 5: Человек проверяет и апрувит
Человек читает technical.md.
Если ОК: меняет Status: approved

### Шаг 6: ИИ реализует (может быть в новом чате)
```bash
# Команда: "Примени изменения из <component>.technical.md"

# ИИ проверяет:
# 1. Status: approved (если draft - стоп)
# 2. Status: committed (если committed - стоп, уже реализовано)
# 3. git diff HEAD specs/<domain>/<component>.technical.md
#    Если нет diff (файл новый) → читаю всю technical.md

# ИИ применяет:
# 1. Создает/изменяет код в src/
# 2. Создает tests/spec/<domain>/test_<component>_spec.py
# 3. Запускает тесты
# 4. Коммит: [<component>] initial implementation
#    → Pre-commit hook автоматически обновляет Status: committed
```

---

## Workflow 2: Изменение спеки

### Шаг 1: Человек меняет narrative.md
```bash
# Человек редактирует specs/<domain>/<component>.narrative.md
# Хэш изменился
```

### Шаг 2: Pre-commit блокирует
```bash
git commit -m "update"
# ERROR: Hash mismatch for <component>
#   Stored:  573d12c...
#   Current: a1b2c3d...
```

### Шаг 3: ИИ обновляет technical.md
```bash
# Команда: "Обнови technical.md для <component>"

# ИИ:
md5sum specs/<domain>/<component>.narrative.md  # новый хэш
# Обновляет Narrative-Hash в technical.md
# Status: draft (сброс с committed/approved)
# Обновляет секции State/Methods/Formulas если нужно
```

### Шаг 4: Человек проверяет
Человек читает изменения в technical.md.
Если ОК: Status: approved

### Шаг 5: ИИ применяет изменения (может быть в новом чате)
```bash
# Команда: "Примени изменения из <component>.technical.md"

# ИИ проверяет:
# 1. Status: approved (если draft - стоп)
# 2. git diff HEAD specs/<domain>/<component>.technical.md
#    Если есть diff → читаю только изменения из diff

# ИИ применяет:
# 1. Применяет diff к коду (только изменённые методы/формулы)
# 2. Обновляет тесты
# 3. Запускает тесты
# 4. Коммит: [<component>] <description>
#    → Pre-commit hook автоматически обновляет Status: committed
```

---

## Workflow 3: Onboarding существующего модуля

Для модулей, написанных до внедрения SDD. Цель — завести существующий код под контроль спеки, чтобы дальнейшие изменения шли через стандартный цикл.

### Отличия от Workflow 1

| | Workflow 1 (новый код) | Workflow 3 (onboarding) |
|---|---|---|
| Narrative Intent | "что хочу построить" | "что построено и зачем" |
| Clarifications | уточняют требования | уточняют намерения за существующим кодом |
| Technical | контракт до кода | контракт из кода (baseline) |
| Реализация (Шаг 6) | писать код | писать тесты + применить diff к коду |

### Шаг 1: Человек создаёт narrative.md
```bash
# Человек описывает назначение модуля, бизнес-контекст, ограничения
# Intent: "что модуль делает и зачем" (не "что хочу")
# Status: open
```

### Шаг 2: ИИ читает код и задаёт вопросы
ИИ читает существующий код модуля и добавляет вопросы в Clarifications:
- "Правильно ли я понимаю, что X делает Y?"
- "Это намеренное поведение или костыль?"
- "Значение Z — бизнес-требование или произвольный выбор?"
- "В коде есть X, но в narrative не упомянуто — это scope спеки?"

### Шаг 3: Человек отвечает
Ответы фиксируют что является контрактом, а что — случайностью реализации.
Когда все вопросы закрыты — Status: resolved

### Шаг 4: ИИ генерирует technical.md из кода
```bash
md5sum specs/<domain>/<component>.narrative.md

# ИИ создаёт technical.md:
# - State, Methods — из существующего кода
# - Invariants — из поведения кода + ответов на вопросы
# - Formulas — из бизнес-логики в коде
# - Test Cases — покрывают текущее поведение
# - Narrative-Hash: [хэш]
# - Status: draft
```

**Важно:** technical.md фиксирует **целевой контракт**, не текущие баги. Если в ответах на вопросы выявлены расхождения кода с намерением — technical описывает правильное поведение, а diff при реализации исправит код.

### Шаг 5: Человек проверяет и апрувит
Человек проверяет: "да, это контракт модуля". Status: approved

### Шаг 6: ИИ реализует
```bash
# ИИ:
# 1. Создаёт tests/spec/<domain>/test_<component>_spec.py
# 2. Запускает тесты
# 3. Если тесты падают — код расходится с контрактом → исправляет код
# 4. Коммит: [<component>] onboard to SDD
#    → Pre-commit hook обновляет Status: committed
```

После onboarding модуль под SDD. Дальнейшие изменения — через Workflow 2.

---

## Workflow 4: Обратное обновление спеки (implementation feedback)

Когда при реализации выясняется, что спека содержит неточность (например, API фреймворка работает иначе, чем описано в invariant), спека обновляется.

### Когда применять

- Фреймворк/библиотека работает иначе, чем описано в Invariants
- Обнаружен edge case, не покрытый Test Cases
- Формула в Formulas оказалась неточной
- Сигнатура метода требует изменений из-за ограничений платформы

### Когда НЕ применять

- "Мне так удобнее" — не причина менять спеку
- Оптимизация реализации — если контракт не нарушен, спека не меняется
- Добавление фич — это Workflow 2, а не обратное обновление

### Процесс

```bash
# 1. ИИ обнаруживает расхождение при реализации
# 2. ИИ фиксирует расхождение: что в спеке vs что на самом деле
# 3. ИИ обновляет technical.md:
#    - Исправляет конкретный invariant/formula/test case
#    - НЕ меняет Status (остаётся committed)
#    - НЕ меняет Narrative-Hash (narrative не изменился)
#    - Добавляет комментарий: "Updated: <что и почему>"
# 4. Коммит: [<component>] fix spec: <описание>
```

### Правило

Реализация, обоснованно отклоняющаяся от спеки → спека обновляется в том же коммите. Не должно быть ситуации, когда код работает правильно, а спека описывает другое поведение.

---

## Pre-commit hook

Выполняет при каждом коммите:

```bash
# 1. Auto-update статуса (approved → committed)
#    Если в коммите есть код/тесты для спеки со статусом approved:
#    → Автоматически обновляет Status: committed
#    → Добавляет technical.md в staging
#    Это гарантирует атомарность: код и статус в одном коммите

# 2. Валидация хэшей
#    Для каждой technical.md с Status: approved или committed:
#    Хэш narrative.md == Narrative-Hash → OK / ERROR

# 3. Spec-тесты запускаются отдельным hook (pytest-check)

# Блокирует коммит если ERROR
```

Скрипт: `hooks/sdd_validator.py`

---

## SPEC_INDEX.md

```
[component] -> [dependency]     # использует
[component] <- [dependent]      # используется

Пример:
user_auth -> database, session_store
user_auth <- api_gateway, admin_panel
```

---

## TODO.md — Backlog для новых спек

При работе над спекой часто всплывают требования к другим модулям. Чтобы не терять их:

1. Если в Clarifications появляется упоминание другой спеки — записать в `specs/TODO.md`
2. Формат записи: `- [ ] <component>: <краткое описание из контекста>`
3. TODO.md — это backlog, не обязательство. Приоритеты расставляет Человек.

---

## Быстрый старт в новом чате

### Человек пишет:
"Примени изменения из <component>.technical.md"

### ИИ делает:
1. Читает CLAUDE.md (если есть) - инструкции проекта
2. Читает specs/<domain>/<component>.technical.md
3. Проверяет Status:
   - draft → стоп, Человек не одобрил
   - approved → реализуем
   - committed → стоп, уже реализовано
4. Проверяет хэш
5. `git diff HEAD specs/<domain>/<component>.technical.md`
   - Нет diff → новая спека, читаю всю
   - Есть diff → читаю только изменения
6. Применяет к коду
7. Создает/обновляет тесты
8. Запускает тесты
9. Коммит: код + тесты (Status обновится автоматически через pre-commit hook)

---

## Статусы и переходы

### narrative.md
```
open ←→ resolved
```

### technical.md
```
draft → approved → committed
  ↑         ↑
  └─────────┘  (при изменении narrative)

blocked ←→ draft  (при зависимости от другой спеки)
```

Status:

- draft — ИИ пишет, Человек проверяет
- approved — Человек одобрил, можно реализовать
- committed — Реализация закоммичена
- blocked — Реализация заблокирована зависимостью от другой спеки

При изменении narrative.md:
- committed → draft
- approved → draft

---

## Команды

```bash
# Вычислить хэш
md5sum specs/<domain>/<component>.narrative.md

# Проверить diff
git diff HEAD specs/<domain>/<component>.technical.md

# Запустить тесты
pytest tests/spec/<domain>/ -v

# Коммит (проверяется pre-commit hook)
git commit -m "[<component>] description"
```

---

## Проверка в новом чате

После реализации ИИ должен:

1. Показать git log последнего коммита
2. Показать git diff (что изменилось)
3. Показать количество тестов и их статус
4. Подтвердить Status: committed в technical.md

Пример:
```
Реализация завершена:
- Коммит: ca8072f [user_auth] add password validation
- Изменено: auth.py (строки 42, 87)
- Создано: test_user_auth_spec.py (156 строк)
- Тесты: 8/8 passed
- Status: committed
```
