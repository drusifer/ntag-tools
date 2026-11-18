"""CSV key store: same contract as the memory store, plus persistence and safe file handling."""

import csv

import pytest

from ntag_keys import (
    CounterStoreError,
    CsvSecretStore,
    KeyConflictError,
    TagSecret,
    create_secret_store,
)

UID = "04B7664A2F7080"
K3 = "825F8399CF2CACF92232B79C406170AF"
K0 = "0123456789ABCDEF0123456789ABCDEF"
K1 = "FEDCBA9876543210FEDCBA9876543210"
OTHER = "11112222333344445555666677778888"


@pytest.fixture
def store(tmp_path):
    return CsvSecretStore(tmp_path / "tag_keys.csv")


def test_default_backend_is_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert isinstance(create_secret_store(), CsvSecretStore)


def test_unknown_backend_names_allowed_values():
    with pytest.raises(ValueError, match="csv, memory, k3s"):
        create_secret_store("nope")


def test_save_get_roundtrip_persists_across_instances(tmp_path):
    path = tmp_path / "keys.csv"
    CsvSecretStore(path).save_key(TagSecret(uid=UID, k3=K3, k0=K0, k1=K1))
    got = CsvSecretStore(path).get_key(UID)
    assert (got.uid, got.k0, got.k1, got.k3, got.status) == (UID, K0, K1, K3, "active")


def test_other_instance_sees_new_writes(tmp_path):
    path = tmp_path / "keys.csv"
    reader, writer = CsvSecretStore(path), CsvSecretStore(path)
    assert reader.get_key(UID) is None
    writer.save_key(TagSecret(uid=UID, k3=K3))
    assert reader.get_key(UID) is not None


def test_worm_rejects_different_key_but_allows_identical(store):
    store.save_key(TagSecret(uid=UID, k3=K3))
    assert store.save_key(TagSecret(uid=UID, k3=K3)) is True
    with pytest.raises(KeyConflictError):
        store.save_key(TagSecret(uid=UID, k3=OTHER))


def test_soft_delete_and_undelete(store):
    store.save_key(TagSecret(uid=UID, k3=K3))
    assert store.delete_key(UID) is True
    assert store.get_key(UID) is None
    assert store.get_key(UID, include_deleted=True).status == "deleted"
    assert store.list_uids() == []
    assert store.list_uids(include_deleted=True) == [UID]
    assert store.undelete_key(UID) is True
    assert store.get_key(UID).deleted_at is None
    assert store.delete_key("04000000000000") is False


def test_uid_lookup_normalises(store):
    store.save_key(TagSecret(uid=UID, k3=K3))
    assert store.get_key("04:b7:66:4a:2f:70:80") is not None


def test_file_has_only_tag_columns(store, tmp_path):
    store.save_key(TagSecret(uid=UID, k3=K3))
    with open(tmp_path / "tag_keys.csv", newline="") as f:
        header = next(csv.reader(f))
    assert header == ["uid", "k0", "k1", "k3", "status", "created_at", "deleted_at"]


def test_counter_consume_is_strictly_increasing_and_persists(tmp_path):
    path = tmp_path / "keys.csv"
    a = CsvSecretStore(path)
    assert a.consume_counter(UID, 5) is True
    assert a.consume_counter(UID, 5) is False
    assert a.consume_counter(UID, 4) is False
    assert CsvSecretStore(path).consume_counter(UID, 5) is False
    assert CsvSecretStore(path).consume_counter(UID, 6) is True


def test_corrupt_row_names_the_line(tmp_path):
    path = tmp_path / "keys.csv"
    path.write_text("uid,k0,k1,k3,status,created_at,deleted_at\nZZ,1,2,3,active,x,\n")
    with pytest.raises(ValueError, match=r"keys\.csv.*line 2"):
        CsvSecretStore(path).get_key(UID)


def test_unreadable_counter_file_raises_counter_error(tmp_path):
    path = tmp_path / "keys.csv"
    s = CsvSecretStore(path)
    (tmp_path / "keys.counters.csv").write_text("uid,counter\n%s,notanumber\n" % UID)
    with pytest.raises(CounterStoreError):
        s.consume_counter(UID, 1)


def test_healthy_when_directory_writable(store):
    assert store.is_healthy() is True


def test_unwritable_location_is_unhealthy_and_save_names_path(tmp_path):
    s = CsvSecretStore(tmp_path / "missing_dir" / "keys.csv", create_dirs=False)
    assert s.is_healthy() is False
    with pytest.raises(OSError, match="missing_dir"):
        s.save_key(TagSecret(uid=UID, k3=K3))


def test_k3s_without_extra_names_the_extra(monkeypatch):
    import ntag_keys.k3s_store as k

    monkeypatch.setattr(k, "K8S_AVAILABLE", False)
    with pytest.raises(ImportError, match=r"ntag-keys\[k3s\]"):
        k.K3sSecretStore()
