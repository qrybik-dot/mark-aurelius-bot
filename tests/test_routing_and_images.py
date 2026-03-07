import asyncio
from types import SimpleNamespace

import app
from image_gen import build_image_prompt, generate_image_url


class _ThinkMessage:
    def __init__(self):
        self.edited_text = None

    async def edit_text(self, text):
        self.edited_text = text


class _Message:
    def __init__(self, text: str, chat_id: int = 42):
        self.text = text
        self.chat_id = chat_id
        self.message_id = 7
        self.photo_calls = []
        self.reply_text_calls = []

    async def reply_text(self, text, **kwargs):
        self.reply_text_calls.append(text)
        return _ThinkMessage()

    async def reply_photo(self, **kwargs):
        self.photo_calls.append(kwargs)


class _Bot:
    def __init__(self):
        self.actions = []

    async def send_chat_action(self, **kwargs):
        self.actions.append(kwargs)


def _run_handle_text(text: str, monkeypatch, judge_impl):
    message = _Message(text)
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


def test_narisuy_solnce_goes_image_flow_and_skips_llm(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            raise AssertionError("LLM branch must not be called for image flow")

    message, bot = _run_handle_text("нарисуй солнце", monkeypatch, _Judge())
    assert bot.actions
    assert len(message.photo_calls) == 1


def test_narisuy_hleb_prompt_and_url():
    prompt_en = build_image_prompt("хлеб")
    assert prompt_en
    assert "fresh bread" in prompt_en
    url = generate_image_url(prompt_en)
    assert "image.pollinations.ai" in url


def test_narisuy_without_prompt_returns_fallback(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    message, _ = _run_handle_text("нарисуй", monkeypatch, _Judge())
    assert any("нужна сама идея" in text for text in message.reply_text_calls)


def test_est_hleb_goes_text_flow_not_image(monkeypatch):
    class _Judge:
        def __init__(self):
            self.called = False

        def evaluate(self, *_args, **_kwargs):
            self.called = True
            return "ok"

    judge = _Judge()
    message, bot = _run_handle_text("есть хлеб", monkeypatch, judge)
    assert judge.called is True
    assert not bot.actions
    assert not message.photo_calls
