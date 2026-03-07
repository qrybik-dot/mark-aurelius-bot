import asyncio
import atexit
import concurrent.futures
import logging
import re
import threading
import time

from flask import Flask, jsonify, request
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from config import settings, validate_settings
from image_gen import (
    build_image_prompt,
    build_image_url_fallback,
    build_image_url_primary,
    extract_image_prompt,
    is_image_request,
    normalize_image_prompt,
)
from prompts import EMPTY_MENTION_REPLY, IMAGE_CAPTION_TEMPLATE, THINKING_TEXT
from stoic_ai import StoicJudge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

logger.info("Telegram token loaded: %s", bool(settings.telegram_bot_token))

flask_app = Flask(__name__)
judge = StoicJudge()
style_by_chat: dict[int, dict[str, str]] = {}

telegram_app = None
telegram_loop = None
telegram_thread = None
_is_initialized = False


def get_telegram_app() -> Application | None:
    global telegram_app

    if telegram_app is not None:
        return telegram_app

    if not settings.telegram_bot_token:
        return None

    telegram_app = Application.builder().token(settings.telegram_bot_token).build()
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    telegram_app.add_error_handler(handle_telegram_error)
    return telegram_app


async def handle_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка в Telegram handler. Update=%s", update, exc_info=context.error)


def normalize_username(username: str) -> str:
    return username.lower().lstrip("@")


def should_respond(update: Update, bot_username: str) -> bool:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not message.text:
        return False

    if chat.type == ChatType.PRIVATE:
        return True

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        is_reply_to_bot = bool(
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.username
            and normalize_username(message.reply_to_message.from_user.username)
            == normalize_username(bot_username)
        )
        mention_pattern = re.compile(rf"@{re.escape(normalize_username(bot_username))}\b", re.IGNORECASE)
        has_mention = bool(mention_pattern.search(message.text))
        return is_reply_to_bot or has_mention

    return False


def strip_bot_mention(text: str, bot_username: str) -> str:
    pattern = re.compile(rf"@{re.escape(normalize_username(bot_username))}\b", re.IGNORECASE)
    return pattern.sub("", text).strip()


def apply_style_command(chat_id: int, stripped_text: str) -> str | None:
    lowered_text = stripped_text.lower()

    if lowered_text in {"режим дерзкий", "отвечай дерзко", "будь жестче", "будь жёстче", "режим roast"}:
        style_by_chat[chat_id] = {"mode": "bold", "custom": ""}
        return "Принято. Теперь буду резче. Без хамства, но с удовольствием."

    if lowered_text in {"режим обычный", "отвечай обычно", "сбрось стиль"}:
        style_by_chat[chat_id] = {"mode": "default", "custom": ""}
        return "Принято. Возвращаюсь к спокойной манере."

    if lowered_text in {"режим стоик", "режим стоический"}:
        style_by_chat[chat_id] = {"mode": "stoic", "custom": ""}
        return "Принято. Возвращаюсь к сухой строгости."

    custom_style_match = re.match(r"^(отвечай|говори)\s+как\s+(.+)$", stripped_text, re.IGNORECASE)
    if custom_style_match:
        custom_style = custom_style_match.group(2).strip(" .,!?:;—-")
        if custom_style:
            style_by_chat[chat_id] = {"mode": "custom", "custom": custom_style}
            return f"Принято. Теперь говорю в таком стиле: {custom_style}"

    return None


async def send_generated_image(message, context, chat_id: int, prompt_raw: str) -> None:
    logger.info("Image request received: %s", prompt_raw)
    normalized_prompt = normalize_image_prompt(prompt_raw)
    prompt_en = build_image_prompt(prompt_raw)
    logger.info("Image prompt normalized: %s", normalized_prompt)

    if not prompt_en:
        await message.reply_text("После слова 'нарисуй' нужна сама идея. Даже император не изображает пустоту.")
        return

    primary_url = build_image_url_primary(prompt_en)
    fallback_url = build_image_url_fallback(prompt_en)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)

    for backend_name, image_url in (("primary", primary_url), ("fallback", fallback_url)):
        logger.info("Image backend=%s url=%s", backend_name, image_url)
        try:
            await message.reply_photo(
                photo=image_url,
                caption=IMAGE_CAPTION_TEMPLATE.format(prompt=prompt_raw[:120]),
                reply_to_message_id=message.message_id,
            )
            return
        except Exception as exc:
            logger.warning("Image send failed on backend=%s: %s", backend_name, exc)

    await message.reply_text(
        "Генерация изображения сейчас недоступна. Текстовый суд работает, а визуальный — нет."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    if not should_respond(update, settings.telegram_bot_username):
        return

    clean_text = strip_bot_mention(message.text, settings.telegram_bot_username)
    if not clean_text:
        await message.reply_text(EMPTY_MENTION_REPLY)
        return

    stripped_text = clean_text.strip()
    lowered_text = stripped_text.lower()

    chat = update.effective_chat
    chat_id = chat.id if chat else message.chat_id

    style_reply = apply_style_command(chat_id, stripped_text)
    if style_reply:
        await message.reply_text(style_reply)
        return

    if is_image_request(lowered_text):
        prompt_raw = extract_image_prompt(stripped_text)
        if not prompt_raw:
            await message.reply_text("После слова 'нарисуй' нужна сама идея. Даже император не изображает пустоту.")
            return
        await send_generated_image(message, context, chat_id, prompt_raw)
        return

    think_message = await message.reply_text(THINKING_TEXT, reply_to_message_id=message.message_id)
    await asyncio.sleep(0.05)
    style_state = style_by_chat.get(chat_id, {"mode": "default", "custom": ""})
    try:
        final_text = judge.evaluate(
            clean_text,
            style_mode=style_state.get("mode", "default"),
            custom_style=style_state.get("custom", ""),
        )
    except Exception:
        logger.exception("Failed to evaluate text request")
        final_text = (
            "Я бы ответил точнее, но сегодня даже разум спотыкается о судьбу. "
            "Скажи мысль проще и короче — разберём хладнокровно."
        )
    await think_message.edit_text(final_text)


async def initialize_telegram_app(app: Application) -> None:
    await app.initialize()
    await app.start()

    if settings.public_base_url and settings.webhook_secret:
        webhook_url = settings.webhook_url()
        await app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=Update.ALL_TYPES,
        )
        logger.info("Webhook установлен: %s", webhook_url)
    else:
        logger.warning("PUBLIC_BASE_URL или WEBHOOK_SECRET не заданы. Webhook не установлен.")


