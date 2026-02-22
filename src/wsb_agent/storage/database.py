"""SQLite-based persistence layer for WSB Agent.

Stores raw posts, comments, features, and signals for historical analysis
and pipeline state tracking.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from wsb_agent.models import Post, Comment, Signal

logger = logging.getLogger("wsb_agent.storage.database")

# Schema version for simple migration support
SCHEMA_VERSION = 2

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Raw Reddit posts
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    upvote_ratio REAL NOT NULL DEFAULT 0.0,
    num_comments INTEGER NOT NULL DEFAULT 0,
    created_utc TEXT NOT NULL,
    author TEXT,
    url TEXT,
    permalink TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Raw Reddit comments
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    created_utc TEXT NOT NULL,
    post_id TEXT NOT NULL,
    author TEXT,
    parent_id TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- Generated signals
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    composite_score REAL NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    components TEXT,  -- JSON serialized
    reasoning TEXT,
    metadata TEXT, -- JSON serialized
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Portfolio history tracking
CREATE TABLE IF NOT EXISTS portfolio_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_equity REAL NOT NULL,
    cash REAL NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Pipeline run log
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    posts_ingested INTEGER DEFAULT 0,
    comments_ingested INTEGER DEFAULT 0,
    tickers_found INTEGER DEFAULT 0,
    signals_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_portfolio_history_timestamp ON portfolio_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
"""


