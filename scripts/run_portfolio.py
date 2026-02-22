"""CLI entry point for the WSB Portfolio Agent.

Orchestrates the pipeline and connects generated signals to the Portfolio Manager for execution.
"""

import argparse
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

from wsb_agent.portfolio.broker import AlpacaBroker, MockBroker
from wsb_agent.portfolio.manager import PortfolioManager

logger = logging.getLogger("wsb_agent.scripts.run_portfolio")


def _setup_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WSB Portfolio Agent Execution")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually submit trades to Alpaca. If omitted, runs a dry-run with a Mock broker.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom settings.yaml.",
    )
    parser.add_argument(
        "--mock-reddit",
        type=str,
        nargs="?",
        const="tests/fixtures/sample_posts.json",
        help="Use mock Reddit JSON data instead of fetching live.",
    )
    return parser


def run_portfolio() -> None:
    """Execute the full WSB Portfolio loop."""
    parser = _setup_argparser()
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    config = load_config(config_path=config_path)

    setup_logging(level=config.logging.level, log_format=config.logging.format)
    logger.info("Starting WSB Portfolio Agent...")

    # Initialize Portfolio Subsystem
    if args.execute:
        logger.warning("EXECUTE FLAG DETECTED. Real (or Paper) trades will be submitted via Alpaca.")
        try:
            broker = AlpacaBroker(config.portfolio)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
    else:
        logger.info("Running in DRY-RUN mode. Trades will be logged but not submitted.")
        broker = MockBroker()
        
    portfolio_manager = PortfolioManager(config.portfolio, broker)

    db = Database(config.storage.absolute_database_path)
    run_id = db.start_pipeline_run()

    try:
        # Initialize Pipeline Components
        if args.mock_reddit:
            mock_path = Path(args.mock_reddit) if args.mock_reddit is not True else None
            reddit = MockRedditIngester(config.reddit, mock_path)
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

        limit = config.reddit.batch_size

        # Stage 1: Ingestion
        logger.info("Fetching Data...")
        posts, comments = reddit.fetch_all(limit=limit)
        new_posts = db.insert_posts(posts)
        new_comments = db.insert_comments(comments)

        # Stage 2: Feature Extraction
        post_texts = {p.id: p.full_text for p in posts}
        comment_texts = {c.id: c.body for c in comments}
        
        ticker_mentions_posts = ticker_extractor.extract_from_texts(list(post_texts.values()))
        ticker_mentions_comments = ticker_extractor.extract_from_texts(list(comment_texts.values()))
        
        all_tickers = set(ticker_mentions_posts.keys()) | set(ticker_mentions_comments.keys())
        
        texts_by_ticker = {t: [] for t in all_tickers}
        posts_by_ticker = {t: [] for t in all_tickers}
        comments_by_ticker = {t: [] for t in all_tickers}

        for post in posts:
            for m in ticker_extractor.extract(post.full_text):
                texts_by_ticker[m.ticker].append(post.full_text)
                posts_by_ticker[m.ticker].append(post)

        for comment in comments:
            for m in ticker_extractor.extract(comment.body):
                texts_by_ticker[m.ticker].append(comment.body)
                comments_by_ticker[m.ticker].append(comment)

        sentiment_results = {t: sentiment_analyzer.analyze_for_ticker(t, texts) 
                             for t, texts in texts_by_ticker.items() if texts}

        attention_results = attention_tracker.compute_batch_metrics(
            ticker_posts=posts_by_ticker,
            ticker_comments=comments_by_ticker,
        )

        confidence_results = {}
        for ticker in all_tickers:
            conf_post = max([m.confidence for m in ticker_mentions_posts.get(ticker, [])], default=0)
            conf_comment = max([m.confidence for m in ticker_mentions_comments.get(ticker, [])], default=0)
            confidence_results[ticker] = max(conf_post, conf_comment)

        # Stage 3: Market Data & Signal Engine
        viable_tickers = [
            t for t in all_tickers 
            if attention_results[t].mention_count >= config.signal_engine.min_mentions
        ]
        
        market_history_dict = {t: market_provider.get_price_history(t) for t in viable_tickers}
        market_features_dict = market_features_extractor.compute_batch_features(market_history_dict)
        
        signals = signal_engine.generate_batch_signals(
            tickers=viable_tickers,
            sentiment_dict=sentiment_results,
            attention_dict=attention_results,
            market_dict=market_features_dict,
            confidence_dict=confidence_results,
        )

        db.insert_signals(signals)
        db.complete_pipeline_run(
            run_id,
            posts_ingested=new_posts,
            comments_ingested=new_comments,
            tickers_found=len(all_tickers),
            signals_generated=len(signals),
        )

        # Stage 4: Alerting
        notifier = DiscordNotifier()
        if notifier.is_enabled():
            notifier.send_signals(signals)

        # Stage 5: Portfolio Execution
        trades = portfolio_manager.execute_signals(signals)

        # Output Summary
        print("\n" + "="*80)
        print(f"WSB PORTFOLIO EXECUTION SUMMARY")
        print("="*80)
        if not trades:
            print("No action taken. 0 executed trades.")
        for t in trades:
            print(f"[{t.action:4s}] {t.ticker:5s} | Amount: ${t.amount:<8.2f} | Reason: {t.reason}")
        print("="*80)

    except Exception as e:
        logger.exception(f"Portfolio Pipeline failed: {e}")
        db.complete_pipeline_run(run_id, status="failed", error_message=str(e))
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_portfolio()
