import unittest
from unittest.mock import patch, MagicMock
import os

# Set a dummy SDK key for tests if not already set
if "LAUNCHDARKLY_SDK_KEY" not in os.environ:
    os.environ["LAUNCHDARKLY_SDK_KEY"] = "dummy_sdk_key_for_testing"

from libs.py_common.flags import is_enabled, LaunchDarklyClient, close_ld_client

class TestFeatureFlags(unittest.TestCase):

    def setUp(self):
        # Ensure a clean state for each test by closing any existing client
        # and resetting the LaunchDarklyClient._client to None.
        close_ld_client() 

    def tearDown(self):
        # Clean up after each test
        close_ld_client()
        # Reset the _client attribute directly to ensure it's None
        LaunchDarklyClient._client = None

    @patch('libs.py_common.flags.ldclient')
    def test_is_enabled_flag_on(self, mock_ldclient):
        # Arrange
        mock_client_instance = MagicMock()
        mock_client_instance.variation.return_value = True
        
        # Ensure that set_config returns the mock_client_instance
        # This simulates the behavior of ldclient.set_config(Config(sdk_key))
        mock_ldclient.set_config.return_value = mock_client_instance
        
        # Act: Call is_enabled, which will internally call LaunchDarklyClient.get_client()
        # LaunchDarklyClient.get_client() will then use the mocked ldclient.set_config
        result = is_enabled("my-test-flag", "test-user")

        # Assert
        self.assertTrue(result)
        mock_client_instance.variation.assert_called_once_with("my-test-flag", {"key": "test-user"}, False)
        # Ensure client was initialized via set_config
        mock_ldclient.set_config.assert_called_once()

    @patch('libs.py_common.flags.ldclient')
    def test_is_enabled_flag_off(self, mock_ldclient):
        # Arrange
        mock_client_instance = MagicMock()
        mock_client_instance.variation.return_value = False
        mock_ldclient.set_config.return_value = mock_client_instance

        # Act
        result = is_enabled("my-test-flag", "test-user")

        # Assert
        self.assertFalse(result)
        mock_client_instance.variation.assert_called_once_with("my-test-flag", {"key": "test-user"}, False)
        mock_ldclient.set_config.assert_called_once()

    @patch('libs.py_common.flags.ldclient')
    def test_is_enabled_sdk_key_not_set(self, mock_ldclient):
        # Arrange
        original_sdk_key = os.environ.pop("LAUNCHDARKLY_SDK_KEY", None)
        # Client should fall back to MockClient which returns False

        # Act
        result = is_enabled("my-test-flag", "test-user")

        # Assert
        self.assertFalse(result)
        # The ldclient.set_config should not have been called in this case
        mock_ldclient.set_config.assert_not_called()
        # The variation method of the internal mock client (not the one from MagicMock) would be called.
        # We can check if get_client created an internal mock that returns False.
        # This requires a bit more intricate mocking if we want to assert calls on the *internal* mock.
        # For simplicity, we rely on the fact that LAUNCHDARKLY_SDK_KEY missing makes it return False.

        # Restore SDK key if it was present
        if original_sdk_key:
            os.environ["LAUNCHDARKLY_SDK_KEY"] = original_sdk_key

    @patch('libs.py_common.flags.LaunchDarklyClient.get_client')
    def test_is_enabled_variation_exception(self, mock_get_client):
        # Arrange
        mock_client_instance = MagicMock()
        mock_client_instance.variation.side_effect = Exception("LD error")
        mock_get_client.return_value = mock_client_instance

        # Act
        result = is_enabled("my-test-flag", "test-user")

        # Assert
        self.assertFalse(result) # Should default to False on error
        mock_client_instance.variation.assert_called_once_with("my-test-flag", {"key": "test-user"}, False)

if __name__ == '__main__':
    unittest.main() 