"""TAG_VALIDATOR_MODE=validate: no route reads, writes or generates keys."""

import pytest

from tag_validator.api.app import create_app
from tag_validator.crypto.cmac_engine import calculate_sdm_cmac
from tag_validator.models import TagSecret
from tag_validator.store.memory_store import MemorySecretStore

from .test_api import TEST_K3, TEST_UID, WsgiTestClient

KEY_ROUTES = [
    ("GET", "/api/v1/keys"),
    ("GET", f"/api/v1/keys/{TEST_UID}"),
    ("GET", f"/api/v1/keys/{TEST_UID}?raw=true"),
    ("GET", "/api/v1/keys?raw=true"),
    ("POST", "/api/v1/keys"),
    ("POST", "/api/v1/keys/generate"),
    ("POST", "/api/v1/keys/import-csv"),
    ("DELETE", f"/api/v1/keys/{TEST_UID}"),
    ("POST", f"/api/v1/keys/{TEST_UID}/undelete"),
]


def make(mode: str | None) -> WsgiTestClient:
    store = MemorySecretStore()
    store.save_key(TagSecret(uid=TEST_UID, k3=TEST_K3, k0="A" * 32, k1="B" * 32))
    return WsgiTestClient(create_app(store=store, mode=mode))


def tap(ctr: int) -> dict:
    return {"uid": TEST_UID, "counter": ctr, "cmac": calculate_sdm_cmac(TEST_UID, ctr, TEST_K3)}


@pytest.mark.parametrize("method,path", KEY_ROUTES)
def test_key_routes_are_404_with_no_key_material(method, path):
    path, _, qs = path.partition("?")
    status, body = make("validate").request(method, path, body={} if method != "GET" else None, query_string=qs)
    assert status == 404
    blob = str(body).upper()
    assert TEST_K3 not in blob and "A" * 32 not in blob and "B" * 32 not in blob


@pytest.mark.parametrize("method,path", KEY_ROUTES)
def test_key_routes_still_work_in_default_mode(method, path):
    path, _, qs = path.partition("?")
    status, _ = make(None).request(method, path, body={} if method != "GET" else None, query_string=qs)
    assert status != 404


def test_validate_get_and_post_unchanged_including_consume():
    c = make("validate")
    ok, body = c.request("POST", "/api/v1/validate", body=tap(7))
    assert ok == 200 and body["valid"] is True
    status, body = c.request("POST", "/api/v1/validate", body={**tap(8), "consume": True})
    assert status == 200 and body["consumed"] is True
    status, body = c.request("POST", "/api/v1/validate", body={**tap(8), "consume": True})
    assert body["valid"] is False and body["reason"] == "replayed"
    t = tap(9)
    status, body = c.request("GET", "/api/v1/validate", query_string=f"uid={t['uid']}&ctr=9&cmac={t['cmac']}")
    assert status == 200 and body["valid"] is True


def test_health_routes_remain_and_healthz_lists_validate_only_and_consume():
    c = make("validate")
    status, body = c.request("GET", "/healthz")
    assert status == 200 and "consume" in body["features"] and "validate-only" in body["features"]
    assert c.request("GET", "/readyz")[0] == 200


def test_default_mode_does_not_advertise_validate_only():
    _, body = make(None).request("GET", "/healthz")
    assert "validate-only" not in body["features"] and "consume" in body["features"]


def test_mode_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("TAG_VALIDATOR_MODE", "validate")
    app = create_app(store=MemorySecretStore())
    assert WsgiTestClient(app).request("GET", "/api/v1/keys")[0] == 404


def test_unrecognised_mode_refuses_to_start_and_names_variable_and_values(monkeypatch):
    monkeypatch.setenv("TAG_VALIDATOR_MODE", "readonly")
    with pytest.raises(ValueError) as e:
        create_app(store=MemorySecretStore())
    msg = str(e.value)
    assert "TAG_VALIDATOR_MODE" in msg and "full" in msg and "validate" in msg and "readonly" in msg


def test_cli_check_exits_with_message_on_bad_mode(monkeypatch, capsys):
    from tag_validator.api.app import main

    monkeypatch.setenv("TAG_VALIDATOR_MODE", "bogus")
    with pytest.raises(SystemExit) as e:
        main(["--check", "--backend", "memory"])
    assert "TAG_VALIDATOR_MODE" in str(e.value)
