---
name: telegram
description: Работа с Telegram через Telethon. Чтение сообщений, поиск вакансий, синхронизация чатов.
---

# Telegram Skill

Работа с Telegram API через Telethon.

## Credentials

```
TELEGRAM_API_ID=26517980
TELEGRAM_API_HASH=3212d8f6bc44580a4ad7c02a652bc434
TELEGRAM_PHONE=+79140752575
Session: data/session (в telegram_mcp проекте)
```

## Quick Start

```python
from telethon.sync import TelegramClient
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path('.env'))
api_id = int(os.environ.get('TELEGRAM_API_ID', 0))
api_hash = os.environ.get('TELEGRAM_API_HASH', '')

with TelegramClient('data/session', api_id, api_hash) as client:
    # Получить entity по username
    entity = client.get_entity('username')

    # Читать сообщения
    messages = client.get_messages(entity, limit=100)

    # Читать из топика форума
    messages = client.get_messages(entity, limit=100, reply_to=topic_id)
```

## Whitelist чатов

Файл: `telegram_mcp/data/chats.toml`

```toml
[group.cy_it_hr]
id = -1001246902558
depth_months = 6
description = "CY iT HR - IT вакансии"

# Топики:
# - 46679: Vacancy – Cyprus companies
# - 46685: Vacancy – Worldwide companies (remote)
# - 46681: CV (резюме)

[channel.cryptojobslist]
id = -1001100655091

[channel.web3hiring]
id = -1001561339286
```

## Полезные команды

### Получить ID чата/канала

```python
entity = client.get_entity('username')
print(f"ID: {entity.id}")
# Для каналов добавить -100 prefix: -100{entity.id}
```

### Читать сообщения из топика форума

```python
messages = client.get_messages(
    chat_id,
    limit=500,
    reply_to=topic_id  # ID топика
)
```

### Поиск по ключевым словам

```python
keywords = ['data engineer', 'etl', 'airflow']
for msg in messages:
    if msg.text and any(kw in msg.text.lower() for kw in keywords):
        print(msg.text)
```

## Проекты

- **telegram_mcp** - MCP сервер для поиска по Telegram чатам
- Session хранится в `telegram_mcp/data/session`

## Job Search каналы

| Канал | ID | Описание |
|-------|-----|----------|
| CY iT HR | -1001246902558 | IT вакансии Кипр/Remote |
| CryptoJobsList | -1001100655091 | Web3 jobs |
| Web3 Jobs | -1001561339286 | Daily web3 вакансии |
| Remote Web3 Jobs | -1001589564382 | Remote blockchain |
| LaborX | -1001215494604 | Web3 + AI jobs |
| Data Science Jobs | -1001321264581 | Data/ML вакансии |

## CV Format (CY iT HR)

```
#CV #dataengineer #python #clickhouse

Data Engineer | Remote | 4 года опыта
Стек: Python, ClickHouse, PostgreSQL, Kafka, Airflow, dbt, Greenplum, Docker
TG: @Abrak44
LinkedIn: linkedin.com/in/maksim-p-8147a9337
```

## Outreach Template

```
Привет, увидел вакансию [Позиция] в [Компания] в CY iT HR.
4 года опыта. Стек: Python, ClickHouse, PostgreSQL, Kafka, Airflow, dbt, Greenplum, Docker.
CV приложил.
```