def run_telegram_loop() -> None:
    global telegram_loop
    loop = asyncio.new_event_loop()
    telegram_loop = loop
    asyncio.set_event_loop(loop)
    loop.run_forever()


def initialize_telegram() -> None:
    global _is_initialized, telegram_thread
    if _is_initialized:
        return

    app = get_telegram_app()
    if app is None:
        logger.warning("TELEGRAM_BOT_TOKEN не задан. Telegram приложение не инициализировано.")
        return

    if telegram_loop is None:
        telegram_thread = threading.Thread(
            target=run_telegram_loop,
            daemon=True,
            name="telegram-event-loop",
        )
        telegram_thread.start()

        while telegram_loop is None:
            time.sleep(0.01)

    init_future = asyncio.run_coroutine_threadsafe(initialize_telegram_app(app), telegram_loop)
    init_future.result(timeout=30)

    _is_initialized = True


def shutdown_telegram() -> None:
    global telegram_loop, telegram_thread, _is_initialized

    app = get_telegram_app()
    if app is None or telegram_loop is None:
        return

    if _is_initialized:
        stop_future = asyncio.run_coroutine_threadsafe(app.stop(), telegram_loop)
        shutdown_future = asyncio.run_coroutine_threadsafe(app.shutdown(), telegram_loop)
        try:
            stop_future.result(timeout=30)
            shutdown_future.result(timeout=30)
        except Exception as exc:
            logger.exception("Ошибка завершения Telegram приложения: %s", exc)

    telegram_loop.call_soon_threadsafe(telegram_loop.stop)
    if telegram_thread and telegram_thread.is_alive():
        telegram_thread.join(timeout=5)
    telegram_loop.close()
    telegram_loop = None
    telegram_thread = None
    _is_initialized = False


atexit.register(shutdown_telegram)


@flask_app.get("/")
def healthcheck():
    return jsonify(
        {
            "status": "ok",
            "service": "mark-aurelius-bot",
            "env": {
                "telegram_bot_token_present": bool(settings.telegram_bot_token),
                "telegram_bot_username_present": bool(settings.telegram_bot_username),
                "webhook_secret_present": bool(settings.webhook_secret),
                "public_base_url_present": bool(settings.public_base_url),
            },
        }
    )


@flask_app.post("/webhook/<path_secret>")
def telegram_webhook(path_secret: str):
    app = get_telegram_app()
    if app is None:
        return jsonify({"ok": False, "error": "telegram app is not configured"}), 503

    if path_secret != settings.webhook_secret:
        return jsonify({"ok": False, "error": "invalid webhook path"}), 403

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret != settings.webhook_secret:
        return jsonify({"ok": False, "error": "invalid telegram secret token"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "invalid update payload"}), 400

    update = Update.de_json(data, app.bot)
    try:
        if telegram_loop is None:
            return jsonify({"ok": False, "error": "telegram event loop is not initialized"}), 503

        future = asyncio.run_coroutine_threadsafe(app.process_update(update), telegram_loop)
        future.result(timeout=30)
    except concurrent.futures.TimeoutError:
        logger.exception("Таймаут обработки апдейта")
        return jsonify({"ok": False}), 500
    except Exception as exc:
        logger.exception("Ошибка обработки апдейта: %s", exc)
        return jsonify({"ok": False}), 500

    return jsonify({"ok": True})


def bootstrap() -> None:
    missing_critical = validate_settings()
    if missing_critical:
        logger.warning("Missing critical settings: %s", ", ".join(missing_critical))

    try:
        initialize_telegram()
    except Exception as exc:
        logger.exception("Ошибка инициализации Telegram webhook: %s", exc)


bootstrap()
app = flask_app

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=settings.port)
