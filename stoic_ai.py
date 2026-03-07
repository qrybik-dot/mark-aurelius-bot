import logging
import random
from typing import Optional

from config import settings
from prompts import OPENING_VARIANTS, STYLE_INSTRUCTIONS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class StoicJudge:
    def evaluate(self, user_text: str, style_mode: str = "default", custom_style: str = "") -> str:
        ai_reply = self._openrouter_reply(user_text, style_mode, custom_style)
        if ai_reply:
            return ai_reply
        return self._fallback_reply(user_text, style_mode)

    def _style_layer(self, style_mode: str, custom_style: str) -> str:
        if style_mode == "custom" and custom_style:
            return f"Желаемый стиль ответа от пользователя: {custom_style}. Соблюдай его бережно и без мата."
        return STYLE_INSTRUCTIONS.get(style_mode, STYLE_INSTRUCTIONS["default"])

    def _openrouter_reply(self, user_text: str, style_mode: str, custom_style: str) -> Optional[str]:
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
        payload = {
            "model": settings.openrouter_model or "openrouter/free",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": self._style_layer(style_mode, custom_style)},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.8,
            "max_tokens": 220,
        }

        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=20)
            if response.status_code in (401, 402, 403, 429, 500, 502, 503, 504):
                logger.warning("OpenRouter недоступен, код=%s", response.status_code)
                return None
            response.raise_for_status()
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return content or None
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            logger.warning("Ошибка запроса к OpenRouter: %s", exc)
            return None

    def _fallback_reply(self, user_text: str, style_mode: str = "default") -> str:
        text = user_text.lower()
        good_markers = ["спорт", "читать", "учёб", "учеб", "дисциплин", "работ", "помог", "сон"]
        bad_markers = ["мст", "лень", "вран", "завист", "злост", "алкогол", "прокраст", "измен"]

        score = sum(marker in text for marker in good_markers) - sum(
            marker in text for marker in bad_markers
        )

        if score >= 0:
            verdict = "Марк Аврелий доволен тобой."
            reason = (
                "Ты хотя бы пытаешься управлять собой, а не погодой в голове. "
                "Это уже редкость в эпоху импульсивных подвигов и ленивых оправданий. "
                "Продолжай: достоинство растёт от повторения, а не от красивых обещаний."
            )
        else:
            verdict = "Марк Аврелий недоволен тобой."
            reason = (
                "Ты снова назначил эмоции полководцами, а разум — писарем на побегушках. "
                "Так справедливость к себе не строят, так строят хаос с самоиронией. "
                "Соберись: свобода начинается там, где заканчиваются удобные отговорки."
            )

        if style_mode == "bold":
            opener = random.choice(OPENING_VARIANTS)
            return f"{opener}\n\n{verdict}\n\n{reason}"
        if style_mode == "stoic":
            return f"{verdict}\n\n{reason.split('. ')[0].strip()}."
        if style_mode == "custom":
            return f"{verdict}\n\n{reason}"
        return f"{verdict}\n\n{reason}"
