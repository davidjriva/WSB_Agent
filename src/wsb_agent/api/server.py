"""FastAPI server acting as the WSB Agent's memory and observability layer."""

import logging
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from wsb_agent.utils.config import load_config
from wsb_agent.storage.database import Database
from wsb_agent.portfolio.broker import AlpacaBroker, MockBroker
from wsb_agent.portfolio.manager import PortfolioManager

logger = logging.getLogger(__name__)

# Global instances for the API to interact with
_config = None
_db = None
_broker = None
_portfolio_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    global _config, _db, _broker, _portfolio_manager
    
    logger.info("Initializing WSB Agent API State...")
    _config = load_config()
    _db = Database(_config.storage.database_path)
    
    if _config.portfolio.paper_trading:
        _broker = AlpacaBroker(_config.portfolio)
    else:
        _broker = MockBroker()
        
    _portfolio_manager = PortfolioManager(_config.portfolio, _broker)
    
    yield
    
    logger.info("Shutting down WSB Agent API...")
    if _db:
        _db.close()


app = FastAPI(
    title="WSB Agent API",
    description="Observability and Memory layer for the retail sentiment bot",
    version="2.1.0",
    lifespan=lifespan,
)

# Permissive CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# --- Response Models ---

class HealthResponse(BaseModel):
    status: str
    version: str
    database_connected: bool
    broker_type: str


class SignalResponse(BaseModel):
    ticker: str
    score: float
    action: str
    confidence: float
    reasoning: str
    components: dict[str, float]
    metadata: dict[str, Any]
    timestamp: str


class PortfolioResponse(BaseModel):
    balance: float
    open_positions: list[str]


class ValuationEntry(BaseModel):
    total_equity: float
    cash: float
    timestamp: str


class ValuationHistoryResponse(BaseModel):
    history: list[ValuationEntry]


# --- Endpoints ---

@app.get("/ping")
async def ping():
    return {"message": "pong", "version": "2.1.0-debug"}


@app.get("/health", response_model=HealthResponse)
async def get_health():
    """System status check."""
    return HealthResponse(
        status="active",
        version="2.1.0",
        database_connected=_db is not None,
        broker_type=type(_broker).__name__ if _broker else "None"
    )


@app.get("/signals", response_model=list[SignalResponse])
async def get_recent_signals(limit: int = 50):
    """Retrieve the most recent trading signals from memory."""
    if not _db:
        raise HTTPException(status_code=500, detail="Database not initialized")
        
    signals = _db.get_recent_signals(limit=limit)
    
    response = []
    for s in signals:
        try:
            # Defensive check: if database returned dict instead of Signal object
            if isinstance(s, dict):
                response.append(
                    SignalResponse(
                        ticker=s.get("ticker", "UNKNOWN"),
                        score=s.get("composite_score", 0.0),
                        action=s.get("action", "HOLD"),
                        confidence=s.get("confidence", 0.0),
                        reasoning=s.get("reasoning", ""),
                        components=json.loads(s.get("components", "{}")) if isinstance(s.get("components"), str) else s.get("components", {}),
                        metadata=s.get("metadata", {}),
                        timestamp=s.get("created_at", "")
                    )
                )
            else:
                response.append(
                    SignalResponse(
                        ticker=s.ticker,
                        score=s.composite_score,
                        action=s.action,
                        confidence=s.confidence,
                        reasoning=s.reasoning,
                        components=s.components,
                        metadata=s.metadata,
                        timestamp=s.timestamp.isoformat()
                    )
                )
        except Exception as e:
            logger.error(f"Error mapping signal response: {e}")
            
    return response


@app.get("/signals/{ticker}", response_model=list[SignalResponse])
async def get_ticker_history(ticker: str, limit: int = 50):
    """Retrieve historical signals for a specific stock."""
    if not _db:
        raise HTTPException(status_code=500, detail="Database not initialized")
        
    signals = _db.get_ticker_signals(ticker, limit=limit)
    
    response = []
    for s in signals:
        response.append(
            SignalResponse(
                ticker=s.ticker,
                score=s.composite_score,
                action=s.action,
                confidence=s.confidence,
                reasoning=s.reasoning,
                components=s.components,
                metadata=s.metadata,
                timestamp=s.timestamp.isoformat()
            )
        )
            
    return response


@app.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """Retrieve current Alpaca holdings and balance."""
    if not _broker:
        raise HTTPException(status_code=500, detail="Broker not initialized")
        
    balance = _broker.get_account_balance()
    positions = _broker.get_open_positions()
    
    return PortfolioResponse(
        balance=balance,
        open_positions=positions
    )


@app.get("/portfolio/history", response_model=ValuationHistoryResponse)
async def get_portfolio_history(limit: int = 100):
    """Retrieve historical portfolio valuation data."""
    if not _db:
        raise HTTPException(status_code=500, detail="Database not initialized")
        
    history = _db.get_portfolio_history(limit=limit)
    
    return ValuationHistoryResponse(
        history=[
            ValuationEntry(
                total_equity=entry["total_equity"],
                cash=entry["cash"],
                timestamp=entry["timestamp"]
            )
            for entry in history
        ]
    )
