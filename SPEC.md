# Wall Street Bets Agentic System

## North Star

Build a production-grade, agentic system that ingests the Wall Street Bets (WSB) subreddit in real-time, analyzes sentiment and "ape" behavior, and generates high-conviction trade ideas for meme stocks.

The system combines:
- Social sentiment and attention dynamics from WallStreetBets
- Quantitative financial data from Yahoo Finance or equivalent APIs

The objective is not guaranteed price prediction, but signal generation and decision-making under uncertainty

## Goals

### Primary Goals -- V1
* Aggregate WallStreetBets activity into structured features
* Fetch market data for referenced securities
* Generate trading signals from combined features

### Stretch Goals (Simulation) -- V2
* Simulate portfolio management decisions
* Track portfolio performance over time
* Evaluate signal effectiveness 
* Support experimentation with strategies
* Provide interpretable diagnostics (observability)
* Store long-term memory regarding previous analytics/research of different tickers

## System Architecture

┌─────────────────────┐
│     Data Sources    │
│─────────────────────│
│ • WallStreetBets    │
│ • Finance API       │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Data Ingestion     │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Feature Extraction  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│   Signal Engine     │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Portfolio Agent    │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│   Simulation Engine │
└─────────────────────┘

## Data Sources

### WallStreetBets (Subreddit): 
Data Types:
* Submissions (title + body)
* Comments
* Metadata (timestamp, score, upvotes)

Collection mechanism:
* Reddit API via Python Reddit API Wrapper (`praw`)

Extracted Fields:
* Text content
* Timestamp
* Score / engagement
* Author (optional)

### Finance Data:
Source options:
* Yahoo Finance via `yfinance`
* Alpha Vantage / Polygon / IEX Cloud (optional)

Data Types:
* Historical price data (OHLCV)
* Volume
* Market metadata
* Fundamentals (optional)

## Feature Extraction
### Ticket Identification
Objective: detect stock symbols mentioned in WSB content:
Techniques:
* Regex patterns (`$TSLA`)
* Uppercase token matching (`GME`, `NVDA`)
* Whitelist filtering against valid tickers

### Sentiment Analysis
Objective: Estimate crowd sentiment per ticker

Methods:
* Rule-based (VADER/TextBlob)
* ML classifier (optional)
* LLM based classification (optional)

Outputs:
* Sentiment score per mention
* Aggregated sentiment per ticker

### Attention Metrics
For each ticker over a time window:
* Mention count
* Mention velocity (change over time)
* Engagement-weighted mentions
* Sentiment-weighted mentions

### Market Features
For each ticker:
* Returns (N-day)
* Volatility
* Volume changes
* Technical indicators (optional)

## Signal Engine
Objective: Convert features into tradable signals

Inputs:
* Sentiment features
* Attention features
* Market features

Outputs:
* Signal score per ticker
* Suggested action:
    * BUY
    * SELL
    * HOLD

Example logic
* High mention velocity + positive sentiment -> bullish signal
* Negative sentiment spike -> bearish signal
* Signal thresholds configurable

## Portfolio Agent
Objective: Maintain and update simulated portfolio state.

Responsibilities:
* Track positions
* Allocate capital
* Execute simulated trades
* Apply constraints

Portfolio State:
* Cash balance
* Open positions
* Entry prices
* PnL tracking

Decision Logic:
* Evaluate signals
* Apply risk rules
* Determine position sizing

## Simulation Engine
Objective: Evaluate performance without real capital

Features:
* Historical backtesting
* Stepwise time simulation
* Transaction cost modeling
* Slippage assumptions (optional)

## Risk Management
Configurable rules:
* Max position size
* Stop-loss thresholds
* Max portfolio exposure
* Diversification constraints

## Evaluation Metrics
* Portfolio return
* Sharpe ratio (optional)
* Max drawdown
* Win/loss ratio
* Signal accuracy (optional)

## Storage & State Management
Data Storage Options:
* Local database (SQLite / Postgres)
* Flat files (CSV / Parquet)

Stored Objects:
* Raw WSB data
* Processed features
* Signals
* Portfolio history

## Extensibility
Future enhancements may include:
* Additional social sources (Twitter, news)
* ML-based prediction models
* Reinforcement learning agent
* Live paper trading

## Non-Goals
This system:
* Doesn't guarantee financial performance
* Is **not** financial advice for real humans. This is **purely an experiment**.
* Is **intended for research/simulation/experimentation**.