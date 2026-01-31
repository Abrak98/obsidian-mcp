# MCP Server

## Intent

MCP (Model Context Protocol) сервер для ClaudeDesktop. Оборачивает Operations в MCP tools, которые ClaudeDesktop вызывает напрямую — без shell, без WSL, без CLI.

Транспорт: stdio (stdin/stdout JSON-RPC). ClaudeDesktop запускает процесс и общается через stdin/stdout.

### Tools (1:1 с Operations):

1. **read_note(name)** — прочитать полный текст заметки (frontmatter + body)
2. **create_note(name, content?, frontmatter?)** — создать заметку
3. **append_note(name, text)** — дописать текст в конец
4. **update_note(name, content)** — полностью заменить body, сохранив frontmatter
5. **delete_note(name, dry_run?)** — удалить (обновить ссылки, переместить в .trash/)
6. **rename_note(old_name, new_name, dry_run?)** — переименовать + обновить ссылки
7. **search_notes(query, mode?)** — поиск (name, name_partial, content, tag)
8. **get_links(name, direction?)** — входящие/исходящие ссылки
9. **get_frontmatter(name)** — получить frontmatter как JSON
10. **set_frontmatter(name, key, value)** — установить ключ frontmatter
11. **list_notes(limit?, offset?)** — список заметок (только имена, без путей). Default limit=100, offset=0. Для поиска конкретной заметки использовать search_notes.
12. **replace_note(name, old_text, new_text, replace_all?)** — частичная замена текста в body
13. **insert_note(name, text, before?, after?)** — вставка текста до/после паттерна
14. **read_section(name, section)** — прочитать содержимое секции (без заголовка)
15. **append_section(name, section, text)** — дописать текст в конец секции

### Конфигурация:

Vault path берётся из переменной окружения `OBSIDIAN_VAULT_PATH` — передаётся через `env` в claude_desktop_config.json.

### Формат ответов:

Все tools возвращают JSON. Ошибки возвращаются как MCP ToolError с текстом ошибки.

### Auto-context: персональные заметки Claude

**Проблема:** Claude Desktop игнорирует поле `instructions` из MCP InitializeResult. Контекст, переданный через instructions, не попадает в system prompt модели. Единственное что Claude Desktop гарантированно видит — tool results.

**Решение:** Инжектировать auto-context (список заметок с тегом `claude` + descriptions) в результат первого tool call в сессии. Не в instructions.

При старте MCP сервера — собрать все заметки с тегом `claude`, прочитать из их frontmatter поле `description`. При первом вызове любого tool — добавить к результату блок с auto-context. Последующие вызовы — без инъекции (флаг `_context_injected` в state сервера).

Поле `description` обязательно для заметок с тегом `claude`. Описывает **когда читать** заметку, не что в ней.

Пример frontmatter заметки:
```yaml
---
tags: [claude]
description: "Читать перед генерацией любого текста для пользователя. Анти-паттерны ИИ-текста."
---
```

Пример инъекции в tool result (первый вызов):
```
[оригинальный результат tool]

---
## Your personal notes

- "AI Text Quality Guidelines" — Читать перед генерацией любого текста для пользователя. Анти-паттерны ИИ-текста.

Use read_note() to access full content when needed.
---
```

Instructions (FastMCP `instructions=`) содержат только base instructions (правила работы с vault). Механизм CLAUDE.md в корне vault удаляется — vault-specific rules это обычная заметка с тегом `claude`.

### Tag policy: hard validation

Все уникальные теги из vault = allowed list. При любой операции, записывающей теги (create_note с frontmatter содержащим tags, set_frontmatter с key="tags") — валидировать каждый тег против allowed list. Если тег не в списке — reject с ошибкой и списком allowed tags. Claude Desktop увидит ошибку и должен спросить пользователя.

Tag policy также инжектируется в tool result вместе с auto-context (первый вызов любого tool) — как soft reminder.

Пример ошибки:
```
Tag 'career' not in allowed list. Allowed: vc, vc/project, Person, Organization, claude, dns, Fingular.
Ask user before creating new tags.
```

## Clarifications

Q1: Нужен ли tool list_notes?
A1: Да. ClaudeDesktop нужен способ увидеть что есть в vault без поиска.

Q2: frontmatter в create_note — как передаётся?
A2: JSON-строка. Парсится в dict на стороне сервера.

Q3: Нужен ли batch через MCP?
A3: Нет. ClaudeDesktop вызывает tools по одному. Batch — фича CLI для скриптов.

Q4: Как обрабатываются ошибки?
A4: VaultError → ToolError с текстом. Vault не настроен → сервер не стартует (ошибка при инициализации).

Q5: Что делать если у заметки с тегом `claude` нет поля `description` в frontmatter?
A5: Заполни его текстом с призывом ClaudeDesktop заполнить это поле при первой возможности. Чтобы при получении списка заметок с тегом он увидел этот текст и заполнил.

