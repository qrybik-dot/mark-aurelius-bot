from config import Settings


def test_image_provider_primary_from_env(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER_PRIMARY", "cloudflare")
    cfg = Settings()
    assert cfg.image_provider_primary == "cloudflare"