class Database:
    """SQLite database manager for WSB Agent.

    Handles schema creation, data insertion, and querying.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._conn is None:
            # Ensure the data directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")

            logger.info(f"Connected to database at {self._db_path}")
            self._ensure_schema()

        return self._conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript(SCHEMA_SQL)

        # Check/set schema version
        cursor = self.conn.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = cursor.fetchone()
        current_version = row[0] if row[0] is not None else 0

        if current_version < SCHEMA_VERSION:
            if current_version < 2:
                logger.info("Migrating database to version 2: Adding 'metadata' to 'signals' table...")
                try:
                    self.conn.execute("ALTER TABLE signals ADD COLUMN metadata TEXT")
                    self.conn.commit()
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.debug("Metadata column already exists, skipping ALTER.")
                    else:
                        raise e

            self.conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            self.conn.commit()
            logger.info(f"Database schema at version {SCHEMA_VERSION}")

    # ── Post operations ─────────────────────────────────────────────────

    def insert_posts(self, posts: list[Post]) -> int:
        """Insert posts into the database, skipping duplicates.

        Args:
            posts: List of Post dataclasses.

        Returns:
            Number of new posts inserted.
        """
        inserted = 0
        for post in posts:
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO posts
                    (id, title, body, score, upvote_ratio, num_comments,
                     created_utc, author, url, permalink)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        post.id,
                        post.title,
                        post.body,
                        post.score,
                        post.upvote_ratio,
                        post.num_comments,
                        post.created_utc.isoformat(),
                        post.author,
                        post.url,
                        post.permalink,
                    ),
                )
                if self.conn.total_changes > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Error inserting post {post.id}: {e}")

        self.conn.commit()
        logger.info(f"Inserted {inserted} new posts (skipped {len(posts) - inserted} duplicates)")
        return inserted

    def insert_comments(self, comments: list[Comment]) -> int:
        """Insert comments into the database, skipping duplicates.

        Args:
            comments: List of Comment dataclasses.

        Returns:
            Number of new comments inserted.
        """
        inserted = 0
        for comment in comments:
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO comments
                    (id, body, score, created_utc, post_id, author, parent_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        comment.id,
                        comment.body,
                        comment.score,
                        comment.created_utc.isoformat(),
                        comment.post_id,
                        comment.author,
                        comment.parent_id,
                    ),
                )
                if self.conn.total_changes > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Error inserting comment {comment.id}: {e}")

        self.conn.commit()
        logger.info(f"Inserted {inserted} new comments")
        return inserted

    # ── Signal operations ────────────────────────────────────────────────

    def insert_signals(self, signals: list[Signal]) -> int:
        """Insert generated signals into the database.

        Args:
            signals: List of Signal dataclasses.

        Returns:
            Number of signals inserted.
        """
        inserted = 0
        for signal in signals:
            try:
                self.conn.execute(
                    """INSERT INTO signals
                    (ticker, composite_score, action, confidence,
                     components, reasoning, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        signal.ticker,
                        signal.composite_score,
                        signal.action,
                        signal.confidence,
                        json.dumps(signal.components),
                        signal.reasoning,
                        json.dumps(signal.metadata),
                        signal.timestamp.isoformat(),
                    ),
                )
                inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Error inserting signal for {signal.ticker}: {e}")

        self.conn.commit()
        logger.info(f"Inserted {inserted} signals")
        return inserted

    # ── Portfolio history operations ─────────────────────────────────────

    def insert_portfolio_snapshot(self, total_equity: float, cash: float) -> None:
        """Record a snapshot of portfolio valuation.

        Args:
            total_equity: Total value including holdings.
            cash: Uninvested cash available.
        """
        try:
            self.conn.execute(
                "INSERT INTO portfolio_history (total_equity, cash, timestamp) VALUES (?, ?, ?)",
                (total_equity, cash, datetime.now().isoformat()),
            )
            self.conn.commit()
            logger.info(f"Recorded portfolio snapshot: Equity=${total_equity:,.2f}")
        except sqlite3.Error as e:
            logger.error(f"Error inserting portfolio snapshot: {e}")

    def get_portfolio_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch historical portfolio valuation data.

        Args:
            limit: Max number of data points to return.

        Returns:
            List of historic snapshot dicts.
        """
        cursor = self.conn.execute(
            "SELECT * FROM portfolio_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        # Return as dicts so they are easy to serialize to JSON by FastAPI
        return [dict(row) for row in cursor.fetchall()]

    # ── Pipeline run tracking ────────────────────────────────────────────

    def start_pipeline_run(self) -> int:
        """Record the start of a pipeline run.

        Returns:
            The run ID for tracking.
        """
        cursor = self.conn.execute(
            "INSERT INTO pipeline_runs (started_at) VALUES (?)",
            (datetime.now().isoformat(),),
        )
        self.conn.commit()
        run_id = cursor.lastrowid
        logger.info(f"Started pipeline run #{run_id}")
        return run_id  # type: ignore[return-value]

    def complete_pipeline_run(
        self,
        run_id: int,
        posts_ingested: int = 0,
        comments_ingested: int = 0,
        tickers_found: int = 0,
        signals_generated: int = 0,
        status: str = "completed",
        error_message: str | None = None,
    ) -> None:
        """Record the completion of a pipeline run.

        Args:
            run_id: The run ID from start_pipeline_run.
            posts_ingested: Number of posts processed.
            comments_ingested: Number of comments processed.
            tickers_found: Number of unique tickers identified.
            signals_generated: Number of signals produced.
            status: Final status ("completed" or "failed").
            error_message: Error details if status is "failed".
        """
        self.conn.execute(
            """UPDATE pipeline_runs SET
                completed_at = ?,
                posts_ingested = ?,
                comments_ingested = ?,
                tickers_found = ?,
                signals_generated = ?,
                status = ?,
                error_message = ?
            WHERE id = ?""",
            (
                datetime.now().isoformat(),
                posts_ingested,
                comments_ingested,
                tickers_found,
                signals_generated,
                status,
                error_message,
                run_id,
            ),
        )
        self.conn.commit()
        logger.info(f"Completed pipeline run #{run_id} (status: {status})")

    # ── Query helpers ────────────────────────────────────────────────────

    def get_recent_signals(self, limit: int = 50) -> list[Signal]:
        """Fetch the most recent signals.

        Args:
            limit: Max number of signals to return.

        Returns:
            List of Signal objects.
        """
        cursor = self.conn.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        signals = []
        for row in cursor.fetchall():
            try:
                signals.append(
                    Signal(
                        ticker=row["ticker"],
                        composite_score=row["composite_score"],
                        action=row["action"],
                        confidence=row["confidence"],
                        components=json.loads(row["components"]) if row["components"] else {},
                        reasoning=row["reasoning"],
                        metadata=json.loads(row["metadata"]) if "metadata" in row.keys() and row["metadata"] else {},
                        timestamp=datetime.fromisoformat(row["created_at"]),
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing signal row: {e}")
        return signals

    def get_ticker_signals(self, ticker: str, limit: int = 50) -> list[Signal]:
        """Fetch historical signals for a specific ticker.

        Args:
            ticker: The stock ticker to filter by.
            limit: Max number of signals to return.

        Returns:
            List of Signal objects.
        """
        cursor = self.conn.execute(
            "SELECT * FROM signals WHERE ticker = ? ORDER BY created_at DESC LIMIT ?",
            (ticker.upper(), limit),
        )
        signals = []
        for row in cursor.fetchall():
            try:
                signals.append(
                    Signal(
                        ticker=row["ticker"],
                        composite_score=row["composite_score"],
                        action=row["action"],
                        confidence=row["confidence"],
                        components=json.loads(row["components"]) if row["components"] else {},
                        reasoning=row["reasoning"],
                        metadata=json.loads(row["metadata"]) if "metadata" in row.keys() and row["metadata"] else {},
                        timestamp=datetime.fromisoformat(row["created_at"]),
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing signal row for {ticker}: {e}")
        return signals

    def get_post_count(self) -> int:
        """Get total number of stored posts."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM posts")
        return cursor.fetchone()[0]

    def get_comment_count(self) -> int:
        """Get total number of stored comments."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM comments")
        return cursor.fetchone()[0]

    def clear_signals(self) -> None:
        """Triggers a full reset of the signals table."""
        try:
            self.conn.execute("DELETE FROM signals")
            self.conn.commit()
            logger.info("Signals table cleared successfully")
        except sqlite3.Error as e:
            logger.error(f"Error clearing signals table: {e}")

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
