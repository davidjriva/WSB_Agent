"""Signal engine for the WSB Agent.

Aggregates NLP features (sentiment, attention) and market features 
(returns, volume) using a weighted formula to produce composite BUY/SELL/HOLD signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from wsb_agent.models import AttentionMetrics, MarketFeatures, SentimentResult, Signal
from wsb_agent.utils.config import SignalEngineConfig

logger = logging.getLogger("wsb_agent.signals.engine")


class SignalEngine:
    """Core decision engine that scores tickers and generates signals."""

    def __init__(self, config: SignalEngineConfig) -> None:
        self._config = config

    def generate_signal(
        self,
        ticker: str,
        sentiment: SentimentResult | None = None,
        attention: AttentionMetrics | None = None,
        market: MarketFeatures | None = None,
        confidence: float = 1.0,
    ) -> Signal | None:
        """Generate a trading signal for a single ticker.

        Args:
            ticker: The stock symbol.
            sentiment: Sentiment analysis results.
            attention: Attention/momentum metrics.
            market: Technical/market features.
            confidence: Base confidence of the ticker extraction (0.0 to 1.0).

        Returns:
            Signal dataclass, or None if the ticker doesn't meet minimum requirements.
        """
        # Filter low confidence extractions
        if confidence < self._config.min_confidence:
            logger.debug(f"Skipping {ticker}: low extraction confidence ({confidence} < {self._config.min_confidence})")
            return None

        # Filter low mention counts (ensure we have attention data)
        if not attention or attention.mention_count < self._config.min_mentions:
            mentions = attention.mention_count if attention else 0
            logger.debug(f"Skipping {ticker}: not enough mentions ({mentions} < {self._config.min_mentions})")
            return None

        # Gather component scores (normalized to [-1.0, 1.0])
        components: dict[str, float] = {}

        # 1. Sentiment Score [-1.0 to 1.0]
        # Already normalized by WSBSentimentAnalyzer
        components["sentiment"] = sentiment.score if sentiment else 0.0

        # 2. Velocity Score [-1.0 to 1.0]
        # Normalize: assumes 10 mentions/hour is "max" velocity (1.0)
        velocity = attention.mention_velocity if attention else 0.0
        # Determine direction largely from sentiment to sign velocity correctly for the final sum
        # If bullish, high velocity adds to buy. If bearish, high velocity adds to sell.
        direction = 1.0 if components["sentiment"] >= 0 else -1.0
        normalized_velocity = min(1.0, velocity / 10.0) * direction
        components["velocity"] = normalized_velocity

        # 3. Volume Change Score [-1.0 to 1.0]
        # Normalize: Volume > 2x average = 1.0. Volume < 0.5x average = -1.0 (though less volume usually means 0)
        vol_ratio = market.volume_change_ratio if market and market.volume_change_ratio else 1.0
        # Map [0, 1, ~3+] -> [-1, 0, 1] roughly.
        if vol_ratio >= 1.0:
            normalized_vol = min(1.0, (vol_ratio - 1.0) / 2.0)
        else:
            normalized_vol = max(-1.0, vol_ratio - 1.0)
        # Volume amplifies the prevailing sentiment direction
        components["volume"] = normalized_vol * direction

        # 4. Momentum Score (5d return) [-1.0 to 1.0]
        # Normalize: +/- 10% return in 5 days is 1.0 bounds
        ret_5d = market.return_5d if market and market.return_5d else 0.0
        normalized_momentum = max(-1.0, min(1.0, ret_5d / 0.10))
        components["momentum"] = normalized_momentum

        # Calculate composite score
        weights = self._config.weights
        composite_score = (
            weights.sentiment * components["sentiment"] +
            weights.velocity * components["velocity"] +
            weights.volume * components["volume"] +
            weights.momentum * components["momentum"]
        )
        
        # Ensure it stays within bounds
        composite_score = max(-1.0, min(1.0, composite_score))

        # Determine ACTION
        if composite_score >= self._config.thresholds.buy:
            action = "BUY"
        elif composite_score <= self._config.thresholds.sell:
            action = "SELL"
        else:
            action = "HOLD"

        # Generate reasoning string
        reasoning = self._generate_reasoning(
            action, composite_score, components, attention, market
        )

        signal = Signal(
            ticker=ticker,
            composite_score=round(composite_score, 4),
            action=action,
            confidence=round(confidence, 4),
            components={k: round(v, 4) for k, v in components.items()},
            reasoning=reasoning,
            metadata=sentiment.metadata if sentiment else {},
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(f"Signal generated: {action} {ticker} (score={composite_score:.2f})")
        return signal

    def generate_batch_signals(
        self,
        tickers: list[str],
        sentiment_dict: dict[str, SentimentResult],
        attention_dict: dict[str, AttentionMetrics],
        market_dict: dict[str, MarketFeatures],
        confidence_dict: dict[str, float] | None = None,
    ) -> list[Signal]:
        """Generate signals for multiple tickers.

        Args:
            tickers: List of ticker symbols to evaluate.
            sentiment_dict: Mapping of ticker -> SentimentResult.
            attention_dict: Mapping of ticker -> AttentionMetrics.
            market_dict: Mapping of ticker -> MarketFeatures.
            confidence_dict: Mapping of ticker -> confidence score.

        Returns:
            List of generated Signal objects (excluding skipped/filtered tickers).
        """
        confidence_dict = confidence_dict or {}
        signals = []

        for ticker in tickers:
            signal = self.generate_signal(
                ticker=ticker,
                sentiment=sentiment_dict.get(ticker),
                attention=attention_dict.get(ticker),
                market=market_dict.get(ticker),
                confidence=confidence_dict.get(ticker, 1.0),
            )
            if signal:
                signals.append(signal)

        # Sort with most extreme signals first (strongest buys, then strongest sells, etc.)
        signals.sort(key=lambda s: abs(s.composite_score), reverse=True)
        
        logger.info(f"Generated {len(signals)} total signals from {len(tickers)} tickers")
        return signals

    def _generate_reasoning(
        self,
        action: str,
        composite_score: float,
        components: dict[str, float],
        attention: AttentionMetrics | None,
        market: MarketFeatures | None,
    ) -> str:
        """Create a human-readable explanation of why the signal was triggered."""
        if action == "HOLD":
            return f"Composite score ({composite_score:.2f}) not strong enough to trigger action."

        reasons = []
        
        # Sentiment reasoning
        if abs(components["sentiment"]) > 0.4:
            s_type = "Bullish" if components["sentiment"] > 0 else "Bearish"
            reasons.append(f"Strong {s_type} sentiment score ({components['sentiment']:.2f})")
            
        # Attention reasoning
        if attention and attention.mention_velocity > 2.0:
            reasons.append(f"High mention velocity ({attention.mention_velocity:.1f}/hr)")
            
        # Volume reasoning
        if market and market.volume_change_ratio and market.volume_change_ratio > 1.5:
            reasons.append(f"Unusual trading volume ({market.volume_change_ratio:.1f}x relative to past 20d)")
            
        # Momentum reasoning
        if market and market.return_5d and abs(market.return_5d) > 0.05:
            dir_str = "up" if market.return_5d > 0 else "down"
            reasons.append(f"Strong 5d price momentum ({dir_str} {market.return_5d*100:.1f}%)")

        if not reasons:
            return f"{action} signal based on combined metrics."

        return f"{action} triggered. " + "; ".join(reasons) + "."
