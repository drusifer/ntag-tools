"""Characterization tests for UID type handling in StoreKeyManager.

These tests document and verify the expected behavior for UID normalization.
The goal: StoreKeyManager and TagKeys use UID objects consistently throughout.
"""

import pytest

from ntag_keys import CsvSecretStore
from sdm_provisioner.store_key_manager import StoreKeyManager
from shared import TagKeys
from sdm_provisioner.uid_utils import UID


class TestTagKeysUidNormalization:
    """Test that TagKeys works correctly with UID objects."""

    def test_uid_object_with_uppercase_string(self):
        """TagKeys works with UID created from uppercase string."""
        keys = TagKeys(
            uid=UID("04B3664A2F7080"),
            picc_master_key="00" * 16,
            app_read_key="00" * 16,
            sdm_mac_key="00" * 16,
            provisioned_date="2025-01-01T00:00:00",
            status="factory",
        )
        assert keys.uid.uid == "04B3664A2F7080"
        assert isinstance(keys.uid, UID)

    def test_uid_lowercase_string_normalizes_to_uppercase(self):
        """UID normalizes lowercase strings to uppercase."""
        keys = TagKeys(
            uid=UID("04b3664a2f7080"),
            picc_master_key="00" * 16,
            app_read_key="00" * 16,
            sdm_mac_key="00" * 16,
            provisioned_date="2025-01-01T00:00:00",
            status="factory",
        )
        assert keys.uid.uid == "04B3664A2F7080"
        assert isinstance(keys.uid, UID)

    def test_uid_mixed_case_normalizes_to_uppercase(self):
        """UID normalizes mixed-case strings to uppercase."""
        keys = TagKeys(
            uid=UID("04B3664a2F7080"),
            picc_master_key="00" * 16,
            app_read_key="00" * 16,
            sdm_mac_key="00" * 16,
            provisioned_date="2025-01-01T00:00:00",
            status="factory",
        )
        assert keys.uid.uid == "04B3664A2F7080"
        assert isinstance(keys.uid, UID)

    def test_short_uid_raises_value_error(self):
        """UID rejects invalid length strings."""
        with pytest.raises(ValueError, match="even|hexadecimal"):
            UID("04B3664A2F7")

        with pytest.raises(ValueError, match="at least 7"):
            UID("04B3664A2F")

    def test_from_factory_keys_normalizes_uid(self):
        """TagKeys.from_factory_keys normalizes lowercase UID."""
        keys = TagKeys.from_factory_keys(UID("04b3664a2f7080"))
        assert keys.uid.uid == "04B3664A2F7080"
        assert isinstance(keys.uid, UID)

    def test_get_asset_tag_works_with_uid(self):
        """get_asset_tag works correctly with UID object."""
        keys = TagKeys(
            uid=UID("04b3664a2f7080"),  # lowercase input
            picc_master_key="00" * 16,
            app_read_key="00" * 16,
            sdm_mac_key="00" * 16,
            provisioned_date="2025-01-01T00:00:00",
            status="factory",
        )
        # Should not raise - UID normalizes to uppercase
        asset_tag = keys.get_asset_tag()
        assert asset_tag == 'B3-664A'
        assert isinstance(asset_tag, str)


class TestStoreKeyManagerUidHandling:
    """Test StoreKeyManager with UID objects."""

    @pytest.fixture
    def temp_csv(self, tmp_path):
        """Create a temporary CSV file for testing."""
        csv_path = tmp_path / "test_keys.csv"
        return StoreKeyManager(CsvSecretStore(csv_path))

    def test_get_tag_keys_with_uppercase_uid(self, temp_csv):
        """get_tag_keys works with uppercase UID."""
        keys = temp_csv.get_tag_keys(UID("04B3664A2F7080"))
        assert keys.uid.uid == "04B3664A2F7080"
        assert keys.status == "factory"

    def test_get_tag_keys_with_lowercase_uid(self, temp_csv):
        """get_tag_keys normalizes lowercase UID."""
        keys = temp_csv.get_tag_keys(UID("04b3664a2f7080"))
        assert keys.uid.uid == "04B3664A2F7080"  # Normalized to uppercase
        assert keys.status == "factory"

    def test_save_and_retrieve_tag_keys(self, temp_csv):
        """save_tag_keys and get_tag_keys round-trip correctly."""
        # Save with lowercase
        keys = TagKeys(
            uid=UID("04b3664a2f7080"),
            picc_master_key="AA" * 16,
            app_read_key="BB" * 16,
            sdm_mac_key="CC" * 16,
            provisioned_date="2025-01-01T00:00:00",
            status="provisioned",
        )
        temp_csv.save_tag_keys(keys)

        # Retrieve with uppercase
        retrieved = temp_csv.get_tag_keys(UID("04B3664A2F7080"))
        assert retrieved.uid.uid == "04B3664A2F7080"
        assert retrieved.picc_master_key == "AA" * 16

    def test_get_key_with_uid(self, temp_csv):
        """get_key works with UID object."""
        # Save some keys first
        keys = TagKeys(
            uid=UID("04B3664A2F7080"),
            picc_master_key="AA" * 16,
            app_read_key="BB" * 16,
            sdm_mac_key="CC" * 16,
            provisioned_date="2025-01-01T00:00:00",
            status="provisioned",
        )
        temp_csv.save_tag_keys(keys)

        # Get key 0 (PICC master)
        key = temp_csv.get_key(UID("04B3664A2F7080"), 0)
        expected = b"\xAA" * 16
        assert key == expected

    def test_generate_random_keys_normalizes_uid(self, temp_csv):
        """generate_random_keys normalizes lowercase UID."""
        keys = temp_csv.generate_random_keys(UID("04b3664a2f7080"))
        assert keys.uid.uid == "04B3664A2F7080"
        assert keys.status == "provisioned"

    def test_saving_the_same_keys_again_keeps_one_row(self, temp_csv):
        """Re-saving a tag's keys (any UID case) updates the one row; it never duplicates."""
        k = dict(picc_master_key="AA" * 16, app_read_key="BB" * 16, sdm_mac_key="CC" * 16)
        temp_csv.save_tag_keys(TagKeys(uid=UID("04B3664A2F7080"), status="provisioned", **k))
        temp_csv.save_tag_keys(TagKeys(uid=UID("04b3664a2f7080"), status="active", **k))
        assert len(temp_csv.list_tags()) == 1
        assert temp_csv.get_tag_keys(UID("04B3664A2F7080")).sdm_mac_key == "CC" * 16

    def test_different_keys_for_a_stored_tag_are_refused(self, temp_csv):
        """Keys are write-once: replacing them is refused with a clear error."""
        from sdm_provisioner.store_key_manager import KeyStoreError

        temp_csv.save_tag_keys(TagKeys(uid=UID("04B3664A2F7080"), picc_master_key="AA" * 16,
                                       app_read_key="BB" * 16, sdm_mac_key="CC" * 16))
        with pytest.raises(KeyStoreError, match="immutable"):
            temp_csv.save_tag_keys(TagKeys(uid=UID("04B3664A2F7080"), picc_master_key="DD" * 16,
                                           app_read_key="EE" * 16, sdm_mac_key="FF" * 16))
