from fastapi import FastAPI, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from backend.services.data_service import get_top_tickers, get_current_price
from backend.services.analysis_service import analyze_ticker, get_dashboard_summary
from backend.services.portfolio_service import portfolio_manager
from backend.services.trading_loop import resume_existing_loops, start_pm_loop, stop_pm_loop, run_market_analysis
from backend.services.weekly_analyst import weekly_analyst
import asyncio
from backend.utils.logger import logger
from backend.utils.auth import get_api_key
from backend.utils.rate_limiter import get_rate_limiter
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from backend.runtime import (
    auto_resume_enabled,
    internal_scheduler_enabled,
    startup_analysis_enabled,
    state_file,
)


app = FastAPI(title="Market Analyst API", description="Senior Technical Analyst Backend")

# Compress all responses >= 2KB (JSON, HTML, etc.)
app.add_middleware(GZipMiddleware, minimum_size=2000)

# CORS - Restricted to trusted origins for security
# Production: https://app1.attikonlab.uk
# Local/Development: http://localhost:8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "https://app1.attikonlab.uk"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate Limiting Middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting on API requests."""
    
    async def dispatch(self, request: Request, call_next):
        rate_limiter = get_rate_limiter()
        
        if rate_limiter is not None:
            # Try to acquire a token from the rate limiter
            if not rate_limiter.try_acquire():
                logger.warning(f"Rate limit exceeded for {request.client.host}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too many requests",
                        "message": "Rate limit exceeded. Please try again later."
                    }
                )
        
        response = await call_next(request)
        return response


app.add_middleware(RateLimitMiddleware)

# Scheduler
scheduler = BackgroundScheduler()



