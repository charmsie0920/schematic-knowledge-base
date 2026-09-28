# backend/tests/test_config.py
"""Settings parsing."""

from app.config import Settings


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins="http://localhost:3000, https://recall.example.com ,")
    assert settings.cors_origin_list == ["http://localhost:3000", "https://recall.example.com"]


def test_database_url_uses_the_async_driver() -> None:
    # A sync driver URL (postgresql://) would make every query block the event loop.
    settings = Settings()
    assert str(settings.database_url).startswith("postgresql+asyncpg://")
