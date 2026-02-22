# WSB Agent 🚀

An autonomous AI agent that leverages the Wall Street Bets (WSB) subreddit and financial data to actively manage a portfolio. It applies multi-layered NLP to extract sentiment and momentum features, combines them with historical market data, and generates actionable trading signals.

## Features

- **Robust Ingestion**: Pulls hot/new posts and top comments using the Reddit API. Includes duplicate detection and SQLite persistence for pipeline runs.
- **Advanced Ticker Extraction**: Finds cashtags (`$GME`) and uppercase patterns (`AAPL`). Filters out common false positives (e.g. "CEO", "YOLO", "AI") using a custom blacklist and whitelist methodology with context-based confidence scoring.
- **Custom WSB Sentiment**: Augments standard VADER sentiment analysis with a custom [lexicon](data/wsb_lexicon.yaml) of 100+ WSB-specific slang terms ("diamond hands", "tendies", "guh") and emojis to accurately gauge retail sentiment.
- **Attention & Momentum Metrics**: Calculates mention velocity (mentions per hour), engagement-weighting (upvotes), and sentiment-weighted momentum.
- **Signal Engine**: Fetches live market data via `yfinance` to compute technical features (returns, volatility, abnormal volume). Blends NLP features with market features using configurable weights to generate `BUY`, `SELL`, or `HOLD` signals.
- **Alerting**: Supports dispatching rich-embed webhook alerts to Discord when strong signals are detected.

---

## Installation

This project uses `uv` for dependency management.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/wsb_agent.git
   cd wsb_agent
   ```

2. **Sync dependencies:**
   ```bash
   uv sync
   ```

3. **Configure Environment:**
   Copy the example environment file and fill in your Reddit API credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, etc.
   # Optionally add DISCORD_WEBHOOK_URL for alerts.
   ```

4. **Review Settings:**
   Review `config/settings.yaml` to tune engine parameters (signal weights, minimum mentions required, API batch limits).

---

## Usage

Run the pipeline using the command line interface:

```bash
# Run the full end-to-end pipeline (Ingest -> NLP -> Market Data -> Signal -> DB)
uv run python scripts/run_pipeline.py

# Run and output results in a human-readable table instead of JSON
uv run python scripts/run_pipeline.py --output-format table

# Test the pipeline using mock data instead of calling the Reddit API
uv run python scripts/run_pipeline.py --mock --output-format table
```

### Output Example

```
================================================================================
WSB AGENT PIPELINE RESULTS (2 Signals)
================================================================================
[BUY ] PLTR  | Score:  0.81 | BUY triggered. Strong Bullish sentiment score (0.78); High mention velocity (15.2/hr); Unusual trading volume (2.1x relative to past 20d).
[SELL] TSLA  | Score: -0.65 | SELL triggered. Strong Bearish sentiment score (-0.62); Strong 5d price momentum (down -8.5%).
================================================================================
```

---

## Architecture (V1)

1. **Ingestion Layer:** Connects to Reddit API, fetches posts/comments, normalizes data into standard dataclasses, and stores them in `wsb_agent.db`.
2. **Feature Extraction:** 
   - `TickerExtractor`: Identifies what stocks are being discussed.
   - `WSBSentimentAnalyzer`: Computes polarity.
   - `AttentionTracker`: Computes virality and attention metrics.
3. **Market Features:** Connects to Yahoo Finance (`yfinance`) with an in-memory TTL caching layer to calculate price momentum and volume anomalies.
4. **Signal Engine:** Normalizes all inputs into `-1.0` to `1.0` scales, applies matrix weights defined in `settings.yaml`, and triggers actions with human-readable reasoning based on threshold bounds.

## Next Steps / V2 Roadmap
- **Observability:** Granular Grafana/Prometheus metrics for extraction rates.
- **Portfolio Agent:** Auto-execution via Alpaca or Interactive Brokers paper trading API based on generated signals.
- **LLM Sentiment:** Swap VADER + Lexicon for a small LLM (e.g., LLaMA 3 8B) for nuanced reasoning over long text blocks.
