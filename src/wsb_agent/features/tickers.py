"""Ticker extraction from WallStreetBets text.

Identifies stock ticker mentions using multiple strategies:
1. Dollar-sign cashtags ($GME, $AAPL)
2. Uppercase words matching known tickers (GME, AAPL)
3. Context-aware confidence scoring to reduce false positives
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from wsb_agent.models import TickerMention
from wsb_agent.utils.config import TickerExtractionConfig, PROJECT_ROOT

logger = logging.getLogger("wsb_agent.features.tickers")

# Regex patterns
CASHTAG_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")
UPPERCASE_WORD_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")


class TickerExtractor:
    """Extracts stock ticker mentions from text with confidence scoring.

    Uses a whitelist of valid tickers and a blacklist of common words
    that happen to look like tickers (DD, YOLO, ALL, etc.).
    """

    def __init__(
        self,
        config: TickerExtractionConfig,
        whitelist_path: Path | None = None,
    ) -> None:
        self._config = config
        self._blacklist = set(config.blacklist)

        # Load the ticker whitelist
        if whitelist_path is None:
            whitelist_path = PROJECT_ROOT / "data" / "ticker_whitelist.csv"
        self._whitelist = self._load_whitelist(whitelist_path)

        logger.info(
            f"TickerExtractor initialized: "
            f"{len(self._whitelist)} whitelisted tickers, "
            f"{len(self._blacklist)} blacklisted terms"
        )

    @staticmethod
    def _load_whitelist(path: Path) -> set[str]:
        """Load valid tickers from CSV whitelist file."""
        tickers: set[str] = set()
        if not path.exists():
            logger.warning(f"Ticker whitelist not found at {path}")
            return tickers

        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row.get("ticker", "").strip().upper()
                if ticker:
                    tickers.add(ticker)

        logger.info(f"Loaded {len(tickers)} tickers from whitelist")
        return tickers

    def extract(self, text: str) -> list[TickerMention]:
        """Extract all ticker mentions from a piece of text.

        Applies both cashtag ($GME) and uppercase word (GME) detection,
        then deduplicates, filters against whitelist/blacklist, and
        assigns confidence scores.

        Args:
            text: The text to extract tickers from (post title + body).

        Returns:
            List of TickerMention objects, sorted by confidence descending.
        """
        mentions: dict[str, TickerMention] = {}

        # Strategy 1: Dollar-sign cashtags (highest confidence)
        for match in CASHTAG_PATTERN.finditer(text):
            ticker = match.group(1).upper()
            if self._is_valid_ticker(ticker):
                mention = TickerMention(
                    ticker=ticker,
                    confidence=self._score_confidence(ticker, "dollar_sign", text),
                    source_text=match.group(0),
                    context="dollar_sign",
                )
                # Keep the highest confidence mention per ticker
                if ticker not in mentions or mention.confidence > mentions[ticker].confidence:
                    mentions[ticker] = mention

        # Strategy 2: Uppercase words matching whitelist
        for match in UPPERCASE_WORD_PATTERN.finditer(text):
            word = match.group(1).upper()
            if word in self._whitelist and self._is_valid_ticker(word):
                if word not in mentions:  # Don't override dollar-sign matches
                    mention = TickerMention(
                        ticker=word,
                        confidence=self._score_confidence(word, "uppercase", text),
                        source_text=match.group(0),
                        context="uppercase",
                    )
                    mentions[word] = mention

        # Filter by minimum confidence
        result = [
            m for m in mentions.values()
            if m.confidence >= self._config.min_confidence
        ]

        # Sort by confidence descending
        result.sort(key=lambda m: m.confidence, reverse=True)

        if result:
            logger.debug(
                f"Extracted {len(result)} tickers: "
                f"{[f'{m.ticker}({m.confidence:.2f})' for m in result]}"
            )

        return result

    def extract_from_texts(self, texts: list[str]) -> dict[str, list[TickerMention]]:
        """Extract tickers from multiple texts and aggregate by ticker.

        Args:
            texts: List of text strings to process.

        Returns:
            Dict mapping ticker → list of all mentions across all texts.
        """
        all_mentions: dict[str, list[TickerMention]] = {}

        for text in texts:
            mentions = self.extract(text)
            for mention in mentions:
                if mention.ticker not in all_mentions:
                    all_mentions[mention.ticker] = []
                all_mentions[mention.ticker].append(mention)

        logger.info(
            f"Extracted {len(all_mentions)} unique tickers "
            f"from {len(texts)} texts"
        )
        return all_mentions

    def _is_valid_ticker(self, ticker: str) -> bool:
        """Check if a ticker passes blacklist and whitelist filters."""
        if ticker in self._blacklist:
            return False
        if not self._whitelist:
            # If no whitelist loaded, accept anything not blacklisted
            return True
        return ticker in self._whitelist

    def _score_confidence(self, ticker: str, context: str, full_text: str) -> float:
        """Calculate a confidence score for a ticker mention.

        Factors:
        - Detection method (cashtag vs uppercase word)
        - Whether ticker is in whitelist
        - Surrounding context quality
        - Ticker length (longer = less likely to be a false positive)

        Args:
            ticker: The detected ticker string.
            context: How it was detected ("dollar_sign" or "uppercase").
            full_text: The full text for context analysis.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        score = 0.0

        # Base score by detection method
        if context == "dollar_sign":
            score = 0.9  # Cashtags are almost always intentional
        elif context == "uppercase":
            score = 0.5  # Uppercase words need more validation

        # Bonus: ticker is in whitelist
        if ticker in self._whitelist:
            score = min(1.0, score + 0.1)

        # Bonus: longer tickers are less likely to be false positives
        if len(ticker) >= 4:
            score = min(1.0, score + 0.05)

        # Bonus: financial context words near the ticker
        financial_context_words = {
            "stock", "share", "shares", "calls", "puts", "options",
            "buy", "sell", "long", "short", "bullish", "bearish",
            "earnings", "revenue", "price", "target", "squeeze",
        }
        text_lower = full_text.lower()
        context_matches = sum(1 for w in financial_context_words if w in text_lower)
        if context_matches >= 2:
            score = min(1.0, score + 0.1)
        elif context_matches >= 1:
            score = min(1.0, score + 0.05)

        # Penalty: very short tickers detected as uppercase (high FP risk)
        if context == "uppercase" and len(ticker) <= 2:
            score = max(0.0, score - 0.2)

        return round(score, 2)
