"""Tests for the configuration loader."""

from pathlib import Path
import tempfile
import os

import pytest
import yaml

from wsb_agent.utils.config import load_config, AppConfig


@pytest.fixture
def minimal_settings(tmp_path: Path) -> Path:
    """Create a minimal settings.yaml for testing."""
    settings = {
        "reddit": {
            "subreddit": "wallstreetbets",
            "batch_size": 10,
            "lookback_hours": 12,
        },
        "market": {
            "provider": "yfinance",
            "cache_ttl_minutes": 15,
        },
        "features": {
            "ticker_extraction": {
                "min_confidence": 0.5,
                "blacklist": ["DD", "YOLO", "ALL"],
            },
        },
        "signal_engine": {
            "weights": {
                "sentiment": 0.4,
                "velocity": 0.3,
                "volume": 0.2,
                "momentum": 0.1,
            },
            "thresholds": {
                "buy": 0.7,
                "sell": -0.5,
            },
            "min_mentions": 5,
        },
        "storage": {
            "database_path": str(tmp_path / "test.db"),
        },
        "logging": {
            "level": "DEBUG",
            "format": "text",
        },
    }

    config_path = tmp_path / "settings.yaml"
    with open(config_path, "w") as f:
        yaml.dump(settings, f)

    return config_path


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    """Create a test .env file."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "REDDIT_CLIENT_ID=test_client_id\n"
        "REDDIT_CLIENT_SECRET=test_client_secret\n"
        "REDDIT_USER_AGENT=test-agent:v1.0\n"
        "REDDIT_USERNAME=test_user\n"
        "REDDIT_PASSWORD=test_pass\n"
    )
    return env_path


def test_load_config_from_yaml(minimal_settings: Path, env_file: Path) -> None:
    """Test that config loads correctly from YAML + .env."""
    config = load_config(config_path=minimal_settings, env_path=env_file)

    assert isinstance(config, AppConfig)
    assert config.reddit.client_id == "test_client_id"
    assert config.reddit.client_secret == "test_client_secret"
    assert config.reddit.subreddit == "wallstreetbets"
    assert config.reddit.batch_size == 10
    assert config.reddit.lookback_hours == 12


def test_market_config(minimal_settings: Path, env_file: Path) -> None:
    """Test market config loading."""
    config = load_config(config_path=minimal_settings, env_path=env_file)

    assert config.market.provider == "yfinance"
    assert config.market.cache_ttl_minutes == 15


def test_feature_config(minimal_settings: Path, env_file: Path) -> None:
    """Test feature extraction config loading."""
    config = load_config(config_path=minimal_settings, env_path=env_file)

    assert config.features.ticker_extraction.min_confidence == 0.5
    assert "DD" in config.features.ticker_extraction.blacklist
    assert "YOLO" in config.features.ticker_extraction.blacklist


def test_signal_engine_config(minimal_settings: Path, env_file: Path) -> None:
    """Test signal engine config loading."""
    config = load_config(config_path=minimal_settings, env_path=env_file)

    assert config.signal_engine.weights.sentiment == 0.4
    assert config.signal_engine.thresholds.buy == 0.7
    assert config.signal_engine.thresholds.sell == -0.5
    assert config.signal_engine.min_mentions == 5


def test_defaults_when_yaml_missing(env_file: Path, tmp_path: Path) -> None:
    """Test that defaults are used when settings.yaml doesn't exist."""
    nonexistent = tmp_path / "nonexistent.yaml"
    config = load_config(config_path=nonexistent, env_path=env_file)

    assert config.reddit.subreddit == "wallstreetbets"
    assert config.reddit.batch_size == 25
    assert config.market.provider == "yfinance"
    assert config.signal_engine.weights.sentiment == 0.35


def test_config_is_frozen(minimal_settings: Path, env_file: Path) -> None:
    """Test that config dataclasses are immutable."""
    config = load_config(config_path=minimal_settings, env_path=env_file)

    with pytest.raises(AttributeError):
        config.reddit.subreddit = "stocks"  # type: ignore
