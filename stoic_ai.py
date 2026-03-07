import json
import logging
import re
from typing import Optional

from config import settings
from prompts import STYLE_INSTRUCTIONS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FALLBACK_EXPLANATIONS = {
    "positive": (
        "В этом есть движение и польза. Лучше действовать осмысленно, "
        "чем разлагаться в пустых желаниях."
    ),
    "negative": (
        "Это звучит слабо и без внутреннего стержня. "
        "Выбери не самое простое, а самое достойное."
    ),
    "empty": "Мысль слишком пустая и сырая. Сформулируй её ясно, если хочешь честный суд.",
}

VERDICT_LINES = {
    "positive": "Марк Аврелий доволен тобой.",
    "negative": "Марк Аврелий недоволен тобой.",
}

RESPONSE_SCHEMA = {
    "name": "stoic_verdict",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["positive", "negative"]},
            "explanation": {"type": "string"},
        },
        "required": ["verdict", "explanation"],
        "additionalProperties": False,
    },
}


def _candidate_models() -> list[str]:
    models: list[str] = []

    configured_primary = settings.openrouter_model_primary
    configured_backup = settings.openrouter_model_backup

    if configured_primary:
        primary = configured_primary
    elif settings.openrouter_model and settings.openrouter_model != "openrouter/free":
        primary = settings.openrouter_model
    else:
        primary = ""

    backup = configured_backup or "openrouter/free"

    if primary:
        models.append(primary)
    if backup:
        models.append(backup)
    if "openrouter/free" not in models:
        models.append("openrouter/free")

    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def normalize_explanation(explanation: str) -> str:
    text = re.sub(r"\s+", " ", (explanation or "").strip())
    if not text:
        return ""

    has_cyrillic = bool(re.search(r"[А-Яа-яЁё]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if not has_cyrillic or latin_count > 12:
        return ""

    sentence_count = len([part for part in re.split(r"[.!?]+", text) if part.strip()])
    if sentence_count < 2:
        return ""

    if len(text) > 500:
        text = text[:500].rstrip(" ,;:-") + "."

    return text


def style_explanation(explanation: str, style_mode: str = "default", custom_style: str = "") -> str:
    base = explanation.strip()
    if style_mode == "stoic":
        first_sentence = re.split(r"(?<=[.!?])\s+", base)[0].strip()
        return first_sentence or base
    if style_mode == "bold":
        return f"Сурово, но честно: {base}"
    if style_mode == "custom" and custom_style:
        return f"Стиль «{custom_style}»: {base}"
    return base


def build_final_reply(verdict: str, explanation: str) -> str:
    verdict_key = verdict if verdict in VERDICT_LINES else "negative"
    cleaned_explanation = normalize_explanation(explanation)
    if not cleaned_explanation:
        cleaned_explanation = (
            FALLBACK_EXPLANATIONS["empty"]
            if not (explanation or "").strip()
            else FALLBACK_EXPLANATIONS[verdict_key]
        )
    return f"{VERDICT_LINES[verdict_key]}\n\n{cleaned_explanation}"


def build_system_prompt(style_mode: str = "default", custom_style: str = "") -> list[dict[str, str]]:
    style_layer = STYLE_INSTRUCTIONS.get(style_mode, STYLE_INSTRUCTIONS["default"])
    if style_mode == "custom" and custom_style:
        style_layer = (
            "Манера объяснения: "
            f"{custom_style}. Держи объяснение читабельным, коротким и безопасным."
        )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": style_layer},
    ]


def analyze_idea_fallback(user_text: str) -> tuple[str, str]:
    text = (user_text or "").strip().lower()
    if not text:
        return "negative", FALLBACK_EXPLANATIONS["empty"]

    words = re.findall(r"[а-яёa-z]+", text)
    if len(words) < 2:
        return "negative", FALLBACK_EXPLANATIONS["empty"]

    negative_markers = [
        "вред",
        "груб",
        "лень",
        "пуст",
        "слаб",
        "бессодерж",
        "мст",
        "прокраст",
        "злост",
        "оскорб",
    ]
    positive_markers = [
        "развит",
        "действ",
        "спорт",
        "дело",
        "решени",
        "учеб",
        "трен",
        "работ",
        "дисциплин",
        "коньк",
    ]

    neg_score = sum(marker in text for marker in negative_markers)
    pos_score = sum(marker in text for marker in positive_markers)

    if neg_score > 0 and neg_score >= pos_score:
        return "negative", FALLBACK_EXPLANATIONS["negative"]
    if pos_score > neg_score:
        return "positive", FALLBACK_EXPLANATIONS["positive"]
    return "negative", FALLBACK_EXPLANATIONS["empty"]


class StoicJudge:
    def analyze_deterministic(self, user_text: str) -> tuple[str, str]:
        return analyze_idea_fallback(user_text)

    def render_final(self, verdict: str, explanation: str, style_mode: str = "default", custom_style: str = "") -> str:
        styled = style_explanation(explanation, style_mode=style_mode, custom_style=custom_style)
        return build_final_reply(verdict, styled)

    def evaluate(self, user_text: str, style_mode: str = "default", custom_style: str = "") -> str:
        model_result = self._openrouter_reply(user_text, style_mode, custom_style)
        if model_result is None:
            logger.warning("Falling back to deterministic analyzer")
            verdict, explanation = analyze_idea_fallback(user_text)
        else:
            verdict, explanation = model_result

        return self.render_final(verdict, explanation, style_mode=style_mode, custom_style=custom_style)

    def _openrouter_reply(
        self, user_text: str, style_mode: str, custom_style: str
    ) -> Optional[tuple[str, str]]:
        if not settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY не задан, включаю fallback")
            return None

        try:
            import requests
        except Exception as exc:
            logger.warning("requests недоступен (%s), включаю fallback", exc)
            return None

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        for model_name in _candidate_models():
            logger.info("Trying text model: %s", model_name)
            payload = {
                "model": model_name,
                "messages": [
                    *build_system_prompt(style_mode, custom_style),
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
                "seed": 42,
                "response_format": {"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
            }

            try:
                response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=20)
                if response.status_code in (401, 402, 403, 429, 500, 502, 503, 504):
                    logger.warning("Text model failed: %s", model_name)
                    continue
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = json.loads(content)
                verdict = parsed.get("verdict")
                explanation = parsed.get("explanation", "")
                if verdict not in {"positive", "negative"}:
                    logger.warning("Structured output invalid for model: %s", model_name)
                    continue
                if not isinstance(explanation, str):
                    logger.warning("Structured output invalid for model: %s", model_name)
                    continue
                return verdict, explanation
            except (requests.Timeout, requests.RequestException):
                logger.warning("Text model failed: %s", model_name)
                continue
            except (ValueError, KeyError, IndexError, json.JSONDecodeError):
                logger.warning("Structured output invalid for model: %s", model_name)
                continue

        return None
