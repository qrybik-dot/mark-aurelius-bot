import re
from urllib.parse import quote

IMAGE_TRIGGERS = [
    "нарисуй",
    "изобрази",
    "сгенерируй",
    "покажи",
    "нагенерируй",
]

PRIMARY_IMAGE_ENDPOINT = "https://image.pollinations.ai/prompt"
FALLBACK_IMAGE_ENDPOINT = "https://image.pollinations.ai/prompt"


_RU_IMAGE_HINTS = {
    "кофе": "a cup of coffee",
    "кофейня": "cozy coffee shop interior",
    "хлеб": "fresh bread loaf",
    "солнце": "bright sun in the sky",
    "круг": "simple geometric circle on clean background",
    "философ": "ancient philosopher portrait",
    "парашютист": "skydiver in freefall",
}


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


def build_image_url_primary(prompt_en: str) -> str:
    safe_prompt = quote(prompt_en.strip())
    return f"{PRIMARY_IMAGE_ENDPOINT}/{safe_prompt}?width=1024&height=1024&nologo=true"


def build_image_url_fallback(prompt_en: str) -> str:
    safe_prompt = quote(prompt_en.strip())
    return f"{FALLBACK_IMAGE_ENDPOINT}/{safe_prompt}?width=768&height=768&model=flux&nologo=true"
