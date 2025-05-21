# libs/py_common/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "SpaceApp"
    admin_email: str = "admin@example.com"
    # Add other common settings here

    # Example for service-specific settings that might be loaded via common config
    # database_url: str = "postgresql://user:pass@localhost/db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings()

# You might want to load different .env files based on an environment variable
# For example, by checking a `SPACE_ENV` (dev, staging, prod) variable. 