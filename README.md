# Марк Аврелий — Telegram-бот стоического приговора

Production-ready MVP Telegram-бота на Python с webhook-архитектурой для деплоя на Railway, Koyeb и Render.

Бот принимает идею пользователя и отвечает как ироничный стоический судья:
- сначала пишет: **«Марк Аврелий размышляет...»**
- через 2–3 секунды выносит вердикт
- добавляет короткое объяснение на русском языке

Также умеет генерировать изображения по командам вида «нарисуй ...» с primary/backup backend цепочкой и fallback-отправкой bytes, если Telegram не принимает внешний URL.

## Стек
- Python 3.11
- Flask
- python-telegram-bot
- OpenRouter Chat Completions API
- Pollinations (image endpoint)
- Gunicorn
- Railway / Koyeb / Render

## Структура проекта
- `app.py` — Flask-приложение, webhook endpoint, Telegram handlers
- `config.py` — env-конфигурация и валидация критичных env
- `prompts.py` — системный prompt и шаблоны сообщений
- `stoic_ai.py` — OpenRouter-интеграция и fallback-эвристика
- `image_gen.py` — детект и генерация URL для картинок
- `requirements.txt` — зависимости
- `render.yaml` — конфигурация деплоя на Render
- `.env.example` — шаблон переменных окружения

## Переменные окружения
### Критичные для Telegram-функционала
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME`

### Некритичные для старта healthcheck
- `WEBHOOK_SECRET`
- `PUBLIC_BASE_URL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (legacy-совместимость, по умолчанию `openrouter/free`)
- `OPENROUTER_MODEL_PRIMARY` (основная текстовая модель)
- `OPENROUTER_MODEL_BACKUP` (резервная текстовая модель, по умолчанию `openrouter/free`)
- `IMAGE_BACKEND_PRIMARY` (основной image backend, по умолчанию `pollinations`)
- `IMAGE_BACKEND_BACKUP` (резервный image backend, по умолчанию `pollinations_flux`)
- `PORT` (по умолчанию `10000`)

> Важно: сервис стартует даже без `TELEGRAM_BOT_TOKEN`, чтобы healthcheck не падал.

## Локальный запуск
1. Создай окружение и установи зависимости:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Скопируй `.env.example` в `.env` и заполни значения.
3. Запусти:
   ```bash
   python app.py
   ```

`python-dotenv` подхватит `.env` автоматически для локальной разработки.

## Healthcheck
`GET /` возвращает:
```json
{
  "status": "ok",
  "service": "mark-aurelius-bot",
  "env": {
    "telegram_bot_token_present": true,
    "telegram_bot_username_present": true,
    "webhook_secret_present": true,
    "public_base_url_present": true
  }
}
```

Секреты и токены в ответе не раскрываются, только `true/false`.

## Настройка BotFather
1. Создай бота: `/newbot`.
2. Получи токен и сохрани в `TELEGRAM_BOT_TOKEN`.
3. Убедись, что `TELEGRAM_BOT_USERNAME` совпадает с username бота.

## Деплой: Railway + Koyeb + Render

### Railway
1. Создай новый сервис из GitHub-репозитория.
2. Добавь environment variables из списка выше.
3. Убедись, что Railway поднял HTTP service и назначил публичный домен.
4. Укажи:
   - `PUBLIC_BASE_URL=https://<your-railway-domain>`
   - `WEBHOOK_SECRET=<случайная-строка>`
5. После старта приложение само вызовет `setWebhook` при наличии токена.

### Koyeb
1. Создай Web Service из репозитория.
2. Задай build/start команду (обычно через `gunicorn app:app`).
3. Добавь env vars.
4. Укажи публичный Koyeb URL в `PUBLIC_BASE_URL`.
5. Проверь, что endpoint `/webhook/<WEBHOOK_SECRET>` доступен извне по HTTPS.

### Render
1. Запушь репозиторий в GitHub.
2. На Render создай **Web Service** из репозитория (или используй `render.yaml`).
3. Добавь env vars.
4. Проверь:
   - `PUBLIC_BASE_URL=https://<your-render-service>.onrender.com`
   - `WEBHOOK_SECRET=<случайная-строка>`

## Логика ответов
### Личные сообщения
Бот отвечает на любой текст.

### Группы
Бот отвечает только если:
- есть mention `@TELEGRAM_BOT_USERNAME`, или
- сообщение — reply на сообщение бота.

Иначе сообщение игнорируется (mention/reply-only режим для групп и supergroup).

Mention удаляется из текста перед анализом.
Если после удаления mention текст пустой, бот отвечает короткой фразой.

### Текстовый flow (primary/backup + deterministic fallback)
1. Бот пробует `OPENROUTER_MODEL_PRIMARY`.
2. При ошибке/таймауте/невалидном structured-output пробует `OPENROUTER_MODEL_BACKUP`.
3. Если обе модели не дали валидный ответ, использует локальный deterministic analyzer.
4. Финальный формат ответа всегда фиксирован: первая строка verdict + пустая строка + короткое объяснение.

### Генерация изображений
Если сообщение начинается с «нарисуй» (или синонимов), бот:
1. берёт оставшийся текст как prompt и нормализует его,
2. строит кандидатов `IMAGE_BACKEND_PRIMARY` -> `IMAGE_BACKEND_BACKUP`,
3. для каждого backend пробует отправку `reply_photo(url)`,
4. если URL не принят Telegram — скачивает изображение и отправляет как bytes/file-like object,
5. если все backend исчерпаны — отправляет честный технический fallback.

## Проверка перед продом
- Проверь, что `PUBLIC_BASE_URL` указывает на публичный HTTPS URL сервиса.
- Проверь, что `WEBHOOK_SECRET` совпадает в URL и заголовке Telegram webhook.
- Убедись, что не коммитишь `.env` и токены.
