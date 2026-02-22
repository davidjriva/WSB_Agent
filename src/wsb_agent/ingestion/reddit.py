"""Reddit data ingestion for WallStreetBets.

Uses PRAW (Python Reddit API Wrapper) for authenticated access to Reddit.
Designed for batch ingestion (1-2 runs/day), not real-time streaming.
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

import praw
from praw.models import Submission

from wsb_agent.models import Post, Comment
from wsb_agent.utils.config import RedditConfig

logger = logging.getLogger("wsb_agent.ingestion.reddit")


class RedditIngester:
    """Fetches posts and comments from r/WallStreetBets via the Reddit API.

    Handles rate limiting, error recovery, and data normalization.
    """

    def __init__(self, config: RedditConfig) -> None:
        self._config = config
        self._reddit: praw.Reddit | None = None

    @property
    def reddit(self) -> praw.Reddit:
        """Lazily initialize the PRAW Reddit instance."""
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=self._config.client_id,
                client_secret=self._config.client_secret,
                user_agent=self._config.user_agent,
                username=self._config.username,
                password=self._config.password,
            )
            logger.info("Initialized Reddit API connection")
        return self._reddit

    @property
    def subreddit(self) -> praw.models.Subreddit:
        """Get the configured subreddit."""
        return self.reddit.subreddit(self._config.subreddit)

    def fetch_hot_posts(self, limit: int | None = None) -> list[Post]:
        """Fetch top hot posts from WallStreetBets.

        Args:
            limit: Max number of posts to fetch. Defaults to config batch_size.

        Returns:
            List of Post dataclasses.
        """
        limit = limit or self._config.batch_size
        logger.info(f"Fetching up to {limit} hot posts from r/{self._config.subreddit}")
        return self._fetch_posts(self.subreddit.hot(limit=limit))

    def fetch_new_posts(self, limit: int | None = None) -> list[Post]:
        """Fetch latest new posts from WallStreetBets.

        Args:
            limit: Max number of posts to fetch. Defaults to config batch_size.

        Returns:
            List of Post dataclasses.
        """
        limit = limit or self._config.batch_size
        logger.info(f"Fetching up to {limit} new posts from r/{self._config.subreddit}")
        return self._fetch_posts(self.subreddit.new(limit=limit))

    def fetch_comments(self, post_id: str, limit: int | None = None) -> list[Comment]:
        """Fetch comments for a specific post.

        Args:
            post_id: Reddit submission ID.
            limit: Max comments to fetch. Defaults to config max_comments_per_post.

        Returns:
            List of Comment dataclasses.
        """
        limit = limit or self._config.max_comments_per_post
        logger.info(f"Fetching up to {limit} comments for post {post_id}")

        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)  # Skip "load more" links

            comments: list[Comment] = []
            for comment in submission.comments.list()[:limit]:
                try:
                    comments.append(
                        Comment(
                            id=comment.id,
                            body=comment.body or "",
                            score=comment.score,
                            created_utc=datetime.fromtimestamp(
                                comment.created_utc, tz=timezone.utc
                            ),
                            post_id=post_id,
                            author=str(comment.author) if comment.author else None,
                            parent_id=comment.parent_id,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing comment {comment.id}: {e}")
                    continue

            logger.info(f"Fetched {len(comments)} comments for post {post_id}")
            return comments

        except Exception as e:
            logger.error(f"Error fetching comments for post {post_id}: {e}")
            return []

    def fetch_all(
        self, limit: int | None = None
    ) -> tuple[list[Post], list[Comment]]:
        """Fetch hot + new posts and comments for top posts.

        This is the main entry point for a pipeline run. It:
        1. Fetches hot and new posts
        2. Deduplicates by post ID
        3. Fetches comments for the top posts by engagement

        Args:
            limit: Max posts per category (hot, new). Defaults to config batch_size.

        Returns:
            Tuple of (all_posts, all_comments).
        """
        limit = limit or self._config.batch_size

        # Fetch both hot and new posts
        hot_posts = self.fetch_hot_posts(limit)
        new_posts = self.fetch_new_posts(limit)

        # Deduplicate by post ID
        seen_ids: set[str] = set()
        all_posts: list[Post] = []
        for post in hot_posts + new_posts:
            if post.id not in seen_ids:
                seen_ids.add(post.id)
                all_posts.append(post)

        logger.info(
            f"Total unique posts: {len(all_posts)} "
            f"(hot: {len(hot_posts)}, new: {len(new_posts)}, "
            f"duplicates removed: {len(hot_posts) + len(new_posts) - len(all_posts)})"
        )

        # Fetch comments for top posts by engagement
        all_posts_sorted = sorted(all_posts, key=lambda p: p.score, reverse=True)
        top_posts = all_posts_sorted[: self._config.top_posts_for_comments]

        all_comments: list[Comment] = []
        for post in top_posts:
            comments = self.fetch_comments(post.id)
            all_comments.extend(comments)
            # Small delay between comment fetches to be kind to rate limits
            time.sleep(0.5)

        logger.info(
            f"Fetched {len(all_comments)} total comments "
            f"from top {len(top_posts)} posts"
        )

        return all_posts, all_comments

    def _fetch_posts(self, submissions) -> list[Post]:
        """Convert PRAW submission objects to Post dataclasses.

        Args:
            submissions: Iterable of PRAW Submission objects.

        Returns:
            List of Post dataclasses.
        """
        posts: list[Post] = []
        for submission in submissions:
            try:
                post = self._submission_to_post(submission)
                posts.append(post)
            except Exception as e:
                logger.warning(f"Error parsing submission: {e}")
                continue

        logger.info(f"Parsed {len(posts)} posts")
        return posts

    @staticmethod
    def _submission_to_post(submission: Submission) -> Post:
        """Convert a single PRAW Submission to a Post dataclass."""
        return Post(
            id=submission.id,
            title=submission.title or "",
            body=submission.selftext or "",
            score=submission.score,
            upvote_ratio=submission.upvote_ratio,
            num_comments=submission.num_comments,
            created_utc=datetime.fromtimestamp(
                submission.created_utc, tz=timezone.utc
            ),
            author=str(submission.author) if submission.author else None,
            url=submission.url,
            permalink=f"https://reddit.com{submission.permalink}",
        )
