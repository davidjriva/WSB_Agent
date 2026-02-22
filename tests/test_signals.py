"""Tests for the Signal Engine and Market Features."""

import pytest
import pandas as pd
from datetime import datetime, timezone

from wsb_agent.models import AttentionMetrics, MarketFeatures, SentimentResult, Signal
from wsb_agent.utils.config import SignalEngineConfig, SignalThresholds, SignalWeights
from wsb_agent.signals.market_features import MarketFeatureExtractor
from wsb_agent.signals.engine import SignalEngine


@pytest.fixture
def market_extractor() -> MarketFeatureExtractor:
    return MarketFeatureExtractor()


@pytest.fixture
def signal_config() -> SignalEngineConfig:
    return SignalEngineConfig(
        min_confidence=0.5,
        min_mentions=3,
        thresholds=SignalThresholds(buy=0.4, sell=-0.4),
        weights=SignalWeights(sentiment=0.4, velocity=0.2, volume=0.2, momentum=0.2),
    )


@pytest.fixture
def engine(signal_config: SignalEngineConfig) -> SignalEngine:
    return SignalEngine(signal_config)


def test_market_features_empty_df(market_extractor: MarketFeatureExtractor) -> None:
    """Test extracting from empty or None dataframe."""
    result1 = market_extractor.compute_features("GME", None)
    assert result1.ticker == "GME"
    assert result1.return_5d is None

    result2 = market_extractor.compute_features("GME", pd.DataFrame())
    assert result2.ticker == "GME"
    assert result2.return_5d is None


def test_market_features_computation(market_extractor: MarketFeatureExtractor) -> None:
    """Test computation on valid dummy data."""
    # Create 30 days of dummy data
    dates = pd.date_range("2024-01-01", periods=30)
    data = {"Close": list(range(100, 130)), "Volume": [1000] * 25 + [2000] * 5}
    df = pd.DataFrame(data, index=dates)

    features = market_extractor.compute_features("AAPL", df)
    
    assert features.ticker == "AAPL"
    assert features.current_price == 129.0
    # 5d return: (129 - 124) / 124 = 5 / 124 = ~0.0403
    assert features.return_5d == pytest.approx(5 / 124)
    # volume ratio: short avg (2000) / long avg (mix of 1000 and 2000)
    # long avg = (15 * 1000 + 5 * 2000) / 20 = 1250
    assert features.volume_change_ratio == pytest.approx(2000 / 1250)
    assert features.volatility_20d is not None


def test_generate_signal_strong_buy(engine: SignalEngine) -> None:
    """Test generating a strong BUY signal."""
    sentiment = SentimentResult("GME", 0.9, "bullish", 0.8, 10, [])
    attention = AttentionMetrics("GME", 100, 15.0, 50.0, 50.0, 6) # high velocity
    market = MarketFeatures("GME", 50.0, 0.05, 0.15, 0.30, 0.8, 3.0) # strong volume and return
    
    signal = engine.generate_signal("GME", sentiment, attention, market, 0.9)
    
    assert signal is not None
    assert signal.action == "BUY"
    assert signal.composite_score > engine._config.thresholds.buy
    assert "Strong Bullish" in signal.reasoning
    assert "High mention velocity" in signal.reasoning


def test_generate_signal_strong_sell(engine: SignalEngine) -> None:
    """Test generating a strong SELL signal."""
    sentiment = SentimentResult("TSLA", -0.8, "bearish", -0.7, 50, [])
    attention = AttentionMetrics("TSLA", 50, 12.0, 20.0, -20.0, 6) # high velocity amplifies sell
    market = MarketFeatures("TSLA", 200.0, -0.02, -0.15, -0.20, 0.5, 2.5) # dropping fast on high vol
    
    signal = engine.generate_signal("TSLA", sentiment, attention, market, 0.9)
    
    assert signal is not None
    assert signal.action == "SELL"
    assert signal.composite_score < engine._config.thresholds.sell


def test_generate_signal_hold(engine: SignalEngine) -> None:
    """Test generating a HOLD signal."""
    sentiment = SentimentResult("AAPL", 0.1, "neutral", 0.1, 5, [])
    attention = AttentionMetrics("AAPL", 5, 0.5, 2.0, 0.5, 6)
    market = MarketFeatures("AAPL", 150.0, 0.001, 0.01, 0.02, 0.2, 1.0)
    
    signal = engine.generate_signal("AAPL", sentiment, attention, market, 0.9)
    
    assert signal is not None
    assert signal.action == "HOLD"
    assert engine._config.thresholds.sell < signal.composite_score < engine._config.thresholds.buy


def test_generate_signal_filters_low_confidence(engine: SignalEngine) -> None:
    """Test that low confidence extractions are filtered."""
    sentiment = SentimentResult("XYZ", 0.9, "bullish", 0.8, 10, [])
    attention = AttentionMetrics("XYZ", 10, 1.0, 5.0, 5.0, 6)
    
    # confidence=0.2 is below min_confidence=0.5
    signal = engine.generate_signal("XYZ", sentiment, attention, None, 0.2)
    assert signal is None


def test_generate_signal_filters_low_mentions(engine: SignalEngine) -> None:
    """Test that tickers with too few mentions are filtered."""
    sentiment = SentimentResult("XYZ", 0.9, "bullish", 0.8, 2, [])
    attention = AttentionMetrics("XYZ", 2, 0.1, 1.0, 1.0, 6)
    
    # mention_count=2 is below min_mentions=3
    signal = engine.generate_signal("XYZ", sentiment, attention, None, 0.9)
    assert signal is None
