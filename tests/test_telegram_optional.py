from lunia_core.app.services import telegram


def test_telegram_optional_surface() -> None:
    assert hasattr(telegram, "is_available")
    assert isinstance(telegram.is_available(), bool)
    _ = telegram.reason_unavailable()
