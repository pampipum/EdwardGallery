"""
Central Risk Officer (CRO) - System-Level Risk Enforcement

Intercepts every trade request from all Portfolio Managers before execution.
Enforces firm-wide limits that no individual PM can override.

Rules:
  1. Asset concentration cap     — no single asset > MAX_ASSET_PCT of total system AUM
  2. Long beta cap               — total long exposure < MAX_LONG_BETA_PCT of system AUM
  3. Short beta cap              — total short exposure < MAX_SHORT_BETA_PCT of system AUM
  4. Crowding guard              — if >= MIN_CROWDED_PMS already hold the asset, block new openers
  5. Drawdown circuit breaker    — if system AUM < peak * (1 - MAX_DRAWDOWN) → CLOSE_ONLY mode
"""

from __future__ import annotations
from datetime import datetime
from backend.utils.logger import logger

# ============================================================
# CRO CONFIGURATION (tune these per your risk tolerance)
# ============================================================
MAX_ASSET_PCT       = 0.40   # Max % of total system AUM in any single asset
MAX_LONG_BETA_PCT   = 0.70   # Max % of total system AUM as net long
MAX_SHORT_BETA_PCT  = 0.40   # Max % of total system AUM as net short
MIN_CROWDED_PMS     = 3      # Number of PMs already holding an asset to trigger crowding block
MAX_DRAWDOWN        = 0.15   # 15% drawdown from peak triggers CLOSE_ONLY mode

# ============================================================
# INTERNAL STATE
# ============================================================
_peak_system_aum: float = 0.0
_close_only_mode: bool = False
_last_status: dict = {}


def _gather_system_state(all_portfolios) -> dict:
    """
    Collects position and value data across all active PMs.

    Returns:
        {
            "system_aum": float,
            "per_pm": { pm_id: { "total_value": float, "positions": { ticker: pos } } },
            "asset_exposure": { ticker: { "long_usd": float, "short_usd": float, "pm_ids": [str] } },
            "total_long_usd": float,
            "total_short_usd": float,
        }
    """
    per_pm = {}
    asset_exposure: dict[str, dict] = {}
    total_long_usd = 0.0
    total_short_usd = 0.0
    system_aum = 0.0

    # portfolio_manager.portfolios is a dict of {pm_id: PortfolioService}
    try:
        portfolios = all_portfolios.portfolios
    except AttributeError:
        return {}

    for pm_id, svc in portfolios.items():
        try:
            status = svc.get_status()
            total_val = status.get("total_value", 0.0)
            positions = status.get("positions", {})
            current_prices = status.get("current_prices", {})

            system_aum += total_val
            per_pm[pm_id] = {"total_value": total_val, "positions": positions}

            for ticker, pos in positions.items():
                qty = pos.get("qty", 0)
                if qty == 0:
                    continue
                price = current_prices.get(ticker, pos.get("avg_price", 0))
                usd_val = abs(qty) * price

                if ticker not in asset_exposure:
                    asset_exposure[ticker] = {"long_usd": 0.0, "short_usd": 0.0, "pm_ids": []}

                if ticker not in asset_exposure[ticker]["pm_ids"]:
                    asset_exposure[ticker]["pm_ids"].append(pm_id)

                if qty > 0:
                    asset_exposure[ticker]["long_usd"] += usd_val
                    total_long_usd += usd_val
                else:
                    asset_exposure[ticker]["short_usd"] += usd_val
                    total_short_usd += usd_val

        except Exception as e:
            logger.warning(f"[CRO] Error reading state for {pm_id}: {e}")

    return {
        "system_aum": system_aum,
        "per_pm": per_pm,
        "asset_exposure": asset_exposure,
        "total_long_usd": total_long_usd,
        "total_short_usd": total_short_usd,
    }


