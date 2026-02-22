"""Market data provider for fetching financial data.

Uses a provider abstraction (Protocol) so the underlying data source
can be swapped (yfinance → Tiingo → Polygon, etc.) without changing
consumer code.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Protocol

import pandas as pd
import yfinance as yf

from wsb_agent.utils.config import MarketConfig

logger = logging.getLogger("wsb_agent.ingestion.market")


class MarketDataProvider(Protocol):
    """Abstract interface for market data providers.

    Implement this protocol to add new data sources (Tiingo, Polygon, etc.).
    """

    def get_price_history(
        self, ticker: str, period: str = "1mo", interval: str = "1d"
    ) -> pd.DataFrame | None:
        """Fetch historical OHLCV data for a ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL").
            period: Lookback period (e.g., "1mo", "3mo", "1y").
            interval: Data interval (e.g., "1d", "1h").

        Returns:
            DataFrame with columns [Open, High, Low, Close, Volume] or None on error.
        """
        ...

    def get_current_price(self, ticker: str) -> float | None:
        """Get the most recent price for a ticker.

        Args:
            ticker: Stock symbol.

        Returns:
            Current/last price as float, or None if unavailable.
        """
        ...


class YFinanceProvider:
    """Market data provider using the yfinance library.

    Note: yfinance works by web-scraping Yahoo Finance, not an official API.
    It can break without notice. For production use, consider paid alternatives.

    Includes a simple TTL-based cache to avoid redundant requests within
    a single pipeline run.
    """

    def __init__(self, config: MarketConfig) -> None:
        self._config = config
        self._cache: dict[str, tuple[pd.DataFrame, datetime]] = {}

    def get_price_history(
        self,
        ticker: str,
        period: str | None = None,
        interval: str | None = None,
    ) -> pd.DataFrame | None:
        """Fetch historical OHLCV data from Yahoo Finance.

        Results are cached for cache_ttl_minutes to avoid redundant requests.

        Args:
            ticker: Stock symbol (e.g., "AAPL").
            period: Lookback period. Defaults to config value.
            interval: Data interval. Defaults to config value.

        Returns:
            DataFrame with OHLCV columns, or None if ticker is invalid/error.
        """
        period = period or self._config.history_period
        interval = interval or self._config.history_interval
        cache_key = f"{ticker}_{period}_{interval}"

        # Check cache
        if cache_key in self._cache:
            df, cached_at = self._cache[cache_key]
            age = datetime.now(timezone.utc) - cached_at
            if age < timedelta(minutes=self._config.cache_ttl_minutes):
                logger.debug(f"Cache hit for {ticker} (age: {age})")
                return df

        logger.info(f"Fetching price history for {ticker} (period={period}, interval={interval})")

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)

            if df.empty:
                logger.warning(f"No price data returned for {ticker}")
                return None

            # Cache the result
            self._cache[cache_key] = (df, datetime.now(timezone.utc))
            logger.info(f"Fetched {len(df)} rows of price data for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching price data for {ticker}: {e}")
            return None

    def get_current_price(self, ticker: str) -> float | None:
        """Get the most recent closing price from Yahoo Finance.

        Args:
            ticker: Stock symbol.

        Returns:
            Latest close price, or None if unavailable.
        """
        try:
            df = self.get_price_history(ticker, period="5d", interval="1d")
            if df is not None and not df.empty:
                return float(df["Close"].iloc[-1])
            return None

        except Exception as e:
            logger.error(f"Error fetching current price for {ticker}: {e}")
            return None

    def get_batch_prices(self, tickers: list[str]) -> dict[str, float | None]:
        """Fetch current prices for multiple tickers.

        Args:
            tickers: List of stock symbols.

        Returns:
            Dict mapping ticker → price (or None if unavailable).
        """
        logger.info(f"Fetching prices for {len(tickers)} tickers")
        results: dict[str, float | None] = {}

        for ticker in tickers:
            results[ticker] = self.get_current_price(ticker)

        fetched = sum(1 for v in results.values() if v is not None)
        logger.info(f"Successfully fetched prices for {fetched}/{len(tickers)} tickers")
        return results

    def clear_cache(self) -> None:
        """Clear the price data cache."""
        self._cache.clear()
        logger.debug("Price cache cleared")


def create_market_provider(config: MarketConfig) -> MarketDataProvider:
    """Factory function to create the configured market data provider.

    Args:
        config: Market configuration.

    Returns:
        A MarketDataProvider instance.

    Raises:
        ValueError: If the configured provider is not supported.
    """
    if config.provider == "yfinance":
        return YFinanceProvider(config)
    else:
        raise ValueError(
            f"Unknown market data provider: {config.provider}. "
            f"Supported: yfinance"
        )
