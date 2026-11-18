"""StoreKeyManager: the provisioner saves keys straight into a key store (CSV default, k3s optional)."""

import logging

import pytest
from sdm_provisioner.store_key_manager import KeyStoreError, StoreKeyManager

from ntag_keys import CsvSecretStore, MemorySecretStore, TagSecret
from shared import UID, TagKeys

UID_HEX = "04B7664A2F7080"
FACTORY = "0" * 32


@pytest.fixture
def csv_path(tmp_path):
    return tmp_path / "tag_keys.csv"


@pytest.fixture
def km(csv_path):
    return StoreKeyManager(CsvSecretStore(csv_path))


def test_unknown_tag_has_factory_keys(km):
    keys = km.get_tag_keys(UID(UID_HEX))
    assert keys.status == "factory"
    assert keys.sdm_mac_key == FACTORY
    assert km.get_key(UID(UID_HEX), 3) == b"\x00" * 16


def test_generate_saves_keys_into_the_store_before_returning(km, csv_path):
    keys = km.generate_random_keys(UID(UID_HEX))
    secret = CsvSecretStore(csv_path).get_key(UID_HEX)
    assert (secret.k0, secret.k1, secret.k3) == (keys.picc_master_key, keys.app_read_key, keys.sdm_mac_key)
    assert len({keys.picc_master_key, keys.app_read_key, keys.sdm_mac_key}) == 3
    assert FACTORY not in (keys.picc_master_key, keys.sdm_mac_key)


def test_keys_come_back_as_bytes_per_key_number(km):
    keys = km.generate_random_keys(UID(UID_HEX))
    assert km.get_key(UID(UID_HEX), 0) == bytes.fromhex(keys.picc_master_key)
    assert km.get_key(UID(UID_HEX), 1) == bytes.fromhex(keys.app_read_key)
    assert km.get_key(UID(UID_HEX), 3) == bytes.fromhex(keys.sdm_mac_key)
    assert km.get_key(UID(UID_HEX), 2) == b"\x00" * 16
    with pytest.raises(ValueError):
        km.get_key(UID(UID_HEX), 5)


def test_provision_tag_two_phase_and_resume_reuses_stored_keys(csv_path):
    km1 = StoreKeyManager(CsvSecretStore(csv_path))
    with km1.provision_tag(UID(UID_HEX)) as staged:
        first = staged.sdm_mac_key
        assert staged.status == "pending"
    # new process, same store: resume gets the same keys (no new ones generated)
    km2 = StoreKeyManager(CsvSecretStore(csv_path))
    with km2.provision_tag(UID(UID_HEX), url="https://x.example/?uid") as staged:
        assert staged.sdm_mac_key == first
    assert km2.get_tag_keys(UID(UID_HEX)).status == "active"


def test_failed_provisioning_keeps_the_keys_for_resume(csv_path):
    km = StoreKeyManager(CsvSecretStore(csv_path))
    with pytest.raises(RuntimeError), km.provision_tag(UID(UID_HEX)) as staged:
        first = staged.sdm_mac_key
        raise RuntimeError("card removed")
    with km.provision_tag(UID(UID_HEX)) as staged:
        assert staged.sdm_mac_key == first


def test_store_failure_is_reported_before_the_tag_is_touched(tmp_path):
    bad = CsvSecretStore(tmp_path / "gone" / "keys.csv", create_dirs=False)
    km = StoreKeyManager(bad)
    entered = False
    with pytest.raises(KeyStoreError) as e, km.provision_tag(UID(UID_HEX)):
        entered = True
    assert not entered
    assert "CsvSecretStore" in str(e.value) and "gone" in str(e.value)


def test_keys_never_appear_in_logs(km, caplog):
    caplog.set_level(logging.DEBUG)
    keys = km.generate_random_keys(UID(UID_HEX))
    km.save_tag_keys(keys)
    km.get_tag_keys(UID(UID_HEX))
    text = caplog.text.upper()
    assert keys.sdm_mac_key not in text and keys.picc_master_key not in text and keys.app_read_key not in text


def test_store_holds_only_tag_data_no_coin_or_side(km, csv_path):
    km.generate_random_keys(UID(UID_HEX))
    header = csv_path.read_text().splitlines()[0].lower()
    assert "coin" not in header and "outcome" not in header and "heads" not in header
    assert not hasattr(km, "assign_coin_name") and not hasattr(km, "get_next_coin_assignment")
    assert not hasattr(TagKeys.from_factory_keys(UID(UID_HEX)), "coin_name")


def test_validate_sdm_url_uses_stored_k3(km):
    from tag_validator.crypto.cmac_engine import calculate_sdm_cmac

    keys = km.generate_random_keys(UID(UID_HEX))
    cmac = calculate_sdm_cmac(UID_HEX, 3, keys.sdm_mac_key)
    assert km.validate_sdm_url(UID(UID_HEX), 3, cmac)["valid"] is True
    assert km.validate_sdm_url(UID(UID_HEX), 3, "0" * 16)["valid"] is False


def test_list_delete_undelete(km):
    km.generate_random_keys(UID(UID_HEX))
    assert [t.uid.uid for t in km.list_tags()] == [UID_HEX]
    assert km.delete_key(UID_HEX) is True
    assert km.get_tag_keys(UID(UID_HEX)).status == "factory"
    assert km.undelete_key(UID_HEX) is True


def test_changed_keys_for_a_stored_tag_are_refused_with_a_clear_message(km):
    km.generate_random_keys(UID(UID_HEX))
    other = TagKeys(uid=UID(UID_HEX), picc_master_key="1" * 32, app_read_key="2" * 32, sdm_mac_key="3" * 32)
    with pytest.raises(KeyStoreError, match="immutable"):
        km.save_tag_keys(other)


def test_persistence_flag_distinguishes_memory(csv_path):
    assert StoreKeyManager(CsvSecretStore(csv_path)).is_persistent is True
    assert StoreKeyManager(MemorySecretStore()).is_persistent is False


def test_from_env_defaults_to_csv(monkeypatch, tmp_path):
    monkeypatch.delenv("NTAG_KEY_STORE", raising=False)
    monkeypatch.setenv("NTAG_KEY_CSV", str(tmp_path / "k.csv"))
    km = StoreKeyManager.from_env()
    assert isinstance(km.store, CsvSecretStore) and km.location.endswith("k.csv")


def test_from_env_rejects_unknown_store(monkeypatch):
    monkeypatch.setenv("NTAG_KEY_STORE", "sqlite")
    with pytest.raises(ValueError, match="NTAG_KEY_STORE"):
        StoreKeyManager.from_env()


def test_secret_roundtrip_uses_tagsecret_layout(km, csv_path):
    km.generate_random_keys(UID(UID_HEX))
    s = CsvSecretStore(csv_path).get_key(UID_HEX)
    assert isinstance(s, TagSecret) and s.status == "active"
