from types import SimpleNamespace

from stoic_ai import StoicJudge, _candidate_models, analyze_idea_fallback, build_final_reply, style_explanation


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


def test_invalid_model_output_uses_deterministic_fallback():
    class BrokenJudge(StoicJudge):
        def _openrouter_reply(self, user_text, style_mode, custom_style):
            return None

    judge = BrokenJudge()
    reply = judge.evaluate("asdasd lol", style_mode="default", custom_style="")
    assert reply.startswith("Марк Аврелий недоволен тобой.")


def test_primary_fail_backup_ok(monkeypatch):
    from stoic_ai import OPENROUTER_URL
    import stoic_ai

    monkeypatch.setattr(
        stoic_ai,
        "settings",
        SimpleNamespace(
            openrouter_api_key="k",
            openrouter_model="openai/gpt-4o-mini",
            openrouter_model_primary="openai/gpt-4o-mini",
            openrouter_model_backup="openrouter/free",
        ),
    )

    calls = []

    class _Resp:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("bad")

        def json(self):
            return self._payload

    def fake_post(url, headers, json, timeout):
        assert url == OPENROUTER_URL
        model = json["model"]
        calls.append(model)
        if len(calls) == 1:
            return _Resp(status_code=429)
        return _Resp(
            payload={
                "choices": [
                    {
                        "message": {
                            "content": '{"verdict":"positive","explanation":"Это достойно. Продолжай действовать."}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    judge = StoicJudge()
    reply = judge.evaluate("хочу учиться")
    assert calls == ["openai/gpt-4o-mini", "openrouter/free"]
    assert reply.startswith("Марк Аврелий доволен тобой.")


def test_primary_and_backup_fail_use_deterministic(monkeypatch):
    import stoic_ai

    monkeypatch.setattr(
        stoic_ai,
        "settings",
        SimpleNamespace(
            openrouter_api_key="k",
            openrouter_model="",
            openrouter_model_primary="model/primary",
            openrouter_model_backup="model/backup",
        ),
    )

    class _Resp:
        status_code = 429

        def raise_for_status(self):
            return None

        def json(self):
            return {}

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _Resp())

    judge = StoicJudge()
    reply = judge.evaluate("asdasd lol")
    assert reply.startswith("Марк Аврелий недоволен тобой.")


def test_candidate_models_deduplicate_and_append_free(monkeypatch):
    import stoic_ai

    monkeypatch.setattr(
        stoic_ai,
        "settings",
        SimpleNamespace(
            openrouter_model="model/legacy",
            openrouter_model_primary="model/legacy",
            openrouter_model_backup="model/backup",
        ),
    )
    assert _candidate_models() == ["model/legacy", "model/backup", "openrouter/free"]


def test_est_hleb_returns_fixed_verdict_line():
    verdict, explanation = analyze_idea_fallback("есть хлеб")
    reply = build_final_reply(verdict, explanation)
    assert reply.splitlines()[0] in {
        "Марк Аврелий доволен тобой.",
        "Марк Аврелий недоволен тобой.",
    }