# Startup Event to resume existing portfolio loops
@app.on_event("startup")
async def startup_event():
    import os

    if auto_resume_enabled():
        await resume_existing_loops()
    else:
        logger.info("Startup auto-resume disabled. OpenClaw should own PM scheduling.")

    if internal_scheduler_enabled():
        scheduler.start()
        scheduler.add_job(
            lambda: [weekly_analyst.generate_weekly_report(pm_id) for pm_id in ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']],
            trigger=CronTrigger(day_of_week='sun', hour=0, minute=0, timezone=pytz.UTC),
            id='weekly_analyst_job'
        )
        logger.info("Internal weekly scheduler enabled for Sunday 00:00 UTC")
    else:
        logger.info("Internal APScheduler disabled. Use OpenClaw cron jobs instead.")

    if startup_analysis_enabled() or os.getenv("RUN_ON_STARTUP", "").lower() == "true":
        logger.info("🚀 RUN_ON_STARTUP=true detected! Triggering immediate analysis for all active PMs...")
        for pm_id in ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']:
            portfolio = portfolio_manager.get_portfolio(pm_id)
            if portfolio.data.get("is_running"):
                logger.info(f"   ➡️ Triggering analysis for {pm_id}...")
                asyncio.create_task(asyncio.to_thread(run_market_analysis, pm_id))


# API Routes
@app.get("/api/dashboard")
def get_dashboard():
    # Return cached analysis from portfolio service
    # For now, return PM1's analysis as the default
    pm1_portfolio = portfolio_manager.get_portfolio('pm1')
    analysis_data = pm1_portfolio.get_latest_analysis()
    
    # If no analysis data exists yet (fresh restart), fall back to config asset list
    if not analysis_data:
        from backend.services.data.config_service import get_top_tickers
        config_assets = get_top_tickers().get("stocks", []) + get_top_tickers().get("crypto", [])
        analysis_data = [
            {
                "ticker": ticker,
                "summary": {"current_trend": "Neutral"},
                "technical_context": {"price_action": f"Price is {get_current_price(ticker)}"}
            }
            for ticker in config_assets
        ]

    # Inject live prices for the ticker tape
    if analysis_data:
        for item in analysis_data:
            if "ticker" in item:
                try:
                    price = get_current_price(item["ticker"])
                    if price > 0:
                        item["price"] = price
                except Exception:
                    pass

    # --- CHART SANITIZATION ---
    # Strip None/invalid values before sending to frontend so charts
    # never receive garbage data from failed fetches.
    def sanitize_item(item: dict) -> dict:
        """Recursively replace None and non-finite floats with safe defaults."""
        import math
        sanitized = {}
        for k, v in item.items():
            if v is None:
                sanitized[k] = "N/A" if isinstance(v, str) else None
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                sanitized[k] = None
            elif isinstance(v, dict):
                sanitized[k] = sanitize_item(v)
            else:
                sanitized[k] = v
        return sanitized

    if analysis_data:
        clean = []
        for item in analysis_data:
            # Skip items with no valid price — nothing useful to chart
            price = item.get("price")
            if price is None or (isinstance(price, float) and price <= 0):
                logger.warning(f"[Dashboard] Skipping {item.get('ticker', '?')} — invalid price: {price}")
                continue
            clean.append(sanitize_item(item))
        return clean

    return analysis_data

@app.get("/api/llm/logs")
def get_llm_logs():
    """Get recent LLM API request logs for cost supervision"""
    from backend.utils.llm_monitor import llm_monitor
    return llm_monitor.get_logs()

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    return analyze_ticker(ticker)

# Portfolio Routes - PM Specific
@app.post("/api/portfolio/start/{pm_id}")
async def start_portfolio(pm_id: str, capital: float, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    portfolio = portfolio_manager.get_portfolio(pm_id)
    result = portfolio.start_portfolio(capital)
    
    # Start the trading loop for this PM (loop will handle initial analysis automatically)
    await start_pm_loop(pm_id)
    
    return result

@app.post("/api/portfolio/start-all")
async def start_all_portfolios(capital: float, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """Start all portfolios with the same capital."""
    results = {}
    for pm_id in ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']:
        portfolio = portfolio_manager.get_portfolio(pm_id)
        portfolio.start_portfolio(capital)
        await start_pm_loop(pm_id)
        results[pm_id] = {"status": "started", "capital": capital}
        logger.info(f"[{pm_id}] Started with ${capital}")
    return {"message": f"All portfolios started with ${capital}", "results": results}

from backend.services.pm_strategies import get_strategy

@app.get("/api/portfolio/status/{pm_id}")
def get_portfolio_status(pm_id: str):
    portfolio = portfolio_manager.get_portfolio(pm_id)
    status = portfolio.get_status()

    # Inject live prices into latest_analysis.
    # get_status() already fetched prices for open positions — reuse that cache
    # rather than making N separate get_current_price() calls.
    cached_prices = status.get("current_prices", {})
    latest_analysis = status.get("latest_analysis", [])
    if latest_analysis:
        tickers_missing = [
            item["ticker"] for item in latest_analysis
            if "ticker" in item and item["ticker"] not in cached_prices
        ]
        if tickers_missing:
            try:
                from backend.services.market_service import get_current_prices
                fresh = get_current_prices(list(set(tickers_missing)))
                cached_prices = {**cached_prices, **fresh}
            except Exception:
                pass

        for item in latest_analysis:
            ticker = item.get("ticker")
            if ticker and ticker in cached_prices and cached_prices[ticker] > 0:
                item["price"] = cached_prices[ticker]

    # Inject active strategy details
    strategy = get_strategy(pm_id)
    status["strategy_info"] = {
        "name": strategy.name,
        "description": strategy.description,
        "confidence_threshold": strategy.get_confidence_threshold(),
        "check_interval": strategy.get_check_interval(),
        "max_position_size": strategy.get_max_position_size(),
        "min_cash_buffer": strategy.get_min_cash_buffer(),
        "prompt_modifier": strategy.get_full_prompt()
    }
    return status


@app.post("/api/portfolio/tick/{pm_id}")
async def trigger_market_check(pm_id: str, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """Manually trigger a market analysis for a specific PM"""
    background_tasks.add_task(run_market_analysis, pm_id)
    return {"message": f"Market analysis triggered for {pm_id}"}

@app.post("/api/portfolio/restart/{pm_id}")
async def restart_portfolio(pm_id: str, api_key: str = Depends(get_api_key)):
    """Stop the current portfolio run"""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    portfolio.data["is_running"] = False
    portfolio.save_portfolio()
    
    # Stop the trading loop
    await stop_pm_loop(pm_id)
    
    return {"message": f"Portfolio {pm_id} stopped. You can now start a new run."}


@app.get("/api/portfolio/all")
def get_all_portfolios():
    """Get lean summary of all active PMs (for sparklines and comparison chart).
    Heavy per-PM data (manager_log, latest_analysis, trade_log, ledger) is
    available on /api/portfolio/status/{pm_id}.
    """
    return portfolio_manager.get_all_status_lean()

@app.post("/api/portfolio/reload/{pm_id}")
async def reload_portfolio_from_disk(pm_id: str, api_key: str = Depends(get_api_key)):
    """Force-reload a portfolio from the JSON file on disk, flushing the in-memory cache.
    Useful when a portfolio JSON was edited manually or dropped in while the server was running."""
    portfolio = portfolio_manager.reload_portfolio(pm_id)
    status = portfolio.get_status()
    return {
        "message": f"Portfolio {pm_id} reloaded from disk.",
        "is_running": status.get("is_running"),
        "balance": status.get("balance"),
        "positions": list(status.get("positions", {}).keys())
    }

@app.get("/api/market/prices")
def get_market_prices():
    """Get current market prices for all tickers in portfolio"""
    from backend.services.market_service import get_current_prices
    
    # Get all unique tickers across all PMs
    logger.info("Checking for existing portfolios to resume...")
    all_tickers = set()
    for pm_id in ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']:
        portfolio = portfolio_manager.get_portfolio(pm_id)
        status = portfolio.get_status()
        all_tickers.update(status.get("positions", {}).keys())
    
    if not all_tickers:
        return {}
    
    prices = get_current_prices(list(all_tickers))
    return prices

@app.get("/api/market/status")
def get_market_status_api():
    """Get real-time US stock market status"""
    from backend.utils.scheduler import get_market_status
    return get_market_status()


@app.get("/api/live/overview")
def get_live_overview(lines: int = 60):
    """Lightweight real-time payload for the frontend live monitor.

    Returns per-PM heartbeat info + recent app.log tail lines.
    """
    pm_ids = ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']
    pm_status = {}

    for pm_id in pm_ids:
        status = portfolio_manager.get_portfolio(pm_id).get_status()
        trade_log = status.get('trade_log', []) or []
        manager_log = status.get('manager_log', []) or []
        history = status.get('history', []) or []

        pm_status[pm_id] = {
            "is_running": bool(status.get("is_running")),
            "total_value": status.get("total_value", status.get("balance", 0)),
            "positions_count": len(status.get("positions", {}) or {}),
            "analysis_items": len(status.get("latest_analysis", []) or []),
            "last_tick": history[-1].get("timestamp") if history else None,
            "last_trade": trade_log[-1] if trade_log else None,
            "last_manager": manager_log[-1] if manager_log else None,
        }

    # Tail app log
    safe_lines = max(10, min(lines, 300))
    log_tail = []
    log_path = state_file("logs", "app.log")
    try:
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.readlines()
                log_tail = [ln.rstrip("\n") for ln in content[-safe_lines:]]
    except Exception as e:
        logger.warning(f"Failed to read app.log tail: {e}")

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pm": pm_status,
        "log_tail": log_tail,
    }

@app.get("/api/portfolio/ledger/{pm_id}")
def get_portfolio_ledger(pm_id: str):
    """Get portfolio ledger (all transactions) for a specific PM"""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    status = portfolio.get_status()
    return {"ledger": status.get("ledger", [])}

@app.get("/api/trading-mode/{pm_id}")
def get_trading_mode(pm_id: str):
    """Get the trading mode (PAPER/LIVE) for a specific PM based on config."""
    from backend.services.execution.factory import get_executor_mode
    mode = get_executor_mode(pm_id)
    return {"pm_id": pm_id, "mode": mode}


# Weekly Analyst Routes
@app.get("/api/reports/{pm_id}")
def get_reports_list(pm_id: str):
    """Get list of all weekly reports for a PM"""
    return weekly_analyst.get_all_reports(pm_id)

@app.get("/api/reports/{pm_id}/{report_id}")
def get_report_detail(pm_id: str, report_id: str):
    """Get detailed content of a specific report"""
    report = weekly_analyst.get_report(pm_id, report_id)
    if not report:
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return report

@app.post("/api/reports/trigger/{pm_id}")
async def trigger_weekly_report(pm_id: str, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """Manually trigger a weekly analysis report (for testing)"""
    background_tasks.add_task(weekly_analyst.generate_weekly_report, pm_id)
    return {"message": f"Weekly analysis triggered for {pm_id}. This may take a minute."}

@app.post("/api/learnings/ingest/{pm_id}")
async def ingest_learning(pm_id: str, learning_data: dict, api_key: str = Depends(get_api_key)):
    """Ingest a proposed learning into the active strategy overrides."""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    entry = portfolio.ingest_learning(learning_data)
    return {"message": "Learning activated", "entry": entry}

@app.post("/api/learnings/revert/{pm_id}/{learning_id}")
async def revert_learning(pm_id: str, learning_id: str, api_key: str = Depends(get_api_key)):
    """Revert/Deactivate an active learning."""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    success = portfolio.revert_learning(learning_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "Learning not found"})
    return {"message": "Learning reverted"}

@app.post("/api/learnings/graduate/{pm_id}/{learning_id}")
async def graduate_learning(pm_id: str, learning_id: str, api_key: str = Depends(get_api_key)):
    """Graduate a learning (marks it as permanently baked into base prompt)."""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    success = portfolio.graduate_learning(learning_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "Learning not found"})
    return {"message": "Learning graduated"}


# CRO (Central Risk Officer) Routes
@app.get("/api/risk/cro")
def get_cro_status_endpoint():
    """
    Returns the current Central Risk Officer (CRO) system snapshot.
    Includes system AUM, beta exposure, crowded assets, and circuit breaker status.
    Safe to poll frequently — returns cached state, no live computation.
    """
    from backend.services.cro_service import get_cro_status
    status = get_cro_status()
    if not status:
        return {
            "message": "CRO has not processed any trades yet this session.",
            "status": "idle"
        }
    return status

@app.get("/api/risk/cro/config")
def get_cro_config():
    """
    Returns the active CRO rule thresholds.
    Useful for monitoring dashboards to display current limits.
    """
    from backend.services.cro_service import (
        MAX_ASSET_PCT, MAX_LONG_BETA_PCT, MAX_SHORT_BETA_PCT,
        MIN_CROWDED_PMS, MAX_DRAWDOWN
    )
    return {
        "max_asset_concentration_pct": MAX_ASSET_PCT,
        "max_long_beta_pct": MAX_LONG_BETA_PCT,
        "max_short_beta_pct": MAX_SHORT_BETA_PCT,
        "crowding_threshold_pms": MIN_CROWDED_PMS,
        "max_drawdown_before_circuit_breaker": MAX_DRAWDOWN,
        "description": {
            "max_asset_concentration_pct": "Max % of system AUM in any single asset before new opens are blocked",
            "max_long_beta_pct": "Max % of system AUM as total net long exposure",
            "max_short_beta_pct": "Max % of system AUM as total net short exposure",
            "crowding_threshold_pms": "Number of PMs holding same asset that triggers crowding block",
            "max_drawdown_before_circuit_breaker": "Drawdown from peak that triggers CLOSE_ONLY mode"
        }
    }

# Static Files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
def favicon():
    return FileResponse("frontend/static/favicon.png", media_type="image/png")

@app.get("/")
def read_root():
    return FileResponse("frontend/static/index.html")
