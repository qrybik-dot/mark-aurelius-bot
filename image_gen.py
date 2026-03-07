import re
from urllib.parse import quote

from config import settings

IMAGE_TRIGGERS = [
    "нарисуй",
    "изобрази",
    "сгенерируй",
    "покажи",
    "нагенерируй",
]

_IMAGE_BACKENDS = {
    "pollinations": {
        "endpoint": "https://image.pollinations.ai/prompt",
        "params": "width=1024&height=1024&nologo=true",
    },
    "pollinations_flux": {
        "endpoint": "https://image.pollinations.ai/prompt",
        "params": "width=768&height=768&model=flux&nologo=true",
    },
}


_RU_IMAGE_HINTS = {
    "кофе": "a cup of coffee",
    "кофейня": "cozy coffee shop interior",
    "хлеб": "fresh bread loaf",
    "солнце": "bright sun in the sky",
    "круг": "simple geometric circle on clean background",
    "картина": "artistic painting",
    "философ": "ancient philosopher portrait",
    "император": "ancient roman emperor portrait",
    "парашютист": "skydiver in freefall",
    "стоик": "stoic philosopher portrait",
    "небо": "dramatic sky",
    "облака": "clouds in the sky",
}


def _configured_image_backends() -> list[str]:
    primary = settings.image_backend_primary or "pollinations"
    backup = settings.image_backend_backup or "pollinations_flux"
    backends = [primary, backup]
    deduped: list[str] = []
    for backend in backends:
        if backend and backend in _IMAGE_BACKENDS and backend not in deduped:
            deduped.append(backend)
    if not deduped:
        deduped = ["pollinations", "pollinations_flux"]
    return deduped


def is_image_request(text: str) -> bool:
    normalized = text.strip().lower()
    return any(re.match(rf"^{trigger}\b", normalized) for trigger in IMAGE_TRIGGERS)


def extract_image_prompt(text: str) -> str:
    normalized = text.strip()
    for trigger in IMAGE_TRIGGERS:
        pattern = re.compile(rf"^{trigger}\b", re.IGNORECASE)
        if pattern.search(normalized):
            return pattern.sub("", normalized, count=1).strip(" :,-")
    return ""


def normalize_image_prompt(prompt_raw: str) -> str:
    source = (prompt_raw or "").strip()
    if not source:
        return ""
    lowered = source.lower()
    for key, value in _RU_IMAGE_HINTS.items():
        if key in lowered:
            return value
    return source


def build_image_prompt(prompt_raw: str) -> str:
    normalized = normalize_image_prompt(prompt_raw)
    if not normalized:
        return ""
    return f"{normalized}, highly detailed, clean composition"


def _build_backend_url(prompt_en: str, backend: str) -> str:
    safe_prompt = quote(prompt_en.strip())
    cfg = _IMAGE_BACKENDS[backend]
    return f"{cfg['endpoint']}/{safe_prompt}?{cfg['params']}"


def build_image_request_candidates(prompt_en: str) -> list[dict[str, str]]:
    if not prompt_en:
        return []

    candidates: list[dict[str, str]] = []
    for backend in _configured_image_backends():
        candidates.append(
            {
                "backend": backend,
                "mode": "url",
                "url": _build_backend_url(prompt_en, backend),
            }
        )
    return candidates


def build_image_url_primary(prompt_en: str) -> str:
    return _build_backend_url(prompt_en, "pollinations")


def build_image_url_fallback(prompt_en: str) -> str:
    return _build_backend_url(prompt_en, "pollinations_flux")
