"""Tests for the Portfolio Agent subsystem."""

import pytest
from wsb_agent.models import Signal
from wsb_agent.portfolio.broker import MockBroker
from wsb_agent.portfolio.manager import PortfolioManager
from wsb_agent.utils.config import PortfolioConfig


@pytest.fixture
def mock_broker():
    """Provides a fresh MockBroker with $10,000."""
    return MockBroker(initial_balance=10000.0)


@pytest.fixture
def portfolio_config():
    """Provides standard portfolio test config."""
    return PortfolioConfig(
        broker="mock",
        paper_trading=True,
        base_trade_amount=1000.0,
        max_position_size_pct=0.15,  # 15% of 10,000 = 1,500 max per trade
        alpaca_api_key="test",
        alpaca_secret_key="test",
    )


def test_mock_broker_state(mock_broker):
    """Test that the MockBroker tracks virtual positions correctly."""
    assert mock_broker.get_account_balance() == 10000.0
    assert len(mock_broker.get_open_positions()) == 0

    mock_broker.submit_order("AAPL", 500.0, "buy")
    assert "AAPL" in mock_broker.get_open_positions()

    mock_broker.submit_order("AAPL", 500.0, "sell")
    assert "AAPL" not in mock_broker.get_open_positions()


def test_portfolio_manager_sizing(mock_broker, portfolio_config):
    """Test position sizing limits base_trade_amount * confidence."""
    manager = PortfolioManager(portfolio_config, mock_broker)

    signals = [
        # Score 0.8 * 1000 = $800
        Signal(
            ticker="NVDA",
            action="BUY",
            composite_score=0.8,
            confidence=0.9,
            reasoning="Strong buy",
            components={},
        ),
        # Score 0.3 * 1000 = $300 (Technically HOLD usually, but let's test sizing)
        Signal(
            ticker="TSLA",
            action="BUY",
            composite_score=0.3,
            confidence=0.9,
            reasoning="Weak buy",
            components={},
        ),
    ]

    trades = manager.execute_signals(signals)
    assert len(trades) == 2
    
    nvda_trade = next(t for t in trades if t.ticker == "NVDA")
    assert nvda_trade.amount == 800.0

    tsla_trade = next(t for t in trades if t.ticker == "TSLA")
    assert tsla_trade.amount == 300.0


def test_portfolio_manager_max_position_limit(mock_broker, portfolio_config):
    """Test that no trade exceeds max_position_size_pct."""
    manager = PortfolioManager(portfolio_config, mock_broker)

    signals = [
        # Base trade = 1000, max limit = 1500. 
        # But wait, what if config base is huge? Let's override config.
    ]
    
    huge_base_config = PortfolioConfig(
        base_trade_amount=5000.0,  # 5000 is > 15% of 10,000 (1,500)
        max_position_size_pct=0.15,
    )
    manager = PortfolioManager(huge_base_config, mock_broker)
    
    signals = [
        Signal(
            ticker="GME",
            action="BUY",
            composite_score=1.0,
            confidence=1.0,
            reasoning="Max buy",
            components={},
        )
    ]

    trades = manager.execute_signals(signals)
    assert len(trades) == 1
    
    # Amount should be capped at $1500 (15% of 10,000)
    assert trades[0].amount == 1500.0


def test_portfolio_manager_avoids_duplicate_buys(mock_broker, portfolio_config):
    """Test that it won't buy a ticker already held."""
    mock_broker.positions = ["PLTR"]
    manager = PortfolioManager(portfolio_config, mock_broker)

    signals = [
        Signal(
            ticker="PLTR",
            action="BUY",
            composite_score=0.9,
            confidence=0.9,
            reasoning="Buy again",
            components={},
        )
    ]

    trades = manager.execute_signals(signals)
    assert len(trades) == 0  # Should be skipped


def test_portfolio_manager_sell_execution(mock_broker, portfolio_config):
    """Test that SELL orders only execute if holding."""
    mock_broker.positions = ["AMC"]
    manager = PortfolioManager(portfolio_config, mock_broker)

    signals = [
        # Should be skipped because not currently holding AAPL
        Signal(
            ticker="AAPL",
            action="SELL",
            composite_score=-0.8,
            confidence=0.9,
            reasoning="Sell AAPL",
            components={},
        ),
        # Should execute because holding AMC
        Signal(
            ticker="AMC",
            action="SELL",
            composite_score=-0.9,
            confidence=0.9,
            reasoning="Sell AMC",
            components={},
        )
    ]

    trades = manager.execute_signals(signals)
    assert len(trades) == 1
    assert trades[0].ticker == "AMC"
    assert trades[0].action == "SELL"
    # Sizing: abs(-0.9) * 1000 = 900
    assert trades[0].amount == 900.0
    
    # Check broker state
    assert "AMC" not in mock_broker.get_open_positions()
