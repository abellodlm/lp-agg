"""
Configuration settings for LP Aggregation RFQ System.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """Application configuration settings"""

    # Markup
    markup_bps: float = 5.0
    validity_buffer_seconds: float = 2.0

    # Quote streaming
    poll_interval_ms: int = 500
    default_stream_duration_seconds: int = 30
    auto_refresh: bool = True
    improvement_threshold_bps: float = 1.0

    # Database
    database_path: str = "quotes.db"
    enable_database_logging: bool = True

    # Mock LP settings (for testing)
    mock_lp_count: int = 3
    mock_base_price: float = 100000.0
    mock_spread_bps: float = 5.0
    mock_min_delay: float = 0.1
    mock_max_delay: float = 0.5
    mock_failure_rate: float = 0.0

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> 'Settings':
        """
        Load settings from environment variables.

        Args:
            env_file: Path to .env file (optional)

        Returns:
            Settings instance
        """
        # Load .env file if provided
        if env_file and Path(env_file).exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key] = value

        return cls(
            markup_bps=float(os.getenv('MARKUP_BPS', '5.0')),
            validity_buffer_seconds=float(os.getenv('VALIDITY_BUFFER_SECONDS', '2.0')),
            poll_interval_ms=int(os.getenv('POLL_INTERVAL_MS', '500')),
            default_stream_duration_seconds=int(os.getenv('DEFAULT_STREAM_DURATION_SECONDS', '30')),
            auto_refresh=os.getenv('AUTO_REFRESH', 'false').lower() == 'true',
            improvement_threshold_bps=float(os.getenv('IMPROVEMENT_THRESHOLD_BPS', '1.0')),
            database_path=os.getenv('DATABASE_PATH', 'quotes.db'),
            enable_database_logging=os.getenv('ENABLE_DATABASE_LOGGING', 'true').lower() == 'true',
            mock_lp_count=int(os.getenv('MOCK_LP_COUNT', '3')),
            mock_base_price=float(os.getenv('MOCK_BASE_PRICE', '100000.0')),
            mock_spread_bps=float(os.getenv('MOCK_SPREAD_BPS', '5.0')),
            mock_min_delay=float(os.getenv('MOCK_MIN_DELAY', '0.1')),
            mock_max_delay=float(os.getenv('MOCK_MAX_DELAY', '0.5')),
            mock_failure_rate=float(os.getenv('MOCK_FAILURE_RATE', '0.0'))
        )


# Global settings instance
settings = Settings.from_env('.env')
