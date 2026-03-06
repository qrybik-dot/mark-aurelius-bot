import logging
from typing import Optional

from config import settings
from prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class StoicJudge:
    def evaluate(self, user_text: str) -> str:
        ai_reply = self._openrouter_reply(user_text)
        if ai_reply:
            return ai_reply
        return self._fallback_reply(user_text)

    def _openrouter_reply(self, user_text: str) -> Optional[str]:
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

    def _fallback_reply(self, user_text: str) -> str:
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

        return f"{verdict}\n\n{reason}"
