"""Configuration loader for WSB Agent.

Loads settings from config/settings.yaml and environment variables from .env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


# Project root is 3 levels up from this file: src/wsb_agent/utils/config.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@dataclass(frozen=True)
class RedditConfig:
    """Reddit API and ingestion configuration."""

    client_id: str
    client_secret: str
    user_agent: str
    username: str
    password: str
    subreddit: str = "wallstreetbets"
    batch_size: int = 25
    lookback_hours: int = 24
    top_posts_for_comments: int = 10
    max_comments_per_post: int = 50


@dataclass(frozen=True)
class MarketConfig:
    """Market data provider configuration."""

    provider: str = "yfinance"
    cache_ttl_minutes: int = 30
    history_period: str = "1mo"
    history_interval: str = "1d"


@dataclass(frozen=True)
class TickerExtractionConfig:
    """Ticker extraction settings."""

    min_confidence: float = 0.3
    blacklist: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SentimentConfig:
    """Sentiment analysis settings."""

    method: str = "vader"


@dataclass(frozen=True)
class AttentionConfig:
    """Attention metrics settings."""

    window_hours: int = 6


@dataclass(frozen=True)
class FeaturesConfig:
    """Feature extraction configuration."""

    ticker_extraction: TickerExtractionConfig = field(
        default_factory=TickerExtractionConfig
    )
    sentiment: SentimentConfig = field(default_factory=SentimentConfig)
    attention: AttentionConfig = field(default_factory=AttentionConfig)


@dataclass(frozen=True)
class SignalWeights:
    """Signal engine weights."""

    sentiment: float = 0.35
    velocity: float = 0.30
    volume: float = 0.20
    momentum: float = 0.15


@dataclass(frozen=True)
class SignalThresholds:
    """Signal engine thresholds."""

    buy: float = 0.6
    sell: float = -0.4


@dataclass(frozen=True)
class SignalEngineConfig:
    """Signal engine configuration."""

    weights: SignalWeights = field(default_factory=SignalWeights)
    thresholds: SignalThresholds = field(default_factory=SignalThresholds)
    min_mentions: int = 3
    min_confidence: float = 0.3


@dataclass(frozen=True)
class StorageConfig:
    """Storage configuration."""

    database_path: str = "data/wsb_agent.db"

    @property
    def absolute_database_path(self) -> Path:
        """Get absolute path to the database file."""
        path = Path(self.database_path)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "text"


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    reddit: RedditConfig
    market: MarketConfig = field(default_factory=MarketConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    signal_engine: SignalEngineConfig = field(default_factory=SignalEngineConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _load_yaml(config_path: Path | None = None) -> dict[str, Any]:
    """Load settings from YAML config file."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "settings.yaml"

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _build_reddit_config(yaml_data: dict[str, Any]) -> RedditConfig:
    """Build RedditConfig from YAML + environment variables."""
    reddit_yaml = yaml_data.get("reddit", {})
    return RedditConfig(
        client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
        client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
        user_agent=os.environ.get("REDDIT_USER_AGENT", "wsb-agent:v1.0"),
        username=os.environ.get("REDDIT_USERNAME", ""),
        password=os.environ.get("REDDIT_PASSWORD", ""),
        subreddit=reddit_yaml.get("subreddit", "wallstreetbets"),
        batch_size=reddit_yaml.get("batch_size", 25),
        lookback_hours=reddit_yaml.get("lookback_hours", 24),
        top_posts_for_comments=reddit_yaml.get("top_posts_for_comments", 10),
        max_comments_per_post=reddit_yaml.get("max_comments_per_post", 50),
    )


def _build_features_config(yaml_data: dict[str, Any]) -> FeaturesConfig:
    """Build FeaturesConfig from YAML data."""
    features_yaml = yaml_data.get("features", {})
    ticker_yaml = features_yaml.get("ticker_extraction", {})
    sentiment_yaml = features_yaml.get("sentiment", {})
    attention_yaml = features_yaml.get("attention", {})

    return FeaturesConfig(
        ticker_extraction=TickerExtractionConfig(
            min_confidence=ticker_yaml.get("min_confidence", 0.3),
            blacklist=ticker_yaml.get("blacklist", []),
        ),
        sentiment=SentimentConfig(
            method=sentiment_yaml.get("method", "vader"),
        ),
        attention=AttentionConfig(
            window_hours=attention_yaml.get("window_hours", 6),
        ),
    )


def _build_signal_config(yaml_data: dict[str, Any]) -> SignalEngineConfig:
    """Build SignalEngineConfig from YAML data."""
    signal_yaml = yaml_data.get("signal_engine", {})
    weights_yaml = signal_yaml.get("weights", {})
    thresholds_yaml = signal_yaml.get("thresholds", {})

    return SignalEngineConfig(
        weights=SignalWeights(
            sentiment=weights_yaml.get("sentiment", 0.35),
            velocity=weights_yaml.get("velocity", 0.30),
            volume=weights_yaml.get("volume", 0.20),
            momentum=weights_yaml.get("momentum", 0.15),
        ),
        thresholds=SignalThresholds(
            buy=thresholds_yaml.get("buy", 0.6),
            sell=thresholds_yaml.get("sell", -0.4),
        ),
        min_mentions=signal_yaml.get("min_mentions", 3),
        min_confidence=signal_yaml.get("min_confidence", 0.3),
    )


def load_config(config_path: Path | None = None, env_path: Path | None = None) -> AppConfig:
    """Load the full application configuration.

    Loads settings from:
    1. .env file (for secrets like API keys)
    2. config/settings.yaml (for all other parameters)

    Args:
        config_path: Optional path to settings.yaml. Defaults to config/settings.yaml.
        env_path: Optional path to .env file. Defaults to project root .env.

    Returns:
        Fully populated AppConfig instance.
    """
    # Load environment variables from .env
    if env_path is None:
        env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path)

    # Load YAML settings
    yaml_data = _load_yaml(config_path)

    # Build market config
    market_yaml = yaml_data.get("market", {})
    market_config = MarketConfig(
        provider=market_yaml.get("provider", "yfinance"),
        cache_ttl_minutes=market_yaml.get("cache_ttl_minutes", 30),
        history_period=market_yaml.get("history_period", "1mo"),
        history_interval=market_yaml.get("history_interval", "1d"),
    )

    # Build storage config
    storage_yaml = yaml_data.get("storage", {})
    storage_config = StorageConfig(
        database_path=storage_yaml.get("database_path", "data/wsb_agent.db"),
    )

    # Build logging config
    logging_yaml = yaml_data.get("logging", {})
    logging_config = LoggingConfig(
        level=logging_yaml.get("level", "INFO"),
        format=logging_yaml.get("format", "text"),
    )

    return AppConfig(
        reddit=_build_reddit_config(yaml_data),
        market=market_config,
        features=_build_features_config(yaml_data),
        signal_engine=_build_signal_config(yaml_data),
        storage=storage_config,
        logging=logging_config,
    )
