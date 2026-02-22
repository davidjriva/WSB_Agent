"""Broker integration for executing trades based on generated signals.

Provides a unified interface with Alpaca and Mock implementations.
"""

import logging
from typing import Protocol

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from wsb_agent.utils.config import PortfolioConfig

logger = logging.getLogger(__name__)


class BrokerProvider(Protocol):
    """Protocol defining the required interface for all brokers."""

    def get_account_balance(self) -> float:
        """Get the total equity / available buying power."""
        ...

    def get_open_positions(self) -> list[str]:
        """Get a list of ticker symbols currently held in the portfolio."""
        ...

    def submit_order(self, ticker: str, notional_amount: float, side: str) -> None:
        """Submit a market order for a specific dollar amount.

        Args:
            ticker: The stock symbol (e.g. "AAPL")
            notional_amount: The dollar amount to buy/sell
            side: "buy" or "sell"
        """
        ...


class AlpacaBroker:
    """Live/Paper integration with Alpaca Trading API."""

    def __init__(self, config: PortfolioConfig):
        """Initialize Alpaca client."""
        if not config.alpaca_api_key or not config.alpaca_secret_key:
            raise ValueError(
                "Missing Alpaca API keys. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env"
            )

        self.client = TradingClient(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_secret_key,
            paper=config.paper_trading,
        )
        logger.info(
            f"Initialized AlpacaBroker (Paper Trading: {config.paper_trading})"
        )

    def get_account_balance(self) -> float:
        """Get current equity from Alpaca."""
        account = self.client.get_account()
        return float(account.equity)

    def get_open_positions(self) -> list[str]:
        """Get all currently held symbols from Alpaca."""
        positions = self.client.get_all_positions()
        return [p.symbol for p in positions]

    def submit_order(self, ticker: str, notional_amount: float, side: str) -> None:
        """Submit a fractional market order to Alpaca."""
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        request = MarketOrderRequest(
            symbol=ticker,
            notional=notional_amount,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )

        try:
            self.client.submit_order(order_data=request)
            logger.info(
                f"ALPACA EXECUTED: {side.upper()} ${notional_amount:.2f} of {ticker}"
            )
        except Exception as e:
            logger.error(f"Failed to execute Alpaca order for {ticker}: {str(e)}")


class MockBroker:
    """Mock broker that simply logs trades instead of making network calls.
    Used for local testing / dry runs.
    """

    def __init__(self, initial_balance: float = 100000.0):
        self.balance = initial_balance
        self.positions: list[str] = []
        logger.info(f"Initialized MockBroker with ${initial_balance:,.2f} equity")

    def get_account_balance(self) -> float:
        return self.balance

    def get_open_positions(self) -> list[str]:
        return list(self.positions)

    def submit_order(self, ticker: str, notional_amount: float, side: str) -> None:
        """Simulate submitting an order."""
        if side.lower() == "buy":
            if ticker not in self.positions:
                self.positions.append(ticker)
            logger.info(f"MOCK BUY EXECUTED: ${notional_amount:.2f} of {ticker}")

        elif side.lower() == "sell":
            if ticker in self.positions:
                self.positions.remove(ticker)
            logger.info(f"MOCK SELL EXECUTED: ${notional_amount:.2f} of {ticker}")
