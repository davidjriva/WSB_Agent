"""Tests for the SQLite database storage layer."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from wsb_agent.storage.database import Database
from wsb_agent.models import Post, Comment, Signal


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a temporary test database."""
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def sample_posts() -> list[Post]:
    """Create sample posts for testing."""
    return [
        Post(
            id="post_001",
            title="$GME to the moon 🚀🚀🚀",
            body="Diamond hands forever!",
            score=10000,
            upvote_ratio=0.95,
            num_comments=500,
            created_utc=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            author="test_ape",
        ),
        Post(
            id="post_002",
            title="NVDA earnings play",
            body="Loading up on calls",
            score=5000,
            upvote_ratio=0.88,
            num_comments=200,
            created_utc=datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc),
            author="options_guy",
        ),
    ]


@pytest.fixture
def sample_comments() -> list[Comment]:
    """Create sample comments for testing."""
    return [
        Comment(
            id="comment_001",
            body="This is the way 🚀",
            score=500,
            created_utc=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
            post_id="post_001",
            author="ape1",
        ),
        Comment(
            id="comment_002",
            body="Bearish on this one",
            score=50,
            created_utc=datetime(2024, 1, 15, 11, 30, tzinfo=timezone.utc),
            post_id="post_001",
            author="bear_guy",
        ),
    ]


@pytest.fixture
def sample_signals() -> list[Signal]:
    """Create sample signals for testing."""
    return [
        Signal(
            ticker="GME",
            composite_score=0.75,
            action="BUY",
            confidence=0.8,
            components={"sentiment": 0.9, "velocity": 0.7},
            reasoning="High mention velocity with strong bullish sentiment",
            timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        ),
        Signal(
            ticker="NVDA",
            composite_score=0.45,
            action="HOLD",
            confidence=0.6,
            components={"sentiment": 0.5, "velocity": 0.4},
            reasoning="Moderate sentiment, below buy threshold",
            timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        ),
    ]


def test_schema_creation(db: Database) -> None:
    """Test that the database schema is created on first connection."""
    # Access .conn to trigger schema creation
    conn = db.conn
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}

    assert "posts" in tables
    assert "comments" in tables
    assert "signals" in tables
    assert "pipeline_runs" in tables
    assert "schema_version" in tables


def test_insert_posts(db: Database, sample_posts: list[Post]) -> None:
    """Test inserting posts."""
    inserted = db.insert_posts(sample_posts)
    assert inserted > 0
    assert db.get_post_count() == 2


def test_insert_posts_dedup(db: Database, sample_posts: list[Post]) -> None:
    """Test that duplicate posts are skipped."""
    db.insert_posts(sample_posts)
    # Insert same posts again
    db.insert_posts(sample_posts)
    # Should still have only 2 posts
    assert db.get_post_count() == 2


def test_insert_comments(
    db: Database, sample_posts: list[Post], sample_comments: list[Comment]
) -> None:
    """Test inserting comments."""
    db.insert_posts(sample_posts)  # Need posts for FK
    inserted = db.insert_comments(sample_comments)
    assert inserted > 0
    assert db.get_comment_count() == 2


def test_insert_signals(db: Database, sample_signals: list[Signal]) -> None:
    """Test inserting signals."""
    inserted = db.insert_signals(sample_signals)
    assert inserted == 2

    recent = db.get_recent_signals(limit=10)
    assert len(recent) == 2


def test_pipeline_run_tracking(db: Database) -> None:
    """Test pipeline run start and completion tracking."""
    run_id = db.start_pipeline_run()
    assert run_id is not None

    db.complete_pipeline_run(
        run_id=run_id,
        posts_ingested=50,
        comments_ingested=200,
        tickers_found=15,
        signals_generated=8,
        status="completed",
    )

    cursor = db.conn.execute(
        "SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)
    )
    row = dict(cursor.fetchone())
    assert row["status"] == "completed"
    assert row["posts_ingested"] == 50
    assert row["signals_generated"] == 8


def test_context_manager(tmp_path: Path) -> None:
    """Test database as context manager."""
    with Database(tmp_path / "ctx_test.db") as db:
        assert db.get_post_count() == 0
    # Connection should be closed after context exit
    assert db._conn is None
