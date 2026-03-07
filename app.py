import asyncio
import logging
import random
import re

from flask import Flask, jsonify, request
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from config import settings
from image_gen import build_pollinations_url, extract_image_prompt, is_image_request
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

telegram_app = Application.builder().token(settings.telegram_bot_token).build()
_is_initialized = False


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

    if is_image_request(clean_text):
        prompt = extract_image_prompt(clean_text)
        if not prompt:
            await message.reply_text("После «нарисуй» добавь, что именно изобразить.")
            return

        image_url = build_pollinations_url(prompt)
        await message.reply_photo(
            photo=image_url,
            caption=IMAGE_CAPTION_TEMPLATE.format(prompt=prompt[:120]),
            reply_to_message_id=message.message_id,
        )
        return

    think_message = await message.reply_text(THINKING_TEXT, reply_to_message_id=message.message_id)
    await asyncio.sleep(random.uniform(2.0, 3.0))
    final_text = judge.evaluate(clean_text)
    await think_message.edit_text(final_text)


telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


async def initialize_telegram() -> None:
    global _is_initialized
    if _is_initialized:
        return

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN не задан. Webhook не инициализирован.")
        return

    await telegram_app.initialize()

    if settings.public_base_url and settings.webhook_secret:
        webhook_url = settings.webhook_url()
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=Update.ALL_TYPES,
        )
        logger.info("Webhook установлен: %s", webhook_url)
    else:
        logger.warning("PUBLIC_BASE_URL или WEBHOOK_SECRET не заданы. Webhook не установлен.")

    _is_initialized = True


@flask_app.get("/")
def healthcheck():
    return jsonify({"status": "ok", "service": "mark-aurelius-bot"})


@flask_app.post("/webhook/<path_secret>")
def telegram_webhook(path_secret: str):
    if path_secret != settings.webhook_secret:
        return jsonify({"ok": False, "error": "invalid webhook path"}), 403

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret != settings.webhook_secret:
        return jsonify({"ok": False, "error": "invalid telegram secret token"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "invalid update payload"}), 400

    update = Update.de_json(data, telegram_app.bot)
    try:
        asyncio.run(telegram_app.process_update(update))
    except Exception as exc:
        logger.exception("Ошибка обработки апдейта: %s", exc)
        return jsonify({"ok": False}), 500

    return jsonify({"ok": True})


def bootstrap() -> None:
    try:
        asyncio.run(initialize_telegram())
    except Exception as exc:
        logger.exception("Ошибка инициализации Telegram webhook: %s", exc)


bootstrap()
app = flask_app

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=settings.port)
