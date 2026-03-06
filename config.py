import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_bot_username: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_USERNAME", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", ""))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openrouter/free"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "10000")))

    def webhook_url(self) -> str:
        base = self.public_base_url.rstrip("/")
        return f"{base}/webhook/{self.webhook_secret}"


settings = Settings()
