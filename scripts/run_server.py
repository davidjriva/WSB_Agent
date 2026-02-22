"""FastAPI Entry Point and Background Pipeline Daemon."""

import argparse
import asyncio
import logging
from datetime import datetime

import uvicorn

from wsb_agent.utils.logging import setup_logging
import wsb_agent.api.server as server
from wsb_agent.api.server import app
from wsb_agent.ingestion.reddit import create_reddit_ingester
from wsb_agent.ingestion.mock_reddit import MockRedditIngester
from wsb_agent.ingestion.market import create_market_provider
from wsb_agent.features.tickers import TickerExtractor
from wsb_agent.features.sentiment import WSBSentimentAnalyzer
from wsb_agent.features.llm_sentiment import LLMSentimentAnalyzer
from wsb_agent.features.attention import AttentionTracker
from wsb_agent.signals.market_features import MarketFeatureExtractor
from wsb_agent.signals.engine import SignalEngine
from wsb_agent.utils.notifications import DiscordNotifier

logger = logging.getLogger(__name__)


async def run_pipeline_iteration(use_mock_reddit: bool):
    """Executes a single pass of the WSB agent pipeline."""
    try:
        logger.info(f"Starting pipeline iteration at {datetime.now().isoformat()}")
        
        # We rely on the global state initialized by FastAPI's lifespan
        if not server._config or not server._db or not server._portfolio_manager:
            logger.error("API State not initialized. Skipping pipeline run.")
            return

        run_id = server._db.start_pipeline_run()

        # 1. Ingestion
        if use_mock_reddit:
            reddit_ingester = MockRedditIngester(server._config.reddit)
        else:
            reddit_ingester = create_reddit_ingester(server._config.reddit)
            
        market_provider = create_market_provider(server._config.market)

        # 2. Extractors
        ticker_extractor = TickerExtractor(server._config.features.ticker_extraction)
        
        if server._config.features.sentiment.method == "llm":
            sentiment_analyzer = LLMSentimentAnalyzer(server._config.features)
        else:
            sentiment_analyzer = WSBSentimentAnalyzer(server._config.features.sentiment)
            
        attention_tracker = AttentionTracker(server._config.features.attention)
        market_features_extractor = MarketFeatureExtractor()
        signal_engine = SignalEngine(server._config.signal_engine)

        posts, comments = reddit_ingester.fetch_all()
        new_posts = server._db.insert_posts(posts)
        new_comments = server._db.insert_comments(comments)

        # 3. Ticker Extraction & Association
        texts_by_ticker: dict[str, list[str]] = {}
        posts_by_ticker: dict[str, list] = {}  # list[Post]
        comments_by_ticker: dict[str, list] = {}  # list[Comment]
        confidence_by_ticker: dict[str, float] = {}

        for post in posts:
            mentions = ticker_extractor.extract(post.full_text)
            for m in mentions:
                texts_by_ticker.setdefault(m.ticker, []).append(post.full_text)
                posts_by_ticker.setdefault(m.ticker, []).append(post)
                confidence_by_ticker[m.ticker] = max(confidence_by_ticker.get(m.ticker, 0), m.confidence)

        for comment in comments:
            mentions = ticker_extractor.extract(comment.body)
            for m in mentions:
                texts_by_ticker.setdefault(m.ticker, []).append(comment.body)
                comments_by_ticker.setdefault(m.ticker, []).append(comment)
                confidence_by_ticker[m.ticker] = max(confidence_by_ticker.get(m.ticker, 0), m.confidence)

        all_tickers = list(texts_by_ticker.keys())
        if not all_tickers:
            server._db.complete_pipeline_run(run_id, status="completed_no_tickers")
            return

        # 4. Attention Metrics
        attention_metrics_dict = attention_tracker.compute_batch_metrics(
            ticker_posts=posts_by_ticker,
            ticker_comments=comments_by_ticker
        )

        # 5. Sentiment & Market Features
        signals_to_execute = []
        for ticker in all_tickers:
            metrics = attention_metrics_dict.get(ticker)
            if not metrics or metrics.mention_count < server._config.signal_engine.min_mentions:
                continue

            ticker_texts = texts_by_ticker.get(ticker, [])
            sentiment_result = sentiment_analyzer.analyze_for_ticker(ticker, ticker_texts)
            
            hist_df = market_provider.get_price_history(
                ticker,
                period=server._config.market.history_period,
                interval=server._config.market.history_interval,
            )
            
            market_feats = market_features_extractor.compute_features(ticker, hist_df)
            signal = signal_engine.generate_signal(
                ticker=ticker,
                sentiment=sentiment_result, 
                attention=metrics, 
                market=market_feats,
                confidence=confidence_by_ticker.get(ticker, 1.0)
            )
            
            if signal:
                signals_to_execute.append(signal)

        # 6. Persistence & Execution
        server._db.insert_signals(signals_to_execute)
        trades = server._portfolio_manager.execute_signals(signals_to_execute)
        
        # 6b. Record Portfolio Snapshot
        try:
            balance = server._broker.get_account_balance()
            server._db.insert_portfolio_snapshot(total_equity=balance, cash=balance) # Assuming cash=equity for simplicity in mock
        except Exception as be:
            logger.warning(f"Could not record portfolio snapshot: {be}")

        server._db.complete_pipeline_run(
            run_id, 
            status="completed",
            posts_ingested=new_posts,
            comments_ingested=new_comments,
            tickers_found=len(all_tickers),
            signals_generated=len(signals_to_execute)
        )

        # 7. Notifications
        if trades and server._config.discord_webhook_url:
            notifier = DiscordNotifier(server._config.discord_webhook_url)
            for trade in trades:
                sentiment_emoji = "🚀" if trade.action == "BUY" else "🐻"
                notifier.send_alert(
                    title=f"{sentiment_emoji} WSB Agent Trade Executed: {trade.action} {trade.ticker}",
                    description=f"**Amount**: ${trade.amount:,.2f}\n**Reasoning**: {trade.reason}"
                )

        logger.info(f"Pipeline iteration completed. Executed {len(trades)} trades.")

    except Exception as e:
        logger.exception(f"Pipeline iteration failed: {e}")
        if server._db and 'run_id' in locals():
            server._db.complete_pipeline_run(run_id, status="failed", error_message=str(e))


