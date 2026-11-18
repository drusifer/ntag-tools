"""Unit tests for NtagProvisionerApp wiring and key store startup."""

from unittest.mock import MagicMock

import pytest

from sdm_provisioner.store_key_manager import StoreKeyManager
from sdm_provisioner.tui.app import NtagProvisionerApp
from ntag_keys import CsvSecretStore


def test_tui_app_init_with_custom_key_manager(tmp_path):
    mock_km = MagicMock(spec=StoreKeyManager)
    mock_km.list_tags.return_value = []
    log_file = str(tmp_path / "test_tui.log")

    app = NtagProvisionerApp(log_file=log_file, key_manager=mock_km)
    assert app.key_manager is mock_km


def test_tui_app_default_uses_csv_key_store(tmp_path, monkeypatch):
    monkeypatch.delenv("NTAG_KEY_STORE", raising=False)
    monkeypatch.setenv("NTAG_KEY_CSV", str(tmp_path / "keys.csv"))
    app = NtagProvisionerApp(log_file=str(tmp_path / "test_tui.log"))
    assert isinstance(app.key_manager, StoreKeyManager)
    assert isinstance(app.key_manager.store, CsvSecretStore)


def test_tui_app_unknown_key_store_fails_with_message(tmp_path, monkeypatch):
    monkeypatch.setenv("NTAG_KEY_STORE", "sqlite")
    with pytest.raises(ValueError, match="NTAG_KEY_STORE"):
        NtagProvisionerApp(log_file=str(tmp_path / "test_tui.log"))
