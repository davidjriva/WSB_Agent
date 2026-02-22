"""Portfolio orchestration and position sizing logic."""

import logging
from dataclasses import dataclass

from wsb_agent.models import Signal
from wsb_agent.portfolio.broker import BrokerProvider
from wsb_agent.utils.config import PortfolioConfig

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a generated trade execution."""

    ticker: str
    action: str
    amount: float
    reason: str


class PortfolioManager:
    """Translates trading signals into sized orders."""

    def __init__(self, config: PortfolioConfig, broker: BrokerProvider):
        self.config = config
        self.broker = broker

    def execute_signals(self, signals: list[Signal]) -> list[TradeRecord]:
        """Process incoming signals and execute trades according to risk limits.

        Args:
            signals: List of generated signals.

        Returns:
            List of executed TradeRecords.
        """
        if not signals:
            logger.info("No signals provided to portfolio manager.")
            return []

        try:
            balance = self.broker.get_account_balance()
            holdings = set(self.broker.get_open_positions())
        except Exception as e:
            logger.error(f"Failed to fetch portfolio state from broker: {e}")
            return []

        max_trade_size = balance * self.config.max_position_size_pct
        trades: list[TradeRecord] = []

        logger.info(
            f"Portfolio Manager processing {len(signals)} signals. "
            f"Current Balance: ${balance:,.2f} | Open Positions: {len(holdings)}"
        )

        for s in signals:
            if s.action == "HOLD":
                continue

            ticker = s.ticker
            score = abs(s.composite_score)
            action = s.action

            # Simple Position Sizing: Scale base amount by conviction (score)
            # Cap the trade at max_trade_size (based on total account pct)
            desired_amount = min(
                self.config.base_trade_amount * score, max_trade_size
            )

            if desired_amount < 1.0:
                logger.info(f"[{ticker}] Trade amount (${desired_amount:.2f}) too small. Skipping.")
                continue

            if action == "BUY":
                if ticker in holdings:
                    logger.info(f"[{ticker}] BUY signal skipped: Already holding position.")
                    continue
                logger.info(f"[{ticker}] Executing BUY for ${desired_amount:.2f} (Conviction: {score:.2f})")
                self.broker.submit_order(ticker, desired_amount, "buy")
                
                trades.append(TradeRecord(ticker=ticker, action="BUY", amount=desired_amount, reason=s.reasoning))
                holdings.add(ticker)

            elif action == "SELL":
                if ticker not in holdings:
                    logger.info(f"[{ticker}] SELL signal skipped: Not currently holding position.")
                    continue
                logger.info(f"[{ticker}] Executing SELL for ${desired_amount:.2f} (Conviction: {score:.2f})")
                self.broker.submit_order(ticker, desired_amount, "sell")
                
                trades.append(TradeRecord(ticker=ticker, action="SELL", amount=desired_amount, reason=s.reasoning))
                holdings.remove(ticker)

        logger.info(f"Portfolio Manager execution complete. {len(trades)} trades submitted.")
        return trades
