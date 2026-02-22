"""CLI entry point for the WSB Agent pipeline.

Orchestrates the entire process:
1. Ingest Reddit posts and comments
2. Extract ticker mentions
3. Calculate sentiment and attention metrics
4. Fetch market data for identified tickers
5. Generate composite signals
6. Store results and output JSON
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from wsb_agent.utils.config import load_config
from wsb_agent.utils.logging import setup_logging
from wsb_agent.ingestion.reddit import RedditIngester
from wsb_agent.ingestion.mock_reddit import MockRedditIngester
from wsb_agent.ingestion.market import create_market_provider
from wsb_agent.features.tickers import TickerExtractor
from wsb_agent.features.sentiment import WSBSentimentAnalyzer
from wsb_agent.features.llm_sentiment import LLMSentimentAnalyzer
from wsb_agent.features.attention import AttentionTracker
from wsb_agent.signals.market_features import MarketFeatureExtractor
from wsb_agent.signals.engine import SignalEngine
from wsb_agent.storage.database import Database
from wsb_agent.utils.notifications import DiscordNotifier

logger = logging.getLogger("wsb_agent.scripts.run_pipeline")


def _setup_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WSB Agent Pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        help="Max number of Reddit posts to ingest per category (hot/new). Override config.",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        help="Only consider posts from the last H hours. Override config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run ingestion only for testing connectivity, print to stdout.",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "table"],
        default="json",
        help="Output format for generated signals.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom settings.yaml.",
    )
    parser.add_argument(
        "--mock",
        type=str,
        nargs="?",
        const="tests/fixtures/sample_posts.json",
        help="Run pipeline using mock JSON data instead of fetching from Reddit. Optionally provide path.",
    )
    return parser


def run_pipeline() -> None:
    """Execute the full WSB Agent pipeline."""
    parser = _setup_argparser()
    args = parser.parse_args()

    # 1. Load configuration and setup logging
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path=config_path)

    # CLI overrides
    limit = args.limit or config.reddit.batch_size
    # (lookback limitation conceptually applies during ingestion DB queries or feature calc, 
    # but for V1 we just use it implicitly via batch_size and hot/new sort)

    # Initialize logging format based on args if needed (defaulting to text, output can be json)
    # The actual application logs will be text, but final result printed correctly.
    setup_logging(level=config.logging.level, log_format=config.logging.format)

    logger.info(f"Starting WSB Agent pipeline run (limit={limit})")

    # 2. Setup Database
    db = Database(config.storage.absolute_database_path)
    run_id = db.start_pipeline_run()

    try:
        # Initialize components
        if args.mock:
            mock_path = Path(args.mock) if args.mock is not True else None
            reddit = MockRedditIngester(config.reddit, mock_path)
            logger.info("Using MOCK Reddit Ingester")
        else:
            reddit = RedditIngester(config.reddit)
            
        market_provider = create_market_provider(config.market)
        
        ticker_extractor = TickerExtractor(config.features.ticker_extraction)
        
        if config.features.sentiment.method == "llm":
            logger.info(f"Initializing LLMSentimentAnalyzer ({config.features.llm.model})")
            sentiment_analyzer = LLMSentimentAnalyzer(config.features)
        else:
            logger.info("Initializing WSBSentimentAnalyzer (VADER+Lexicon)")
            sentiment_analyzer = WSBSentimentAnalyzer(config.features.sentiment)
            
        attention_tracker = AttentionTracker(config.features.attention)
        
        market_features_extractor = MarketFeatureExtractor()
        signal_engine = SignalEngine(config.signal_engine)

        # ── Stage 1: Ingestion ──────────────────────────────────────────────
        logger.info("Stage 1: Ingesting Reddit data...")
        posts, comments = reddit.fetch_all(limit=limit)
        
        # Save raw data to DB
        new_posts = db.insert_posts(posts)
        new_comments = db.insert_comments(comments)
        
        if args.dry_run:
            logger.info(f"DRY RUN: Fetched {len(posts)} posts and {len(comments)} comments. Exiting.")
            print(json.dumps({"posts": len(posts), "comments": len(comments)}))
            db.complete_pipeline_run(run_id, posts_ingested=new_posts, comments_ingested=new_comments)
            return

        # ── Stage 2: Feature Extraction ─────────────────────────────────────
        logger.info("Stage 2: Extracting features...")
        
        # Combine texts for ticker extraction (post titles are key)
        post_texts = {p.id: p.full_text for p in posts}
        comment_texts = {c.id: c.body for c in comments}
        
        # Extract tickers
        ticker_mentions_posts = ticker_extractor.extract_from_texts(list(post_texts.values()))
        ticker_mentions_comments = ticker_extractor.extract_from_texts(list(comment_texts.values()))
        
        all_tickers = set(ticker_mentions_posts.keys()) | set(ticker_mentions_comments.keys())
        logger.info(f"Identified {len(all_tickers)} unique tickers for analysis")

        # Create dictionaries to hold texts per ticker for sentiment
        texts_by_ticker: dict[str, list[str]] = {t: [] for t in all_tickers}
        posts_by_ticker: dict[str, list] = {t: [] for t in all_tickers}
        comments_by_ticker: dict[str, list] = {t: [] for t in all_tickers}

        # Map posts to tickers
        for post in posts:
            mentions = ticker_extractor.extract(post.full_text)
            for m in mentions:
                texts_by_ticker[m.ticker].append(post.full_text)
                posts_by_ticker[m.ticker].append(post)

        # Map comments to tickers
        for comment in comments:
            mentions = ticker_extractor.extract(comment.body)
            for m in mentions:
                texts_by_ticker[m.ticker].append(comment.body)
                comments_by_ticker[m.ticker].append(comment)

        # Compute Sentiment per ticker
        sentiment_results = {}
        for ticker, texts in texts_by_ticker.items():
            if texts:
                sentiment_results[ticker] = sentiment_analyzer.analyze_for_ticker(ticker, texts)

        # Compute Attention per ticker
        attention_results = attention_tracker.compute_batch_metrics(
            ticker_posts=posts_by_ticker,
            ticker_comments=comments_by_ticker,
            # We skip sentiment_scores per text item right now to simplify, 
            # or we could pre-calculate them all. For MVP, we stick to basic engagement.
        )

        # Calculate max confidence per ticker
        confidence_results = {}
        for ticker in all_tickers:
            conf_post = max([m.confidence for m in ticker_mentions_posts.get(ticker, [])], default=0)
            conf_comment = max([m.confidence for m in ticker_mentions_comments.get(ticker, [])], default=0)
            confidence_results[ticker] = max(conf_post, conf_comment)

        # ── Stage 3: Market Data & Signal Engine ───────────────────────────
        logger.info("Stage 3: Fetching market data and generating signals...")
        
        # We only want to fetch market data for tickers that meet basic mention thresholds
        # to avoid spamming the Yahoo API.
        viable_tickers = [
            t for t in all_tickers 
            if attention_results[t].mention_count >= config.signal_engine.min_mentions
        ]
        
        logger.info(f"Fetching market data for {len(viable_tickers)} viable tickers")
        market_history_dict = {}
        for ticker in viable_tickers:
            market_history_dict[ticker] = market_provider.get_price_history(ticker)
            
        market_features_dict = market_features_extractor.compute_batch_features(market_history_dict)
        
        # Generate Signals
        signals = signal_engine.generate_batch_signals(
            tickers=viable_tickers,
            sentiment_dict=sentiment_results,
            attention_dict=attention_results,
            market_dict=market_features_dict,
            confidence_dict=confidence_results,
        )

        # Save to DB
        db.insert_signals(signals)

        # Complete run
        db.complete_pipeline_run(
            run_id,
            posts_ingested=new_posts,
            comments_ingested=new_comments,
            tickers_found=len(all_tickers),
            signals_generated=len(signals),
        )

        # ── Stage 4: Alerting ──────────────────────────────────────────────
        notifier = DiscordNotifier()
        if notifier.is_enabled():
            notifier.send_signals(signals)

        # Output Results
        output_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "posts_processed": len(posts),
                "comments_processed": len(comments),
                "tickers_analyzed": len(viable_tickers),
                "signals_generated": len(signals),
            },
            "signals": [
                {
                    "ticker": s.ticker,
                    "action": s.action,
                    "composite_score": s.composite_score,
                    "confidence": s.confidence,
                    "reasoning": s.reasoning,
                    "components": s.components,
                }
                for s in signals
            ]
        }

        if args.output_format == "json":
            print(json.dumps(output_data, indent=2))
        else:
            print("\n" + "="*80)
            print(f"WSB AGENT PIPELINE RESULTS ({len(signals)} Signals)")
            print("="*80)
            for s in signals:
                print(f"[{s.action:4s}] {s.ticker:5s} | Score: {s.composite_score:5.2f} | {s.reasoning}")
            print("="*80)

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        db.complete_pipeline_run(run_id, status="failed", error_message=str(e))
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()
