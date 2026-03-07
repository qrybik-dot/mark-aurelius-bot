import re
from urllib.parse import quote

IMAGE_TRIGGERS = [
    "нарисуй",
    "изобрази",
    "сгенерируй",
    "покажи",
    "нагенерируй",
]


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


_RU_IMAGE_HINTS = {
    "солнце": "sun in the sky",
    "кофе": "cup of coffee",
    "кофейня": "cozy coffee shop",
    "хлеб": "fresh bread loaf",
    "булка": "fresh bakery bun",
    "стоик": "stoic philosopher portrait",
    "философ": "ancient philosopher portrait",
    "парашютист": "skydiver in freefall",
    "император": "roman emperor portrait",
    "рим": "ancient rome cityscape",
    "облака": "dramatic clouds in the sky",
}


def build_image_prompt(prompt_raw: str) -> str:
    source = prompt_raw.strip()
    lowered = source.lower()

    mapped = next((value for key, value in _RU_IMAGE_HINTS.items() if key in lowered), source)
    enhanced = mapped if mapped else source
    return f"{enhanced}, highly detailed, cinematic, dramatic lighting, clean composition"


def generate_image_url(prompt_en: str) -> str:
    return build_pollinations_url(prompt_en)


def build_pollinations_url(prompt: str) -> str:
    safe_prompt = quote(prompt.strip())
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
