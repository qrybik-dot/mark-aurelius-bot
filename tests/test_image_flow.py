import asyncio
from types import SimpleNamespace

import app
from image_gen import (
    build_image_prompt,
    build_image_url_fallback,
    build_image_url_primary,
)


class _ThinkMessage:
    def __init__(self):
        self.edited_text = None

    async def edit_text(self, text):
        self.edited_text = text


class _Message:
    def __init__(self, text: str, chat_id: int = 42, fail_count: int = 0):
        self.text = text
        self.chat_id = chat_id
        self.message_id = 7
        self.photo_calls = []
        self.reply_text_calls = []
        self.fail_count = fail_count

    async def reply_text(self, text, **kwargs):
        self.reply_text_calls.append(text)
        return _ThinkMessage()

    async def reply_photo(self, **kwargs):
        self.photo_calls.append(kwargs)
        if self.fail_count > 0:
            self.fail_count -= 1
            raise RuntimeError("photo send failed")


class _Bot:
    def __init__(self):
        self.actions = []

    async def send_chat_action(self, **kwargs):
        self.actions.append(kwargs)


def _run_handle_text(text: str, monkeypatch, judge_impl, fail_count: int = 0):
    message = _Message(text, fail_count=fail_count)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=42))
    context = SimpleNamespace(bot=_Bot())

    monkeypatch.setattr(app, "should_respond", lambda *_: True)
    monkeypatch.setattr(app, "strip_bot_mention", lambda txt, *_: txt)

    async def _fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(app.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(app, "judge", judge_impl)

    asyncio.run(app.handle_text(update, context))
    return message, context.bot


def test_narisuy_kofe_goes_image_flow(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            raise AssertionError("Text branch must not be called for image flow")

    message, bot = _run_handle_text("нарисуй кофе", monkeypatch, _Judge())
    assert bot.actions
    assert len(message.photo_calls) == 1


def test_narisuy_krug_goes_image_flow(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            raise AssertionError("Text branch must not be called for image flow")

    message, _ = _run_handle_text("нарисуй круг", monkeypatch, _Judge())
    assert len(message.photo_calls) == 1


def test_narisuy_without_prompt_returns_error(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    message, _ = _run_handle_text("нарисуй", monkeypatch, _Judge())
    assert any("нужна сама идея" in text for text in message.reply_text_calls)


def test_primary_url_builds():
    prompt = build_image_prompt("кофе")
    url = build_image_url_primary(prompt)
    assert "image.pollinations.ai" in url
    assert "width=1024" in url


def test_fallback_url_builds():
    prompt = build_image_prompt("круг")
    url = build_image_url_fallback(prompt)
    assert "image.pollinations.ai" in url
    assert "model=flux" in url


def test_if_primary_fails_fallback_called(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    message, _ = _run_handle_text("нарисуй кофе", monkeypatch, _Judge(), fail_count=1)
    assert len(message.photo_calls) == 2


def test_if_both_fail_honest_tech_fallback(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    message, _ = _run_handle_text("нарисуй кофе", monkeypatch, _Judge(), fail_count=2)
    assert any("Генерация изображения сейчас недоступна" in text for text in message.reply_text_calls)


def test_est_hleb_not_image_flow(monkeypatch):
    class _Judge:
        def __init__(self):
            self.called = False

        def evaluate(self, *_args, **_kwargs):
            self.called = True
            return "Марк Аврелий доволен тобой.\n\nЭто полезная мысль. Действуй дальше."

    judge = _Judge()
    message, bot = _run_handle_text("есть хлеб", monkeypatch, judge)
    assert judge.called is True
    assert not bot.actions
    assert not message.photo_calls
