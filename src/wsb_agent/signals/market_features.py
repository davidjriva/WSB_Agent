"""Market features extraction for the WSB Agent.

Calculates technical indicators and features from historical price
and volume data to feed into the signal engine.
"""

from __future__ import annotations

import logging
import pandas as pd
import numpy as np

from wsb_agent.models import MarketFeatures

logger = logging.getLogger("wsb_agent.signals.market_features")


class MarketFeatureExtractor:
    """Computes technical, momentum, and volume features from price history."""

    def compute_features(
        self, ticker: str, history_df: pd.DataFrame | None
    ) -> MarketFeatures:
        """Compute market features for a ticker from its price history.

        Args:
            ticker: Stock symbol.
            history_df: DataFrame with Date index and Open, High, Low, Close, Volume.
                        Can be None if data is missing.

        Returns:
            MarketFeatures dataclass. If data is missing or insufficient,
            returns partially or fully None features.
        """
        if history_df is None or history_df.empty:
            logger.warning(f"No price history available for {ticker} to compute features")
            return MarketFeatures(ticker=ticker)

        try:
            # Ensure we have the required columns
            required_cols = {"Close", "Volume"}
            if not required_cols.issubset(history_df.columns):
                logger.error(f"Missing required columns {required_cols} in history for {ticker}")
                return MarketFeatures(ticker=ticker)

            # Need at least 2 rows for 1-day returns, etc.
            if len(history_df) < 2:
                return MarketFeatures(
                    ticker=ticker,
                    current_price=float(history_df["Close"].iloc[-1])
                )

            # Sort chronological
            df = history_df.sort_index()

            current_price = float(df["Close"].iloc[-1])
            
            # Returns
            return_1d = self._compute_return(df, periods=1)
            return_5d = self._compute_return(df, periods=5)
            return_20d = self._compute_return(df, periods=20)
            
            # Volatility (annualized, assuming ~252 trading days)
            volatility_20d = self._compute_volatility(df, window=20)
            
            # Volume change ratio (recent vs historical average)
            volume_change_ratio = self._compute_volume_ratio(df, short_window=5, long_window=20)

            features = MarketFeatures(
                ticker=ticker,
                current_price=current_price,
                return_1d=return_1d,
                return_5d=return_5d,
                return_20d=return_20d,
                volatility_20d=volatility_20d,
                volume_change_ratio=volume_change_ratio,
            )
            
            logger.debug(f"Computed market features for {ticker}: 5d_ret={return_5d}, vol={volume_change_ratio}")
            return features

        except Exception as e:
            logger.error(f"Error computing market features for {ticker}: {e}")
            return MarketFeatures(ticker=ticker)

    def compute_batch_features(
        self,
        history_dict: dict[str, pd.DataFrame | None]
    ) -> dict[str, MarketFeatures]:
        """Compute features for multiple tickers.
        
        Args:
            history_dict: Dict mapping ticker -> history DataFrame.
            
        Returns:
            Dict mapping ticker -> MarketFeatures.
        """
        results = {}
        for ticker, df in history_dict.items():
            results[ticker] = self.compute_features(ticker, df)
        
        logger.info(f"Computed market features for {len(results)} tickers")
        return results

    @staticmethod
    def _compute_return(df: pd.DataFrame, periods: int) -> float | None:
        """Calculate percentage return over N periods."""
        if len(df) <= periods:
            return None
            
        current = df["Close"].iloc[-1]
        historical = df["Close"].iloc[-(periods + 1)]
        
        if historical == 0:
            return None
            
        return float((current - historical) / historical)

    @staticmethod
    def _compute_volatility(df: pd.DataFrame, window: int) -> float | None:
        """Calculate annualized volatility from daily returns over a window."""
        if len(df) < window + 1:
            return None
            
        # Daily log returns
        daily_returns = np.log(df["Close"] / df["Close"].shift(1))
        
        # Standard deviation over the window
        recent_returns = daily_returns.iloc[-window:]
        daily_volatility = recent_returns.std()
        
        # Annualize (assuming 252 trading days)
        annualized = daily_volatility * np.sqrt(252)
        
        return float(annualized) if not np.isnan(annualized) else None

    @staticmethod
    def _compute_volume_ratio(df: pd.DataFrame, short_window: int, long_window: int) -> float | None:
        """Calculate ratio of recent average volume to historical average volume."""
        if len(df) < long_window:
            return None
            
        short_avg = df["Volume"].iloc[-short_window:].mean()
        long_avg = df["Volume"].iloc[-long_window:].mean()
        
        if long_avg == 0:
            return None
            
        ratio = short_avg / long_avg
        return float(ratio) if not np.isnan(ratio) else None
