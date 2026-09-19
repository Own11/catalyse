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

## Установка и запуск

Требуется Python 3.11 или новее.

### macOS и Linux

```bash
cd catalys
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Откройте <http://127.0.0.1:8000/>.

## Деплой на Vercel + Neon

1. Создайте проект в Neon и скопируйте pooled connection string в переменную `DATABASE_URL`.
2. Импортируйте репозиторий в Vercel. Файл `vercel.json` уже направляет запросы в Django WSGI-приложение.
3. Добавьте переменные окружения Vercel:

```text
DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require
DJANGO_SECRET_KEY=случайная-длинная-строка
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=.vercel.app
CSRF_TRUSTED_ORIGINS=https://ваш-проект.vercel.app
```

Опционально добавьте `GEMINI_API_KEY`, `OPENAI_API_KEY` и соответствующие настройки моделей.

После первого деплоя выполните миграции из локального терминала с тем же `DATABASE_URL`:

```bash
DATABASE_URL="ваша строка Neon" python3 manage.py migrate
```

В Vercel функция работает в serverless-режиме, поэтому SQLite и локальные файлы нельзя использовать как постоянное хранилище. Профили сохраняются в Neon, а изображения остаются внешними ссылками на источники.

### Windows PowerShell

```powershell
cd catalys
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Если PowerShell запрещает активацию окружения, выполните один раз:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Для Windows CMD активация выглядит так:

```bat
.venv\Scripts\activate.bat
```

Остановить сервер: `Ctrl+C`.

## Gemini AI

AI-описание профиля работает при наличии ключа Gemini. Переменные нужно задать в том же терминале, где запускается Django.

### macOS и Linux

```bash
export GEMINI_API_KEY="your_key"
export GEMINI_MODEL="gemini-3.5-flash-lite"
python manage.py runserver
```

### Windows PowerShell

```powershell
$env:GEMINI_API_KEY="your_key"
$env:GEMINI_MODEL="gemini-3.5-flash-lite"
python manage.py runserver
```

Без ключа поиск работает, но используется резервное описание вместо AI-описания.

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

Затем откройте интерфейс и нажмите `History`.

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
assets/                    # дополнительные локальные ресурсы (если добавлены)
```

Проверка изображений через Vision выполняется опционально при наличии соответствующего API-ключа.

AI-слой возвращает `summary`, `highlights`, `recommendation` и поле `mode` (`gemini` или `fallback`). Название университета обрабатывается по пользовательскому запросу; заранее заданных университетов и аббревиатур нет.