async def background_pipeline_loop(interval_minutes: int, use_mock_reddit: bool):
    """Runs the pipeline periodically in the background."""
    logger.info(f"Starting background pipeline loop (interval: {interval_minutes}m)")
    
    # Wait for FastAPI lifespan to initialize globals
    await asyncio.sleep(2)
    
    while True:
        await run_pipeline_iteration(use_mock_reddit)
        logger.info(f"Sleeping for {interval_minutes} minutes before next run...")
        await asyncio.sleep(interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description="WSB Agent FastAPI Server & Daemon")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host interface to bind to"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on"
    )
    parser.add_argument(
        "--interval", type=int, default=15, help="Minutes between pipeline runs"
    )
    parser.add_argument(
        "--mock-reddit", action="store_true", help="Use local JSON fixtures instead of live Reddit API"
    )
    args = parser.parse_args()

    setup_logging(level="INFO")
    
    # We create the asyncio loop explicitly to attach our background task alongside Uvicorn
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Schedule the background pipeline
    loop.create_task(background_pipeline_loop(args.interval, args.mock_reddit))
    
    # Configure and run Uvicorn
    config = uvicorn.Config(
        app=app,
        host=args.host,
        port=args.port,
        loop="asyncio",
        log_level="info"
    )
    uv_server = uvicorn.Server(config)
    
    logger.info(f"Booting WSB Agent Daemon... UI at http://{args.host}:{args.port}/docs")
    loop.run_until_complete(uv_server.serve())


if __name__ == "__main__":
    main()
