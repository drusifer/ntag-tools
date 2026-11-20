"""No route of the validator returns key material, in any mode (Sprint 2, proposal part 4).

The sweep stores keys with a distinctive first and last 8 hex characters, calls every route the app
has, and fails if a response (body) holds a whole key or either 8-character end of one.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from tag_validator.api.app import create_app
from tag_validator.crypto.cmac_engine import calculate_sdm_cmac
from tag_validator.models import TagSecret
from tag_validator.store.memory_store import MemorySecretStore

from .test_api import TEST_UID, WsgiTestClient

K0 = "C0FFEE01" + "1" * 16 + "0DDBA115"
K1 = "ABAD1DEA" + "2" * 16 + "FEEDFACE"
K3 = "DEC0DED5" + "3" * 16 + "BADC0DE5"
NEW_UID = "04AABBCCDDEEFF"
NEW_K3 = "5EC12E75" + "4" * 16 + "CAFEF00D"
NEW_K0 = "B0A710AD" + "5" * 16 + "D15EA5E5"

ALL_KEYS = (K0, K1, K3, NEW_K3, NEW_K0)
CSV = f"uid,k0,k1,k3\n04112233445566,{NEW_K0},{'6' * 32},{NEW_K3}\n"

# (method, path, query string, body). Every route the app has, with and without ?raw=true.
ROUTES = [
    ("GET", "/healthz", "", None),
    ("GET", "/readyz", "", None),
    ("GET", "/api/v1/keys", "", None),
    ("GET", "/api/v1/keys", "raw=true", None),
    ("GET", "/api/v1/keys", "raw=true&details=true&include_deleted=true", None),
    ("GET", f"/api/v1/keys/{TEST_UID}", "", None),
    ("GET", f"/api/v1/keys/{TEST_UID}", "raw=true", None),
    ("POST", "/api/v1/keys", "", {"uid": NEW_UID, "k0": NEW_K0, "k1": "7" * 32, "k3": NEW_K3}),
    ("POST", "/api/v1/keys", "", {"uid": TEST_UID, "k3": NEW_K3}),  # conflict: must not echo either key
    ("POST", "/api/v1/keys/generate", "", {"uid": "04887766554433"}),
    ("POST", "/api/v1/keys/import-csv", "", CSV),
    ("DELETE", f"/api/v1/keys/{TEST_UID}", "", None),
    ("POST", f"/api/v1/keys/{TEST_UID}/undelete", "", {}),
    ("GET", "/api/v1/validate", f"uid={TEST_UID}&ctr=3&cmac=0000000000000000", None),
    ("POST", "/api/v1/validate", "", {"uid": TEST_UID, "counter": 4, "cmac": "0000000000000000"}),
    ("POST", "/api/v1/validate", "", {"uid": TEST_UID, "counter": 5, "cmac": calculate_sdm_cmac(TEST_UID, 5, K3)}),
    ("POST", "/api/v1/validate", "", {"uid": "ZZ", "counter": 1, "cmac": "00"}),
    ("GET", "/no/such/route", "", None),
]


def make(mode: str | None) -> WsgiTestClient:
    store = MemorySecretStore()
    store.save_key(TagSecret(uid=TEST_UID, k0=K0, k1=K1, k3=K3))
    return WsgiTestClient(create_app(store=store, mode=mode))


def leaks(text: str) -> list[str]:
    blob = text.upper()
    found = []
    for key in ALL_KEYS:
        for part in (key, key[:8], key[-8:]):
            if part in blob:
                found.append(part)
    return found


@pytest.mark.parametrize("mode", [None, "validate"])
@pytest.mark.parametrize("method,path,query,body", ROUTES)
def test_no_route_returns_key_material(mode, method, path, query, body):
    status, parsed = make(mode).request(method, path, body=body, query_string=query)
    assert leaks(json.dumps(parsed)) == [], (status, parsed)


@pytest.mark.parametrize("mode", [None, "validate"])
def test_a_refused_tap_never_reveals_the_cmac_that_would_have_been_accepted(mode):
    """SEC-003: echoing the expected CMAC lets anyone who reaches the port mint a valid tap without a key."""
    c = make(mode)
    right = calculate_sdm_cmac(TEST_UID, 9, K3)
    wrong = "0000000000000000"
    for method, kwargs in (
        ("POST", {"body": {"uid": TEST_UID, "counter": 9, "cmac": wrong}}),
        ("POST", {"body": {"uid": TEST_UID, "counter": 9, "cmac": wrong, "consume": True}}),
        ("GET", {"query_string": f"uid={TEST_UID}&ctr=9&cmac={wrong}"}),
    ):
        status, body = c.request(method, "/api/v1/validate", **kwargs)
        assert body["valid"] is False
        assert right not in json.dumps(body).upper(), body
        assert "cmac_calculated" not in body
    # and the real tap is still accepted
    status, body = c.request("POST", "/api/v1/validate", body={"uid": TEST_UID, "counter": 9, "cmac": right})
    assert body["valid"] is True


def test_generate_is_gone_in_every_mode():
    for mode in (None, "validate"):
        status, body = make(mode).request("POST", "/api/v1/keys/generate", body={"uid": "04887766554433"})
        assert status in (404, 405), body  # 404 in validate mode; no such route (405) in default mode
        assert "k0" not in body and "k3" not in body


def test_raw_query_changes_nothing():
    c = make(None)
    plain = c.request("GET", f"/api/v1/keys/{TEST_UID}")
    raw = c.request("GET", f"/api/v1/keys/{TEST_UID}", query_string="raw=true")
    assert plain == raw
    assert c.request("GET", "/api/v1/keys") == c.request("GET", "/api/v1/keys", query_string="raw=true")


def test_a_key_shows_as_a_fingerprint_not_as_key_characters():
    status, body = make(None).request("GET", f"/api/v1/keys/{TEST_UID}")
    assert status == 200
    expected = hashlib.sha256(bytes.fromhex(K3)).hexdigest()[:8].upper()
    assert body["k3_fingerprint"] == expected
    for field in ("k0", "k1", "k3", "k0_masked", "k1_masked", "k3_masked"):
        assert field not in body


def test_the_model_cannot_serialise_a_key():
    secret = TagSecret(uid=TEST_UID, k0=K0, k1=K1, k3=K3)
    assert leaks(json.dumps(secret.to_dict())) == []
    with pytest.raises(TypeError):
        secret.to_dict(include_secret=True)  # type: ignore[call-arg]
