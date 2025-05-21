import ldclient
from ldclient.config import Config
import os
import logging

logger = logging.getLogger(__name__)

class LaunchDarklyClient:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            sdk_key = os.environ.get("LAUNCHDARKLY_SDK_KEY")
            if not sdk_key:
                logger.warning("LAUNCHDARKLY_SDK_KEY not set. Feature flags will default to False.")
                # Return a mock client that always returns False
                class MockClient:
                    def variation(self, *args, **kwargs):
                        return False
                    def close(self):
                        pass
                cls._client = MockClient()
            else:
                try:
                    # Initialize the client only once
                    ld_config = Config(sdk_key)
                    cls._client = ldclient.set_config(ld_config)
                    # Test connection by requesting a dummy flag. This helps catch init errors early.
                    cls._client.variation("startup-test-flag", {"key": "system"}, False)
                    logger.info("LaunchDarkly client initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to initialize LaunchDarkly client: {e}. Feature flags will default to False.")
                    class MockClient:
                        def variation(self, *args, **kwargs):
                            return False
                        def close(self):
                            pass
                    cls._client = MockClient()
        return cls._client

def is_enabled(flag_name: str, user_key: str = 'system') -> bool:
    client = LaunchDarklyClient.get_client()
    user = {
        "key": user_key
    }
    try:
        return client.variation(flag_name, user, False)
    except Exception as e:
        logger.error(f"Error checking flag {flag_name} for user {user_key}: {e}. Defaulting to False.")
        return False

def close_ld_client():
    if LaunchDarklyClient._client and hasattr(LaunchDarklyClient._client, 'close') and callable(LaunchDarklyClient._client.close):
        try:
            LaunchDarklyClient._client.close()
            logger.info("LaunchDarkly client closed.")
        except Exception as e:
            logger.error(f"Error closing LaunchDarkly client: {e}")
    LaunchDarklyClient._client = None # Reset for potential re-initialization if app restarts 