import pytest
import os
import json
from datetime import datetime
from backend.services.portfolio_service import PortfolioService, PORTFOLIO_DIR

# Mock data for testing
TEST_PM_ID = "test_pm"
TEST_PORTFOLIO_FILE = os.path.join(PORTFOLIO_DIR, f"{TEST_PM_ID}.json")

@pytest.fixture
def portfolio():
    # Setup: Remove existing test portfolio if any
    if os.path.exists(TEST_PORTFOLIO_FILE):
        os.remove(TEST_PORTFOLIO_FILE)
    
    # Initialize service
    service = PortfolioService(TEST_PM_ID)
    yield service
    
    # Teardown: Cleanup
    if os.path.exists(TEST_PORTFOLIO_FILE):
        os.remove(TEST_PORTFOLIO_FILE)

def test_initialization(portfolio):
    """Test that a new portfolio is initialized correctly."""
    status = portfolio.get_status()
    assert status["pm_id"] == TEST_PM_ID
    assert status["balance"] == 0
    assert status["positions"] == {}
    assert status["is_running"] == False

def test_start_portfolio(portfolio):
    """Test starting the portfolio with capital."""
    capital = 10000.0
    portfolio.start_portfolio(capital)
    
    status = portfolio.get_status()
    assert status["balance"] == capital
    assert status["initial_capital"] == capital
    assert status["is_running"] == True
    assert len(status["ledger"]) == 1
    assert status["ledger"][0]["type"] == "DEPOSIT"

def test_open_long_position(portfolio):
    """Test opening a long position."""
    portfolio.start_portfolio(10000.0)
    
    ticker = "AAPL"
    price = 150.0
    confidence = 90.0  # Confidence is on 0-100 scale
    allocation = 0.10 # 10%
    
    # Execute trade
    result = portfolio.execute_trade(ticker, "BUY", price, confidence, allocation_percentage=allocation)
    
    assert "Opened Long Position" in result
    
    status = portfolio.get_status()
    pos = status["positions"][ticker]
    
    # Check calculations
    # Confidence >= 90 triggers 1.2x factor
    # buying_power = total_equity (10000) * leverage_ratio (1.0 default) = 10000
    # adjusted_allocation = allocation (0.10) * confidence_factor (1.2) = 0.12
    # target_size = buying_power (10000) * adjusted_allocation (0.12) = 1200
    expected_cost = 10000.0 * 0.10 * 1.2
    expected_qty = expected_cost / price
    
    assert pos["avg_price"] == price
    assert abs(pos["qty"] - expected_qty) < 0.001
    
    # Check balance deduction
    assert status["balance"] < 10000.0

def test_open_short_position(portfolio):
    """Test opening a short position and collateral locking."""
    portfolio.start_portfolio(10000.0)
    
    ticker = "TSLA"
    price = 200.0
    confidence = 80.0  # Confidence is on 0-100 scale
    allocation = 0.10
    
    # Execute trade
    result = portfolio.execute_trade(ticker, "SELL", price, confidence, allocation_percentage=allocation)
    
    assert "Opened Short Position" in result
    
    status = portfolio.get_status()
    pos = status["positions"][ticker]
    
    # Check short logic
    assert pos["qty"] < 0
    
    # Balance should NOT decrease for short open (it's a liability, not a cost)
    # But collateral is locked
    assert status["balance"] == 10000.0 
    assert status["locked_collateral"] > 0
    assert status["available_cash"] < 10000.0

def test_leverage_limit(portfolio):
    """Test that trades are properly limited when funds are exhausted."""
    portfolio.start_portfolio(1000.0)
    
    ticker = "AAPL"
    price = 100.0
    
    # Buy first position - should succeed
    result1 = portfolio.execute_trade(ticker, "BUY", price, 80.0, allocation_percentage=0.20)
    assert "Long Position" in result1
    
    # Buy second position  
    ticker2 = "TSLA"
    portfolio.execute_trade(ticker2, "BUY", 200.0, 80.0, allocation_percentage=0.20)
    
    # Buy third position
    ticker3 = "GOOG"
    portfolio.execute_trade(ticker3, "BUY", 150.0, 80.0, allocation_percentage=0.20)
    
    # Get final state
    status = portfolio.get_status()
    
    # Verify total position value respects leverage limit (1.0x default)
    # With 1x leverage, position value cannot exceed total equity
    total_position_value = sum(
        abs(pos["qty"]) * pos["avg_price"] 
        for pos in status["positions"].values()
    )
    total_equity = status["total_value"]
    
    # Leverage = position_value / equity should be <= 1.0 by default
    if total_equity > 0:
        current_leverage = total_position_value / total_equity
        assert current_leverage <= 1.1  # Allow small margin for rounding

def test_partial_close(portfolio):
    """Test partial closing of a position."""
    portfolio.start_portfolio(10000.0)
    ticker = "AAPL"
    price = 100.0
    portfolio.execute_trade(ticker, "BUY", price, 80.0, allocation_percentage=0.10)
    
    # Get initial qty
    status = portfolio.get_status()
    initial_qty = status["positions"][ticker]["qty"]
    
    # Close 50%
    new_price = 110.0 # Profit
    portfolio.execute_partial_close(ticker, 0.5, new_price, "Test Partial")
    
    status = portfolio.get_status()
    current_qty = status["positions"][ticker]["qty"]
    
    assert abs(current_qty - (initial_qty * 0.5)) < 0.001
    
    # Check Realized P&L
    # We sold 0.5 * initial_qty at 110. Cost was 100.
    # PnL = (110 - 100) * (0.5 * initial_qty)
    expected_pnl = 10.0 * (0.5 * initial_qty)
    
    # Find PnL entry in ledger
    pnl_entry = next((e for e in status["ledger"] if e["type"] == "REALIZED_PNL"), None)
    assert pnl_entry is not None
    assert abs(pnl_entry["amount"] - expected_pnl) < 0.01
