"""Tests for the sentiment analyzer."""

from pathlib import Path
import yaml

import pytest

from wsb_agent.features.sentiment import WSBSentimentAnalyzer
from wsb_agent.utils.config import SentimentConfig


@pytest.fixture
def lexicon_path(tmp_path: Path) -> Path:
    """Create a temporary custom WSB lexicon."""
    path = tmp_path / "wsb_lexicon.yaml"
    lexicon_data = {
        "bullish_terms": {
            "to the moon": 0.8,
            "diamond hands": 0.8,
            "tendies": 0.7,
        },
        "bearish_terms": {
            "guh": -0.9,
            "paper hands": -0.6,
            "bag holder": -0.6,
        },
        "emoji_sentiment": {
            "🚀": 0.7,
            "💎🙌": 0.8,
            "🐻": -0.5,
        }
    }
    with open(path, "w") as f:
        yaml.dump(lexicon_data, f)
    return path


@pytest.fixture
def config() -> SentimentConfig:
    """Create a test SentimentConfig."""
    return SentimentConfig(method="vader")


@pytest.fixture
def analyzer(config: SentimentConfig, lexicon_path: Path) -> WSBSentimentAnalyzer:
    """Create a WSBSentimentAnalyzer instance."""
    return WSBSentimentAnalyzer(config=config, lexicon_path=lexicon_path)


def test_analyze_text_basic_vader(analyzer: WSBSentimentAnalyzer) -> None:
    """Test fallback to standard VADER sentiment for normal text."""
    result = analyzer.analyze_text("This company has very good earnings and strong growth.")
    assert result["compound"] > 0.0
    assert result["wsb_compound"] > 0.0

    result = analyzer.analyze_text("Terrible quarter, horrible losses, completely awful.")
    assert result["compound"] < 0.0
    assert result["wsb_compound"] < 0.0


def test_wsb_specific_terms_injected(analyzer: WSBSentimentAnalyzer) -> None:
    """Test that single WSB words injected into VADER lexicon work."""
    # 'guh' is in our lexicon with -0.9, injected into VADER as -3.6
    result = analyzer.analyze_text("GUH")
    assert result["compound"] < -0.4
    assert result["wsb_compound"] < -0.4

    result = analyzer.analyze_text("tendies")
    assert result["compound"] > 0.4
    assert result["wsb_compound"] > 0.4


def test_wsb_phrases_and_emojis(analyzer: WSBSentimentAnalyzer) -> None:
    """Test that multi-word phrase adjustments and emojis work."""
    # "diamond hands" and rockets
    result = analyzer.analyze_text("holding with diamond hands 🚀 🚀")
    # Both VADER (for normal parts) and wsb adjustment should combine
    assert result["wsb_compound"] > 0.5


def test_analyze_for_ticker(analyzer: WSBSentimentAnalyzer) -> None:
    """Test aggregating sentiment across multiple texts for a ticker."""
    texts = [
        "Buying $GME to the moon! 🚀",
        "GME is looking really strong here.",
        "Lots of tendies"
    ]
    
    result = analyzer.analyze_for_ticker("GME", texts)
    
    assert result.ticker == "GME"
    assert result.mention_count == 3
    assert len(result.scores) == 3
    assert result.score > 0
    assert result.label == "bullish"


def test_analyze_for_ticker_bearish(analyzer: WSBSentimentAnalyzer) -> None:
    """Test aggregating bearish sentiment."""
    texts = [
        "Sold my $GME, looking like a bag holder.",
        "GUH. GME is tanking fast."
    ]
    
    result = analyzer.analyze_for_ticker("GME", texts)
    
    assert result.ticker == "GME"
    assert result.score < 0
    assert result.label == "bearish"


def test_analyze_no_texts(analyzer: WSBSentimentAnalyzer) -> None:
    """Test handling of empty text lists."""
    result = analyzer.analyze_for_ticker("XYZ", [])
    
    assert result.ticker == "XYZ"
    assert result.mention_count == 0
    assert result.score == 0.0
    assert result.label == "neutral"
