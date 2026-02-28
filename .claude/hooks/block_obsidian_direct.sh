#!/bin/bash
# Hook: блокирует ЛЮБУЮ прямую работу с Obsidian vault
#
# Блокируется: Read, Edit, Write, Grep файлов в Obsidian vault
# Причина: все операции с Obsidian должны идти через MCP obsidian
#
# Без исключений. Если MCP недоступен — пользователь должен его настроить,
# а не обходить через прямой доступ.
#
# Настройка: установить OBSIDIAN_VAULT_PATH в переменных окружения

input=$(cat)

# Извлекаем путь из JSON (file_path для Read/Edit/Write, path для Grep)
file_path=$(echo "$input" | grep -oP '"file_path"\s*:\s*"\K[^"]+')
grep_path=$(echo "$input" | grep -oP '"path"\s*:\s*"\K[^"]+')
path="${file_path:-$grep_path}"

# Obsidian vault path from env
OBSIDIAN_VAULT="${OBSIDIAN_VAULT_PATH:-}"

# Skip check if vault path not configured
if [ -z "$OBSIDIAN_VAULT" ]; then
    exit 0
fi

if echo "$path" | grep -q "$OBSIDIAN_VAULT"; then
    echo "❌ ЗАПРЕЩЕНО: прямая работа с Obsidian vault" >&2
    echo "" >&2
    echo "Все операции с Obsidian — строго через MCP:" >&2
    echo "" >&2
    echo "  Чтение:  mcp__obsidian__read_note(name=\"Note Name\")" >&2
    echo "  Поиск:   mcp__obsidian__search_notes(query=\"...\", mode=\"name_partial\")" >&2
    echo "  Список:  mcp__obsidian__list_notes()" >&2
    echo "  Запись:  mcp__obsidian__create_note() / mcp__obsidian__append_note()" >&2
    echo "  Правка:  mcp__obsidian__replace_text()" >&2
    echo "" >&2
    echo "Если MCP недоступен — настрой его. Прямой доступ запрещён." >&2
    echo "См. .claude/skills/obsidian/SKILL.md" >&2
    exit 2
fi

exit 0
