import app
from stoic_ai import build_final_reply, style_explanation


def test_otvechai_derzko_sets_bold():
    app.style_by_chat.clear()
    app.apply_style_command(1, "отвечай дерзко")
    assert app.style_by_chat[1]["mode"] == "bold"


def test_rezhim_obychnyi_sets_default():
    app.style_by_chat.clear()
    app.style_by_chat[1] = {"mode": "custom", "custom": "test"}
    app.apply_style_command(1, "режим обычный")
    assert app.style_by_chat[1] == {"mode": "default", "custom": ""}


def test_rezhim_stoik_sets_stoic():
    app.style_by_chat.clear()
    app.apply_style_command(1, "режим стоик")
    assert app.style_by_chat[1]["mode"] == "stoic"


def test_custom_style_command_sets_custom():
    app.style_by_chat.clear()
    app.apply_style_command(7, "отвечай как суровый сержант")
    assert app.style_by_chat[7]["mode"] == "custom"
    assert app.style_by_chat[7]["custom"] == "суровый сержант"


def test_verdict_line_unchanged_for_all_styles():
    base_explanation = "Это полезный выбор. Продолжай действовать без суеты."
    for mode, custom in (("default", ""), ("bold", ""), ("stoic", ""), ("custom", "сержант")):
        styled = style_explanation(base_explanation, style_mode=mode, custom_style=custom)
        reply = build_final_reply("negative", styled)
        assert reply.splitlines()[0] == "Марк Аврелий недоволен тобой."
