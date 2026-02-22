"""Tests for the Reddit ingestion module using mocked PRAW."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from wsb_agent.ingestion.reddit import RedditIngester
from wsb_agent.utils.config import RedditConfig
from wsb_agent.models import Post


@pytest.fixture
def reddit_config() -> RedditConfig:
    """Create a test Reddit configuration."""
    return RedditConfig(
        client_id="test_id",
        client_secret="test_secret",
        user_agent="test-agent",
        username="test_user",
        password="test_pass",
        subreddit="wallstreetbets",
        batch_size=5,
        lookback_hours=24,
        top_posts_for_comments=2,
        max_comments_per_post=3,
    )


@pytest.fixture
def mock_submission() -> MagicMock:
    """Create a mock PRAW Submission object."""
    sub = MagicMock()
    sub.id = "abc123"
    sub.title = "$GME to the moon 🚀🚀🚀"
    sub.selftext = "Diamond hands forever! Holding 500 shares."
    sub.score = 10000
    sub.upvote_ratio = 0.95
    sub.num_comments = 500
    sub.created_utc = 1705312200.0  # 2024-01-15T10:30:00 UTC
    sub.author = MagicMock()
    sub.author.__str__ = lambda self: "test_ape"
    sub.url = "https://reddit.com/test"
    sub.permalink = "/r/wallstreetbets/comments/abc123/test"
    return sub


@pytest.fixture
def mock_submission_2() -> MagicMock:
    """Create a second mock submission for dedup testing."""
    sub = MagicMock()
    sub.id = "def456"
    sub.title = "NVDA earnings play"
    sub.selftext = "Loading up on calls"
    sub.score = 5000
    sub.upvote_ratio = 0.88
    sub.num_comments = 200
    sub.created_utc = 1705300000.0
    sub.author = MagicMock()
    sub.author.__str__ = lambda self: "options_guy"
    sub.url = "https://reddit.com/test2"
    sub.permalink = "/r/wallstreetbets/comments/def456/test2"
    return sub


def test_submission_to_post(reddit_config: RedditConfig, mock_submission: MagicMock) -> None:
    """Test conversion of PRAW Submission to Post dataclass."""
    ingester = RedditIngester(reddit_config)
    post = ingester._submission_to_post(mock_submission)

    assert isinstance(post, Post)
    assert post.id == "abc123"
    assert post.title == "$GME to the moon 🚀🚀🚀"
    assert post.body == "Diamond hands forever! Holding 500 shares."
    assert post.score == 10000
    assert post.upvote_ratio == 0.95
    assert post.num_comments == 500
    assert isinstance(post.created_utc, datetime)


def test_post_full_text(reddit_config: RedditConfig, mock_submission: MagicMock) -> None:
    """Test that full_text combines title and body."""
    ingester = RedditIngester(reddit_config)
    post = ingester._submission_to_post(mock_submission)

    assert "$GME to the moon" in post.full_text
    assert "Diamond hands forever" in post.full_text


def test_post_full_text_removed_body() -> None:
    """Test that full_text excludes [removed] body text."""
    post = Post(
        id="test",
        title="Test title",
        body="[removed]",
        score=1,
        upvote_ratio=0.5,
        num_comments=0,
        created_utc=datetime.now(timezone.utc),
    )
    assert post.full_text == "Test title"
    assert "[removed]" not in post.full_text


@patch("wsb_agent.ingestion.reddit.praw.Reddit")
def test_fetch_hot_posts(
    mock_reddit_class: MagicMock,
    reddit_config: RedditConfig,
    mock_submission: MagicMock,
    mock_submission_2: MagicMock,
) -> None:
    """Test fetch_hot_posts returns correct posts."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_subreddit.hot.return_value = [mock_submission, mock_submission_2]
    mock_reddit.subreddit.return_value = mock_subreddit
    mock_reddit_class.return_value = mock_reddit

    ingester = RedditIngester(reddit_config)
    ingester._reddit = mock_reddit

    posts = ingester.fetch_hot_posts(limit=5)

    assert len(posts) == 2
    assert posts[0].id == "abc123"
    assert posts[1].id == "def456"


@patch("wsb_agent.ingestion.reddit.praw.Reddit")
def test_fetch_all_deduplicates(
    mock_reddit_class: MagicMock,
    reddit_config: RedditConfig,
    mock_submission: MagicMock,
    mock_submission_2: MagicMock,
) -> None:
    """Test that fetch_all deduplicates posts appearing in both hot and new."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    # Same submission appears in both hot and new
    mock_subreddit.hot.return_value = [mock_submission]
    mock_subreddit.new.return_value = [mock_submission, mock_submission_2]
    mock_reddit.subreddit.return_value = mock_subreddit
    mock_reddit_class.return_value = mock_reddit

    # Mock comment fetching to avoid real API calls
    mock_comment_submission = MagicMock()
    mock_comment_submission.comments.list.return_value = []
    mock_reddit.submission.return_value = mock_comment_submission

    ingester = RedditIngester(reddit_config)
    ingester._reddit = mock_reddit

    posts, comments = ingester.fetch_all(limit=5)

    # Should have 2 unique posts despite 3 total (1 duplicate)
    assert len(posts) == 2
    post_ids = {p.id for p in posts}
    assert "abc123" in post_ids
    assert "def456" in post_ids
