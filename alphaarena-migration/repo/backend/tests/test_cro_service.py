"""
Tests for the Central Risk Officer (CRO) service.

We mock the PortfolioManager so we can precisely control system state
without hitting actual portfolio files or market data APIs.
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to build mock portfolio managers
# ---------------------------------------------------------------------------

def _build_mock_pm(pm_id: str, total_value: float, positions: dict):
    """
    Creates a minimal mock PortfolioService for a given PM.
    positions = { ticker: {"qty": float, "avg_price": float} }
    """
    svc = MagicMock()
    svc.get_status.return_value = {
        "total_value": total_value,
        "positions": {
            ticker: {**pos, "current_price": pos["avg_price"]}
            for ticker, pos in positions.items()
        },
        "current_prices": {ticker: pos["avg_price"] for ticker, pos in positions.items()},
    }
    return svc


def _build_mock_manager(pm_setup: dict):
    """
    pm_setup = { pm_id: (total_value, {ticker: {"qty": q, "avg_price": p}}) }
    Returns a mock PortfolioManager.
    """
    mgr = MagicMock()
    mgr.portfolios = {
        pm_id: _build_mock_pm(pm_id, tv, pos)
        for pm_id, (tv, pos) in pm_setup.items()
    }
    return mgr


# ---------------------------------------------------------------------------
# Reset CRO global state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_cro():
    import backend.services.cro_service as cro
    cro._peak_system_aum = 0.0
    cro._close_only_mode = False
    cro._last_status = {}
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCROApproval:

    def test_clean_trade_is_approved(self):
        """A simple first trade on an empty system should be approved."""
        from backend.services.cro_service import cro_approve_trade

        mgr = _build_mock_manager({
            "pm1": (10000, {}),
            "pm2": (10000, {}),
        })

        ok, reason = cro_approve_trade("pm1", "BTC-USD", "BUY", 1000, mgr)
        assert ok is True
        assert reason == ""

    def test_asset_concentration_cap_blocks_trade(self):
        """A trade that would push a single asset over MAX_ASSET_PCT should be vetoed."""
        from backend.services.cro_service import cro_approve_trade, MAX_ASSET_PCT

        # System AUM = 20_000. BTC already at 7000 across two PMs.
        # Adding another 2000 would make it 9000 / 20000 = 45% > 40%.
        mgr = _build_mock_manager({
            "pm1": (10000, {"BTC-USD": {"qty": 0.05, "avg_price": 60000}}),   # $3000 BTC
            "pm2": (10000, {"BTC-USD": {"qty": 0.05, "avg_price": 80000}}),   # $4000 BTC (at avg)
        })

        ok, reason = cro_approve_trade("pm3", "BTC-USD", "BUY", 5000, mgr)
        assert ok is False
        assert "concentration" in reason.lower() or "asset" in reason.lower()

    def test_crowding_guard_blocks_third_pm(self):
        """If MIN_CROWDED_PMS PMs already hold the asset, the next opener is blocked."""
        from backend.services.cro_service import cro_approve_trade, MIN_CROWDED_PMS

        # 3 PMs hold ETH already
        mgr = _build_mock_manager({
            "pm1": (10000, {"ETH-USD": {"qty": 1.0, "avg_price": 2000}}),
            "pm2": (10000, {"ETH-USD": {"qty": 1.0, "avg_price": 2000}}),
            "pm3": (10000, {"ETH-USD": {"qty": 1.0, "avg_price": 2000}}),
            "pm4": (10000, {}),
        })

        ok, reason = cro_approve_trade("pm4", "ETH-USD", "BUY", 500, mgr)
        assert ok is False
        assert "crowding" in reason.lower() or "pms" in reason.lower()

    def test_long_beta_cap_blocks_trade(self):
        """Total long exposure exceeding MAX_LONG_BETA_PCT should be vetoed."""
        from backend.services.cro_service import cro_approve_trade, MAX_LONG_BETA_PCT

        # System AUM = 20_000. Already 60% long ($12_000).
        # Adding $3000 more would make it 75% > 70%.
        mgr = _build_mock_manager({
            "pm1": (10000, {
                "NVDA": {"qty": 40, "avg_price": 150},    # $6000 long
            }),
            "pm2": (10000, {
                "AAPL": {"qty": 40, "avg_price": 150},    # $6000 long
            }),
        })

        ok, reason = cro_approve_trade("pm3", "TSLA", "BUY", 3000, mgr)
        assert ok is False
        assert "long beta" in reason.lower() or "long" in reason.lower()

    def test_drawdown_circuit_breaker(self):
        """If system AUM has dropped >MAX_DRAWDOWN from peak, block new openers."""
        import backend.services.cro_service as cro
        from backend.services.cro_service import cro_approve_trade, MAX_DRAWDOWN

        # Simulate a previous peak higher than current AUM
        cro._peak_system_aum = 20000.0   # Peak was $20k

        # Current system AUM is $15k -> 25% drawdown > 15% limit
        mgr = _build_mock_manager({
            "pm1": (7500, {}),
            "pm2": (7500, {}),
        })

        ok, reason = cro_approve_trade("pm1", "BTC-USD", "BUY", 500, mgr)
        assert ok is False
        assert "circuit breaker" in reason.lower() or "drawdown" in reason.lower()
        assert cro._close_only_mode is True

    def test_get_cro_status_returns_snapshot(self):
        """get_cro_status should return a non-empty dict after a trade check."""
        from backend.services.cro_service import cro_approve_trade, get_cro_status

        mgr = _build_mock_manager({"pm1": (10000, {})})
        cro_approve_trade("pm1", "BTC-USD", "BUY", 500, mgr)

        status = get_cro_status()
        assert "system_aum" in status
        assert "long_beta_pct" in status
        assert "crowded_assets" in status
        assert "limits" in status
