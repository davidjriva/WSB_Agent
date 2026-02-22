"""Sentiment analysis for WallStreetBets text.

Combines VADER (Valence Aware Dictionary and sEntiment Reasoner) with a
custom WSB lexicon that maps WSB-specific slang, phrases, and emojis
to sentiment values.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from wsb_agent.models import SentimentResult
from wsb_agent.utils.config import SentimentConfig, PROJECT_ROOT

logger = logging.getLogger("wsb_agent.features.sentiment")


class WSBSentimentAnalyzer:
    """Sentiment analyzer combining VADER with custom WSB lexicon.

    The WSB lexicon augments VADER's default word list with:
    - Bullish terms ("diamond hands", "to the moon", "tendies")
    - Bearish terms ("guh", "bag holder", "paper hands")
    - Emoji sentiment (🚀 = bullish, 🐻 = bearish)
    """

    def __init__(
        self,
        config: SentimentConfig,
        lexicon_path: Path | None = None,
    ) -> None:
        self._config = config
        self._vader = SentimentIntensityAnalyzer()

        # Load and inject WSB lexicon
        if lexicon_path is None:
            lexicon_path = PROJECT_ROOT / "data" / "wsb_lexicon.yaml"
        self._wsb_lexicon = self._load_wsb_lexicon(lexicon_path)
        self._inject_lexicon()

    def _load_wsb_lexicon(self, path: Path) -> dict[str, float]:
        """Load the custom WSB lexicon from YAML.

        Returns a flat dict mapping term → sentiment value.
        """
        lexicon: dict[str, float] = {}

        if not path.exists():
            logger.warning(f"WSB lexicon not found at {path}")
            return lexicon

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Flatten the categorized structure into a single dict
        for category in ["bullish_terms", "bearish_terms", "emoji_sentiment"]:
            terms = data.get(category, {})
            if isinstance(terms, dict):
                for term, score in terms.items():
                    lexicon[str(term)] = float(score)

        logger.info(f"Loaded {len(lexicon)} terms from WSB lexicon")
        return lexicon

    def _inject_lexicon(self) -> None:
        """Inject WSB-specific terms into VADER's lexicon.

        VADER uses a dict (self._vader.lexicon) mapping word → sentiment.
        We add/override entries with our WSB-specific scores, scaled to
        VADER's typical range (~-4 to +4).
        """
        injected = 0
        for term, score in self._wsb_lexicon.items():
            # VADER lexicon uses a -4 to +4 scale, our lexicon uses -1 to +1
            vader_score = score * 4.0
            self._vader.lexicon[term] = vader_score
            injected += 1

        logger.info(f"Injected {injected} WSB terms into VADER lexicon")

    def analyze_text(self, text: str) -> dict[str, float]:
        """Get sentiment scores for a piece of text.

        Returns VADER's full score dict plus a WSB-adjusted compound score.

        Args:
            text: Text to analyze.

        Returns:
            Dict with keys: neg, neu, pos, compound, wsb_compound.
        """
        # Run VADER (now with WSB terms injected)
        vader_scores = self._vader.polarity_scores(text)

        # Also calculate WSB-specific score based on phrase matching
        wsb_adjustment = self._calculate_wsb_adjustment(text)

        # Blend: VADER compound + WSB adjustment
        blended = vader_scores["compound"] + wsb_adjustment
        # Clamp to [-1, 1]
        blended = max(-1.0, min(1.0, blended))

        return {
            "neg": vader_scores["neg"],
            "neu": vader_scores["neu"],
            "pos": vader_scores["pos"],
            "compound": vader_scores["compound"],
            "wsb_compound": round(blended, 4),
        }

    def _calculate_wsb_adjustment(self, text: str) -> float:
        """Calculate sentiment adjustment from multi-word WSB phrases and emojis.

        VADER only handles single words in its lexicon. This method detects
        multi-word phrases (e.g., "diamond hands", "to the moon") and emojis
        that VADER might miss, and produces an adjustment score.

        Args:
            text: The text to analyze.

        Returns:
            Adjustment value to add to VADER's compound score.
        """
        text_lower = text.lower()
        adjustment = 0.0
        matches = 0

        for term, score in self._wsb_lexicon.items():
            # Only process multi-word phrases and emojis here
            # (single words are already handled by VADER injection)
            if " " in term or not term.isascii():
                if term.lower() in text_lower or term in text:
                    adjustment += score * 0.3  # Weighted contribution
                    matches += 1

        if matches > 0:
            logger.debug(f"WSB adjustment: {adjustment:.3f} from {matches} phrase/emoji matches")

        return adjustment

    def analyze_for_ticker(
        self,
        ticker: str,
        texts: list[str],
    ) -> SentimentResult:
        """Analyze sentiment across multiple texts mentioning a ticker.

        Args:
            ticker: The stock ticker being analyzed.
            texts: All text snippets mentioning this ticker.

        Returns:
            Aggregated SentimentResult for the ticker.
        """
        if not texts:
            return SentimentResult(
                ticker=ticker,
                score=0.0,
                label="neutral",
                compound=0.0,
                mention_count=0,
                scores=[],
            )

        scores: list[float] = []
        compounds: list[float] = []

        for text in texts:
            result = self.analyze_text(text)
            scores.append(result["wsb_compound"])
            compounds.append(result["compound"])

        avg_score = sum(scores) / len(scores)
        avg_compound = sum(compounds) / len(compounds)

        # Determine label
        if avg_score > 0.1:
            label = "bullish"
        elif avg_score < -0.1:
            label = "bearish"
        else:
            label = "neutral"

        return SentimentResult(
            ticker=ticker,
            score=round(avg_score, 4),
            label=label,
            compound=round(avg_compound, 4),
            mention_count=len(texts),
            scores=scores,
        )
