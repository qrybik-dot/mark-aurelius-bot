from stoic_ai import (
    StoicJudge,
    analyze_idea_fallback,
    build_final_reply,
    style_explanation,
)


def test_build_final_reply_positive_prefix():
    reply = build_final_reply("positive", "Это полезная и ясная мысль. Действуй спокойно и твердо.")
    assert reply.startswith("Марк Аврелий доволен тобой.")


def test_build_final_reply_negative_prefix():
    reply = build_final_reply("negative", "Это слабая позиция. Выбери дисциплину и ясность, а не инерцию.")
    assert reply.startswith("Марк Аврелий недоволен тобой.")


def test_style_cannot_change_first_line():
    explanation = "Это уверенный шаг. Сохраняй курс и усиливай дисциплину."
    for mode, custom in (("default", ""), ("bold", ""), ("stoic", ""), ("custom", "сержант")):
        styled = style_explanation(explanation, style_mode=mode, custom_style=custom)
        reply = build_final_reply("positive", styled)
        assert reply.splitlines()[0] == "Марк Аврелий доволен тобой."


def test_empty_explanation_gets_fallback():
    reply = build_final_reply("negative", "")
    assert "Мысль слишком пустая и сырая" in reply


def test_garbage_structured_output_uses_deterministic_fallback():
    class BrokenJudge(StoicJudge):
        def _openrouter_reply(self, user_text, style_mode, custom_style):
            return None

    judge = BrokenJudge()
    reply = judge.evaluate("asdasd lol", style_mode="default", custom_style="")
    assert reply.startswith("Марк Аврелий недоволен тобой.")


def test_est_hleb_returns_fixed_verdict_line():
    verdict, explanation = analyze_idea_fallback("есть хлеб")
    reply = build_final_reply(verdict, explanation)
    assert reply.splitlines()[0] in {
        "Марк Аврелий доволен тобой.",
        "Марк Аврелий недоволен тобой.",
    }


def test_konki_returns_fixed_verdict_line():
    verdict, explanation = analyze_idea_fallback("хочу кататься на коньках")
    reply = build_final_reply(verdict, explanation)
    assert reply.splitlines()[0] in {
        "Марк Аврелий доволен тобой.",
        "Марк Аврелий недоволен тобой.",
    }
