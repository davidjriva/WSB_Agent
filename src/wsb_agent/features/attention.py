"""Attention metrics for tracking ticker momentum on WallStreetBets.

Measures how much attention a ticker is receiving and how fast
that attention is changing — key for detecting emerging plays
before they go viral.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from wsb_agent.models import AttentionMetrics, Post, Comment
from wsb_agent.utils.config import AttentionConfig

logger = logging.getLogger("wsb_agent.features.attention")


class AttentionTracker:
    """Tracks mention velocity and engagement metrics per ticker.

    Metrics computed:
    - mention_count: Total number of posts/comments mentioning the ticker
    - mention_velocity: Rate of change in mentions (mentions/hour)
    - engagement_weighted_mentions: Mentions weighted by post/comment score
    - sentiment_weighted_mentions: Mentions weighted by sentiment score
    """

    def __init__(self, config: AttentionConfig) -> None:
        self._config = config

    def compute_metrics(
        self,
        ticker: str,
        posts: list[Post],
        comments: list[Comment],
        post_scores: dict[str, int] | None = None,
        sentiment_scores: dict[str, float] | None = None,
    ) -> AttentionMetrics:
        """Compute attention metrics for a single ticker.

        Args:
            ticker: The stock ticker to compute metrics for.
            posts: Posts that mention this ticker.
            comments: Comments that mention this ticker.
            post_scores: Optional dict mapping post_id → score for weighting.
            sentiment_scores: Optional dict mapping text_id → sentiment score.

        Returns:
            AttentionMetrics for this ticker.
        """
        # Total mentions across posts and comments
        mention_count = len(posts) + len(comments)

        # Mention velocity: mentions per hour in the configured window
        mention_velocity = self._compute_velocity(posts, comments)

        # Engagement-weighted mentions (upvotes matter)
        engagement_weighted = self._compute_engagement_weighted(
            posts, comments, post_scores
        )

        # Sentiment-weighted mentions
        sentiment_weighted = self._compute_sentiment_weighted(
            posts, comments, sentiment_scores
        )

        metrics = AttentionMetrics(
            ticker=ticker,
            mention_count=mention_count,
            mention_velocity=round(mention_velocity, 4),
            engagement_weighted_mentions=round(engagement_weighted, 4),
            sentiment_weighted_mentions=round(sentiment_weighted, 4),
            window_hours=self._config.window_hours,
        )

        logger.debug(
            f"Attention for {ticker}: "
            f"mentions={mention_count}, "
            f"velocity={mention_velocity:.2f}/hr, "
            f"engagement={engagement_weighted:.1f}"
        )

        return metrics

    def compute_batch_metrics(
        self,
        ticker_posts: dict[str, list[Post]],
        ticker_comments: dict[str, list[Comment]],
        sentiment_scores: dict[str, float] | None = None,
    ) -> dict[str, AttentionMetrics]:
        """Compute attention metrics for multiple tickers.

        Args:
            ticker_posts: Dict mapping ticker → list of posts mentioning it.
            ticker_comments: Dict mapping ticker → list of comments mentioning it.
            sentiment_scores: Optional dict mapping text_id → sentiment score.

        Returns:
            Dict mapping ticker → AttentionMetrics.
        """
        all_tickers = set(ticker_posts.keys()) | set(ticker_comments.keys())
        results: dict[str, AttentionMetrics] = {}

        for ticker in all_tickers:
            posts = ticker_posts.get(ticker, [])
            comments = ticker_comments.get(ticker, [])
            results[ticker] = self.compute_metrics(
                ticker=ticker,
                posts=posts,
                comments=comments,
                sentiment_scores=sentiment_scores,
            )

        logger.info(f"Computed attention metrics for {len(results)} tickers")
        return results

    def _compute_velocity(
        self,
        posts: list[Post],
        comments: list[Comment],
    ) -> float:
        """Calculate mention velocity (mentions per hour).

        Uses the configured time window to determine the rate of mentions.
        Only counts items created within the window.

        Args:
            posts: Posts mentioning the ticker.
            comments: Comments mentioning the ticker.

        Returns:
            Mentions per hour within the window.
        """
        window = timedelta(hours=self._config.window_hours)
        now = datetime.now(timezone.utc)
        cutoff = now - window

        # Count items within the window
        recent_posts = sum(
            1 for p in posts
            if p.created_utc.tzinfo is not None and p.created_utc >= cutoff
        )
        recent_comments = sum(
            1 for c in comments
            if c.created_utc.tzinfo is not None and c.created_utc >= cutoff
        )

        total_recent = recent_posts + recent_comments

        if self._config.window_hours > 0:
            return total_recent / self._config.window_hours
        return 0.0

    def _compute_engagement_weighted(
        self,
        posts: list[Post],
        comments: list[Comment],
        post_scores: dict[str, int] | None = None,
    ) -> float:
        """Calculate engagement-weighted mention count.

        Each mention is weighted by the score (upvotes - downvotes) of the
        post/comment. Higher-scoring content counts more.

        Weighting: log2(max(score, 1) + 1) to dampen extreme scores.

        Args:
            posts: Posts mentioning the ticker.
            comments: Comments mentioning the ticker.
            post_scores: Optional explicit scores (overrides post.score).

        Returns:
            Engagement-weighted mention sum.
        """
        import math

        weighted = 0.0

        for post in posts:
            score = post.score if post.score > 0 else 1
            weighted += math.log2(score + 1)

        for comment in comments:
            score = comment.score if comment.score > 0 else 1
            weighted += math.log2(score + 1)

        return weighted

    @staticmethod
    def _compute_sentiment_weighted(
        posts: list[Post],
        comments: list[Comment],
        sentiment_scores: dict[str, float] | None = None,
    ) -> float:
        """Calculate sentiment-weighted mention count.

        If sentiment scores are provided, each mention is weighted by its
        sentiment score. Otherwise, returns 0.

        Args:
            posts: Posts mentioning the ticker.
            comments: Comments mentioning the ticker.
            sentiment_scores: Dict mapping item_id → sentiment score.

        Returns:
            Sentiment-weighted mention sum.
        """
        if not sentiment_scores:
            return 0.0

        weighted = 0.0
        for post in posts:
            if post.id in sentiment_scores:
                weighted += sentiment_scores[post.id]
        for comment in comments:
            if comment.id in sentiment_scores:
                weighted += sentiment_scores[comment.id]

        return weighted
