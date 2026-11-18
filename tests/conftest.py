# tests/conftest.py
"""Keep every test offline: no real DNS lookups and no real emails"""

import pytest

from backend.src.config.settings import settings

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(settings, "check_email_domain", False)
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_from", "")
