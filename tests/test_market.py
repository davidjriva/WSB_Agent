"""Tests for the market data provider."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from wsb_agent.ingestion.market import YFinanceProvider, create_market_provider
from wsb_agent.utils.config import MarketConfig


@pytest.fixture
def market_config() -> MarketConfig:
    """Create a test market configuration."""
    return MarketConfig(
        provider="yfinance",
        cache_ttl_minutes=30,
        history_period="1mo",
        history_interval="1d",
    )


@pytest.fixture
def sample_price_df() -> pd.DataFrame:
    """Create a sample price DataFrame."""
    dates = pd.date_range("2024-01-10", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [150.0, 152.0, 151.0, 153.0, 155.0],
            "High": [153.0, 154.0, 153.0, 156.0, 157.0],
            "Low": [149.0, 151.0, 150.0, 152.0, 154.0],
            "Close": [152.0, 151.0, 153.0, 155.0, 156.0],
            "Volume": [1000000, 1200000, 900000, 1100000, 1300000],
        },
        index=dates,
    )


@patch("wsb_agent.ingestion.market.yf.Ticker")
def test_get_price_history(
    mock_ticker_class: MagicMock,
    market_config: MarketConfig,
    sample_price_df: pd.DataFrame,
) -> None:
    """Test that price history is fetched correctly."""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = sample_price_df
    mock_ticker_class.return_value = mock_ticker

    provider = YFinanceProvider(market_config)
    df = provider.get_price_history("AAPL")

    assert df is not None
    assert len(df) == 5
    assert "Close" in df.columns
    assert df["Close"].iloc[-1] == 156.0


@patch("wsb_agent.ingestion.market.yf.Ticker")
def test_get_price_history_caching(
    mock_ticker_class: MagicMock,
    market_config: MarketConfig,
    sample_price_df: pd.DataFrame,
) -> None:
    """Test that repeated calls use the cache."""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = sample_price_df
    mock_ticker_class.return_value = mock_ticker

    provider = YFinanceProvider(market_config)

    # First call should hit the API
    df1 = provider.get_price_history("AAPL")
    # Second call should use cache
    df2 = provider.get_price_history("AAPL")

    assert df1 is not None
    assert df2 is not None
    # yf.Ticker should only have been instantiated once for the first call
    # (second call is cached, but Ticker is instantiated per call to get_price_history)
    # The key assertion: history() was only called once
    assert mock_ticker.history.call_count == 1


@patch("wsb_agent.ingestion.market.yf.Ticker")
def test_get_price_history_empty_df(
    mock_ticker_class: MagicMock,
    market_config: MarketConfig,
) -> None:
    """Test handling of empty DataFrame (invalid ticker)."""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker_class.return_value = mock_ticker

    provider = YFinanceProvider(market_config)
    df = provider.get_price_history("INVALID_TICKER")

    assert df is None


@patch("wsb_agent.ingestion.market.yf.Ticker")
def test_get_current_price(
    mock_ticker_class: MagicMock,
    market_config: MarketConfig,
    sample_price_df: pd.DataFrame,
) -> None:
    """Test getting the current/latest price."""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = sample_price_df
    mock_ticker_class.return_value = mock_ticker

    provider = YFinanceProvider(market_config)
    price = provider.get_current_price("AAPL")

    assert price == 156.0


@patch("wsb_agent.ingestion.market.yf.Ticker")
def test_get_batch_prices(
    mock_ticker_class: MagicMock,
    market_config: MarketConfig,
    sample_price_df: pd.DataFrame,
) -> None:
    """Test batch price fetching."""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = sample_price_df
    mock_ticker_class.return_value = mock_ticker

    provider = YFinanceProvider(market_config)
    prices = provider.get_batch_prices(["AAPL", "MSFT"])

    assert len(prices) == 2
    assert prices["AAPL"] is not None
    assert prices["MSFT"] is not None


def test_create_market_provider(market_config: MarketConfig) -> None:
    """Test factory function creates correctly typed provider."""
    provider = create_market_provider(market_config)
    assert isinstance(provider, YFinanceProvider)


def test_create_market_provider_unknown() -> None:
    """Test factory function raises on unknown provider."""
    config = MarketConfig(provider="unknown")
    with pytest.raises(ValueError, match="Unknown market data provider"):
        create_market_provider(config)


def test_clear_cache(market_config: MarketConfig) -> None:
    """Test cache clearing."""
    provider = YFinanceProvider(market_config)
    provider._cache["test_key"] = (pd.DataFrame(), datetime.now(timezone.utc))
    assert len(provider._cache) == 1

    provider.clear_cache()
    assert len(provider._cache) == 0
