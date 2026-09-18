# Catalys

Catalys — сервис для создания визуального профиля университета. Он принимает название университета, ищет изображения через DuckDuckGo, Wikimedia Commons и Wikipedia, удаляет дубликаты, распределяет фото по категориям и сохраняет результат со ссылками на источники.

## Возможности

- поиск изображений в DuckDuckGo, Wikimedia Commons и Wikipedia;
- параллельная проверка доступности изображений через `httpx`;
- фильтрация невалидных ссылок и фотостоков;
- дедупликация по URL и visual hash;
- категории: Campus, Dormitory, Auditoriums, Sport, Student life;
- confidence score;
- история профилей;
- экспорт JSON и share-сценарий;
- demo seed для презентации без внешнего поиска;
- JSON API.
- подготовленная фоновая обработка через Celery и Redis.

## Запуск

Требуется Python 3.11+.

```bash
cd catalys
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

Откройте <http://127.0.0.1:8000/>.

## Redis и Celery

DuckDuckGo работает без платного API-ключа. Для фоновых задач запустите Redis:

```bash
redis-server
```

В отдельном терминале запустите Celery worker:

```bash
celery -A celery.app worker --loglevel=info
```

Фоновая задача находится в `profiles/tasks.py`. Текущий endpoint использует прямой быстрый сценарий MVP; переход на `task_id → progress → result` можно добавить для production.

## Demo-режим

Создайте заранее сохранённый профиль:

```bash
python3 manage.py seed_demo
```

Затем откройте интерфейс и нажмите `History`. Это удобно для презентации, если внешний поиск временно недоступен.

## API

Проверка сервиса:

```http
GET /health/
```

Автоматический поиск:

```http
POST /api/v1/discover/
Content-Type: application/json

{"name": "Nazarbayev University"}
```

Создание профиля из готовых данных:

```http
POST /api/v1/profiles/
Content-Type: application/json
```

История и сохранённый профиль:

```http
GET /api/v1/profiles/history/
GET /api/v1/profiles/<id>/
```

## Проверка

```bash
python3 manage.py check
python3 -m pytest -q
```

## Структура проекта

```text
university_profile.py       # очистка, дедупликация и категоризация
profiles/services.py        # поиск и бизнес-логика
profiles/tasks.py           # фоновые Celery-задачи
celery.py                   # конфигурация Celery
profiles/views.py           # web views и API
profiles/models.py          # сохранение профилей
profiles/management/        # команда seed_demo
templates/landing.html      # интерфейс Catalys
assets/nazarbayev-university.png # локальное hero-изображение для demo
```

Vision-проверка изображений запланирована отдельным Gemini-адаптером после стабилизации основного MVP.

## Gemini AI

Для включения AI-резюме профиля задайте ключ Gemini:

```bash
export GEMINI_API_KEY="your_key"
export GEMINI_MODEL="gemini-3.5-flash-lite"
```

Без ключа используется локальный fallback, поэтому demo не ломается. AI-слой возвращает `summary`, `highlights`, `recommendation` и поле `mode` (`gemini` или `fallback`).

Перед поиском Gemini также нормализует название университета и раскрывает аббревиатуры (`MIT`, `NYU`, `KAIST`, `MBZUAI`). При недоступности API используется локальный словарь aliases.
