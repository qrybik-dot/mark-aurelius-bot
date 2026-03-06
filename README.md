# Марк Аврелий — Telegram-бот стоического приговора

Production-ready MVP Telegram-бота на Python с webhook-архитектурой под бесплатный деплой на Render.

Бот принимает идею пользователя и отвечает как ироничный стоический судья:
- сначала пишет: **«Марк Аврелий размышляет...»**
- через 2–3 секунды выносит вердикт
- добавляет короткое объяснение на русском языке

Также умеет генерировать изображения через Pollinations по командам вида «нарисуй ...».

## Стек
- Python 3.11
- Flask
- python-telegram-bot
- OpenRouter Chat Completions API
- Pollinations (image endpoint)
- Gunicorn
- Render

## Структура проекта
- `app.py` — Flask-приложение, webhook endpoint, Telegram handlers
- `config.py` — env-конфигурация
- `prompts.py` — системный prompt и шаблоны сообщений
- `stoic_ai.py` — OpenRouter-интеграция и fallback-эвристика
- `image_gen.py` — детект и генерация URL для картинок
- `requirements.txt` — зависимости
- `render.yaml` — конфигурация деплоя на Render
- `.env.example` — шаблон переменных окружения

## Переменные окружения
Нужно задать:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME`
- `WEBHOOK_SECRET`
- `PUBLIC_BASE_URL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (по умолчанию `openrouter/free`)
- `PORT` (по умолчанию `10000`)

## Локальный запуск
1. Создай окружение и установи зависимости:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Скопируй `.env.example` в `.env` и заполни значения.
3. Экспортируй переменные в окружение (например через `set -a; source .env; set +a`).
4. Запусти:
   ```bash
   python app.py
   ```
5. Проверь healthcheck:
   - `GET /` вернёт JSON `{"status": "ok", ...}`

## Настройка BotFather
1. Создай бота: `/newbot`.
2. Получи токен и сохрани в `TELEGRAM_BOT_TOKEN`.
3. (Опционально) Настрой описание/аватар.
4. Убедись, что `TELEGRAM_BOT_USERNAME` совпадает с username бота без ошибок.

## Деплой на Render
1. Запушь репозиторий в GitHub.
2. На Render создай **Web Service** из репозитория.
3. Укажи Python environment (или используй `render.yaml`).
4. Добавь env vars из списка выше.
5. После старта приложение автоматически вызывает `setWebhook` на URL:
   - `PUBLIC_BASE_URL + /webhook/WEBHOOK_SECRET`

## Логика ответов
### Личные сообщения
Бот отвечает на любой текст.

### Группы
Бот отвечает только если:
- есть mention `@TELEGRAM_BOT_USERNAME`, или
- сообщение — reply на сообщение бота.

Mention удаляется из текста перед анализом.
Если после удаления mention текст пустой, бот отвечает короткой фразой.

### Генерация изображений
Если сообщение начинается с «нарисуй» (или синонимов), бот:
1. берёт оставшийся текст как prompt,
2. генерирует URL для Pollinations,
3. отправляет изображение как `photo reply` с короткой подписью.

## Примеры использования
- Личка:
  - `Хочу месяц вставать в 6 утра и не срываться` 
- Группа:
  - `@mark_aurelius_bot хочу спорить с каждым в чате ради эго`
  - reply на сообщение бота: `Ладно, сегодня без прокрастинации`
- Картинки:
  - `Нарисуй римского императора под неоном в киберпанк-городе`

## Известные ограничения бесплатного стека
- На бесплатных тарифах возможны «пробуждения» сервиса после простоя.
- OpenRouter free-модели могут отвечать нестабильно или отдавать rate limit.
- При проблемах OpenRouter бот переключится на встроенный fallback-режим и не упадёт.

## Проверка перед продом
- Проверь, что `PUBLIC_BASE_URL` указывает на публичный HTTPS URL Render-сервиса.
- Проверь, что `WEBHOOK_SECRET` совпадает в URL и заголовке Telegram webhook.
- Убедись, что не коммитишь `.env` и токены.
