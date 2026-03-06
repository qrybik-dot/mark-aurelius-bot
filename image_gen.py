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


def build_pollinations_url(prompt: str) -> str:
    safe_prompt = quote(prompt.strip())
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
