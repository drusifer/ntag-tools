"""The simulated tag must apply several ChangeKey commands in one session correctly.

ChangeKey encryption uses the session command counter, which goes up by one after every
secured command. The simulator used to assume counter 0, so the second key changed in a
session (key 3 after key 1) was decrypted with the wrong IV and came out as garbage.
"""

from sdm_provisioner.sequence_logger import create_sequence_logger
from sdm_provisioner.seritag_simulator import SeritagCardManager
from sdm_provisioner.services.provisioning_service import ProvisioningService
from sdm_provisioner.store_key_manager import StoreKeyManager

from ntag_keys import MemorySecretStore


def test_every_key_the_provisioner_sets_is_the_key_on_the_tag():
    km = StoreKeyManager(MemorySecretStore())
    mgr = SeritagCardManager(create_sequence_logger("sim-keys"), key_store=km)
    with mgr as card:
        assert ProvisioningService(card, km).provision_keys() is True
    uid = mgr.simulator.state.uid.hex().upper()
    stored = km.get_tag_keys(uid)
    on_tag = mgr.simulator.state.factory_keys
    assert on_tag[0] == stored.get_picc_master_key_bytes()
    assert on_tag[1] == stored.get_app_read_key_bytes()
    assert on_tag[3] == stored.get_sdm_mac_key_bytes()
