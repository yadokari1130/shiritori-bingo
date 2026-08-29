import pytest

from app.limiter import limiter


@pytest.fixture(autouse=True)
def disable_rate_limits_for_tests():
    """テスト実行時は各テストでのレートリミット誤発火を防ぐためデフォルト無効化し、終了後に戻す。"""
    original_enabled = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original_enabled
