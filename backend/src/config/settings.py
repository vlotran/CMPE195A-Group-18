"""
Application Settings
Loads configuration from environment variables
"""
import socket
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

# Repo root = backend/src/config/settings.py -> up 3 levels.
# Loading .env by absolute path fixes the bug where settings silently fell back
# to defaults when the backend was started from a different working directory.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from .env file"""

    # Application
    app_name: str = "Smart Hydroponic System"
    debug: bool = True
    log_level: str = "INFO"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_path: str = "./data/hydroponic.db"

    # Sensors
    use_mock_sensors: bool = False
    sensor_read_interval: int = 30  # seconds

    # Actuator observation is opt-in per user profile. GPIO remains disabled
    # until explicitly enabled on the Raspberry Pi's repo-root .env.
    actuator_profile_user_id: Optional[int] = None
    actuator_hardware_enabled: bool = False

    # Controller identity 
    # Name shown in the frontend navbar. Override with CONTROLLER_NAME in .env;
    # otherwise falls back to the Pi's hostname (e.g. "raspberrypi").
    controller_name: str = socket.gethostname()

    # CORS
    allowed_origins: str = "*"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert comma-separated origins to list"""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    # Pydantic settings config
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()