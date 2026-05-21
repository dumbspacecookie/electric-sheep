import os
import tempfile
from pathlib import Path

import pytest

from electric_sheep.core import db


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    path = tmp_path / "arcade.db"
    monkeypatch.setenv("ELECTRIC_SHEEP_DB", str(path))
    db.reset_db_path_for_tests(path)
    db.init_db()
    yield
    db.reset_db_path_for_tests(None)


@pytest.fixture
def night(monkeypatch):
    monkeypatch.setenv("ELECTRIC_SHEEP_NOW", "2026-05-20T22:00:00Z")
    yield


@pytest.fixture
def day(monkeypatch):
    monkeypatch.setenv("ELECTRIC_SHEEP_NOW", "2026-05-20T10:00:00Z")
    yield
