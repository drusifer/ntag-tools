"""k3s counter behaviour (moved from the validator tests with the store)."""

from types import SimpleNamespace

import pytest

from ntag_keys import CounterStoreError
from ntag_keys.k3s_store import K3sSecretStore

TEST_UID = "04B7664A2F7080"


class FakeApiException(Exception):
    def __init__(self, status):
        self.status = status


class FakeV1:
    """Just enough CoreV1Api: secrets with resource versions and 409 on stale replace."""

    def __init__(self):
        self.items = {}
        self.conflicts = 0  # inject this many 409s before a replace succeeds

    def read_namespaced_secret(self, name, namespace):
        if name not in self.items:
            raise FakeApiException(404)
        return self.items[name]

    def create_namespaced_secret(self, namespace, body):
        if body.metadata.name in self.items:
            raise FakeApiException(409)
        body.metadata.resource_version = "1"
        self.items[body.metadata.name] = body

    def replace_namespaced_secret(self, name, namespace, body):
        current = self.items[name]
        if self.conflicts or body.metadata.resource_version != current.metadata.resource_version:
            self.conflicts = max(0, self.conflicts - 1)
            raise FakeApiException(409)
        body.metadata.resource_version = str(int(current.metadata.resource_version) + 1)
        self.items[name] = body


@pytest.fixture
def k3s(monkeypatch):
    from ntag_keys import k3s_store

    monkeypatch.setattr(k3s_store, "ApiException", FakeApiException)
    monkeypatch.setattr(k3s_store, "K8S_AVAILABLE", True)
    monkeypatch.setattr(
        k3s_store,
        "k8s_client",
        SimpleNamespace(
            V1Secret=lambda **kw: SimpleNamespace(**kw),
            V1ObjectMeta=lambda **kw: SimpleNamespace(**{"resource_version": None, **kw}),
        ),
    )
    store = K3sSecretStore.__new__(K3sSecretStore)
    store.namespace, store._initialized, store._v1 = "tag-secrets", True, FakeV1()
    return store


def test_k3s_counter_lives_in_its_own_secret_and_never_touches_the_key(k3s):
    assert k3s.consume_counter(TEST_UID, 4) is True
    assert list(k3s._v1.items) == [f"tag-ctr-{TEST_UID.lower()}"]
    assert k3s.consume_counter(TEST_UID, 4) is False
    assert k3s.consume_counter(TEST_UID, 3) is False
    assert k3s.consume_counter(TEST_UID, 5) is True


def test_k3s_retries_a_lost_race_and_then_sees_the_replay(k3s):
    assert k3s.consume_counter(TEST_UID, 4) is True
    k3s._v1.conflicts = 1
    assert k3s.consume_counter(TEST_UID, 5) is True
    assert k3s.consume_counter(TEST_UID, 5) is False


def test_k3s_gives_up_loudly_if_it_cannot_settle(k3s):
    assert k3s.consume_counter(TEST_UID, 4) is True
    k3s._v1.conflicts = 99
    with pytest.raises(CounterStoreError):
        k3s.consume_counter(TEST_UID, 5)


def test_k3s_not_initialised_is_a_store_error(k3s):
    k3s._initialized = False
    with pytest.raises(CounterStoreError):
        k3s.consume_counter(TEST_UID, 1)


def test_k3s_two_creators_racing_only_one_wins(k3s):
    first = k3s._v1.create_namespaced_secret
    calls = []

    def racy_create(namespace, body):
        if not calls:  # someone else creates it between our read and our create
            calls.append(1)
            first(namespace, SimpleNamespace(metadata=body.metadata, data={"last": _b64("9")}))
        return first(namespace, body)

    k3s._v1.create_namespaced_secret = racy_create
    assert k3s.consume_counter(TEST_UID, 4) is False  # 4 <= 9 once it re-reads


def _b64(text):
    import base64

    return base64.b64encode(text.encode()).decode()
