from types import SimpleNamespace

from telegram.constants import ChatType

from app import should_respond


def _update(chat_type, text, reply_username=None):
    reply_to_message = None
    if reply_username is not None:
        reply_to_message = SimpleNamespace(from_user=SimpleNamespace(username=reply_username))
    message = SimpleNamespace(text=text, reply_to_message=reply_to_message)
    chat = SimpleNamespace(type=chat_type)
    return SimpleNamespace(effective_message=message, effective_chat=chat)


def test_private_chat_always_true():
    update = _update(ChatType.PRIVATE, "привет")
    assert should_respond(update, "MarcusAurelius_G_bot") is True


def test_group_without_mention_or_reply_false():
    update = _update(ChatType.GROUP, "привет")
    assert should_respond(update, "MarcusAurelius_G_bot") is False


def test_group_with_mention_true():
    update = _update(ChatType.GROUP, "@MarcusAurelius_G_bot привет")
    assert should_respond(update, "MarcusAurelius_G_bot") is True


def test_group_with_reply_to_bot_true():
    update = _update(ChatType.SUPERGROUP, "привет", reply_username="MarcusAurelius_G_bot")
    assert should_respond(update, "MarcusAurelius_G_bot") is True
