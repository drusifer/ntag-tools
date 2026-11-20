"""Unit tests for official TagValidatorClient SDK."""

from unittest.mock import patch

import pytest

from tag_validator.client import TagValidatorClient, validate_tag_remotely


def test_client_init():
    client = TagValidatorClient(service_url="http://custom-url:8080")
    assert client.service_url == "http://custom-url:8080"


def test_client_init_invalid_scheme():
    with pytest.raises(ValueError, match="Invalid service_url"):
        TagValidatorClient(service_url="tcp://invalid")


def test_validate_tag():
    client = TagValidatorClient(service_url="http://mock-service")
    with patch.object(client, "_http_request") as mock_req:
        mock_req.return_value = (200, {
            "valid": True,
            "uid": "04AE664A2F7080",
            "counter": 10,
        })
        res = client.validate_tag("04AE664A2F7080", 10, "1122334455667788")
        assert res["valid"] is True
        assert res["counter"] == 10


def test_get_key_returns_metadata_and_the_client_cannot_ask_for_keys():
    client = TagValidatorClient(service_url="http://mock-service")
    assert not hasattr(client, "generate_key")
    with patch.object(client, "_http_request") as mock_req:
        mock_req.return_value = (200, {
            "uid": "04AE664A2F7080",
            "status": "active",
            "k0_fingerprint": "AAAAAAAA",
            "k1_fingerprint": "BBBBBBBB",
            "k3_fingerprint": "CCCCCCCC",
        })
        got = client.get_key("04AE664A2F7080")
        assert got["k3_fingerprint"] == "CCCCCCCC"
        mock_req.assert_called_once_with("GET", "/api/v1/keys/04AE664A2F7080")
        with pytest.raises(TypeError):
            client.get_key("04AE664A2F7080", raw=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            client.list_keys(raw=True)  # type: ignore[call-arg]


def test_list_keys_details_asks_for_metadata_only():
    client = TagValidatorClient(service_url="http://mock-service")
    with patch.object(client, "_http_request") as mock_req:
        mock_req.return_value = (200, {"count": 1, "uids": ["04AE664A2F7080"], "keys": [{"uid": "04AE664A2F7080"}]})
        assert client.list_keys() == ["04AE664A2F7080"]
        assert client.list_keys(details=True) == [{"uid": "04AE664A2F7080"}]
        assert mock_req.call_args.args == ("GET", "/api/v1/keys?details=true")


def test_delete_and_undelete():
    client = TagValidatorClient(service_url="http://mock-service")
    with patch.object(client, "_http_request") as mock_req:
        mock_req.return_value = (200, {"status": "deleted"})
        assert client.delete_key("04AE664A2F7080") is True

        mock_req.return_value = (200, {"status": "restored"})
        assert client.undelete_key("04AE664A2F7080") is True


def test_convenience_function():
    with patch("tag_validator.client.TagValidatorClient.validate_tag") as mock_val:
        mock_val.return_value = {"valid": True}
        res = validate_tag_remotely("04AE664A2F7080", 5, "CMAC123", service_url="http://test")
        assert res["valid"] is True
