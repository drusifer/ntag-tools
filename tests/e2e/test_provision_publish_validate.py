"""End to end: provision a simulated tag, publish its keys, validate its taps.

The provisioner (StoreKeyManager over a CSV key store) writes the keys. A separate validator
instance in validate-only mode reads the same file, like the sidecar reading k3s Secrets. The tap
CMAC is computed here from the NXP SDM recipe with pycryptodome, independently of the validator
code, so a disagreement between provisioner and validator about key layout or CMAC fails here.

Note: the simulated tag decrypts every ChangeKey with a fixed command counter, so it reproduces
keys 0 and 1 faithfully but not key 3; the K3 link is therefore proven through the store.
"""

import csv
import io
import json

import pytest
from Crypto.Cipher import AES
from Crypto.Hash import CMAC
from sdm_provisioner.sequence_logger import create_sequence_logger
from sdm_provisioner.seritag_simulator import SeritagCardManager
from sdm_provisioner.services.provisioning_service import ProvisioningService
from sdm_provisioner.store_key_manager import StoreKeyManager
from tag_validator.api.app import create_app

from ntag_keys import CsvSecretStore


def tag_tap_cmac(uid_hex: str, counter: int, k3_hex: str) -> str:
    """What the tag computes for an SDM URL (NXP AN12196), independent of the validator's code."""
    sv2 = bytes.fromhex("3CC300010080") + bytes.fromhex(uid_hex) + counter.to_bytes(3, "little")
    session_key = CMAC.new(bytes.fromhex(k3_hex), msg=sv2, ciphermod=AES).digest()
    msg = f"{uid_hex}&ctr={counter:06X}&cmac=".encode()
    full = CMAC.new(session_key, msg=msg, ciphermod=AES).digest()
    return bytes(full[i] for i in range(1, 16, 2)).hex().upper()


def call(app, method, path, body=None, query=""):
    raw = json.dumps(body).encode() if body is not None else b""
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)), "CONTENT_TYPE": "application/json",
        "wsgi.input": io.BytesIO(raw),
    }
    status = {}
    out = app(environ, lambda s, h, *a: status.update(code=int(s.split()[0])))
    data = b"".join(out)
    return status["code"], (json.loads(data) if data else {})


@pytest.fixture
def world(tmp_path):
    path = tmp_path / "tag_keys.csv"
    km = StoreKeyManager(CsvSecretStore(path))
    mgr = SeritagCardManager(create_sequence_logger("e2e"), key_store=km)
    with mgr as card:
        svc = ProvisioningService(card, km)
        assert svc.provision_keys() is True
        assert svc.provision_url("https://flip.example/tap") is True
    uid = mgr.simulator.state.uid.hex().upper()
    validator = create_app(store=CsvSecretStore(path), mode="validate")  # a separate reader
    return {"path": path, "uid": uid, "tag": mgr.simulator.state, "validator": validator, "km": km}


def tap(world, counter, **extra):
    k3 = CsvSecretStore(world["path"]).get_key(world["uid"]).k3
    return {"uid": world["uid"], "counter": counter, "cmac": tag_tap_cmac(world["uid"], counter, k3), **extra}


def test_published_keys_are_the_keys_on_the_tag(world):
    s = CsvSecretStore(world["path"]).get_key(world["uid"])
    assert s.status == "active"
    assert s.k0 == world["tag"].factory_keys[0].hex().upper()
    assert s.k1 == world["tag"].factory_keys[1].hex().upper()
    assert "0" * 32 not in (s.k0, s.k1, s.k3)


def test_genuine_tap_is_accepted(world):
    code, body = call(world["validator"], "POST", "/api/v1/validate", tap(world, 5))
    assert code == 200 and body["valid"] is True


def test_replayed_counter_is_rejected_when_consuming(world):
    first = call(world["validator"], "POST", "/api/v1/validate", tap(world, 9, consume=True))[1]
    again = call(world["validator"], "POST", "/api/v1/validate", tap(world, 9, consume=True))[1]
    assert first["valid"] is True and first["consumed"] is True
    assert again["valid"] is False and again["reason"] == "replayed"


def test_forged_cmac_is_rejected_and_does_not_burn_the_counter(world):
    forged = {**tap(world, 12, consume=True), "cmac": "0123456789ABCDEF"}
    assert call(world["validator"], "POST", "/api/v1/validate", forged)[1]["valid"] is False
    assert call(world["validator"], "POST", "/api/v1/validate", tap(world, 12, consume=True))[1]["valid"] is True


def test_a_cmac_made_with_the_wrong_key_is_rejected(world):
    wrong = {**tap(world, 3), "cmac": tag_tap_cmac(world["uid"], 3, "AB" * 16)}
    assert call(world["validator"], "POST", "/api/v1/validate", wrong)[1]["valid"] is False


def test_the_provisioner_and_validator_agree_on_the_same_tap(world):
    t = tap(world, 21)
    assert world["km"].validate_sdm_url(world["uid"], 21, t["cmac"])["valid"] is True
    assert call(world["validator"], "POST", "/api/v1/validate", t)[1]["valid"] is True


def test_validate_only_validator_cannot_be_asked_for_keys(world):
    k = CsvSecretStore(world["path"]).get_key(world["uid"])
    for method, path, qs in [
        ("GET", "/api/v1/keys", "raw=true"), ("GET", f"/api/v1/keys/{world['uid']}", "raw=true"),
        ("POST", "/api/v1/keys/generate", ""),
    ]:
        code, body = call(world["validator"], method, path, {}, qs)
        assert code == 404 and k.k3 not in json.dumps(body).upper()


def test_key_file_layout_is_the_documented_one(world):
    with open(world["path"], newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["uid", "k0", "k1", "k3", "status", "created_at", "deleted_at"]
    assert rows[0]["uid"] == world["uid"]


def test_a_hand_written_key_file_in_that_layout_is_validated(tmp_path):
    uid, k3 = "04AABBCCDDEEFF", "00112233445566778899AABBCCDDEEFF"
    path = tmp_path / "keys.csv"
    path.write_text(f"uid,k0,k1,k3,status,created_at,deleted_at\n{uid},{'1' * 32},{'2' * 32},{k3},active,2026-11-17T00:00:00+00:00,\n")
    app = create_app(store=CsvSecretStore(path), mode="validate")
    t = {"uid": uid, "counter": 1, "cmac": tag_tap_cmac(uid, 1, k3)}
    assert call(app, "POST", "/api/v1/validate", t)[1]["valid"] is True
