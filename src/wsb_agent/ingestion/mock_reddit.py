import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wsb_agent.models import Post, Comment
from wsb_agent.utils.config import RedditConfig, PROJECT_ROOT

logger = logging.getLogger("wsb_agent.ingestion.mock")


class MockRedditIngester:
    """Mock ingester that loads data from a local JSON file."""

    def __init__(self, config: RedditConfig, filepath: Path | None = None) -> None:
        self._config = config
        if filepath is None:
            self._filepath = PROJECT_ROOT / "tests" / "fixtures" / "sample_posts.json"
        else:
            self._filepath = filepath

    def fetch_all(
        self, limit: int | None = None
    ) -> tuple[list[Post], list[Comment]]:
        """Load posts and comments from the mock JSON file."""
        limit = limit or self._config.batch_size
        logger.info(f"MOCK: Loading up to {limit} posts from {self._filepath}")

        if not self._filepath.exists():
            logger.error(f"Mock data file not found at {self._filepath}")
            return [], []

        try:
            with open(self._filepath) as f:
                data = json.load(f)

            if isinstance(data, list):
                raw_posts = data
                raw_comments = []
            else:
                raw_posts = data.get("posts", [])
                raw_comments = data.get("comments", [])
            
            # Apply limit to posts only as per fetch_all semantics
            raw_posts = raw_posts[:limit]

            posts: list[Post] = []
            for p in raw_posts:
                created_val = p.get("created_utc")
                if isinstance(created_val, str):
                    created_utc = datetime.fromisoformat(created_val)
                elif isinstance(created_val, (int, float)):
                    created_utc = datetime.fromtimestamp(created_val, tz=timezone.utc)
                else:
                    created_utc = datetime.now(timezone.utc)
                    
                posts.append(
                    Post(
                        id=p["id"],
                        title=p["title"],
                        body=p.get("body", ""),
                        score=p.get("score", 100),
                        upvote_ratio=p.get("upvote_ratio", 0.9),
                        num_comments=p.get("num_comments", 0),
                        created_utc=created_utc,
                        author=p.get("author"),
                        url=p.get("url", ""),
                        permalink=p.get("permalink", ""),
                    )
                )

            comments: list[Comment] = []
            for c in raw_comments:
                created_val = c.get("created_utc")
                if isinstance(created_val, str):
                    created_utc = datetime.fromisoformat(created_val)
                elif isinstance(created_val, (int, float)):
                    created_utc = datetime.fromtimestamp(created_val, tz=timezone.utc)
                else:
                    created_utc = datetime.now(timezone.utc)
                    
                comments.append(
                    Comment(
                        id=c["id"],
                        body=c["body"],
                        score=c.get("score", 10),
                        created_utc=created_utc,
                        post_id=c["post_id"],
                        author=c.get("author"),
                        parent_id=c.get("parent_id"),
                    )
                )

            logger.info(f"MOCK: Loaded {len(posts)} posts and {len(comments)} comments")
            return posts, comments

        except Exception as e:
            logger.error(f"MOCK: Failed to load mock data: {e}")
            return [], []
