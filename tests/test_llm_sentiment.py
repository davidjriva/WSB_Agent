"""Tests for the local LLM Sentiment Analyzer."""

import json
from unittest.mock import patch, Mock

import pytest
from requests.exceptions import Timeout, RequestException

from wsb_agent.features.llm_sentiment import LLMSentimentAnalyzer, FALLBACK_SCORE
from wsb_agent.utils.config import FeaturesConfig, LLMConfig, SentimentConfig, TickerExtractionConfig, AttentionConfig


@pytest.fixture
def mock_config():
    return FeaturesConfig(
        ticker_extraction=TickerExtractionConfig(),
        sentiment=SentimentConfig(method="llm"),
        llm=LLMConfig(provider="ollama", model="test-llama", endpoint="http://localhost:11434"),
        attention=AttentionConfig(),
    )


@patch("wsb_agent.features.llm_sentiment.requests.get")
def test_initialization_connection_check(mock_get, mock_config):
    """Test that it pings Ollama on startup."""
    mock_get.return_value = Mock(status_code=200)
    analyzer = LLMSentimentAnalyzer(mock_config)
    mock_get.assert_called_once_with("http://localhost:11434/", timeout=3)


@patch("wsb_agent.features.llm_sentiment.requests.get")
def test_json_parsing_direct(mock_get, mock_config):
    """Test parsing standard JSON response."""
    analyzer = LLMSentimentAnalyzer(mock_config)
    
    valid_json = '{"score": 0.8, "reasoning": "Very bullish on earnings"}'
    parsed = analyzer._parse_llm_response(valid_json)
    
    assert parsed["score"] == 0.8
    assert "bullish" in parsed["reasoning"]


@patch("wsb_agent.features.llm_sentiment.requests.get")
def test_json_parsing_markdown_blocks(mock_get, mock_config):
    """Test extracting JSON from markdown code blocks."""
    analyzer = LLMSentimentAnalyzer(mock_config)
    
    complex_response = '''Here is your analysis:
    ```json
    {
        "score": -0.5,
        "reasoning": "They missed revenue targets."
    }
    ```
    Hope this helps!'''
    
    parsed = analyzer._parse_llm_response(complex_response)
    assert parsed["score"] == -0.5
    assert "revenue" in parsed["reasoning"]


@patch("wsb_agent.features.llm_sentiment.requests.get")
def test_json_parsing_failure_fallback(mock_get, mock_config):
    """Test totally corrupted output falls back safely."""
    analyzer = LLMSentimentAnalyzer(mock_config)
    
    bad_response = "I am an AI and I cannot answer this."
    parsed = analyzer._parse_llm_response(bad_response)
    
    assert parsed["score"] == FALLBACK_SCORE
    assert "Failed" in parsed["reasoning"]


@patch("wsb_agent.features.llm_sentiment.requests.post")
@patch("wsb_agent.features.llm_sentiment.requests.get")
def test_analyze_for_ticker_success(mock_get, mock_post, mock_config):
    """Test full execution of the generation endpoint."""
    analyzer = LLMSentimentAnalyzer(mock_config)
    
    # Mock Ollama response
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"score": 1.0, "reasoning": "Rocket emojis."}'
    }
    mock_post.return_value = mock_response
    
    result = analyzer.analyze_for_ticker("GME", ["GME to the moon! 🚀🚀🚀"])
    
    assert result.score == 1.0
    assert result.mention_count == 1
    
    # Verify payload format
    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["json"]["model"] == "test-llama"
    assert called_kwargs["json"]["format"] == "json"
    assert "GME" in called_kwargs["json"]["prompt"]


@patch("wsb_agent.features.llm_sentiment.requests.post")
@patch("wsb_agent.features.llm_sentiment.requests.get")
def test_analyze_for_ticker_timeout(mock_get, mock_post, mock_config):
    """Test that timeouts don't crash the pipeline, but return neutral."""
    analyzer = LLMSentimentAnalyzer(mock_config)
    mock_post.side_effect = Timeout("Connection timed out")
    
    result = analyzer.analyze_for_ticker("AAPL", ["I think AAPL is okay."])
    
    assert result.score == FALLBACK_SCORE
    assert result.mention_count == 1
