import importlib
import importlib.util
import os
from dataclasses import dataclass, field


def _load_local_dotenv() -> None:
    if importlib.util.find_spec("dotenv") is None:
        return

    dotenv = importlib.import_module("dotenv")
    dotenv.load_dotenv()


_load_local_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    telegram_bot_username: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@"))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", "").strip())
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/"))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openrouter/free").strip())
    openrouter_model_primary: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL_PRIMARY", "").strip()
    )
    openrouter_model_backup: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL_BACKUP", "").strip()
    )
    image_backend_primary: str = field(default_factory=lambda: os.getenv("IMAGE_BACKEND_PRIMARY", "").strip())
    image_backend_backup: str = field(default_factory=lambda: os.getenv("IMAGE_BACKEND_BACKUP", "").strip())
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "10000")))

    def webhook_url(self) -> str:
        base = self.public_base_url.rstrip("/")
        return f"{base}/webhook/{self.webhook_secret}"


settings = Settings()


def validate_settings() -> list[str]:
    missing: list[str] = []

    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")

    if not settings.telegram_bot_username:
        missing.append("TELEGRAM_BOT_USERNAME")

    return missing