def cro_approve_trade(
    pm_id: str,
    ticker: str,
    action: str,          # "BUY" or "SELL"
    estimated_usd: float,
    all_portfolios,
) -> tuple[bool, str]:
    """
    Main CRO gate. Call this before every new position opening.

    Returns:
        (True, "")          — trade approved
        (False, reason_str) — trade vetoed with human-readable reason
    """
    global _peak_system_aum, _close_only_mode, _last_status

    state = _gather_system_state(all_portfolios)
    if not state:
        # If we can't gather state, fail open (don't block trades due to CRO error)
        logger.warning("[CRO] Failed to gather system state — approving trade by default")
        return True, ""

    system_aum = state["system_aum"]
    asset_exposure = state["asset_exposure"]
    total_long_usd = state["total_long_usd"]
    total_short_usd = state["total_short_usd"]

    # Update peak AUM for drawdown tracking
    if system_aum > _peak_system_aum:
        _peak_system_aum = system_aum

    # ── Rule 5: Drawdown Circuit Breaker ──────────────────────────────────────
    if _peak_system_aum > 0:
        drawdown = (_peak_system_aum - system_aum) / _peak_system_aum
        if drawdown >= MAX_DRAWDOWN:
            _close_only_mode = True
            reason = (
                f"Drawdown circuit breaker ACTIVE: system AUM ${system_aum:,.0f} is "
                f"{drawdown:.1%} below peak ${_peak_system_aum:,.0f} "
                f"(limit: {MAX_DRAWDOWN:.0%}). CLOSE_ONLY mode."
            )
            logger.warning(f"[CRO] 🔴 {reason}")
            _last_status = _build_status(state, drawdown_pct=drawdown, close_only=True)
            return False, reason
        else:
            _close_only_mode = False

    if system_aum <= 0:
        _last_status = _build_status(state)
        return True, ""  # Nothing to gate against yet

    # ── Rule 4: Crowding Guard ─────────────────────────────────────────────────
    existing_exp = asset_exposure.get(ticker, {})
    holding_pms = existing_exp.get("pm_ids", [])
    if len(holding_pms) >= MIN_CROWDED_PMS:
        reason = (
            f"Crowding guard: {len(holding_pms)}/{MIN_CROWDED_PMS} PMs already hold {ticker} "
            f"({', '.join(holding_pms)}). New openers blocked."
        )
        logger.warning(f"[CRO] 🟡 {reason}")
        _last_status = _build_status(state)
        return False, reason

    # ── Rule 1: Asset Concentration Cap ───────────────────────────────────────
    existing_asset_usd = existing_exp.get("long_usd", 0.0) + existing_exp.get("short_usd", 0.0)
    projected_asset_usd = existing_asset_usd + estimated_usd
    projected_asset_pct = projected_asset_usd / system_aum

    if projected_asset_pct > MAX_ASSET_PCT:
        reason = (
            f"Asset concentration cap: {ticker} would be "
            f"{projected_asset_pct:.1%} of system AUM (limit: {MAX_ASSET_PCT:.0%}). "
            f"Current exposure ${existing_asset_usd:,.0f}, adding ${estimated_usd:,.0f}."
        )
        logger.warning(f"[CRO] 🟡 {reason}")
        _last_status = _build_status(state)
        return False, reason

    # ── Rule 2: Long Beta Cap ─────────────────────────────────────────────────
    if action == "BUY":
        projected_long_usd = total_long_usd + estimated_usd
        projected_long_pct = projected_long_usd / system_aum
        if projected_long_pct > MAX_LONG_BETA_PCT:
            reason = (
                f"Long beta cap: total long exposure would be "
                f"{projected_long_pct:.1%} of system AUM (limit: {MAX_LONG_BETA_PCT:.0%}). "
                f"Current long exposure ${total_long_usd:,.0f}."
            )
            logger.warning(f"[CRO] 🟡 {reason}")
            _last_status = _build_status(state)
            return False, reason

    # ── Rule 3: Short Beta Cap ─────────────────────────────────────────────────
    if action == "SELL":
        projected_short_usd = total_short_usd + estimated_usd
        projected_short_pct = projected_short_usd / system_aum
        if projected_short_pct > MAX_SHORT_BETA_PCT:
            reason = (
                f"Short beta cap: total short exposure would be "
                f"{projected_short_pct:.1%} of system AUM (limit: {MAX_SHORT_BETA_PCT:.0%}). "
                f"Current short exposure ${total_short_usd:,.0f}."
            )
            logger.warning(f"[CRO] 🟡 {reason}")
            _last_status = _build_status(state)
            return False, reason

    # All rules passed
    logger.info(
        f"[CRO] ✅ Approved {action} {ticker} for {pm_id} "
        f"(system AUM=${system_aum:,.0f}, asset_pct={projected_asset_pct:.1%})"
    )
    _last_status = _build_status(state)
    return True, ""


def _build_status(state: dict, drawdown_pct: float = None, close_only: bool = False) -> dict:
    """Builds a serialisable status snapshot for the frontend / monitoring."""
    system_aum = state.get("system_aum", 0)
    total_long = state.get("total_long_usd", 0)
    total_short = state.get("total_short_usd", 0)

    crowded_assets = [
        ticker
        for ticker, exp in state.get("asset_exposure", {}).items()
        if len(exp.get("pm_ids", [])) >= MIN_CROWDED_PMS
    ]

    # Calculate max asset concentration
    max_asset_usd = 0.0
    for exp in state.get("asset_exposure", {}).values():
        asset_usd = exp.get("long_usd", 0.0) + exp.get("short_usd", 0.0)
        if asset_usd > max_asset_usd:
            max_asset_usd = asset_usd
            
    current_max_asset_pct = (max_asset_usd / system_aum) if system_aum > 0 else 0.0

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system_aum": round(system_aum, 2),
        "peak_aum": round(_peak_system_aum, 2),
        "drawdown_pct": round(drawdown_pct, 4) if drawdown_pct is not None else None,
        "close_only_mode": close_only,
        "max_asset_pct": round(current_max_asset_pct, 4),
        "long_beta_usd": round(total_long, 2),
        "long_beta_pct": round(total_long / system_aum, 4) if system_aum > 0 else 0,
        "short_beta_usd": round(total_short, 2),
        "short_beta_pct": round(total_short / system_aum, 4) if system_aum > 0 else 0,
        "crowded_assets": crowded_assets,
        "limits": {
            "max_asset_pct": MAX_ASSET_PCT,
            "max_long_beta_pct": MAX_LONG_BETA_PCT,
            "max_short_beta_pct": MAX_SHORT_BETA_PCT,
            "min_crowded_pms": MIN_CROWDED_PMS,
            "max_drawdown": MAX_DRAWDOWN,
        },
    }


def get_cro_status() -> dict:
    """
    Returns the latest CRO system snapshot.
    Safe to call from API endpoints without triggering a full state re-computation.
    """
    if not _last_status:
        return _build_status({})
    return _last_status
