import app
from stoic_ai import build_system_prompt


def test_style_switch_to_bold():
    app.style_by_chat.clear()
    reply = app.apply_style_command(1, "отвечай дерзко")
    assert "Теперь буду резче" in reply
    assert app.style_by_chat[1]["mode"] == "bold"


def test_style_switch_to_default():
    app.style_by_chat.clear()
    app.style_by_chat[1] = {"mode": "custom", "custom": "test"}
    reply = app.apply_style_command(1, "режим обычный")
    assert "спокойной манере" in reply
    assert app.style_by_chat[1] == {"mode": "default", "custom": ""}


def test_style_switch_to_stoic():
    app.style_by_chat.clear()
    reply = app.apply_style_command(1, "режим стоик")
    assert "сухой строгости" in reply
    assert app.style_by_chat[1]["mode"] == "stoic"


def test_custom_style_saved():
    app.style_by_chat.clear()
    reply = app.apply_style_command(7, "отвечай как суровый сержант")
    assert "суровый сержант" in reply
    assert app.style_by_chat[7]["mode"] == "custom"
    assert app.style_by_chat[7]["custom"] == "суровый сержант"


def test_system_prompt_builders_differ_by_mode():
    default_prompt = build_system_prompt("default", "")
    bold_prompt = build_system_prompt("bold", "")
    stoic_prompt = build_system_prompt("stoic", "")
    custom_prompt = build_system_prompt("custom", "суровый сержант")

    assert default_prompt[1]["content"] != bold_prompt[1]["content"]
    assert stoic_prompt[1]["content"] != custom_prompt[1]["content"]
    assert "суровый сержант" in custom_prompt[1]["content"]


def test_image_command_does_not_change_style_state():
    app.style_by_chat.clear()
    app.style_by_chat[99] = {"mode": "bold", "custom": ""}

    reply = app.apply_style_command(99, "нарисуй солнце")

    assert reply is None
    assert app.style_by_chat[99] == {"mode": "bold", "custom": ""}
