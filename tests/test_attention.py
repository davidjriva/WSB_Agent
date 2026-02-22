"""Tests for the attention metrics feature."""

from datetime import datetime, timezone, timedelta
import pytest

from wsb_agent.features.attention import AttentionTracker
from wsb_agent.utils.config import AttentionConfig
from wsb_agent.models import Post, Comment


@pytest.fixture
def config() -> AttentionConfig:
    """Create a test AttentionConfig."""
    return AttentionConfig(window_hours=6)


@pytest.fixture
def tracker(config: AttentionConfig) -> AttentionTracker:
    """Create an AttentionTracker instance."""
    return AttentionTracker(config)


def test_compute_metrics_basic(tracker: AttentionTracker) -> None:
    """Test basic attention metrics computation without specific sentiments."""
    now = datetime.now(timezone.utc)
    
    posts = [
        Post(id="p1", title="A", body="", score=10, upvote_ratio=0.9, num_comments=5, created_utc=now),
        Post(id="p2", title="B", body="", score=3, upvote_ratio=0.9, num_comments=1, created_utc=now - timedelta(hours=1)),
    ]
    comments = [
        Comment(id="c1", body="C", score=100, created_utc=now - timedelta(hours=2), post_id="p1"),
    ]
    
    metrics = tracker.compute_metrics("GME", posts, comments)
    
    assert metrics.ticker == "GME"
    assert metrics.mention_count == 3
    assert metrics.mention_velocity == 3 / 6  # 3 mentions in 6 hour window
    # check that engagement weighted is non-zero
    assert metrics.engagement_weighted_mentions > 0
    assert metrics.sentiment_weighted_mentions == 0.0


def test_compute_metrics_velocity_window(tracker: AttentionTracker) -> None:
    """Test that velocity calculation respects the time window."""
    now = datetime.now(timezone.utc)
    
    posts = [
        Post(id="p1", title="A", body="", score=10, upvote_ratio=0.9, num_comments=5, created_utc=now),
        # This post is older than the window
        Post(id="p2", title="B", body="", score=3, upvote_ratio=0.9, num_comments=1, created_utc=now - timedelta(hours=10)),
    ]
    
    metrics = tracker.compute_metrics("GME", posts, [])
    
    assert metrics.mention_count == 2
    # Only 1 mention falls inside the 6 hour window
    assert metrics.mention_velocity == pytest.approx(1 / 6, abs=1e-3)


def test_compute_sentiment_weighted(tracker: AttentionTracker) -> None:
    """Test sentiment weighting calculations."""
    now = datetime.now(timezone.utc)
    
    posts = [
        Post(id="p1", title="A", body="", score=10, upvote_ratio=0.9, num_comments=5, created_utc=now),
    ]
    comments = [
        Comment(id="c1", body="C", score=100, created_utc=now, post_id="p1"),
    ]
    
    sentiment_scores = {"p1": 0.8, "c1": -0.2}
    
    metrics = tracker.compute_metrics("AAPL", posts, comments, sentiment_scores=sentiment_scores)
    
    assert metrics.sentiment_weighted_mentions == pytest.approx(0.6)


def test_compute_batch_metrics(tracker: AttentionTracker) -> None:
    """Test batch metrics calculation across multiple tickers."""
    now = datetime.now(timezone.utc)
    p1 = Post(id="p1", title="A", body="", score=10, upvote_ratio=0.9, num_comments=5, created_utc=now)
    c1 = Comment(id="c1", body="C", score=100, created_utc=now, post_id="px")
    
    ticker_posts = {"TSLA": [p1]}
    ticker_comments = {"TSLA": [c1], "AAPL": [c1]}
    
    results = tracker.compute_batch_metrics(ticker_posts, ticker_comments)
    
    assert "TSLA" in results
    assert results["TSLA"].mention_count == 2
    
    assert "AAPL" in results
    assert results["AAPL"].mention_count == 1
