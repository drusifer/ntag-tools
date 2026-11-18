"""Test: Provisioning Service Hardware Safety Rules

Validates that ProvisioningService strictly enforces real persistent StoreKeyManager
when interacting with real hardware HAL, and that simulation flags allow mock/test managers.
"""
import os
from unittest.mock import MagicMock

import pytest

from ntag_keys import CsvSecretStore, MemorySecretStore
from sdm_provisioner.hal import NTag424CardConnection
from sdm_provisioner.store_key_manager import StoreKeyManager
from sdm_provisioner.services.provisioning_service import ProvisioningService


def test_hardware_with_service_key_manager_initializes_cleanly():
    """Verify that real hardware HAL card (is_simulation=False) initializes cleanly with StoreKeyManager."""
    card = MagicMock(spec=NTag424CardConnection)
    card.is_simulation = False

    service_km = MagicMock(spec=StoreKeyManager)

    # Must not raise NameError (missing os) or RuntimeError (invalid key store)
    service = ProvisioningService(card=card, key_mgr=service_km)
    assert service.key_mgr is service_km


def test_hardware_with_csv_key_store_is_allowed(tmp_path):
    """A persistent CSV key store is a valid store for real hardware."""
    card = MagicMock(spec=NTag424CardConnection)
    card.is_simulation = False
    km = StoreKeyManager(CsvSecretStore(tmp_path / "keys.csv"))
    assert ProvisioningService(card=card, key_mgr=km).key_mgr is km


def test_hardware_with_memory_key_store_raises_runtime_error():
    """Real hardware must never be attached to a store that forgets keys."""
    card = MagicMock(spec=NTag424CardConnection)
    card.is_simulation = False
    with pytest.raises(RuntimeError, match="CRITICAL HARDWARE KEY SAFETY RULE"):
        ProvisioningService(card=card, key_mgr=StoreKeyManager(MemorySecretStore()))


def test_hardware_with_non_store_manager_raises_runtime_error():
    card = MagicMock(spec=NTag424CardConnection)
    card.is_simulation = False
    with pytest.raises(RuntimeError, match="CRITICAL HARDWARE KEY SAFETY RULE"):
        ProvisioningService(card=card, key_mgr=MagicMock())


def test_simulation_flag_allows_mock_key_manager():
    """Verify that setting is_simulation=True allows non-StoreKeyManager."""
    card = MagicMock(spec=NTag424CardConnection)
    card.is_simulation = True

    mock_km = MagicMock()
    service = ProvisioningService(card=card, key_mgr=mock_km)
    assert service.key_mgr is mock_km


def test_env_simulation_flag_allows_mock_key_manager(monkeypatch):
    """Verify that setting NTAG_SIMULATION=1 in environment allows non-StoreKeyManager even if card.is_simulation is False."""
    card = MagicMock(spec=NTag424CardConnection)
    card.is_simulation = False

    monkeypatch.setenv("NTAG_SIMULATION", "1")
    mock_km = MagicMock()
    service = ProvisioningService(card=card, key_mgr=mock_km)
    assert service.key_mgr is mock_km
