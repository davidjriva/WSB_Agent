"""Tests for the ticker extraction feature."""

from pathlib import Path
import tempfile
import csv

import pytest

from wsb_agent.features.tickers import TickerExtractor
from wsb_agent.utils.config import TickerExtractionConfig


@pytest.fixture
def whitelist_path(tmp_path: Path) -> Path:
    """Create a temporary whitelist CSV."""
    path = tmp_path / "whitelist.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "name", "exchange"])
        writer.writeheader()
        writer.writerow({"ticker": "GME", "name": "GameStop", "exchange": "NYSE"})
        writer.writerow({"ticker": "AAPL", "name": "Apple", "exchange": "NASDAQ"})
        writer.writerow({"ticker": "TSLA", "name": "Tesla", "exchange": "NASDAQ"})
        writer.writerow({"ticker": "NVDA", "name": "Nvidia", "exchange": "NASDAQ"})
    return path


@pytest.fixture
def config() -> TickerExtractionConfig:
    """Create a test TickerExtractionConfig."""
    return TickerExtractionConfig(
        min_confidence=0.3,
        blacklist=["DD", "YOLO", "ALL", "FOR"],
    )


@pytest.fixture
def extractor(config: TickerExtractionConfig, whitelist_path: Path) -> TickerExtractor:
    """Create a TickerExtractor instance."""
    return TickerExtractor(config=config, whitelist_path=whitelist_path)


def test_extract_cashtags(extractor: TickerExtractor) -> None:
    """Test extracting tickers using cashtags."""
    text = "Loading up on $GME and $AAPL options!"
    mentions = extractor.extract(text)
    
    assert len(mentions) == 2
    
    tickers = {m.ticker: m for m in mentions}
    assert "GME" in tickers
    assert tickers["GME"].context == "dollar_sign"
    assert tickers["GME"].confidence >= 0.9  # High confidence for cashtag + whitelist
    
    assert "AAPL" in tickers
    assert tickers["AAPL"].context == "dollar_sign"


def test_extract_uppercase_words(extractor: TickerExtractor) -> None:
    """Test extracting tickers using uppercase words."""
    text = "I think TSLA is going to moon."
    mentions = extractor.extract(text)
    
    assert len(mentions) == 1
    assert mentions[0].ticker == "TSLA"
    assert mentions[0].context == "uppercase"
    # Lower confidence than cashtag, but boosted by being in whitelist
    assert 0.5 <= mentions[0].confidence < 0.9


def test_extract_deduplication(extractor: TickerExtractor) -> None:
    """Test that multiple mentions of same ticker keep the highest confidence."""
    # $GME (cashtag) should win over GME (uppercase)
    text = "GME is great. I love $GME. GME to the moon!"
    mentions = extractor.extract(text)
    
    assert len(mentions) == 1
    assert mentions[0].ticker == "GME"
    assert mentions[0].context == "dollar_sign"


def test_blacklist_filtering(extractor: TickerExtractor) -> None:
    """Test that blacklisted words are ignored even if capitalized."""
    text = "I did my DD on ALL the stocks for YOLO."
    mentions = extractor.extract(text)
    
    assert len(mentions) == 0


def test_whitelist_filtering(extractor: TickerExtractor) -> None:
    """Test that non-whitelisted words and cashtags are ignored."""
    text = "RANDOM uppercase word and $FAKE cashtag"
    mentions = extractor.extract(text)
    
    # "RANDOM" is uppercase but not in whitelist
    # "$FAKE" is a cashtag but not in whitelist
    assert len(mentions) == 0


def test_financial_context_boost(extractor: TickerExtractor) -> None:
    """Test that financial words boost the confidence score."""
    text_no_context = "I saw $GME."
    text_with_context = "I saw $GME stock calls options."
    
    mentions_no_context = extractor.extract(text_no_context)
    mentions_with_context = extractor.extract(text_with_context)
    
    assert mentions_with_context[0].confidence >= mentions_no_context[0].confidence


def test_extract_from_texts(extractor: TickerExtractor) -> None:
    """Test aggregation across multiple texts."""
    texts = [
        "Buying $GME",
        "Selling $AAPL",
        "More GME stock"
    ]
    results = extractor.extract_from_texts(texts)
    
    assert "GME" in results
    assert len(results["GME"]) == 2  # Appears in two texts
    assert "AAPL" in results
    assert len(results["AAPL"]) == 1