Q6: `_build_instructions` сейчас принимает `vault_path: Path` и работает напрямую с файловой системой. Для auto-context нужен доступ к `Operations.search()` (поиск по тегу) и `Vault.list_notes()` (чтение frontmatter). Менять сигнатуру `_build_instructions` на приём `Operations`, или создать отдельную функцию `_build_autocontext(ops)` которую вызывать после инициализации?

Вариант A — `_build_instructions(ops: Operations)`:
- ✓ Одна функция, всё в одном месте
- ✗ Ломает lazy-init _ops, требует создавать Operations раньше

Вариант B — отдельная `_build_autocontext(ops)`:
- ✗ FastMCP получает instructions при создании. Дописать позже — костыль.

Вариант C — `_build_instructions(vault: Vault)` + убрать global singleton:
- ✓ Operations не нужен для auto-context. Vault.list_notes() даёт Note с .tags и .frontmatter.
- ✓ vault.vault_path доступен для загрузки CLAUDE.md.
- ✓ Vault создаётся один раз в main(), передаётся и в _build_instructions, и в Operations.
- ✓ Убирает global `_ops` и lazy-init `_get_ops()` — явная передача зависимостей.
- ✗ Меняет инициализацию: _register_tools(server, ops) вместо global _ops. Но это правильный рефакторинг — global singleton был костылём.

A6: Вариант C. Единственный без костылей.

Q7: Если заметок с тегом `claude` нет — пропускать секцию молча, или добавлять пустую секцию с подсказкой "No personal notes found. Create notes with tag 'claude' to use auto-context."?
A7: Добавь пустую секцию с подсказкой

Q8: replace_note — `replace_all` параметр: bool, по умолчанию false. Формат ответа — JSON с количеством замен?
A8: Да, JSON с количеством: `{"replaced": int}`. Количество критично для верификации что замена сработала.

Q9: insert_note — `before` и `after` мутуально эксклюзивны. В MCP это просто два опциональных string параметра. Валидация на стороне сервера (ValueError → ToolError)?
A9: Да, валидация на сервере. Оба переданы или оба пустые → ToolError с понятным сообщением типа "Exactly one of 'before' or 'after' must be provided".

Q10: read_section — возвращает plain text (как read_note) или JSON?
A10: Plain text, как read_note. MCP сам оборачивает в JSON-RPC. Нужен контент секции, не дополнительная обёртка.

Q11: Tag policy тоже в instructions. Claude Desktop его тоже не видит. Переносить tag policy в tool result вместе с auto-context (в тот же первый вызов)?
A11: Да, tag policy также инжектируется 1 раз вместе с auto-context — чтобы Claude не генерировал теги бесконечно.

Q12: Если заметок с тегом `claude` нет — инжектировать пустую секцию с подсказкой в tool result, или пропускать инъекцию вообще (экономия токенов)?
A12: Я же где-то описывал. Ах да, вопрос Q7

Q13: CLAUDE.md (vault-specific rules) — аналогичная проблема. Тоже в instructions, тоже не видим Claude Desktop. Переносить в tool result? Уточнение: CLAUDE.md — это файл в корне vault, НЕ заметка. У него нет frontmatter и тега `claude`. Это отдельный механизм (аналог .cursorrules), не часть auto-context. Сейчас читается при старте и добавляется в instructions. Переносить его содержимое в tool result вместе с auto-context и tag policy?
A13: Отдельный файл CLAUDE.md не нужен. Используем заметку с тегом `claude` по аналогии с CLAUDE.md для проектов.

Q14: Формат инъекции. Два варианта:
- A) Текстовый блок, приклеенный к результату через `\n\n---\n` (просто, но смешивает данные с метаданными)
- B) Отдельный content block в MCP response (чище, но зависит от поддержки multi-content клиентом)
A14: А

Q15: list_notes возвращает 97K символов (765 заметок с путями). Это сжигает токены и бесполезно — Claude Desktop не может осмысленно обработать список из 765 элементов. Нужно ли ограничить output или убрать tool?
A15: Возвращай только имена без путей и ограничь, скажем, 100 заметок. Если нужно найти конкретную — пусть использует search_notes. Добавь параметр limit с дефолтом 100 и offset для пагинации.

Q16: Tag policy инжектируется один раз в хвосте первого tool result. На практике первый вызов — list_notes (97K символов), tag policy тонет в конце и Claude Desktop его не видит. Нужна hard validation: create_note и set_frontmatter должны проверять теги против allowed list и reject'ить с ошибкой если тег невалидный. Allowed list = все уникальные теги из vault на момент вызова.
A16: Да. Валидация на уровне кода. Если тег не в allowed list — возвращать ошибку с текстом "Tag 'X' not in allowed list. Allowed: [list]. Ask user before creating new tags." Пусть Claude Desktop видит ошибку и спрашивает у пользователя.

Status: resolved
