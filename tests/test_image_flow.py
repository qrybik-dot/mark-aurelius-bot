import asyncio
import io
from types import SimpleNamespace

import app
from image_gen import build_image_prompt, build_image_request_candidates, extract_image_prompt, is_image_request


class _ThinkMessage:
    def __init__(self):
        self.edited_text = None

    async def edit_text(self, text):
        self.edited_text = text


class _Message:
    def __init__(self, text: str, chat_id: int = 42, fail_urls=None, fail_bytes=None):
        self.text = text
        self.chat_id = chat_id
        self.message_id = 7
        self.photo_calls = []
        self.reply_text_calls = []
        self.fail_urls = set(fail_urls or [])
        self.fail_bytes = set(fail_bytes or [])

    async def reply_text(self, text, **kwargs):
        self.reply_text_calls.append(text)
        return _ThinkMessage()

    async def reply_photo(self, **kwargs):
        self.photo_calls.append(kwargs)
        photo = kwargs.get("photo")
        if isinstance(photo, str):
            if any(tag in photo for tag in self.fail_urls):
                raise RuntimeError("url send failed")
        elif isinstance(photo, io.BytesIO):
            if photo.name.replace(".jpg", "") in self.fail_bytes:
                raise RuntimeError("bytes send failed")


class _Bot:
    def __init__(self):
        self.actions = []

    async def send_chat_action(self, **kwargs):
        self.actions.append(kwargs)


class _Response:
    def __init__(self, content=b"img", content_type="image/jpeg"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None


def _run_handle_text(text: str, monkeypatch, judge_impl, message: _Message):
    update = SimpleNamespace(
        effective_message=message,
        effective_chat=SimpleNamespace(id=42),
    )
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

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _Response())
    message = _Message("нарисуй кофе")
    message, bot = _run_handle_text("нарисуй кофе", monkeypatch, _Judge(), message)
    assert bot.actions
    assert len(message.photo_calls) == 1


def test_narisuy_krug_goes_image_flow(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            raise AssertionError("Text branch must not be called for image flow")

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _Response())
    message = _Message("нарисуй круг")
    message, _ = _run_handle_text("нарисуй круг", monkeypatch, _Judge(), message)
    assert len(message.photo_calls) == 1


def test_narisuy_without_prompt_returns_error(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    message = _Message("нарисуй")
    message, _ = _run_handle_text("нарисуй", monkeypatch, _Judge(), message)
    assert any("нужна сама идея" in text for text in message.reply_text_calls)


def test_builds_candidates_for_primary_and_backup(monkeypatch):
    import image_gen

    monkeypatch.setattr(
        image_gen,
        "settings",
        SimpleNamespace(image_backend_primary="pollinations", image_backend_backup="pollinations_flux"),
    )
    prompt = build_image_prompt("кофе")
    candidates = build_image_request_candidates(prompt)
    assert [c["backend"] for c in candidates] == ["pollinations", "pollinations_flux"]


def test_if_url_fails_bytes_mode_is_used(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _Response())
    message = _Message("нарисуй кофе", fail_urls={"pollinations"})
    message, _ = _run_handle_text("нарисуй кофе", monkeypatch, _Judge(), message)
    assert len(message.photo_calls) >= 2
    assert any(isinstance(call["photo"], io.BytesIO) for call in message.photo_calls)


def test_if_primary_fails_backup_called(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _Response())
    message = _Message("нарисуй кофе", fail_urls={"pollinations"}, fail_bytes={"pollinations"})
    message, _ = _run_handle_text("нарисуй кофе", monkeypatch, _Judge(), message)
    sent_urls = [call["photo"] for call in message.photo_calls if isinstance(call["photo"], str)]
    assert any("model=flux" in u for u in sent_urls)


def test_if_all_fail_honest_tech_fallback(monkeypatch):
    class _Judge:
        def evaluate(self, *_args, **_kwargs):
            return "should not happen"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _Response(content_type="text/plain"))
    message = _Message(
        "нарисуй кофе",
        fail_urls={"pollinations", "pollinations_flux"},
        fail_bytes={"pollinations", "pollinations_flux"},
    )
    message, _ = _run_handle_text("нарисуй кофе", monkeypatch, _Judge(), message)
    assert any("Генерация изображения сейчас недоступна" in text for text in message.reply_text_calls)


def test_extract_and_trigger():
    assert is_image_request("нарисуй кофе")
    assert extract_image_prompt("нарисуй кофе") == "кофе"
